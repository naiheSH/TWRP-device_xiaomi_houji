#!/system/bin/sh
# SPDX-License-Identifier: Apache-2.0
# No firmware, modules, calibration or credentials are written to flash.
set -eu
umask 077
PATH=/system/bin:/sbin
work=/tmp/houji-wifi
iface=wlan0

note() { echo "houji-wifi: $*" >> /tmp/recovery.log; }
mounted() { grep -q " $1 " /proc/mounts; }
fail() { note "$*"; exit 1; }
read_state() { cat "$work/$1" 2>/dev/null || true; }
block_path() {
    for candidate in "/dev/block/bootdevice/by-name/$1" "/dev/block/by-name/$1"; do
        if [ -e "$candidate" ]; then echo "$candidate"; return 0; fi
    done
    return 1
}
stop_dhcp() {
    stop houji.wifi-dhcp || true
    attempt=0
    while [ "$(getprop init.svc.houji.wifi-dhcp)" != stopped ] && [ "$attempt" -lt 30 ]; do
        sleep 0.1
        attempt=$((attempt + 1))
    done
    [ "$(getprop init.svc.houji.wifi-dhcp)" = stopped ]
}
clear_network() {
    if [ -e "/sys/class/net/$iface" ]; then
        ip route flush dev "$iface" || true
        ip addr flush dev "$iface" || true
    fi
    for property in ipaddress gateway dns1 dns2; do
        setprop "net.$iface.$property" '' || true
    done
    # Only update the RAM-backed DNS file created during preparation.
    [ ! -f "$work/resolv.conf" ] || : > "$work/resolv.conf"
}

mount_filesystem() {
    device=$1
    destination=$2
    mounted "$destination" && return 0
    mkdir -p "$destination"
    mount -t erofs -o ro "$device" "$destination" 2>/dev/null ||
        mount -t ext4 -o ro,noload "$device" "$destination"
}

# A subshell gives each recursive call its own variables. Dependencies come
# from the running ROM; an already loaded/built-in module is never reinserted.
load_module() (
    name=${1##*/}
    module=${name%.ko}
    module=$(echo "$module" | tr - _)
    [ -d "/sys/module/$module" ] && exit 0
    depth=${2:-0}
    [ "$depth" -lt 50 ] || { note 'module dependency depth exceeded'; exit 1; }
    [ -f "$modules/$name" ] || { note "missing kernel module $name"; exit 1; }
    dependencies=$(awk -v name="$name:" '
        { key=$1; sub(/^.*\//, "", key); if (key == name) {
            for (i=2;i<=NF;i++) print $i; exit
        }}' "$modules/modules.dep")
    for dependency in $dependencies; do
        load_module "$dependency" "$((depth + 1))" || exit 1
    done
    insmod "$modules/$name" || { note "kernel rejected $name"; exit 1; }
    if [ "$module" = cnss2 ] && [ -w /sys/kernel/cnss/fs_ready ]; then
        echo 1 > /sys/kernel/cnss/fs_ready
    fi
)

prepare() {
    [ "$(getprop ro.product.device)" = houji ] || fail 'this runtime requires houji'
    # Refuse before touching a vendor path if it refers to a mounted ROM.
    mounted /vendor && fail 'unmount vendor before enabling experimental Wi-Fi'
    mounted /system && fail 'unmount system before enabling experimental Wi-Fi'
    mkdir -p "$work"
    attempt=0
    cleanup_state=$(getprop init.svc.houji.wifi-cleanup)
    while [ -n "$cleanup_state" ] && [ "$cleanup_state" != stopped ] && [ "$attempt" -lt 50 ]; do
        sleep 0.1
        attempt=$((attempt + 1))
        cleanup_state=$(getprop init.svc.houji.wifi-cleanup)
    done
    case "$cleanup_state" in ''|stopped) ;; *) fail 'Wi-Fi cleanup is still running';; esac
    suffix=$(getprop ro.boot.slot_suffix)
    case "$suffix" in _a|_b) ;; *) fail 'unknown active slot';; esac
    # Keep the firmware mounted while WLAN is enabled, independent of the
    # existing ADSP/QSEE /firmware mount/unmount sequence.
    if ! mounted /vendor/firmware_mnt; then
        mkdir -p /vendor/firmware_mnt
        mount -t vfat -o ro "$(block_path "modem$suffix")" /vendor/firmware_mnt
    fi
    [ -f /vendor/firmware_mnt/image/kiwi/amss.bin ] || fail 'Kiwi modem firmware missing'
    # A separate read-only mount avoids replacing TWRP's persist bindings.
    if ! mounted "$work/persist"; then
        mount_filesystem "$(block_path persist)" "$work/persist"
    fi
    mkdir -p /vendor/firmware/wlan/qca_cld/kiwi_v2
    ln -sf /vendor/etc/wifi/kiwi_v2/WCNSS_qcom_cfg.ini \
        /vendor/firmware/wlan/qca_cld/kiwi_v2/WCNSS_qcom_cfg.ini
    ln -sf "$work/persist/wlan/wlan_mac.bin" \
        /vendor/firmware/wlan/qca_cld/kiwi_v2/wlan_mac.bin

    if [ ! -d /sys/module/qca_cld3_kiwi_v2 ]; then
        block="/dev/block/mapper/vendor_dlkm$suffix"
        [ -e "$block" ] || block=/dev/block/mapper/vendor_dlkm
        [ -e "$block" ] || fail 'vendor_dlkm is not mapped; finish recovery startup first'
        mount_filesystem "$block" "$work/vendor_dlkm"
        modules="$work/vendor_dlkm/lib/modules"
        [ -s "$modules/modules.dep" ] || fail 'module dependency file missing'
        if [ -w /sys/kernel/cnss/fs_ready ]; then
            echo 1 > /sys/kernel/cnss/fs_ready
        fi
        load_module qca_cld3_kiwi_v2.ko
    fi
    if [ -w /sys/kernel/cnss/fs_ready ]; then
        echo 1 > /sys/kernel/cnss/fs_ready
    fi
    if [ ! -e "/sys/class/net/$iface" ] && [ -c /dev/wlan ]; then
        echo ON > /dev/wlan
    fi
    attempt=0
    while [ ! -e "/sys/class/net/$iface" ] && [ "$attempt" -lt 150 ]; do
        sleep 0.1
        attempt=$((attempt + 1))
    done
    [ -e "/sys/class/net/$iface" ] || fail 'driver did not create wlan0; HAL initialization may be required'
    ifconfig "$iface" up
    mkdir -p /tmp/recovery/sockets
    chmod 0711 /tmp/recovery
    chown wifi:wifi /tmp/recovery/sockets
    chmod 0770 /tmp/recovery/sockets
    # The recovery wpa_cli drops to wifi and creates its client socket in /tmp.
    chmod 1777 /tmp
    rm -f /tmp/recovery/sockets/wlan0
    : > "$work/resolv.conf"
    chmod 0644 "$work/resolv.conf"
    # /system and /vendor are verified unmounted above. Replace only a RAM
    # directory entry; never follow an existing resolver symlink into flash.
    ln -sf "$work/resolv.conf" /etc/resolv.conf
    echo "$$" > "$work/session"
    setprop wifi.interface "$iface"
    note 'runtime ready; starting recovery supplicant'
}

cleanup() {
    # Ignore a delayed stopped event if the user already started a new session.
    [ "$(getprop init.svc.wpa_supplicant)" != running ] || return 0
    rm -f "$work/session" "$work/dhcp.request"
    stop_dhcp || fail 'DHCP worker did not stop'
    clear_network
    if [ -e "/sys/class/net/$iface" ]; then ifconfig "$iface" down || true; fi
    rm -f "$work/dhcp.ok" "$work/dhcp.failed" /tmp/recovery/sockets/wlan0
    note 'DHCP stopped; WLAN address, routes and DNS cleared'
}

dhcp_failed() {
    [ "$(read_state dhcp.request)" = "$1" ] || return 0
    [ "$(read_state session)" = "${1%%:*}" ] || return 0
    rm -f "$work/dhcp.request"
    stop_dhcp || fail 'DHCP worker did not stop'
    clear_network
    rm -f "$work/dhcp.ok" "$work/dhcp.failed"
}

dhcp_worker() {
    mkdir -p "$work"
    request=$(read_state dhcp.request)
    session=$(read_state session)
    [ -n "$session" ] && [ "${request%%:*}" = "$session" ] || exit 1
    # The AOSP recovery tool performs one IPv4 DHCP transaction and exits.
    # Do not use the upstream prebuilt daemon's /data/misc/dhcp state.
    if ! dhcpdbg "$iface" > "$work/dhcp.log" 2>&1; then
        echo "$request" > "$work/dhcp.failed"
        exit 1
    fi
    [ "$(getprop init.svc.wpa_supplicant)" = running ] || exit 1
    [ "$(read_state session)" = "$session" ] || exit 1
    [ "$(read_state dhcp.request)" = "$request" ] || exit 1
    address=$(ifconfig "$iface" | awk '
        /inet / { for (i=1;i<=NF;i++) {
            if ($i ~ /^addr:/) {sub(/^addr:/,"",$i); print $i; exit}
            if ($i == "inet") {print $(i+1); exit}
        }}')
    [ -n "$address" ] && [ "$address" != 0.0.0.0 ] || {
        echo "$request" > "$work/dhcp.failed"; exit 1;
    }
    setprop "net.$iface.ipaddress" "$address"
    : > "$work/resolv.conf"
    for property in dns1 dns2; do
        dns=$(getprop "net.$iface.$property")
        [ -z "$dns" ] || echo "nameserver $dns" >> "$work/resolv.conf"
    done
    chmod 0644 "$work/resolv.conf"
    [ "$(getprop init.svc.wpa_supplicant)" = running ] || exit 1
    [ "$(read_state session)" = "$session" ] || exit 1
    [ "$(read_state dhcp.request)" = "$request" ] || exit 1
    echo "$request" > "$work/dhcp.ok"
}

case "${1:-}" in
    run) prepare; exec wpa_supplicant -Dnl80211 -iwlan0 -c/system/etc/wifi/houji.conf -O/tmp/recovery/sockets ;;
    cleanup) cleanup ;;
    dhcp-worker) dhcp_worker ;;
    dhcp-failed) dhcp_failed "${2:-}" ;;
    *) echo 'usage: houji-wifi-control {run|cleanup|dhcp-worker}' >&2; exit 2 ;;
esac
