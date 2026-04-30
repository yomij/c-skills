# Dual-Host Skill Install Design

## Goal

让本仓库的 skill 继续支持 Codex，同时新增对 Claude Code 的安装支持，并把 `generate-image` 迁入本仓库，保持单一 skill 源目录。

## Scope

- 仓库继续以 `skills/<skill-name>/` 作为唯一源目录。
- CLI 新增宿主选择能力，支持安装到 Codex 或 Claude Code 的全局/项目 skills 目录。
- 迁移 `skills/generate-image/` 及其脚本、测试、元数据。
- `generate-image` 不再把 `$CODEX_HOME` 作为唯一前提，而是支持双宿主默认路径和显式覆盖变量。
- README 补充 Claude Code 的安装说明与 `generate-image` 的双宿主配置说明。

## Non-Goals

- 不引入两套 skill 源目录。
- 不要求 Claude Code 提供 `CLAUDE_HOME` 环境变量。
- 不改变现有默认行为：未显式指定宿主时仍默认安装到 Codex。

## Install Model

CLI 增加 `--host codex|claude`，默认 `codex`。

路径规则：

- Codex 全局：`${CODEX_HOME:-$HOME/.codex}/skills`
- Codex 项目：`./.codex/skills`
- Claude 全局：`$HOME/.claude/skills`
- Claude 项目：`./.claude/skills`

`--dest` 仍优先级最高，并继续表示“直接安装到这个 skills 根目录”，不再和具体宿主路径解析耦合。

## Generate-Image Path Model

`generate-image` 的 Python 脚本采用下面的配置解析优先级：

1. CLI `--config`
2. 环境变量 `GENERATE_IMAGE_CONFIG`
3. 环境变量 `GENERATE_IMAGE_HOME` 推导出的 `<home>/config.json`
4. 从脚本安装位置反推宿主根目录后，使用默认配置路径
5. 兜底到 `~/.codex/generate-image/config.json`

宿主默认配置路径：

- Codex：`${CODEX_HOME:-$HOME/.codex}/generate-image/config.json`
- Claude：`$HOME/.claude/generate-image/config.json`

脚本需要能够从安装位置识别：

- `<host-root>/skills/generate-image/scripts/generate_image.py`

其中 `<host-root>` 可能是：

- `~/.codex`
- `$CODEX_HOME`
- `~/.claude`
- 项目级 `.codex`
- 项目级 `.claude`

## Documentation Model

- README 增加 `--host claude` 的安装示例。
- `generate-image/SKILL.md` 中不再把 `$CODEX_HOME` 写成唯一固定路径。
- 文档明确给出双宿主默认路径与覆盖变量：
  - `GENERATE_IMAGE_HOME`
  - `GENERATE_IMAGE_CONFIG`

## Testing

- Node 测试覆盖：
  - `parseInstallArgs` 正确解析 `--host`
  - `resolveTargetRoot` 对 Codex/Claude 的全局与项目路径解析
  - 默认宿主仍为 Codex
- Python 测试覆盖：
  - 脚本默认配置路径支持 Codex 与 Claude 安装位置
  - `GENERATE_IMAGE_HOME` 与 `GENERATE_IMAGE_CONFIG` 优先级
  - `SKILL.md` 中的路径说明不再只绑定 Codex

## Risks

- `generate-image` 现有测试大量绑定 `$CODEX_HOME` 文案，需要同步更新断言。
- Claude Code 官方只明确 `.claude` 目录约定，没有 `CLAUDE_HOME` 变量，因此实现必须依赖目录推断而不是新造宿主变量。
