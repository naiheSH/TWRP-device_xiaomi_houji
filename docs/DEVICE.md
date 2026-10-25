# Device configuration

## Recovery image

Xiaomi 14 (`houji`) uses a dedicated A/B recovery partition with a
104,857,600-byte limit. The recovery image uses boot header v4, 4,096-byte
alignment and an LZ4/newc ramdisk without an embedded kernel. Keep the stock
boot and vendor-boot kernel/DTB arrangement for the installed firmware.

## Logical partitions

This tree does not build a super image:

```make
PRODUCT_USE_DYNAMIC_PARTITIONS := true
PRODUCT_BUILD_SUPER_PARTITION := false
```

Runtime mapping uses the installed ROM's LP metadata rather than hardcoded
super sizes or groups. HyperOS `OS3.0.307.0.WNCCNXM` describes both `super`
and `super_ext`; older firmware may use a different allocation.

## Encryption and HALs

The configuration includes FBE v2, inline encryption, metadata encryption,
KeyMint, Gatekeeper, Weaver and OMAPI support. User-data decryption depends on
the installed firmware and lock-screen configuration.

Android 16 recovery reads its HAL manifest from `/system/etc/vintf`, including
the `manifest/` fragments. The tree supplies system copies of the required
vendor HAL declarations. These copies use the framework schema so ordinary
hwservicemanager can read them; recovery libvintf explicitly treats them as
device declarations. Vendor originals are retained.

The platform-built `libc++.so` must remain the default ramdisk C++ library.
The separately named `libc++-v35.so` is retained for vendor compatibility.

## Hardware support

The tree retains the houji Synaptics touch stack and loads these vendor modules:

```text
adsp_loader_dlkm.ko
synaptics_tcm2.ko
nxp-nci.ko
stm_st54se_gpio.ko
stm_nfc_i2c.ko
```

The configuration supports EROFS/ext4 logical partitions and F2FS userdata.
No other SM8650 device's kernel, firmware or partition geometry is substituted.
