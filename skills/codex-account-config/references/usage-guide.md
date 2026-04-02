# 详细使用说明

这份文档面向实际执行场景，说明在 skill 完成配置后，用户应该如何理解目录结构、完成登录、启动账号，以及如何验证配置是否生效。

平台约定：
- macOS / Linux：默认 shell 是 `zsh`，入口文件是 `codex-with.zsh`
- Windows：默认 shell 是 PowerShell，入口文件是 `codex-with.ps1`
- 当前 Windows 支持只面向 PowerShell，不面向 `cmd.exe`

## 1. 会生成什么

完成配置后，通常会得到一个多账号根目录，例如：

```text
/Users/name/Desktop/codex-accounts/
├── packycode/
│   └── config.toml
├── codexzh/
│   └── config.toml
├── Official/
│   └── config.toml
├── bin/
│   └── codex-with
├── accounts.tsv
└── codex-with.zsh
```

各文件职责：
- `<root>/<account>/config.toml`：该账号独立使用的 Codex 配置文件。
- `<root>/bin/codex-with`：实际执行入口，负责切换 `CODEX_HOME` 并转发到 `codex`。
- `<root>/accounts.tsv`：记录账号名和登录方式，例如 `api` 或 `official`。
- `<root>/codex-with.zsh`：macOS / Linux 的 shell 入口文件。
- `<root>/codex-with.ps1`：Windows PowerShell 的入口文件。

## 2. 只保留一个公开命令

配置完成后，用户只需要记住一套命令：

```text
codex-with -help
codex-with -list
codex-with <名称>
codex-with <名称> -login
codex-with <名称> -status
codex-with <名称> -logout
codex-with <名称> -app
```

说明：
- 参数风格统一为单破折号，不兼容 `--help`、`--list` 之类别名。
- 默认动作是 `codex-with <名称>`，也就是切换到该账号的 `CODEX_HOME` 后直接启动 `codex`。
- `-app` 会转发到 `codex app`。
- `-status` 会转发到 `codex login status`。

## 3. 手动配置流程

### 第一步：确认根目录

先和用户确认导出根目录，例如：

```text
/Users/name/Desktop/codex-accounts
```

Windows 示例：

```text
C:\Users\name\Desktop\codex-accounts
```

这个目录会存放：
- 各账号独立 `config.toml`
- 账号切换脚本
- shell 入口文件

### 第二步：确认账号和登录方式

至少确认：
- 有哪些账号
- 每个账号叫什么名字
- 每个账号是 `api` 还是 `official`

规则：
- `api`：该账号后续使用 `codex login --with-api-key`
- `official`：该账号后续使用正常 `codex login`

例如：

```text
packycode:api
codexzh:api
Official:official
```

### 第三步：生成骨架

macOS / Linux：

```bash
bash ~/.codex/skills/codex-account-config/scripts/scaffold_root.sh \
  /Users/name/Desktop/codex-accounts \
  --append-zshrc \
  packycode:api \
  codexzh:api \
  Official:official
```

说明：
- `--append-zshrc` 表示如有需要，把 `source <root>/codex-with.zsh` 追加到 `~/.zshrc`。
- 如果选择“是，写入 shell profile”，以后新开终端就能直接执行 `codex-with`。
- 如果选择“否，不写入 shell profile”，以后需要先执行 `source <root>/codex-with.zsh`。

Windows PowerShell：

```powershell
powershell -ExecutionPolicy Bypass -File `
  $HOME\.codex\skills\codex-account-config\scripts\scaffold_root.ps1 `
  C:\Users\name\Desktop\codex-accounts `
  -AppendPowerShellProfile `
  packycode:api codexzh:api Official:official
```

说明：
- `-AppendPowerShellProfile` 表示如有需要，把 `. "<root>\codex-with.ps1"` 追加到 PowerShell profile。
- 如果选择“是，写入 shell profile”，以后新开 PowerShell 就能直接执行 `codex-with`。
- 如果选择“否，不写入 shell profile”，以后需要先执行 `. <root>\codex-with.ps1`。

### 第四步：写入每个账号的 `config.toml`

脚手架只会先创建占位文件。之后需要根据用户要求，把真实配置写入：

- `packycode/config.toml`
- `codexzh/config.toml`
- `Official/config.toml`

写入原则：
- 不覆盖用户明确不希望改动的现有配置。
- 保持 provider 和登录方式一致。
- 手动配置时，不要擅自猜测用户的 MCP 或 provider 参数。

## 4. 从 `cc-switch` 导入流程

### 第一步：先确认是否导入

固定确认话术：

```text
检测到你安装了 cc-switch，是否直接从其中导入 Codex 配置？
```

如果用户拒绝：
- 立即转入手动配置流程。

这一步只问“是否导入”，不要把下面这些问题提前混进来：
- 根目录
- provider 范围
- 是否导入 MCP 配置
- 是否写入 shell profile

### 第二步：确认导入范围

用户同意导入后，必须继续确认：
- 根目录是什么
- 导入全部 provider，还是部分 provider
- 是否一并导入 MCP 配置
- 是否把 shell 入口追加到 shell profile

正确做法是：
- 先读取 `cc-switch` 中可用的 provider
- 然后直接把列表列出来，让用户按“全部”或编号选择

### 第三步：先列出可导入 provider

macOS / Linux：

```bash
python3 ~/.codex/skills/codex-account-config/scripts/import_cc_switch_codex.py \
  --list
```

Windows PowerShell：

```powershell
python $HOME\.codex\skills\codex-account-config\scripts\import_cc_switch_codex.py `
  --platform windows `
  --list
```

推荐提问方式：

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
   说明：`是` 表示把入口文件写入 shell profile。以后新开终端即可直接执行 `codex-with`。
   说明：`否` 表示不修改 shell profile。你之后需要手动执行 `source <root>/codex-with.zsh`，或在 PowerShell 里执行 `. <root>\codex-with.ps1`。
```

### 第四步：执行导入

导入全部：

macOS / Linux：

```bash
python3 ~/.codex/skills/codex-account-config/scripts/import_cc_switch_codex.py \
  --root /Users/name/Desktop/codex-accounts \
  --append-shell-profile
```

只导入部分：

```bash
python3 ~/.codex/skills/codex-account-config/scripts/import_cc_switch_codex.py \
  --root /Users/name/Desktop/codex-accounts \
  --provider packycode \
  --provider codexzh \
  --provider Official
```

Windows PowerShell：

```powershell
python $HOME\.codex\skills\codex-account-config\scripts\import_cc_switch_codex.py `
  --platform windows `
  --root C:\Users\name\Desktop\codex-accounts `
  --append-shell-profile
```

只导入部分：

```powershell
python $HOME\.codex\skills\codex-account-config\scripts\import_cc_switch_codex.py `
  --platform windows `
  --root C:\Users\name\Desktop\codex-accounts `
  --provider packycode `
  --provider codexzh
```

### 第五步：说明导入行为

导入脚本会：
- 从 `~/.cc-switch/cc-switch.db` 读取 Codex provider
- 自动推断每个 provider 的登录方式
- 使用 `common_config_codex` 作为补全基线
- 生成多账号目录与 shell 入口
- 写出账号级 `config.toml`

不会做的事：
- 不会自动把数据库里的敏感认证信息直接回显给用户
- 不会在用户未确认前直接执行导入

## 5. 配置完成后的登录步骤

### API Key 账号

macOS / Linux：

先设置环境变量：

```zsh
export OPENAI_API_KEY_PACKYCODE="sk-..."
export OPENAI_API_KEY_CODEXZH="sk-..."
```

再登录：

```zsh
codex-with packycode -login
codex-with codexzh -login
```

Windows PowerShell：

```powershell
$env:OPENAI_API_KEY_PACKYCODE = "sk-..."
$env:OPENAI_API_KEY_CODEXZH = "sk-..."

codex-with packycode -login
codex-with codexzh -login
```

说明：
- `api` 账号在执行 `-login` 时，会读取 `OPENAI_API_KEY_<ACCOUNT_NAME>`。
- 账号名会先转成大写，再把非字母数字字符替换成下划线。
- 例如 `packycode` 对应 `OPENAI_API_KEY_PACKYCODE`。

### 官方账号

直接登录：

```zsh
codex-with Official -login
```

说明：
- API Key 登录并不意味着每次启动都要重新设置环境变量。
- 是否持久化取决于 Codex 的认证存储方式和当前环境。
- 但首次登录至少需要提供一次 API Key。

## 6. 日常使用步骤

### 第一步：加载入口文件

如果没有自动写入 `~/.zshrc`，先手工加载：

```zsh
source /Users/name/Desktop/codex-accounts/codex-with.zsh
```

如果已经写入 `~/.zshrc`：
- 新开一个终端即可使用。
- 或执行一次 `source ~/.zshrc`。

Windows PowerShell：

```powershell
. C:\Users\name\Desktop\codex-accounts\codex-with.ps1
```

如果已经写入 PowerShell profile：
- 新开一个 PowerShell 窗口即可使用。
- 或执行一次 `. $PROFILE`。

### 第二步：查看有哪些账号

```zsh
codex-with -list
```

### 第三步：启动指定账号的 CLI

```zsh
codex-with packycode
codex-with codexzh
codex-with Official
```

### 第四步：启动桌面版

```zsh
codex-with packycode -app
codex-with codexzh -app
codex-with Official -app
```

### 第五步：查看登录状态

```zsh
codex-with packycode -status
codex-with codexzh -status
codex-with Official -status
```

### 第六步：退出登录

```zsh
codex-with packycode -logout
codex-with codexzh -logout
codex-with Official -logout
```

### 第七步：查看帮助

```zsh
codex-with -help
```

## 7. 如何验证配置是否真正生效

推荐按这个顺序验证：

### 验证 1：入口是否可用

macOS / Linux：

```zsh
zsh -ic 'source ~/.zshrc && whence -f codex-with'
```

Windows PowerShell：

```powershell
powershell -NoProfile -Command ". $PROFILE; Get-Command codex-with"
```

### 验证 2：脚本语法是否正常

macOS / Linux：

```zsh
bash -n /Users/name/Desktop/codex-accounts/bin/codex-with
zsh -n /Users/name/Desktop/codex-accounts/codex-with.zsh
```

Windows：
- 这份 skill 当前没有内置 PowerShell 语法检查步骤。
- 实际验证以能否成功 dot-source `codex-with.ps1` 并执行 `codex-with -help` 为准。

### 验证 3：各账号是否命中各自环境

```zsh
codex-with packycode -status
codex-with codexzh -status
codex-with Official -status
```

如果返回 `Not logged in`：
- 说明命令已经命中对应账号目录
- 只是尚未完成登录

### 验证 4：`config.toml` 是否可读

如果本机可用 `taplo`：

```zsh
npx -y @taplo/cli check /Users/name/Desktop/codex-accounts/*/config.toml
```

如果 npm 源异常：
- 可以跳过这一步
- 优先以实际运行 `codex-with <名称> -status` 是否正常为准

## 8. `~/.codex` 会不会冲突

默认不会冲突，前提是使用生成后的 `codex-with` 命令。

原因：
- `codex-with <名称>` 会先设置 `CODEX_HOME`
- 一旦设置了 `CODEX_HOME`，Codex 就会从对应目录读取配置和登录态
- 只有裸命令 `codex` 才会继续使用默认的 `~/.codex`

可以把它理解为：
- 多账号根目录负责“显式切换账号”
- `~/.codex` 保留为默认环境

## 9. 常见问题

### 为什么不直接用 `profile`

因为 `profile` 只切配置值，不适合做账号级隔离。它不能稳定隔离：
- 登录态
- 历史记录
- 缓存
- MCP 配置

### 为什么导入 `cc-switch` 前还要多次确认

因为导入动作会涉及：
- 目标根目录
- 导出哪些账号
- 是否同步 MCP 配置
- 是否修改 shell profile

这些都属于用户应明确确认的范围，不能静默默认。

### 如果用户拒绝从 `cc-switch` 导入怎么办

不要停下来，继续手动配置：
- 询问根目录
- 询问账号和登录方式
- 协助写 `config.toml`
- 协助完成 shell 入口和验证

### 如果 `config.toml` 已经存在怎么办

默认不要覆盖。

只有在用户明确要求覆盖时，才允许替换现有文件。

### Windows 现在能不能直接用

现在可以，但前提是：
- 使用 PowerShell
- 使用 `scaffold_root.ps1`
- 或者在导入模式下给 `import_cc_switch_codex.py` 传 `--platform windows`

当前不支持：
- `cmd.exe` 下的同等入口体验
- 自动生成 `.bat` 或 `.cmd` 包装脚本

## 10. 结构化提问示例

为了减少来回确认，推荐在提问时直接给用户固定回复格式。

### 场景 A：检测到 `cc-switch`

```text
检测到你安装了 cc-switch，是否直接从其中导入 Codex 配置？

说明：
- 是：下一步会列出可导入的 provider 清单，再让你确认根目录、导入范围、MCP 和 shell profile。
- 否：不会读取 cc-switch，改走手动配置流程，并继续协助你填写 config.toml。
```

### 场景 B：用户同意导入

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
   说明：`是` 表示以后新开终端即可直接执行 `codex-with`。
   说明：`否` 表示之后需要手动加载入口文件。
```

### 场景 C：用户拒绝导入，改手动配置

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
   说明：`是` 表示以后新开终端自动可用；`否` 表示之后需要手动加载入口文件。
4. 是否现在就写入每个账号的 config.toml：是 / 否
   说明：`是` 表示本次直接写入真实配置；`否` 表示只先生成目录和占位文件。
```
