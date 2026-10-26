#!/system/bin/sh
# SPDX-License-Identifier: Apache-2.0
# DHCP option values are untrusted; never evaluate them as shell commands.
set -eu
set -f
umask 077
PATH=/system/bin:/sbin
work=/tmp/houji-wifi
[ "${interface:-}" = wlan0 ] || exit 1
read_state() { cat "$work/$1" 2>/dev/null || true; }
[ "$(getprop init.svc.wpa_supplicant)" = running ] || exit 1
[ -n "${HOUJI_WIFI_SESSION:-}" ] || exit 1
[ "$(read_state session)" = "$HOUJI_WIFI_SESSION" ] || exit 1
[ "$(read_state dhcp.request)" = "${HOUJI_WIFI_REQUEST:-}" ] || exit 1
case "${1:-}" in
    deconfig)
        busybox ip route flush dev wlan0 || true
        busybox ip addr flush dev wlan0 || true
        ;;
    bound|renew)
        [ -n "${ip:-}" ] && [ -n "${subnet:-}" ] || exit 1
        case "$ip$subnet" in *[!0-9.]*) exit 1;; esac
        ifconfig wlan0 "$ip" netmask "$subnet" up
        for gateway in ${router:-}; do
            case "$gateway" in ''|*[!0-9.]*) continue;; esac
            busybox ip route replace default via "$gateway" dev wlan0
            setprop net.wlan0.gateway "$gateway"
            break
        done
        : > "$work/resolv.conf"
        count=0
        for server in ${dns:-}; do
            case "$server" in ''|*[!0-9.]*) continue;; esac
            echo "nameserver $server" >> "$work/resolv.conf"
            count=$((count + 1))
            if [ "$count" -le 2 ]; then setprop "net.wlan0.dns$count" "$server"; fi
        done
        chmod 0644 "$work/resolv.conf"
        [ "$(getprop init.svc.wpa_supplicant)" = running ] || exit 1
        [ "$(read_state session)" = "$HOUJI_WIFI_SESSION" ] || exit 1
        [ "$(read_state dhcp.request)" = "$HOUJI_WIFI_REQUEST" ] || exit 1
        echo "$HOUJI_WIFI_REQUEST" > "$work/dhcp.bound"
        ;;
esac
