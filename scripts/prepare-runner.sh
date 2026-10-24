#!/usr/bin/env bash
set -euo pipefail
[[ ${GITHUB_ACTIONS:-} == true && $(uname -s) == Linux ]] || {
  echo 'This script is intended only for an ephemeral GitHub Actions Linux runner.' >&2
  exit 1
}
mkdir -p "$GITHUB_WORKSPACE/logs"
df -h | tee "$GITHUB_WORKSPACE/logs/disk-before.txt"
# These are unused preinstalled SDKs on the disposable hosted runner.
sudo rm -rf /usr/share/dotnet /usr/local/lib/android /opt/ghc /opt/hostedtoolcache/CodeQL
sudo docker image prune --all --force
sudo apt-get update
sudo apt-get install -y --no-install-recommends \
  bc bison build-essential ca-certificates ccache curl flex g++-multilib \
  gcc-multilib git git-lfs gnupg gperf imagemagick lib32readline-dev \
  lib32z1-dev libelf-dev liblz4-tool libncurses5 libncurses-dev libsdl1.2-dev \
  libssl-dev libxml2 libxml2-utils lzop openjdk-17-jdk pngcrush \
  python3 python-is-python3 rsync schedtool squashfs-tools unzip \
  xsltproc zip zlib1g-dev
sudo mkdir -p "$SOURCE_DIR"
sudo chown "$(id -u):$(id -g)" "$SOURCE_DIR"
if [[ ! -f /mnt/houji-build.swap ]]; then
  sudo fallocate -l 8G /mnt/houji-build.swap
  sudo chmod 600 /mnt/houji-build.swap
  sudo mkswap /mnt/houji-build.swap
  sudo swapon /mnt/houji-build.swap
fi
git config --global user.name 'houji recovery builder'
git config --global user.email 'houji-builder@users.noreply.github.com'
git config --global advice.detachedHead false
mkdir -p "$HOME/.local/bin"
curl --fail --location --retry 5 \
  https://storage.googleapis.com/git-repo-downloads/repo -o "$HOME/.local/bin/repo"
chmod +x "$HOME/.local/bin/repo"
echo "$HOME/.local/bin" >> "$GITHUB_PATH"
df -h | tee "$GITHUB_WORKSPACE/logs/disk-prepared.txt"
free -h | tee "$GITHUB_WORKSPACE/logs/memory.txt"
