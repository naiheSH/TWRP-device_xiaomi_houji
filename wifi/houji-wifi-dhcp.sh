#!/system/bin/sh
# SPDX-License-Identifier: Apache-2.0
set -eu
umask 077
PATH=/system/bin:/sbin
[ "${1:-}" = wlan0 ] || exit 2
work=/tmp/houji-wifi
read_state() { cat "$work/$1" 2>/dev/null || true; }
session=$(read_state session)
[ -n "$session" ] || exit 1
[ "$(getprop init.svc.wpa_supplicant)" = running ] || exit 1
stop houji.wifi-dhcp
attempt=0
while [ "$(getprop init.svc.houji.wifi-dhcp)" != stopped ] && [ "$attempt" -lt 30 ]; do
    sleep 0.1
    attempt=$((attempt + 1))
done
[ "$(getprop init.svc.houji.wifi-dhcp)" = stopped ] || exit 1
request="$session:$$"
echo "$request" > "$work/dhcp.request"
succeeded=false
finish_attempt() {
    if [ "$succeeded" = false ]; then
        /system/bin/houji-wifi-control dhcp-failed "$request" || true
    fi
}
trap finish_attempt EXIT
trap 'exit 1' HUP INT TERM
busybox ip route flush dev wlan0
busybox ip addr flush dev wlan0
for property in ipaddress gateway dns1 dns2; do setprop "net.wlan0.$property" ''; done
: > "$work/resolv.conf"
rm -f "$work/dhcp.ok" "$work/dhcp.failed"
start houji.wifi-dhcp
attempt=0
while [ "$attempt" -lt 400 ]; do
    # Validate the session before accepting a success marker from a worker.
    [ "$(getprop init.svc.wpa_supplicant)" = running ] || exit 1
    [ "$(read_state session)" = "$session" ] || exit 1
    [ "$(read_state dhcp.request)" = "$request" ] || exit 1
    if [ "$(read_state dhcp.ok)" = "$request" ]; then
        succeeded=true
        echo HOUJI_WIFI_DHCP_OK
        exit 0
    fi
    [ "$(read_state dhcp.failed)" != "$request" ] || exit 1
    sleep 0.1
    attempt=$((attempt + 1))
done
exit 1
