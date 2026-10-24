#!/usr/bin/env python3
"""Regression tests for path-first dependency resolution."""
import importlib.util
from pathlib import Path
import struct
import sys
import unittest


MODULE = Path(__file__).parents[1] / "scripts" / "elfcheck.py"
SPEC = importlib.util.spec_from_file_location("elfcheck", MODULE)
elfcheck = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = elfcheck
SPEC.loader.exec_module(elfcheck)


def elf_fixture(*, needed=(), soname=None, exports=(), undefined=(), truncate_dynamic=False,
                dynsym=True):
    """Build a tiny valid ELF64LE with non-type sh_name values, no compiler."""
    names = [*needed, *( [soname] if soname else []), *exports, *undefined]
    strings = bytearray(b"\0")
    offsets = {}
    for name in names:
        offsets.setdefault(name, len(strings))
        if offsets[name] == len(strings):
            strings.extend(name.encode() + b"\0")
    dynamic = bytearray()
    for name in needed:
        dynamic.extend(struct.pack("<qQ", 1, offsets[name]))
    if soname:
        dynamic.extend(struct.pack("<qQ", 14, offsets[soname]))
    dynamic.extend(struct.pack("<qQ", 0, 0))
    symbols = bytearray(24)
    for name in undefined:
        symbols.extend(struct.pack("<IBBHQQ", offsets[name], 0x10, 0, 0, 0, 0))
    for name in exports:
        symbols.extend(struct.pack("<IBBHQQ", offsets[name], 0x10, 0, 1, 0, 0))
    section_count = 4 if dynsym else 3
    section_offset = 64
    cursor = 512
    string_offset = cursor
    cursor += len(strings)
    dynamic_offset = (cursor + 7) & ~7
    cursor = dynamic_offset + len(dynamic)
    symbol_offset = (cursor + 7) & ~7
    cursor = symbol_offset + len(symbols)
    image = bytearray(cursor)
    image[:16] = b"\x7fELF\x02\x01\x01\0" + b"\0" * 8
    struct.pack_into("<HHIQQQIHHHHHH", image, 16, 3, 183, 1, 0, 0,
                     section_offset, 0, 64, 0, 0, 64, section_count, 0)
    image[string_offset:string_offset + len(strings)] = strings
    image[dynamic_offset:dynamic_offset + len(dynamic)] = dynamic
    image[symbol_offset:symbol_offset + len(symbols)] = symbols
    def sh(number, section_type, offset, size, link=0, alignment=1, entry_size=0):
        struct.pack_into("<IIQQQQIIQQ", image, section_offset + number * 64,
                         number * 17 + 1, section_type, 0, 0, offset, size,
                         link, 0, alignment, entry_size)
    sh(1, 3, string_offset, len(strings))
    sh(2, 6, dynamic_offset, len(dynamic) + (100000 if truncate_dynamic else 0), 1, 8, 16)
    if dynsym:
        sh(3, 11, symbol_offset, len(symbols), 1, 8, 24)
    return bytes(image)


class ElfcheckTests(unittest.TestCase):
    def test_rejects_escape_from_symlink(self):
        entries = {"link": elfcheck.CpioEntry(0o120777, b"../../outside")}
        with self.assertRaises(ValueError):
            elfcheck.resolve_entry(entries, "link")

    def test_uses_exact_needed_filename_not_soname(self):
        entries = {
            "system/bin/init": elfcheck.CpioEntry(0o100755, elf_fixture(needed=("libc++.so",), undefined=("wanted",))),
            "system/lib64/libc++-v35.so": elfcheck.CpioEntry(0o100644, elf_fixture(soname="libc++.so", exports=("wanted",))),
        }
        # A same-SONAME alternate file must never satisfy DT_NEEDED libc++.so.
        result = elfcheck.check_entries(entries, ("system/bin/init",))["system/bin/init"]
        self.assertEqual(result["missing_libraries"], [{"consumer": "system/bin/init", "needed": "libc++.so"}])

    def test_exact_default_filename_passes_normal_dependency(self):
        entries = {
            "system/bin/init": elfcheck.CpioEntry(0o100755, elf_fixture(needed=("libc++.so",), undefined=("wanted",))),
            "system/lib64/libc++.so": elfcheck.CpioEntry(0o100644, elf_fixture(soname="libc++.so", exports=("wanted",))),
        }
        result = elfcheck.check_entries(entries, ("system/bin/init",))["system/bin/init"]
        self.assertFalse(result["missing_libraries"])
        self.assertFalse(result["missing_strong_symbols"])

    def test_unloaded_v35_same_soname_cannot_supply_default_libcpp_symbol(self):
        entries = {
            "system/bin/init": elfcheck.CpioEntry(0o100755, elf_fixture(needed=("libc++.so",), undefined=("wanted",))),
            "system/lib64/libc++.so": elfcheck.CpioEntry(0o100644, elf_fixture(soname="libc++.so")),
            "system/lib64/libc++-v35.so": elfcheck.CpioEntry(0o100644, elf_fixture(soname="libc++.so", exports=("wanted",))),
        }
        result = elfcheck.check_entries(entries, ("system/bin/init",))["system/bin/init"]
        self.assertEqual(result["missing_strong_symbols"], ["wanted"])
        self.assertEqual(result["soname_collisions"], [])

    def test_transitive_provider_and_root_export_are_accepted(self):
        entries = {
            "system/bin/init": elfcheck.CpioEntry(0o100755, elf_fixture(needed=("liba.so",), exports=("from_root",))),
            "system/lib64/liba.so": elfcheck.CpioEntry(0o100644, elf_fixture(needed=("libb.so",), undefined=("from_transitive", "from_root"))),
            "system/lib64/libb.so": elfcheck.CpioEntry(0o100644, elf_fixture(exports=("from_transitive",))),
        }
        result = elfcheck.check_entries(entries, ("system/bin/init",))["system/bin/init"]
        self.assertFalse(result["missing_libraries"])
        self.assertFalse(result["missing_strong_symbols"])

    def test_loaded_duplicate_soname_is_reported_but_not_a_failure(self):
        entries = {
            "system/bin/init": elfcheck.CpioEntry(0o100755, elf_fixture(needed=("libc++.so", "libdmabufheap.so"))),
            "system/lib64/libc++.so": elfcheck.CpioEntry(0o100644, elf_fixture(soname="libc++.so")),
            "system/lib64/libdmabufheap.so": elfcheck.CpioEntry(0o100644, elf_fixture(needed=("libc++-v35.so",))),
            "system/lib64/libc++-v35.so": elfcheck.CpioEntry(0o100644, elf_fixture(soname="libc++.so")),
        }
        result = elfcheck.check_entries(entries, ("system/bin/init",))["system/bin/init"]
        self.assertFalse(result["missing_strong_symbols"])
        self.assertEqual(result["soname_collisions"], [{
            "soname": "libc++.so",
            "paths": sorted(["system/lib64/libc++.so", "system/lib64/libc++-v35.so"]),
        }])

    def test_truncated_dynamic_section_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "truncated ELF dynamic section"):
            elfcheck.inspect_elf(elf_fixture(truncate_dynamic=True))

    def test_dynamic_elf_without_dynsym_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "dynamic ELF has no readable dynamic symbol table"):
            elfcheck.inspect_elf(elf_fixture(dynsym=False))

    def test_elf_without_section_table_is_rejected(self):
        image = bytearray(elf_fixture())
        struct.pack_into("<Q", image, 40, 0)
        struct.pack_into("<H", image, 60, 0)
        with self.assertRaisesRegex(ValueError, "no readable section table"):
            elfcheck.inspect_elf(bytes(image))

    def test_known_bad_image_reports_init_vtable(self):
        image = Path(__file__).parents[2] / (
            "TWRP-houji-artifacts/run-2-verified/"
            "twrp-lvgl-houji-2-3c65008b.img"
        )
        if not image.is_file():
            self.skipTest("external negative-regression image is not present")
        report = elfcheck.check_image(image.read_bytes())
        missing = report["targets"]["init"]["missing_strong_symbols"]
        self.assertIn(
            "_ZTVNSt3__118basic_stringstreamIcNS_11char_traitsIcEENS_9allocatorIcEEEE",
            missing,
        )


if __name__ == "__main__":
    unittest.main()
