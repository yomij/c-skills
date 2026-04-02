# 示例

如果需要完整的分步骤说明，请继续阅读 `usage-guide.md`。

## 三账号目录结构

使用一个统一根目录，并为每个账号建立独立子目录：

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

## 登录映射

- `packycode:api` -> `codex-with packycode -login`，读取 `OPENAI_API_KEY_PACKYCODE`
- `codexzh:api` -> `codex-with codexzh -login`，读取 `OPENAI_API_KEY_CODEXZH`
- `Official:official` -> `codex-with Official -login`，执行标准 `codex login`

## 常见后续命令

macOS / Linux：

```zsh
source /Users/name/Desktop/codex-accounts/codex-with.zsh

export OPENAI_API_KEY_PACKYCODE="sk-..."
export OPENAI_API_KEY_CODEXZH="sk-..."

codex-with -list
codex-with packycode -login
codex-with codexzh -login
codex-with Official -login

codex-with packycode
codex-with codexzh
codex-with Official

codex-with packycode -status
codex-with Official -app
codex-with -help
```

Windows PowerShell：

```powershell
. C:\Users\name\Desktop\codex-accounts\codex-with.ps1

$env:OPENAI_API_KEY_PACKYCODE = "sk-..."
$env:OPENAI_API_KEY_CODEXZH = "sk-..."

codex-with -list
codex-with packycode -login
codex-with codexzh -login
codex-with Official -login

codex-with packycode
codex-with codexzh
codex-with Official

codex-with packycode -status
codex-with Official -app
codex-with -help
```

## 从 cc-switch 导入

如果用户已经安装了 `cc-switch`，并且明确确认要导入，再读取它保存的 Codex 配置：

```bash
python3 ~/.codex/skills/codex-account-config/scripts/import_cc_switch_codex.py \
  --list

python3 ~/.codex/skills/codex-account-config/scripts/import_cc_switch_codex.py \
  --root /Users/name/Desktop/codex-accounts \
  --append-shell-profile
```

Windows PowerShell：

```powershell
python $HOME\.codex\skills\codex-account-config\scripts\import_cc_switch_codex.py `
  --platform windows `
  --root C:\Users\name\Desktop\codex-accounts `
  --append-shell-profile
```

如果只想导出部分 provider：

```bash
python3 ~/.codex/skills/codex-account-config/scripts/import_cc_switch_codex.py \
  --root /Users/name/Desktop/codex-accounts \
  --provider packycode \
  --provider codexzh \
  --provider Official
```

导入前应先和用户确认：
- 根目录是不是 `/Users/name/Desktop/codex-accounts`
- 是导入全部 provider，还是只导入指定 provider
- 是否连同 MCP 配置一起导入
- 是否把 shell 入口写入 shell profile

## 冲突说明

这些独立账号根目录不会替代默认的 `~/.codex`。

- `codex-with packycode` 会把对应账号目录作为 `CODEX_HOME`
- `codex-with codexzh` 使用它自己的 `CODEX_HOME`
- `codex-with Official` 使用它自己的 `CODEX_HOME`
- 裸命令 `codex` 仍然使用默认的 `~/.codex`
