# houji 真机测试记录

目标机型：Xiaomi 14（houji）。当前无真机测试结果，不能标记为稳定版。

| 系统 | 启动 | 显示/触摸 | ADB/MTP | 动态分区 | 无密码解密 | PIN/密码解密 |
| --- | --- | --- | --- | --- | --- | --- |
| Android 17 AOSP / LineageOS 24 | 未验证 | 未验证 | 未验证 | 未验证 | 未验证 | 未验证 |
| Android 16 AOSP / HyperOS | 未验证 | 未验证 | 未验证 | 未验证 | 未验证 | 未验证 |
| Android 15 AOSP / HyperOS | 未验证 | 未验证 | 未验证 | 未验证 | 未验证 | 未验证 |
| Android 14 AOSP / HyperOS | 未验证 | 未验证 | 未验证 | 未验证 | 未验证 | 未验证 |

每次记录完整 ROM 版本、vendor/firmware 版本、安全补丁日期、当前槽位和镜像 SHA256。

## 测试顺序

1. 先保存当前 ROM 对应的原厂 recovery 镜像及重要数据备份，核对下载镜像的 SHA256。
2. 确认设备 bootloader 已解锁，且设备确为 houji；本构建输出的是 recovery 镜像。
   本树配置 `BOARD_EXCLUDE_KERNEL_FROM_RECOVERY_IMAGE := true`，镜像没有内核，
   不提供未经验证的 `fastboot boot` 操作。
3. 在明确设备分区布局和可恢复路径后再做手动安装测试；CI 不执行刷写。
4. 进入 recovery 后先验证 LVGL 显示、亮度、触摸、ADB 与重启；再只读查看分区。
5. 检查 `/data/media/0` 的真实文件是否可读取，分别测试无锁屏和 PIN/密码情形。
   显示容量或“解密完成”提示本身不足以证明解密成功。
6. 优先验证备份的读取与生成，确认可靠后才测试安装/还原操作。

解密失败时不要通过格式化 data 来冒充修复。保留并提交 recovery 日志后分析。

## 收集日志

在电脑上使用 Android platform-tools（以下均为读取/复制操作）：

```sh
adb pull /tmp/recovery.log
adb shell getprop > recovery-properties.txt
adb shell cat /proc/mounts > recovery-mounts.txt
adb shell dmesg > recovery-dmesg.txt
```

分享日志前检查是否含个人信息。记录故障步骤、密码类型（不记录密码内容）、
是否能正常返回原系统，以及是否涉及触摸或 vendor 模块加载失败。
