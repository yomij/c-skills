---
name: "codex-account-config"
description: "当需要配置多个 Codex 账号、隔离 `CODEX_HOME` 目录、自定义 `config.toml` 或 provider、混用 API Key 与官方账号登录、或在 macOS/Linux/Windows 上创建账号切换 shell 入口时使用。"
metadata:
  short-description: "配置隔离的多账号 Codex 环境"
---

# Codex 账号配置

## 适用场景
- 用户希望把多个 Codex 账号按 `config.toml`、登录态、历史记录、缓存或 MCP 配置彻底分开。
- 用户同时存在多种登录方式，例如自定义 provider 走 API Key，官方账号走正常登录。
- 用户想要可复用的 shell 命令，例如 `codex-packycode` 或 `codex-official`。
- 用户不确定 `profile`、项目级 `.codex/config.toml`、`CODEX_HOME` 和 `~/.codex` 之间是否会冲突。
- 用户已经安装了 `cc-switch`，希望直接复用其中保存的 Codex provider 与 MCP 配置。

## 核心规则
每个账号使用一个独立的 `CODEX_HOME` 目录。不要用 `profile` 做账号隔离。

`profile` 只能切换配置值，不能可靠隔离登录态、历史记录、缓存、MCP 设置以及账号级本地状态。

## 平台说明
- macOS / Linux：使用 `bash` 脚手架和 `zsh` 入口文件。
- Windows：使用 PowerShell 脚手架和 `.ps1` 入口文件。
- 当前 skill 的 Windows 支持面向 PowerShell，不面向 `cmd.exe`。

## 工作流程
1. 先检查用户是否安装了 `cc-switch`。
   - 如果存在 `~/.cc-switch/cc-switch.db`，只把它作为可选配置来源告知用户。
   - 未经用户确认，不要直接读取 `cc-switch` 数据库。
   - 检测到 `cc-switch` 时，优先使用这句固定确认话术：
     - `检测到你安装了 cc-switch，是否直接从其中导入 Codex 配置？`
    - 只有在用户明确表示“从 cc-switch 导入”后，才读取：
     - 读取可用 provider 列表
     - 在后续确认消息里，直接把 provider 列表列给用户选择，不要要求用户凭记忆手填
     - 先确认导出根目录，例如 `/Users/name/Desktop/codex-accounts`
     - 再确认要导入哪些内容，至少包括：
       - 要导入哪些 provider/账号
       - 是否导入对应的 MCP 配置
       - 是否把 shell 入口追加到 `~/.zshrc`
     - 如果用户只接受部分导入，只导出用户确认的那部分配置
     - 在根目录和导入范围未确认前，不要执行导入脚本
     - `providers` 中 `app_type='codex'` 的 provider 配置
     - `provider_endpoints` 中对应 provider 的 endpoint
     - `settings` 中的 `common_config_codex`
     - `mcp_servers` 中 `enabled_codex=1` 的 MCP 配置
   - 如果用户明确拒绝从 `cc-switch` 导入，则立刻转入手动配置流程，继续询问并协助写入各账号的 `config.toml`。
2. 确认隔离根目录，例如 `/Users/name/Desktop/codex-accounts`。
3. 如果没有 `cc-switch`，或用户拒绝从 `cc-switch` 导入，再收集账号名和登录方式。
   - 对必须使用 `codex login --with-api-key` 的账号，使用 `api`。
   - 对应该使用正常 Codex 账号登录的账号，使用 `official`。
4. 使用以下两种方式之一生成根目录骨架：
   - 普通模式：
     - macOS / Linux：`scripts/scaffold_root.sh`
     - Windows：`scripts/scaffold_root.ps1`
   - `cc-switch` 导入模式：`scripts/import_cc_switch_codex.py`
5. 按用户要求精确写入每个账号的 `config.toml`。保留用户指定的 provider 配置和密钥放置方式。
6. 如果用户希望自动加载 shell 入口，仅在 `~/.zshrc` 中尚未存在时追加 `source <root>/codex-accounts.zsh`。
7. 验证：
   - `zsh -n <root>/bin/* <root>/codex-accounts.zsh`
   - `npx -y @taplo/cli check <root>/*/config.toml`
   - `zsh -ic 'source ~/.zshrc && whence -f codex-<name>'`
   - `codex-status-<name>` 应显示登录状态或 `Not logged in`

## 脚本用法
使用内置脚本创建目录结构和 shell 包装命令。

macOS / Linux：

```bash
bash ~/.codex/skills/codex-account-config/scripts/scaffold_root.sh \
  /Users/name/Desktop/codex-accounts \
  --append-zshrc \
  packycode:api \
  codexzh:api \
  Official:official
```

脚本会创建：
- 如果缺失，则创建 `<root>/<account>/config.toml` 占位文件
- `<root>/bin/codex-account`
- `<root>/bin/codex-login`
- `<root>/bin/codex-status`
- `<root>/bin/codex-logout`
- `<root>/bin/codex-app`
- `<root>/codex-accounts.zsh`
- `<root>/accounts.tsv`

Windows PowerShell：

```powershell
powershell -ExecutionPolicy Bypass -File `
  $HOME\.codex\skills\codex-account-config\scripts\scaffold_root.ps1 `
  C:\Users\name\Desktop\codex-accounts `
  -AppendPowerShellProfile `
  packycode:api codexzh:api Official:official
```

Windows 会创建：
- 如果缺失，则创建 `<root>\<account>\config.toml` 占位文件
- `<root>\bin\codex-account.ps1`
- `<root>\bin\codex-login.ps1`
- `<root>\bin\codex-status.ps1`
- `<root>\bin\codex-logout.ps1`
- `<root>\bin\codex-app.ps1`
- `<root>\codex-accounts.ps1`
- `<root>\accounts.tsv`

如果用户安装了 `cc-switch` 且明确确认要导入，再使用导入脚本：

```bash
python3 ~/.codex/skills/codex-account-config/scripts/import_cc_switch_codex.py \
  --root /Users/name/Desktop/codex-accounts \
  --append-shell-profile
```

Windows 示例：

```powershell
python $HOME\.codex\skills\codex-account-config\scripts\import_cc_switch_codex.py `
  --platform windows `
  --root C:\Users\name\Desktop\codex-accounts `
  --append-shell-profile
```

导入脚本会：
- 从 `~/.cc-switch/cc-switch.db` 读取 Codex provider
- 自动推断每个 provider 的登录方式
- 复用 `common_config_codex` 作为差量配置的补全基线
- 调用 `scaffold_root.sh` 创建根目录和 shell 入口
- 为选中的 provider 写出账号级 `config.toml`

## 编辑规则
- 除非用户明确要求，否则不要覆盖已有 `config.toml`。
- provider 相关认证信息放在用户指定的位置。
  - 如果用户希望通过环境变量登录 API Key，使用 `OPENAI_API_KEY_<ACCOUNT_NAME>`。
  - 如果用户希望使用官方登录，则保持包装命令走标准 `codex login`。
- 除非用户明确要求，否则不要删除或重写默认的 `~/.codex` 配置。
- 即使检测到用户安装了 `cc-switch`，也必须先获得确认，再读取其中的数据库配置。
- 如果需要向用户确认，默认使用这句固定话术：
  - `检测到你安装了 cc-switch，是否直接从其中导入 Codex 配置？`
- 如果用户同意导入，也必须继续确认两件事后才能执行：
  - 导出根目录是什么
  - 要导入哪些 provider 和配置范围
- 如果用户拒绝导入，不要停止流程，应继续进行手动配置并协助用户补齐 `config.toml`。
- 如果配置来自 `cc-switch`，不要在回复里回显数据库中的 API Key、token 或其他敏感认证信息。
- 在需要时明确说明优先级：
  - CLI 参数优先级最高
  - 当前激活的 `CODEX_HOME` 决定账号根目录
  - 项目级 `.codex/config.toml` 仍可能覆盖该账号环境中的部分配置
  - 裸命令 `codex` 仍然使用默认的 `~/.codex`

## 提问模板
当需要向用户确认信息时，优先使用结构化提问，避免只问一句过于宽泛的话。

### 模板 1：检测到 `cc-switch`

```text
检测到你安装了 cc-switch，是否直接从其中导入 Codex 配置？
```

这一步只确认是否允许从 `cc-switch` 导入，不要在同一条消息里继续询问根目录、provider 范围或 MCP 选项。

如果用户回答“是”，下一步才读取 provider 列表，并继续用带选项的结构化提问，而不是直接要求用户自己填写 provider 名称。

### 模板 1.1：用户同意从 `cc-switch` 导入后，列出 provider 供选择

```text
可以，我先按你已安装的 cc-switch 配置来导入。

当前检测到这些 Codex provider：
1. packycode
2. codexzh
3. Official

请按这个格式回复：
1. 根目录：例如 /Users/name/Desktop/codex-accounts
   说明：决定配置文件、脚本和入口文件最终写到哪里。
2. 要导入的 provider：全部 / 1,2 / 2,3
   说明：`全部` 表示把当前列出的 provider 全部导入；写编号表示只导入选中的账号。
3. 是否导入 MCP 配置：是 / 否
   说明：`是` 表示把可用的 MCP 配置一起写入；`否` 表示只导入 provider 和基础 config。
4. 是否写入 shell profile：是 / 否
   说明：`是` 表示以后新开终端即可直接使用账号命令；`否` 表示保留手动加载方式。
   补充：macOS / Linux 写入的是 `~/.zshrc`；Windows 写入的是 PowerShell profile。
```

### 模板 2：用户拒绝 `cc-switch` 导入，转手动配置

```text
明白，改为手动配置。

请按这个格式回复：
1. 根目录：例如 /Users/name/Desktop/codex-accounts
   说明：决定多账号目录和入口文件放在哪里。
2. 账号列表：
   - packycode: api
   - codexzh: api
   - Official: official
   说明：`api` 表示后续用 API Key 登录；`official` 表示后续用官方账号登录。
3. 是否写入 shell profile：是 / 否
   说明：`是` 表示以后新开终端自动可用；`否` 表示你之后需要手动加载入口文件。
   补充：macOS / Linux 写入的是 `~/.zshrc`；Windows 写入的是 PowerShell profile。
4. 是否现在就写入每个账号的 config.toml：是 / 否
   说明：`是` 表示本次直接写入真实配置；`否` 表示只先生成目录和占位文件。
```

### 模板 3：用户只想导入部分 provider

```text
可以，只导入你指定的 provider。

请按这个格式回复：
1. 根目录：例如 /Users/name/Desktop/codex-accounts
   说明：决定导出的多账号目录位置。
2. provider 列表：
   - packycode
   - codexzh
3. 是否导入 MCP 配置：是 / 否
   说明：`是` 表示一起导入可用 MCP；`否` 表示只导入你选中的 provider。
4. 是否写入 shell profile：是 / 否
   说明：`是` 表示以后新开终端自动可用；`否` 表示保留手动加载方式。
   补充：macOS / Linux 写入的是 `~/.zshrc`；Windows 写入的是 PowerShell profile。
```

### 模板 4：用户只想手工写 `config.toml`

```text
可以，我按手工配置帮你写。

请按这个格式回复：
1. 根目录：例如 /Users/name/Desktop/codex-accounts
   说明：决定账号目录和入口文件写到哪里。
2. 账号名称：
   说明：会直接影响目录名和命令名，例如 `codex-packycode`。
3. 登录方式：api / official
   说明：`api` 表示后续用 API Key 登录；`official` 表示后续用官方账号登录。
4. 目标 config.toml 内容：可直接粘贴
   说明：如果没有完整内容，也可以先给 provider、model、MCP 这几项关键信息。
5. 是否还要生成 shell 入口：是 / 否
   说明：`是` 表示会同时生成账号切换命令；`否` 表示只写 `config.toml`。
```

## 参考资料
- 通用模板和命令示例见 `references/examples.md`。
- 分步骤的详细使用说明见 `references/usage-guide.md`。

## 期望输出
使用这个 skill 时，优先给出：
- 根目录路径
- 账号名称和登录方式
- 是否更新了 shell profile
- 用户下一步应执行的准确命令
