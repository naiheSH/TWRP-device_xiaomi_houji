#
# Copyright (C) 2024 The Android Open Source Project
#
# SPDX-License-Identifier: Apache-2.0
#

PRODUCT_MAKEFILES := \
    $(LOCAL_DIR)/twrp_houji.mk \
    $(LOCAL_DIR)/twrp_houji_wifi.mk

COMMON_LUNCH_CHOICES := \
    twrp_houji-bp2a-user \
    twrp_houji-bp2a-userdebug \
    twrp_houji-bp2a-eng \
    twrp_houji_wifi-bp2a-eng
