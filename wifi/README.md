# Experimental houji Wi-Fi product

Choose `wifi` in the manually dispatched GitHub workflow to build
`twrp_houji_wifi`. The default `standard` variant remains `twrp_houji`.
The Wi-Fi variant is not yet validated on a device. Wi-Fi connection is
available only through LVGL in this variant; the legacy connect action shows
a message directing users back to LVGL.

This runtime targets the Kiwi v2 stack in Xiaomi 14 HyperOS
`OS3.0.307.0.WNCCNXM` (Android 16):

- Loads the installed ROM's `qca_cld3_kiwi_v2.ko` and its own dependency graph
  from the mapped vendor_dlkm partition. No foreign kernel modules are packed.
- Reads Kiwi firmware from the active modem partition and device-specific MAC
  data from a separate read-only persist mount. MAC data is never packaged.
- Includes the stock read-only `/vendor/etc/wifi/kiwi_v2/WCNSS_qcom_cfg.ini`.
- Starts the plain recovery supplicant only when Wi-Fi is enabled in the UI.
  Credentials remain in memory (`update_config=0`).
- Applies `gui2-dhcp.patch` to the pinned recovery source only for this variant.
  GUI2 invokes an init-managed, bounded IPv4 `dhcpdbg` transaction rather than
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
