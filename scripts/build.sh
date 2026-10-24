#!/usr/bin/env bash
# Android envsetup uses unset variables internally; do not enable `set -u`.
set -eo pipefail
[[ ${GITHUB_ACTIONS:-} == true && $(uname -s) == Linux ]] || exit 1
[[ $BUILD_JOBS == 2 || $BUILD_JOBS == 4 ]] || exit 1
mkdir -p "$GITHUB_WORKSPACE/logs" "$GITHUB_WORKSPACE/artifacts"
exec > >(tee "$GITHUB_WORKSPACE/logs/build.log") 2>&1
cd "$SOURCE_DIR"
export ALLOW_MISSING_DEPENDENCIES=true
source build/envsetup.sh
# The Android 16 build fork requires product + release configuration + variant.
lunch twrp_houji bp2a eng
[[ $(get_build_var TARGET_DEVICE) == houji ]]
mka -j"$BUILD_JOBS" recoveryimage assemble_vintf
platform_libcxx=out/target/product/houji/system/lib64/libc++.so
ramdisk_libcxx=out/target/product/houji/recovery/root/system/lib64/libc++.so
test -s "$platform_libcxx"
test -s "$ramdisk_libcxx"
sha256sum "$platform_libcxx" "$ramdisk_libcxx" \
  > "$GITHUB_WORKSPACE/logs/libcxx-selection.sha256"
if ! cmp -s "$platform_libcxx" "$ramdisk_libcxx"; then
  echo 'Recovery libc++.so differs from the Android platform build output.' >&2
  exit 1
fi
# Use Android's own parser to merge the actual staged recovery manifests.
# All system fragments are framework-typed for hwservicemanager; recovery's
# VintfObjectRecovery deliberately treats the same declarations as device HALs.
vintf_root=out/target/product/houji/recovery/root/system/etc/vintf
vintf_inputs="$vintf_root/manifest.xml"
for fragment in "$vintf_root/manifest/"*.xml; do
  test -s "$fragment"
  vintf_inputs+=":$fragment"
done
out/host/linux-x86/bin/assemble_vintf -i "$vintf_inputs" \
  -o "$GITHUB_WORKSPACE/logs/recovery-vintf-assembled.xml"
python3 - "$GITHUB_WORKSPACE" <<'PYVINTF'
from pathlib import Path
import sys
sys.path.insert(0, str(Path(sys.argv[1]) / 'scripts'))
import vintfcheck
merged = Path(sys.argv[1]) / 'logs/recovery-vintf-assembled.xml'
report = vintfcheck.check_files({vintfcheck.SYSTEM_BASE: merged.read_bytes()})
assert not report['missing'] and not report['errors'], report
PYVINTF
image=out/target/product/houji/recovery.img
test -s "$image"
python3 - "$image" <<'PY'
import pathlib, sys
p = pathlib.Path(sys.argv[1])
assert p.stat().st_size <= 104857600, 'Image exceeds the houji recovery partition'
assert p.open('rb').read(8) == b'ANDROID!', 'Invalid Android recovery boot image magic'
print(f'houji recovery image: {p.stat().st_size} bytes')
PY
# Inspect the final archive after all device ramdisk overlays have been copied.
# A successful link alone cannot detect a library overwritten during packaging.
python3 "$GITHUB_WORKSPACE/scripts/inspect-image.py" "$image" \
  --report "$GITHUB_WORKSPACE/logs/image-inspection.json"
suffix="${GITHUB_RUN_NUMBER}-${GITHUB_SHA:0:8}"
cp "$image" "$GITHUB_WORKSPACE/artifacts/twrp-lvgl-houji-${suffix}.img"
cp "$GITHUB_WORKSPACE/logs/source-manifest.xml" "$GITHUB_WORKSPACE/artifacts/"
cp "$GITHUB_WORKSPACE/logs/device-commit.txt" "$GITHUB_WORKSPACE/artifacts/"
cp "$GITHUB_WORKSPACE/logs/image-inspection.json" "$GITHUB_WORKSPACE/artifacts/"
cp "$GITHUB_WORKSPACE/logs/libcxx-selection.sha256" "$GITHUB_WORKSPACE/artifacts/"
cp "$GITHUB_WORKSPACE/docs/TESTING.md" "$GITHUB_WORKSPACE/artifacts/"
cp "$GITHUB_WORKSPACE/logs/recovery-vintf-assembled.xml" "$GITHUB_WORKSPACE/artifacts/"
cp "$GITHUB_WORKSPACE/docs/VINTF-REPAIR-REVIEW.md" "$GITHUB_WORKSPACE/artifacts/"
cp "$GITHUB_WORKSPACE/docs/RUNTIME-REPAIR-REVIEW.md" "$GITHUB_WORKSPACE/artifacts/"
cd "$GITHUB_WORKSPACE/artifacts"
sha256sum ./*.img > SHA256SUMS
{
  echo '### houji LVGL recovery compiled'
  echo 'Download the image and SHA256SUMS from this run’s artifact.'
  echo 'A successful build does not verify boot, touch, or Android 14–17 data decryption.'
} >> "$GITHUB_STEP_SUMMARY"
