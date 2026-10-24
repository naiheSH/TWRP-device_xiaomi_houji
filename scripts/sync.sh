#!/usr/bin/env bash
set -eo pipefail
[[ ${GITHUB_ACTIONS:-} == true && $(uname -s) == Linux ]] || exit 1
mkdir -p "$GITHUB_WORKSPACE/logs"
exec > >(tee "$GITHUB_WORKSPACE/logs/sync.log") 2>&1
cd "$SOURCE_DIR"
repo init --depth=1 --no-clone-bundle \
  -u https://github.com/TWRP-Test/platform_manifest_twrp_aosp.git \
  -b "$MANIFEST_REVISION" --manifest-upstream-branch twrp-16.0
mkdir -p .repo/local_manifests
cat > .repo/local_manifests/houji.xml <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<manifest>
  <extend-project name="android_bootable_recovery" path="bootable/recovery" revision="$RECOVERY_REVISION" />
</manifest>
EOF
synced=false
for attempt in 1 2 3; do
  if repo sync -c -j4 --no-tags --no-clone-bundle --optimized-fetch --fail-fast; then
    synced=true
    break
  fi
  echo "Source sync attempt $attempt failed."
  sleep 10
done
[[ $synced == true ]] || exit 1
test "$(git -C bootable/recovery rev-parse HEAD)" = "$RECOVERY_REVISION"
test -f external/lvgl/Android.bp
test -d bootable/recovery/gui2
grep -q liblvgl_twrp bootable/recovery/Android.bp
mkdir -p device/xiaomi/houji
rsync -a --exclude=.git --exclude=.github --exclude=artifacts --exclude=logs \
  "$GITHUB_WORKSPACE/" device/xiaomi/houji/
repo manifest -r -o "$GITHUB_WORKSPACE/logs/source-manifest.xml"
git -C "$GITHUB_WORKSPACE" rev-parse HEAD > "$GITHUB_WORKSPACE/logs/device-commit.txt"
df -h | tee "$GITHUB_WORKSPACE/logs/disk-synced.txt"
