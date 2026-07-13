# CodeDesk

CodeDesk 是一个独立开源的远程工作台，面向“通过手机或另一台 Windows/macOS 设备控制主要开发机”的场景。它以完整的通用远程桌面为基础，后续逐步增加针对 Codex、Claude Code、ZCode 及普通 Shell 的 AI coding 工作流。

> CodeDesk 基于开源的 [RustDesk](https://github.com/rustdesk/rustdesk) 客户端和 [RustDesk Server OSS](https://github.com/rustdesk/rustdesk-server) 二次开发。CodeDesk 与 RustDesk 官方及其商业主体不存在隶属、背书或官方合作关系。

[English](../README.md) · [开发路线](ROADMAP.md) · [架构说明](ARCHITECTURE.md) · [构建指南](BUILDING.md)

## 当前状态

项目目前处于独立开发基线阶段。

当前已经具备的能力来自已整合的成熟远控栈：

- 跨平台远程桌面与输入控制
- 文件传输与剪贴板同步
- TCP 端口转发
- 持久化远程终端
- 可自托管的 ID/注册、打洞与中继服务（`hbbs`、`hbbr`）

以下能力属于规划，不代表当前已经实现：

- 面向手机的多行 Prompt、中文输入、快捷键、语音输入和断线恢复优化
- 聚合终端、桌面、文件与服务预览的 Coding Workspace
- Codex、Claude Code、ZCode 与普通 Shell 的可配置启动项
- 经用户授权的 Git 状态、diff、测试命令与本地开发服务预览
- 在开发机本地运行的 AI 任务状态与审批适配器

详细边界和阶段请看[开发路线](ROADMAP.md)。CodeDesk Server 不会发展成模型代理；AI API Key、源码和终端内容不应发送给注册/中继服务器。

## 仓库结构

```text
.
├── src/                 # Rust 客户端与远控服务
├── flutter/             # 当前桌面端和移动端 UI
├── libs/hbb_common/     # 客户端、服务端唯一共享的协议/配置库
├── libs/scrap/          # 屏幕采集
├── libs/enigo/          # 输入控制
├── libs/clipboard/      # 剪贴板
└── server/              # hbbs、hbbr 与服务端工具
```

客户端和服务端共享普通目录 `libs/hbb_common`，不再使用子仓库。两者暂时保留独立 Cargo workspace 和独立 lockfile。本仓库不建立 RustDesk 上游同步任务，也不依赖仓库外文件。

## 构建

所有标准命令都从仓库根目录执行：

```bash
cargo test -p hbb_common --locked
cargo build --locked
DATABASE_URL=sqlite://./db_v2.sqlite3 \
  cargo build --manifest-path server/Cargo.toml --locked --release --bins
```

客户端还需要相应平台的原生库和 Flutter 环境。完整说明见[构建指南](BUILDING.md)。

## 当前服务器策略

为了先验证仓库整合和行为基线，当前开发阶段暂时不改变原有服务器连接行为。任何 CodeDesk 公共二进制发布前，都必须提供自托管服务器配置引导，并移除对 RustDesk 公共注册服务器、更新接口和隐私链接的默认依赖。当前开发配置不应直接视为生产发布配置。

## 参与和许可

请阅读[贡献指南](../CONTRIBUTING.md)、[安全策略](../SECURITY.md)和[行为准则](../CODE_OF_CONDUCT.md)。贡献需要 DCO sign-off。

CodeDesk 按 GNU AGPL-3.0 发布。原有代码版权归原作者所有，CodeDesk 新增和修改代码归属 CodeDesk Contributors。派生关系和第三方来源见 [NOTICE](../NOTICE)。
