#!/usr/bin/env python3
"""Inspect a built houji recovery image without extracting or executing its files."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import subprocess

import elfcheck
import vintfcheck
import wificheck


def cpio_entries(data):
    entries = {}
    offset = 0
    while offset + 110 <= len(data):
        header = data[offset:offset + 110]
        if header[:6] not in (b'070701', b'070702'):
            raise ValueError(f'Invalid newc CPIO header at {offset}')
        fields = [int(header[6 + i * 8:14 + i * 8], 16) for i in range(13)]
        mode, size, name_size = fields[1], fields[6], fields[11]
        name_start = offset + 110
        name_end = name_start + name_size
        if name_size < 1 or name_end > len(data) or data[name_end - 1] != 0:
            raise ValueError('Invalid CPIO entry name')
        name = data[name_start:name_end - 1].decode('utf-8', errors='replace')
        while name.startswith('./'):
            name = name[2:]
        content_start = (name_end + 3) & ~3
        content_end = content_start + size
        if content_end > len(data):
            raise ValueError(f'Truncated CPIO entry: {name}')
        if name == 'TRAILER!!!':
            return entries
        entries[name] = {'size': size, 'mode': oct(mode)}
        offset = (content_end + 3) & ~3
    raise ValueError('CPIO archive has no end marker')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('image', type=Path)
    parser.add_argument('--report', type=Path)
    parser.add_argument('--wifi', action='store_true', help='Require the experimental Wi-Fi runtime')
    args = parser.parse_args()
    image = args.image.read_bytes()
    if not 4096 <= len(image) <= 104857600 or image[:8] != b'ANDROID!':
        raise ValueError('Invalid houji recovery image size or Android boot magic')
    kernel_size, ramdisk_size, _, header_size = struct.unpack_from('<4I', image, 8)
    header_version = struct.unpack_from('<I', image, 40)[0]
    if header_version != 4 or header_size != 1584 or kernel_size != 0:
        raise ValueError('Expected houji boot-header-v4 recovery with no embedded kernel')
    if ramdisk_size == 0 or 4096 + ramdisk_size > len(image):
        raise ValueError('Invalid recovery ramdisk size')
    payload = image[4096:4096 + ramdisk_size]
    if payload.startswith((b'070701', b'070702')):
        ramdisk = payload
    else:
        ramdisk = subprocess.run(
            ['lz4', '-d', '-c'], input=payload, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, check=True,
        ).stdout
    entries = cpio_entries(ramdisk)
    wifi_report = wificheck.check(elfcheck.cpio_entries(ramdisk)) if args.wifi else None
    elf_report = elfcheck.check_image(image)
    vintf_report = vintfcheck.check_files({
        name: entry.data for name, entry in elfcheck.unpack_recovery(image).items()
        if name.startswith("system/etc/vintf/")
    })
    required = [
        'init.recovery.qcom.rc',
        'vendor/bin/prepdecrypt.sh',
        'vendor/bin/touch_report',
        'system/etc/twrp.flags',
        'vendor/odm/firmware/synaptics_spi_houji.img',
    ]
    missing = [name for name in required if name not in entries]
    libraries = {}
    for library in ('libgui2.so', 'liblvgl_twrp.so'):
        matches = [name for name in entries if Path(name).name == library]
        libraries[library] = matches
        if not matches:
            missing.append(library)
    report = {
        'image': args.image.name,
        'size_bytes': len(image),
        'sha256': hashlib.sha256(image).hexdigest(),
        'boot_header_version': header_version,
        'kernel_size': kernel_size,
        'compressed_ramdisk_bytes': ramdisk_size,
        'ramdisk_entry_count': len(entries),
        'lvgl_libraries': libraries,
        'houji_files': {name: entries.get(name) for name in required},
        'missing': missing,
        'elf_check': elf_report,
        'recovery_vintf': vintf_report,
        'wifi': wifi_report,
        'scope': 'Packaging inspection only; boot and data decryption are unverified.',
    }
    rendered = json.dumps(report, indent=2, ensure_ascii=False) + '\n'
    print(rendered, end='')
    if args.report:
        args.report.write_text(rendered)
    if wifi_report and any(wifi_report[k] for k in ('missing', 'errors', 'elf_failures')):
        raise SystemExit('Incomplete experimental Wi-Fi runtime')
    if missing or elf_report['failures'] or vintf_report['missing'] or vintf_report['errors']:
        raise SystemExit('Recovery image has missing files, an ELF closure failure, or incomplete recovery VINTF')


if __name__ == '__main__':
    main()
