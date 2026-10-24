#!/usr/bin/env python3
"""Conservative, offline ELF closure checks for a recovery ramdisk.

This intentionally models only the filename-based part of Android's loader
search.  It does not claim to emulate linker namespaces, SELinux, symbol
versions, or every runtime dlopen() path.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import posixpath
import stat
import struct
import subprocess
from typing import Iterable


@dataclass(frozen=True)
class CpioEntry:
    mode: int
    data: bytes


@dataclass(frozen=True)
class ElfInfo:
    needed: tuple[str, ...]
    soname: str | None
    exports: frozenset[str]
    undefined: frozenset[str]


def _normal_path(path: str) -> str:
    path = path.lstrip("/")
    normal = posixpath.normpath(path)
    if normal in ("", ".") or normal == ".." or normal.startswith("../"):
        raise ValueError(f"unsafe ramdisk path: {path!r}")
    return normal


def cpio_entries(data: bytes) -> dict[str, CpioEntry]:
    entries: dict[str, CpioEntry] = {}
    offset = 0
    while offset + 110 <= len(data):
        header = data[offset : offset + 110]
        if header[:6] not in (b"070701", b"070702"):
            raise ValueError(f"invalid newc CPIO header at {offset}")
        fields = [int(header[6 + i * 8 : 14 + i * 8], 16) for i in range(13)]
        mode, size, name_size = fields[1], fields[6], fields[11]
        name_start = offset + 110
        name_end = name_start + name_size
        if name_size < 1 or name_end > len(data) or data[name_end - 1] != 0:
            raise ValueError("invalid CPIO entry name")
        name = _normal_path(data[name_start : name_end - 1].decode("utf-8", "strict"))
        content_start = (name_end + 3) & ~3
        content_end = content_start + size
        if content_end > len(data):
            raise ValueError(f"truncated CPIO entry: {name}")
        if name == "TRAILER!!!":
            return entries
        entries[name] = CpioEntry(mode=mode, data=data[content_start:content_end])
        offset = (content_end + 3) & ~3
    raise ValueError("CPIO archive has no end marker")


def resolve_entry(entries: dict[str, CpioEntry], path: str) -> tuple[str, CpioEntry]:
    """Resolve a CPIO symlink without ever leaving the ramdisk namespace."""
    current = _normal_path(path)
    seen: set[str] = set()
    while True:
        if current in seen:
            raise ValueError(f"ramdisk symlink loop at {current}")
        seen.add(current)
        entry = entries.get(current)
        if entry is None:
            raise FileNotFoundError(current)
        if not stat.S_ISLNK(entry.mode):
            return current, entry
        target = entry.data.decode("utf-8", "strict")
        if target.startswith("/"):
            current = _normal_path(target)
        else:
            current = _normal_path(posixpath.join(posixpath.dirname(current), target))


def inspect_elf(data: bytes) -> ElfInfo | None:
    """Read ELF64 little-endian DT_NEEDED and strong dynamic symbols only."""
    if data[:6] != b"\x7fELF\x02\x01":
        return None
    if len(data) < 64:
        raise ValueError("truncated ELF header")
    section_offset = struct.unpack_from("<Q", data, 40)[0]
    section_stride, section_count = struct.unpack_from("<HH", data, 58)
    # This checker deliberately relies on section metadata.  Do not make an
    # ELF with no section table appear to have an empty dependency closure.
    if section_count == 0 or section_offset == 0:
        raise ValueError("ELF has no readable section table")
    if section_stride < 64 or section_offset + section_stride * section_count > len(data):
        raise ValueError("invalid ELF section table")
    sections = [
        struct.unpack_from("<IIQQQQIIQQ", data, section_offset + i * section_stride)
        for i in range(section_count)
    ]
    needed: list[str] = []
    soname: str | None = None
    exports: set[str] = set()
    undefined: set[str] = set()
    dynamic_seen = False
    dynsym_seen = False
    for section in sections:
        # Elf64_Shdr begins with sh_name, then sh_type.  Using sh_name as the
        # type silently hides every dynamic section and can false-pass a bad
        # ramdisk closure.
        _, section_type, _, _, data_offset, data_size, link, _, _, entry_size = section
        if section_type not in (6, 11):
            continue
        if data_offset + data_size > len(data):
            raise ValueError("truncated ELF dynamic section")
        if link >= len(sections):
            raise ValueError("invalid ELF string-table index")
        strings_section = sections[link]
        if strings_section[1] != 3:
            raise ValueError("dynamic section does not link to a string table")
        string_offset, string_size = strings_section[4], strings_section[5]
        if string_offset + string_size > len(data):
            raise ValueError("invalid ELF string table")
        strings = data[string_offset : string_offset + string_size]

        def string(index: int) -> str:
            if index >= len(strings):
                raise ValueError("invalid ELF string offset")
            end = strings.find(b"\0", index)
            if end < 0:
                raise ValueError("unterminated ELF string")
            return strings[index:end].decode("utf-8", "replace")

        if section_type == 6:
            dynamic_seen = True
            if entry_size < 16 or data_size % entry_size:
                raise ValueError("invalid ELF dynamic entry size")
            for pos in range(data_offset, data_offset + data_size, entry_size or 16):
                tag, value = struct.unpack_from("<qQ", data, pos)
                if tag == 1:
                    needed.append(string(value))
                elif tag == 14:
                    soname = string(value)
        else:
            dynsym_seen = True
            if entry_size < 24 or data_size % entry_size:
                raise ValueError("invalid ELF dynamic symbol entry size")
            for pos in range(data_offset, data_offset + data_size, entry_size or 24):
                name, info, other, index, _, _ = struct.unpack_from("<IBBHQQ", data, pos)
                binding, visibility = info >> 4, other & 3
                symbol = string(name)
                if not symbol:
                    continue
                if index and binding in (1, 2) and visibility in (0, 3):
                    exports.add(symbol)
                elif not index and binding == 1:
                    undefined.add(symbol)
    if dynamic_seen and not dynsym_seen:
        raise ValueError("dynamic ELF has no readable dynamic symbol table")
    return ElfInfo(tuple(needed), soname, frozenset(exports), frozenset(undefined))


def unpack_recovery(image: bytes) -> dict[str, CpioEntry]:
    if image[:8] != b"ANDROID!":
        raise ValueError("missing Android boot image magic")
    ramdisk_size = struct.unpack_from("<I", image, 12)[0]
    payload = image[4096 : 4096 + ramdisk_size]
    if len(payload) != ramdisk_size:
        raise ValueError("truncated recovery ramdisk")
    if not payload.startswith((b"070701", b"070702")):
        payload = subprocess.run(
            ["lz4", "-d", "-c"], input=payload, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            check=True,
        ).stdout
    return cpio_entries(payload)


def _search_paths(path: str) -> tuple[str, ...]:
    # The recovery ld.config default is /system/${LIB}.  Vendor executables
    # receive a deliberately separate vendor-first profile; this does not
    # assert that every vendor namespace or linker configuration is modeled.
    if path.startswith("vendor/"):
        return ("vendor/lib64", "system/lib64")
    return ("system/lib64",)


def _resolve_needed(
    entries: dict[str, CpioEntry], search_paths: Iterable[str], needed: str,
) -> str | None:
    # DT_NEEDED containing a slash is a pathname, otherwise use exact filename
    # matches in the selected search paths.  A library's SONAME is never used
    # to substitute a differently named file.
    candidates: Iterable[str]
    if "/" in needed:
        candidates = (_normal_path(needed),)
    else:
        candidates = (_normal_path(f"{directory}/{needed}") for directory in search_paths)
    for candidate in candidates:
        try:
            resolved, entry = resolve_entry(entries, candidate)
        except FileNotFoundError:
            continue
        if inspect_elf(entry.data) is not None:
            return resolved
    return None


def check_entries(entries: dict[str, CpioEntry], targets: Iterable[str]) -> dict[str, object]:
    """Check real DT_NEEDED filename resolution and strong symbols transitively."""
    elf_cache: dict[str, ElfInfo] = {}

    def elf(path: str) -> ElfInfo:
        path, entry = resolve_entry(entries, path)
        if path not in elf_cache:
            parsed = inspect_elf(entry.data)
            if parsed is None:
                raise ValueError(f"not an ELF64LE file: {path}")
            elf_cache[path] = parsed
        return elf_cache[path]

    results: dict[str, object] = {}
    for requested in targets:
        try:
            root, _ = resolve_entry(entries, requested)
            elf(root)
        except (FileNotFoundError, ValueError) as error:
            results[requested] = {
                "resolved_path": None,
                "dependency_paths": [],
                "missing_libraries": [],
                "missing_strong_symbols": [],
                "error": str(error),
            }
            continue
        queue = [root]
        # LD_LIBRARY_PATH/search namespace belongs to the process, not to each
        # dependency file.  Keep the root executable's profile for its entire
        # DT_NEEDED closure.
        search_paths = _search_paths(root)
        closure: list[str] = []
        libraries: set[str] = set()
        missing_libraries: list[dict[str, str]] = []
        while queue:
            current = queue.pop()
            if current in libraries:
                continue
            libraries.add(current)
            closure.append(current)
            for needed in elf(current).needed:
                dependency = _resolve_needed(entries, search_paths, needed)
                if dependency is None:
                    missing_libraries.append({"consumer": current, "needed": needed})
                else:
                    if dependency not in libraries:
                        queue.append(dependency)
        # Symbol resolution is assessed over the exact filename-resolved
        # process closure, including executable exports.  This admits normal
        # transitive providers and symbols supplied by the main executable.
        # SONAME collisions remain a reported runtime risk, never a resolver
        # fallback or an automatic failure.
        exports = set().union(*(elf(path).exports for path in libraries))
        missing_symbols = sorted(set().union(*(elf(path).undefined for path in libraries)) - exports)
        sonames: dict[str, list[str]] = {}
        for path in libraries:
            name = elf(path).soname
            if name:
                sonames.setdefault(name, []).append(path)
        soname_collisions = [
            {"soname": name, "paths": sorted(paths)}
            for name, paths in sorted(sonames.items()) if len(paths) > 1
        ]
        results[requested] = {
            "resolved_path": root,
            "dependency_paths": sorted(libraries),
            "missing_libraries": missing_libraries,
            "missing_strong_symbols": missing_symbols,
            "soname_collisions": soname_collisions,
            "error": None,
        }
    return results


def check_image(image: bytes) -> dict[str, object]:
    entries = unpack_recovery(image)
    targets = (
        "init",
        "system/bin/recovery",
        "system/lib64/libgui2.so",
        "system/lib64/liblvgl_twrp.so",
        # This vendor executable uses the vendor-first profile in _search_paths.
        "vendor/bin/se_omapi",
        "vendor/bin/qseecomd",
    )
    checks = check_entries(entries, targets)
    failures = {
        target: value for target, value in checks.items()
        if value["error"] or value["missing_libraries"] or value["missing_strong_symbols"]
    }
    return {
        "scope": "Conservative filename-based DT_NEEDED and process-closure strong-symbol check only. SONAME collisions are reported but never used for resolution; linker namespaces, symbol versions, dlopen paths, SELinux, and boot remain unmodeled.",
        "targets": checks,
        "failures": failures,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image")
    parser.add_argument("--report")
    args = parser.parse_args()
    report = check_image(open(args.image, "rb").read())
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    print(rendered, end="")
    if args.report:
        with open(args.report, "w", encoding="utf-8") as output:
            output.write(rendered)
    if report["failures"]:
        raise SystemExit("ELF closure check failed")


if __name__ == "__main__":
    main()
