#!/usr/bin/env python3
"""Check device identity and recovery packaging without compiling locally."""
from pathlib import Path
import hashlib
import re

import vintfcheck

root = Path(__file__).resolve().parents[1]
board = (root / 'BoardConfig.mk').read_text()
device = (root / 'device.mk').read_text()
product = (root / 'twrp_houji.mk').read_text()
assert re.search(r'^PRODUCT_DEVICE\s*:=\s*houji\s*$', product, re.M)
assert re.search(r'^PRODUCT_NAME\s*:=\s*twrp_houji\s*$', product, re.M)
assert 'device/xiaomi/houji' in product
assert 'fox_houji.mk' not in device
assert 'sm8650-common' not in device
assert 'BOARD_RECOVERYIMAGE_PARTITION_SIZE := 104857600' in board
assert 'BOARD_SUPER_PARTITION_SIZE' not in board
assert 'BOARD_SUPER_PARTITION_GROUPS' not in board
assert 'PRODUCT_USE_DYNAMIC_PARTITIONS := true' in device
assert 'PRODUCT_BUILD_SUPER_PARTITION := false' in device
assert 'BOARD_EXCLUDE_KERNEL_FROM_RECOVERY_IMAGE := true' in board
assert 'BOARD_BOOT_HEADER_VERSION     := 4' in board
assert 'TARGET_PREBUILT_KERNEL' in board
assert 'TW_INCLUDE_CRYPTO_FBE' in board
assert 'TW_INCLUDE_FBE_METADATA_DECRYPT' in board
kernel = root / 'prebuilt/kernel'
assert kernel.stat().st_size > 1024 * 1024
assert kernel.read_bytes()[0x38:0x3c] == b'ARM\x64', 'Invalid ARM64 Image header'
assert not (root / 'vendorsetup.sh').exists(), 'OrangeFox environment must not be sourced'
assert not (root / 'fox_houji.mk').exists()
libcxx_overlay = root / 'recovery/root/system/lib64/libc++.so'
assert not (libcxx_overlay.exists() or libcxx_overlay.is_symlink()), (
    'Do not overwrite the Android platform libc++.so with a device prebuilt'
)
assert 'twrp_houji-bp2a-eng' in (root / 'AndroidProducts.mk').read_text()
fstab = (root / 'recovery.fstab').read_text()
assert 'fileencryption=' in fstab and 'metadata_encryption=' in fstab
assert 'erofs' in fstab and 'ext4' in fstab
assert '/recovery' in (root / 'recovery/root/system/etc/twrp.flags').read_text()
for p in root.rglob('*'):
    if p.is_file() and '.git' not in p.relative_to(root).parts:
        assert p.stat().st_size < 100 * 1024 * 1024, f'GitHub file too large: {p}'
print('houji identity, recovery layout, ARM64 prebuilt, FBE configuration: OK')
print('kernel SHA256:', hashlib.sha256(kernel.read_bytes()).hexdigest())

vintf = vintfcheck.check_source(root)
assert not vintf['missing'] and not vintf['errors'], vintf
print('recovery system VINTF declarations: OK')

# Wi-Fi is an explicit alternate product; the default image stays independent.
assert 'twrp_houji_wifi.mk' in (root / 'AndroidProducts.mk').read_text()
wifi_product = (root / 'twrp_houji_wifi.mk').read_text()
assert 'wpa_supplicant_recovery' in wifi_product and 'wpa_cli_recovery' in wifi_product
assert 'ifeq ($(TARGET_PRODUCT),twrp_houji_wifi)' in board
assert 'update_config=0' in (root / 'wifi/wpa_supplicant.conf').read_text()
assert 'HOUJI_WIFI_DHCP_OK' in (root / 'wifi/gui2-dhcp.patch').read_text()
for name in ('houji-wifi-control.sh', 'houji-wifi-dhcp.sh'):
    assert (root / 'wifi' / name).stat().st_mode & 0o111
print('Optional houji Wi-Fi product inputs: OK')
