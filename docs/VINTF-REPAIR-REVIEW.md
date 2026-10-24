# Recovery VINTF repair review

## Confirmed failure

Run 3 (`20c03e8`, image SHA256
`b28fd6a4462183aafa7a6d4c5d88de551b936c427fb24b5749a84f5027cc7981`)
was tested on houji / OS3.0.307.0.WNCCNXM (Android 16).
The device reached the LVGL startup screen and recovery ADB. Live logs show:

1. Recovery servicemanager cannot find the KeyMint/default and other vendor
   HAL instances in its VINTF manifest and rejects registration.
2. Keystore2 cannot construct the mandatory TEE security level, reports
   `HARDWARE_TYPE_UNAVAILABLE`, and repeatedly aborts.
3. At kernel uptime 25.575402, init reports
   `critical process 'keystore2' exited 4 times before boot completed`.
   The device subsequently enters bootloader fastboot.

The matching official recovery was restored. Android boot completion and both
recovery partition hashes were verified. No format or data wipe was performed.
Raw device logs remain local outside this repository.

## Root cause and repair

The exact libvintf revision in the source manifest is
`2ef218d3586bbef90c2f0c14bbda901c7d60460a`.
[VintfObjectRecovery.cpp](https://android.googlesource.com/platform/system/libvintf/+/2ef218d3586bbef90c2f0c14bbda901c7d60460a/VintfObjectRecovery.cpp)
loads only `/system/etc/vintf/manifest.xml` and its `manifest/` fragments for
recovery registration. The donor tree's device HAL declarations under
`/vendor/etc/vintf` are not visible through that path.

Install system copies of the nine vendor fragments, plus the Gatekeeper
instance from the vendor base manifest. Preserve vendor originals. System
copies use `type="framework"`: ordinary hwservicemanager merges system
framework manifests, while VintfObjectRecovery explicitly forces that same
collection to device type. Existing system OMAPI and Keystore fragments are
retained without duplicating their instances.

Declare the standard HIDL manager 1.2 instance in a separate framework fragment.
The live log shows hwservicemanager disabling itself because that instance is
absent. Its standard recovery binary is already present. This restores the
manifest precondition for HIDL management and existing HIDL health fallback;
it does not substitute HIDL for the required AIDL KeyMint instance.

Do not disable Keystore's critical protection, fake boot completion, change
fstab/super geometry, or replace vendor crypto binaries for this repair.

## Validation

- Input validation checks required recovery-visible declarations and unchanged
  vendor-to-system copies (apart from the deliberate schema type).
- The final packed image is checked for all required service instances, versions,
  and framework-compatible system XML. Vendor-only declarations cannot pass.
- Cloud builds also merge the actual staged XML using Android's `assemble_vintf`
  parser, retaining the merged result in logs and artifacts. This detects XML
  schema and manifest merge conflicts beyond the Python presence check.
- Existing ELF checks and platform-vs-ramdisk C++ identity checks remain enabled.
- The previous failing run 3 image is a local negative regression; an in-memory
  overlay of the new fragments is checked without building Android locally.

A successful build still needs device validation: KeyMint registration,
Keystore survival beyond the previous failure time, UI/input, and data
access/decryption. The run 3 log also contains a `mifs` /data probe and mount
failure. That is unresolved and not claimed fixed by this VINTF change.
Android 14–17 compatibility remains unverified. This repair does not alter the
pinned TWRP source or introduce an Android 17 source baseline.
