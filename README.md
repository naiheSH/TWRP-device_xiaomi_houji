# TWRP for Xiaomi 14 (houji)

An experimental Xiaomi 14 recovery device tree for TWRP-Test's LVGL interface.
Images are built with GitHub Actions using the Android 16 `twrp-16.0` source
baseline. Boot and user-data decryption have been confirmed on HyperOS
`OS3.0.307.0.WNCCNXM` (Android 16). Other ROM and firmware combinations still
need validation.

## Device

| Item | Configuration |
| --- | --- |
| Device | Xiaomi 14 (`houji`; inherited device assertions also include `houjiin`) |
| Platform | Qualcomm SM8650 |
| Product | `twrp_houji` |
| Lunch target | `twrp_houji bp2a eng` |
| Build target | `recoveryimage` |
| Image | Dedicated `recovery.img`, up to 100 MiB |
| Interface | TWRP-Test LVGL `gui2` |
| Source baseline | Android 16 / `twrp-16.0` |

This is a standalone recovery tree. The LineageOS `lineage-24.0` device and
SM8650 common trees are not dependencies. An Android 17 ROM device tree does
not by itself provide Android 17 recovery or data-decryption compatibility.

See [device configuration](docs/DEVICE.md) for image layout, encryption and
logical-partition details.

## Build with GitHub Actions

1. Open **Actions → Build houji LVGL recovery → Run workflow**.
2. Choose **4** parallel jobs, or **2** if the runner runs out of memory.
3. Download the `twrp-lvgl-houji-<run-number>` artifact after a successful build.
4. Verify the image against the included `SHA256SUMS` before installing it.

Artifacts include the image, source revisions, image inspection results and
assembled recovery VINTF manifest. Failed builds retain a
`houji-build-logs-<run-number>` artifact.

The workflow runs only on manual dispatch, uses a GitHub-hosted
`ubuntu-22.04` runner and does not create releases or operate connected devices.
Image artifacts are retained for 30 days and build logs for 14 days. Persistent
source or compiler caching is not currently configured.

The manifest and recovery revisions are pinned in
[the workflow](.github/workflows/build.yml). A resolved source manifest is
saved with every build. Shallow clones retain the complete files at the chosen
revision; the minimal manifest selects the projects needed for recovery.

## Local checks

Local checks do not compile Android or flash a device:

```sh
python3 scripts/validate.py
python3 -m unittest discover -s tests -v
bash -n scripts/*.sh
```

After downloading an image, inspect it with Python 3 and `lz4`:

```sh
python3 scripts/inspect-image.py path/to/recovery.img --report inspection.json
```

The inspector checks the image layout and size, required device files, LVGL
libraries, key ELF dependencies and recovery-visible VINTF declarations.
Cloud builds additionally compare the platform and ramdisk C++ libraries and
merge the staged VINTF manifests with Android's native `assemble_vintf` tool.
These checks do not replace device validation.

## Usage and compatibility

- Keep the matching stock recovery available before installing an image.
- This recovery image has no embedded kernel. The tree does not provide a
  validated `fastboot boot` procedure.
- Confirm boot, input and data access for the exact ROM, vendor firmware and
  security patch combination in use. Android 14, 15 and 17 remain unverified.
- Backup/restore, ZIP installation, MTP transfers, USB-OTG and long-term
  stability have not been fully validated.
- To return from the legacy default theme to LVGL, choose **Reboot → Recovery**.
  Switching to the legacy interface lasts for the current recovery session;
  LVGL starts again on the next recovery boot. Decryption may be required again.

Read-only diagnostic collection:

```sh
adb pull /tmp/recovery.log
adb shell getprop > recovery-properties.txt
adb shell cat /proc/mounts > recovery-mounts.txt
adb shell dmesg > recovery-dmesg.txt
```

Remove personal information before sharing logs. Do not include lock-screen
credentials. Formatting data is not a substitute for working decryption.

## Sources and credits

- Device tree: [QCerberusQ/OFRP-device_xiaomi_houji](https://github.com/QCerberusQ/OFRP-device_xiaomi_houji),
  `fox_14.1`, revision `9f7455903b570814b2e0cdcdbe5328eaa55e9cf6`.
- Manifest: [TWRP-Test/platform_manifest_twrp_aosp](https://github.com/TWRP-Test/platform_manifest_twrp_aosp/tree/twrp-16.0),
  revision `814b553116ceedde197f70389cff9661d81d8337`.
- Recovery: [TWRP-Test/android_bootable_recovery](https://github.com/TWRP-Test/android_bootable_recovery/tree/twrp-16.0),
  revision `0a9962492fc48b9af32cc9943de8ee7105a82af3`.
- Workflow reference: [polygraphene/android_device_lenovo_TB322FC](https://github.com/polygraphene/android_device_lenovo_TB322FC/blob/twrp-16.0/.github/workflows/build.yml).
- Platform reference: [YuKongA/twrp_device_xiaomi_sm8850](https://github.com/YuKongA/twrp_device_xiaomi_sm8850/tree/twrp-16.0).
  Its Xiaomi 17 kernel, firmware, HALs and partition geometry are not used here.

Original copyright and license notices are retained. Vendor binaries retain
their original provenance; this adaptation does not relicense them.
