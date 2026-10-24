# Xiaomi 14 (houji) — TWRP-Test LVGL recovery

基于本地 `OFRP-device_xiaomi_houji` 转换的实验性 recovery 设备树。
仅使用 GitHub Actions 云编译，不在本机同步完整 Android 源码或编译镜像。

## 机型与源码

| 项目 | 配置 |
| --- | --- |
| 设备 | Xiaomi 14 / houji，原设备树包含 houjiin 识别 |
| SoC | Qualcomm SM8650 |
| 编译目标 | `twrp_houji-bp2a-eng` / `recoveryimage` |
| 镜像 | 独立 `recovery.img`，100 MiB 分区上限 |
| UI | TWRP-Test 的 LVGL `gui2` |
| 构建底座 | Android 16，TWRP-Test `twrp-16.0` |
| 运行兼容目标 | Android 14–17；尚未完成真机兼容验证 |

截至 2026-10-24，上游 manifest 和 recovery 仓库实际没有 `main` 分支，
LVGL 已合并在 `twrp-16.0`。工作流固定 manifest 和 recovery 的提交，
同步完成后输出所有依赖的实际 revision 清单。

**Android 17 的 LineageOS `lineage-24.0` 完整 ROM 树不用于此构建。**
`lolipuru/device_xiaomi_sm8650-common` 与 `android_device_xiaomi_houji`
需要完整 ROM 的 HAL、sepolicy 和 vendor 依赖；此 recovery 树已自带所需的机型配置、
预编译内核和专用 ramdisk 文件。不能通过切换到 Lineage 24 的设备树，就获得 Android 17 通用解密。

## GitHub 云编译

1. 打开此仓库的 **Actions → Build houji LVGL recovery → Run workflow**。
2. 默认 4 个并行任务；内存不足时改为 2。
3. 成功后下载 `twrp-lvgl-houji-<运行序号>` artifact，内含 `.img`、
   `SHA256SUMS`、源码 revision 清单及测试说明。
4. 失败也会保留 `houji-build-logs-<运行序号>`，可据此修复后重新触发。

workflow 只手动触发，使用标准 GitHub hosted `ubuntu-22.04` runner，
不自动创建 Release，也不对连接的手机执行任何命令。
构建时清理、安装依赖和 swap 仅在一次性的云端 runner 执行。

本地仅做静态检查：

```sh
python3 scripts/validate.py
bash -n scripts/prepare-runner.sh scripts/sync.sh scripts/build.sh
```

## 已保留的 houji 配置

- boot header v4、GKI、A/B、Virtual A/B、独立 recovery 分区。
- 原设备树的预编译内核、ramdisk、触摸服务及 vendor 模块加载顺序。
- F2FS、FBE v2、metadata encryption，以及 EROFS/ext4 logical 分区配置。
- KeyMint、Gatekeeper、Weaver、OMAPI 所需的原树文件。

去除了 OrangeFox 的 makefile 和环境脚本，lunch 改为 Android 16 的三段目标。
没有用其他 SM8650 机型的分区大小或固件覆盖 houji 的配置。

## 兼容性与验证

编译成功仅代表源码和打包通过，不能证明可启动、触摸正常或能够解密 `/data`。
Android 17 与向下兼容必须逐个验证 ROM、vendor 固件和安全补丁组合。
本树保留的 prepdecrypt 脚本会读取当前系统的版本及补丁信息，
但这不能替代真实设备的 KeyMint/Weaver/metadata 解密测试。

详见 [测试记录与验证步骤](docs/TESTING.md)。LVGL 新 UI 属于上游实验功能，可能存在问题。

## 来源与致谢

- 设备树：[QCerberusQ/OFRP-device_xiaomi_houji](https://github.com/QCerberusQ/OFRP-device_xiaomi_houji)，
  `fox_14.1`，原始提交 `9f7455903b570814b2e0cdcdbe5328eaa55e9cf6`。
- manifest：[TWRP-Test/platform_manifest_twrp_aosp](https://github.com/TWRP-Test/platform_manifest_twrp_aosp/tree/twrp-16.0)，
  `814b553116ceedde197f70389cff9661d81d8337`。
- recovery：[TWRP-Test/android_bootable_recovery](https://github.com/TWRP-Test/android_bootable_recovery/tree/twrp-16.0)，
  `0a9962492fc48b9af32cc9943de8ee7105a82af3`。

保留原文件中的版权及许可证声明。原树中的厂商二进制文件沿用原始来源，
此适配不对这些文件重新授予许可证。
