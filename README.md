# c-skills

这个目录用于集中发布可复用的 Codex skills。

## 目录约定

- `skills/<skill-name>/SKILL.md`：每个 skill 的入口文件，必须存在。
- `skills/<skill-name>/agents/openai.yaml`：可选的 UI 元数据。
- `skills/<skill-name>/scripts/`：可选的脚本资源。
- `skills/<skill-name>/references/`：可选的参考资料。
- `skills/<skill-name>/assets/`：可选的静态资源。

## 推荐发布方式

1. 将单个 skill 放在 `skills/<skill-name>/` 下。
2. 提交到 Git 仓库并推送到 GitHub。
3. 将 skill 目录 URL 发给使用者安装。

## 使用者安装示例

将下面命令中的仓库地址和路径替换为实际值：

```bash
python3 ~/.codex/skills/.system/skill-installer/scripts/install-skill-from-github.py \
  --repo your-org/c-skills \
  --path skills/your-skill
```

或者：

```bash
python3 ~/.codex/skills/.system/skill-installer/scripts/install-skill-from-github.py \
  --url https://github.com/your-org/c-skills/tree/main/skills/your-skill
```

安装完成后需要重启 Codex。
