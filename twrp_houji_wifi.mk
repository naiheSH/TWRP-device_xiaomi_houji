# SPDX-License-Identifier: Apache-2.0
$(call inherit-product, device/xiaomi/houji/twrp_houji.mk)
PRODUCT_NAME := twrp_houji_wifi
PRODUCT_PACKAGES += wpa_supplicant_recovery wpa_cli_recovery dhcpdbg
PRODUCT_COPY_FILES += \
    $(DEVICE_PATH)/wifi/houji-wifi-control.sh:recovery/root/system/bin/houji-wifi-control \
    $(DEVICE_PATH)/wifi/houji-wifi-dhcp.sh:recovery/root/system/bin/houji-wifi-dhcp \
    $(DEVICE_PATH)/wifi/init.houji.wifi.rc:recovery/root/system/etc/init/houji-wifi.rc \
    $(DEVICE_PATH)/wifi/wpa_supplicant.conf:recovery/root/system/etc/wifi/houji.conf \
    $(DEVICE_PATH)/wifi/WCNSS_qcom_cfg.ini:recovery/root/vendor/etc/wifi/kiwi_v2/WCNSS_qcom_cfg.ini
