# Experimental houji Wi-Fi product

Choose `wifi` in the manually dispatched GitHub workflow to build
`twrp_houji_wifi`. The default `standard` variant remains `twrp_houji`.
The Wi-Fi variant still needs clean-boot validation of the updated image.
Scanning, WPA2 association, IPv4 DHCP, DNS and internet access have worked
with temporary runtime corrections on the target firmware. Wi-Fi connection is
available only through LVGL in this variant; the legacy connect action shows
a message directing users back to LVGL.

This runtime targets the Kiwi v2 stack in Xiaomi 14 HyperOS
`OS3.0.307.0.WNCCNXM` (Android 16):

- Loads the installed ROM's `qca_cld3_kiwi_v2.ko` and its own dependency graph
  from the mapped vendor_dlkm partition. Its omitted `rfkill` dependency is
  loaded first from the installed ROM's system_dlkm partition. Both flattened
  and versioned GKI module layouts are supported. No foreign modules are packed.
- Reads Kiwi firmware from the active modem partition and device-specific MAC
  data from a separate read-only persist mount (`kiwi_v2/wlan_mac.bin`, with a
  legacy `wlan/wlan_mac.bin` fallback). MAC data is never packaged.
- Includes the stock read-only `/vendor/etc/wifi/kiwi_v2/WCNSS_qcom_cfg.ini`.
- Starts the plain recovery supplicant only when Wi-Fi is enabled in the UI.
  Credentials remain in memory (`update_config=0`).
- Applies `gui2-dhcp.patch` to the pinned recovery source only for this variant.
  GUI2 invokes an init-managed, bounded IPv4 BusyBox `udhcpc` transaction with a session-checked event callback rather than
  the upstream daemon that requires `/data/misc/dhcp`. The source patch and its
  hash are included in the artifact.
- Stops the DHCP worker and clears WLAN addresses, routes and DNS when disabled.
  Matching shared modules and read-only mounts remain available for reuse.

The driver must create `wlan0` through its `/dev/wlan` control path. If it does
not, startup fails with a diagnostic message; a device-matched vendor HAL client
may need to be added. No HAL binaries from other Xiaomi platforms are used.

Device validation must cover boot/decryption, network scanning, association,
IPv4 DHCP, DNS, internet access and repeated enable/disable. WPA3 and other ROM,
firmware or kernel combinations are not guaranteed. This variant is experimental,
not a claim of working Wi-Fi support.

DHCP currently obtains a lease once and exits; automatic lease renewal is not
implemented. Use this experimental variant for short recovery sessions.
