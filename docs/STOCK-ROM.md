# Xiaomi 14 stock-ROM inspection

Source package: `houji_images_OS3.0.307.0.WNCCNXM_16.0`.

This directory contains CPIO file listings, selected text metadata, and the
single 28,143,616-byte `vendor_dlkm_a` logical extent. The temporary compressed
ramdisks and their expanded CPIO archives were discarded after inspection; no
other `super.img` filesystem was expanded.

## Image layout

| Image | File size | Header / payload facts |
| --- | ---: | --- |
| `boot.img` | 100,663,296 bytes | boot header v4; 4,096-byte pages; kernel 35,432,960 bytes; no boot ramdisk |
| `init_boot.img` | 8,388,608 bytes | boot header v4; 4,096-byte pages; LZ4/newc ramdisk 2,308,962 bytes |
| `vendor_boot.img` | 100,663,296 bytes | vendor boot header v4; 4,096-byte pages; LZ4/newc vendor ramdisk 32,935,111 bytes; DTB 2,364,996 bytes; one ramdisk-table entry; bootconfig 205 bytes |
| `recovery.img` | 104,857,600 bytes | boot header v4; 4,096-byte pages; **kernel size 0**; LZ4/newc recovery ramdisk 28,065,631 bytes |

The empty recovery kernel agrees with an external recovery image using the
device boot kernel (`BOARD_EXCLUDE_KERNEL_FROM_RECOVERY_IMAGE := true`). The
stock recovery partition is exactly 100 MiB, matching the device tree's
`BOARD_RECOVERYIMAGE_PARTITION_SIZE`. The stock vendor boot image has a DTB;
its layout must remain a vendor-boot-v4 image with the DTB retained by the
stock vendor boot partition.

## OS and encryption facts

The package directory is labelled Android 16. Its extracted **recovery and
init_boot properties** identify Xiaomi 14 (`houji`) and report Android 14 /
API 34, build `OS3.0.307.0.WNCCNXM`, with the August 2026 security patch.
These describe those image components; the installed system Android version
cannot be determined from the older recovery build properties alone.
The system partition inside `super.img` was not extracted here. `fstab.qcom` uses FBE v2 with inline crypt and metadata encryption:

```text
fileencryption=aes-256-xts:aes-256-cts:v2+inlinecrypt_optimized+wrappedkey_v0
metadata_encryption=aes-256-xts:wrappedkey_v0
```

This is compatible with the existing tree's FBE, metadata-decryption and
`TW_USE_FSCRYPT_POLICY := 2` choices. The stock recovery property file is
`prop.default` (with `default.prop` a symlink), and the stock init boot
properties identify the phone as `houji`.

## Mount and module comparison

The stock first-stage fstab differs materially from the older device-tree
fstab:

- It adds `/avb/u-gsi.avbpubkey` to the `system` AVB key list.
- It uses EROFS-only entries for `system_ext`, `product`, `vendor`,
  `vendor_dlkm`, and `odm` in this OS 3 package.
- It mounts `mi_ext` at `/mnt/vendor/mi_ext` and applies its product/system
  overlays, including a bind mount to `/mi_ext`.
- It includes `mifs` as an alternate `/data` filesystem and current
  `compress_mode=user` flags.

The tree's broader ext4/EROFS fallback remains useful for older firmware, but
the additional stock GSI AVB public-key entry and the OS 3 `mi_ext` overlay
mounting are candidates for a carefully tested fstab update. Do not replace
the fstab wholesale until a recovery boot and data-decryption test confirm the
existing fallback behavior remains needed.

The stock vendor-boot recovery module list contains platform modules such as
`qseecom_proxy.ko`, `goodix_fod.ko` and `speed_touch.ko`. It does **not** list
the five modules explicitly loaded by the device tree
(`adsp_loader_dlkm.ko`, `synaptics_tcm2.ko`, `nxp-nci.ko`,
`stm_st54se_gpio.ko`, `stm_nfc_i2c.ko`). Stock recovery itself carries only
`adsp_loader_dlkm.ko` among those names and starts it in
`init.recovery.qcom.rc`. This does not prove the device tree is wrong: its
recovery root supplies a separate Synaptics touch stack and pins those modules
for that stack. It does mean the touch/NFC module configuration needs on-device
testing on OS 3 rather than a filename-only update.

## Super partition correction

The original device tree has an incorrect 11,811,160,064-byte super size. The
official partition XML and `rawprogram0.xml` agree that the `super` partition
is 2,031,616 sectors of 4,096 bytes:

```text
2,031,616 * 4,096 = 8,321,499,136 bytes
```

The sparse super-image header independently reports 2,031,616 output blocks
of 4,096 bytes. Its first raw block contains valid LP metadata geometry:
64-KiB metadata slots, three slots and 4-KiB logical blocks.

The official LP metadata declares a second block device, `super_ext`, of
2,147,483,648 bytes. Its exact logical-partition description is:

```text
block devices:
  super      = 8,321,499,136 bytes
  super_ext  = 2,147,483,648 bytes
groups:
  qti_dynamic_partitions_a = 10,458,497,024 bytes
  qti_dynamic_partitions_b = 10,458,497,024 bytes
```

The group size is the combined device capacity less 10,485,760 bytes. Current
OS 3 extents are all on `super`, but the metadata permits future allocations on
`super_ext`. Therefore a single-device group of 8,317,304,832 bytes is a
possible legacy compatibility policy, not the OS 3 LP group value. The tree's
11-GiB single-device values are invalid and must not be treated as stock
layout. A recovery-only build with `PRODUCT_BUILD_SUPER_PARTITION := false`
does not generate a super image; at runtime liblp reads the phone's current LP
metadata. A full super-image build must instead model both block devices.

## vendor_dlkm module evidence

Only the `vendor_dlkm_a` LP extent was mapped out of the sparse image (one
28,143,616-byte extent); no other logical partition was extracted. Its EROFS
metadata contains all five modules loaded by the recovery tree:

```text
adsp_loader_dlkm.ko
synaptics_tcm2.ko
nxp-nci.ko
stm_st54se_gpio.ko
stm_nfc_i2c.ko
```

It also contains `goodix_fod.ko` and `speed_touch.ko`. This confirms the
recovery module names are valid for this OS 3 vendor_dlkm, including
`synaptics_tcm2.ko`; the stock vendor-boot module list is simply not the
source of those DLKM modules. No EROFS reader is installed locally, so the
exact `modules.load` ordering was not extracted. Filename evidence supports
retaining the current `TW_LOAD_VENDOR_MODULES` list; boot testing is still
needed for module order and touch initialization.

KeyMint, Gatekeeper, Weaver and QSEE executables are not embedded in the stock
vendor-boot ramdisk, so this inspection cannot establish binary equivalence
with the device tree's recovery-root copies without unpacking logical
partitions from the 7.2 GiB `super.img`. That was intentionally not done.

## Retained evidence

- `init_boot.cpio.list`, `recovery.cpio.list`, `vendor_boot.cpio.list`: full
  CPIO path lists only.
- `stock-selected/`: fstab, module lists, recovery init files and selected
  property files extracted from those CPIO archives.
- `vendor_dlkm/vendor_dlkm_a.erofs`: the one mapped vendor_dlkm logical extent
  used for the module-name check.
