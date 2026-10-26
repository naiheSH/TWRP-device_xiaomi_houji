# SPDX-License-Identifier: Apache-2.0
$(call inherit-product, device/xiaomi/houji/twrp_houji.mk)
# inherit-product does not export arbitrary parent-local variables into this file.
HOUJI_WIFI_PATH := device/xiaomi/houji/wifi
PRODUCT_NAME := twrp_houji_wifi
PRODUCT_PACKAGES += wpa_supplicant_recovery wpa_cli_recovery dhcpdbg
PRODUCT_COPY_FILES += \
    $(HOUJI_WIFI_PATH)/houji-wifi-control.sh:recovery/root/system/bin/houji-wifi-control \
    $(HOUJI_WIFI_PATH)/houji-wifi-dhcp.sh:recovery/root/system/bin/houji-wifi-dhcp \
    $(HOUJI_WIFI_PATH)/init.houji.wifi.rc:recovery/root/system/etc/init/houji-wifi.rc \
    $(HOUJI_WIFI_PATH)/wpa_supplicant.conf:recovery/root/system/etc/wifi/houji.conf \
    $(HOUJI_WIFI_PATH)/WCNSS_qcom_cfg.ini:recovery/root/vendor/etc/wifi/kiwi_v2/WCNSS_qcom_cfg.ini
