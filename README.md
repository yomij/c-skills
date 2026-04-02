# c-skills

这个仓库同时承担两件事：

1. 存放对外发布的 Codex skills，目录约定为 `skills/<skill-name>/`
2. 提供一个可发布到 npm 的 CLI，使使用者既可以安装 npm 包内置 skill，也可以从 GitHub 仓库拉取 skill

## 目录约定

- `skills/<skill-name>/SKILL.md`：每个 skill 的入口文件，必须存在
- `skills/<skill-name>/agents/openai.yaml`：可选的 UI 元数据
- `skills/<skill-name>/scripts/`：可选的脚本资源
- `skills/<skill-name>/references/`：可选的参考资料
- `skills/<skill-name>/assets/`：可选的静态资源

## 使用者安装

当前 CLI 支持两种安装来源：

- 包内置 skill：适合安装本项目已经随 npm 包一起发布的 skill
- GitHub 仓库 skill：适合安装仓库里后续新增、但还没重新发 npm 包的 skill

GitHub 模式通过 `git sparse-checkout` 拉取单个 skill 目录，因此使用者机器需要：

- `Node.js >= 18`
- `Git`
- 已安装 Codex

当前 CLI 支持三种安装目标：

- 全局安装：默认安装到 `CODEX_HOME/skills`，若未设置 `CODEX_HOME` 则为 `~/.codex/skills`
- 项目安装：安装到当前目录下的 `.codex/skills`
- 自定义目录：通过 `--dest <dir>` 显式指定

### 安装包内置 skill

查看当前 npm 包里自带了哪些 skill：

```bash
npx c-skills list
```

直接按名称安装：

```bash
npx c-skills codex-account-config
```

安装到当前项目：

```bash
npx c-skills codex-account-config --project
```

或者：

```bash
npx c-skills install codex-account-config
```

### 从 GitHub 安装 skill

```bash
npx c-skills your-org/c-skills skills/your-skill
```

或者直接传 GitHub URL：

```bash
npx c-skills https://github.com/your-org/c-skills/tree/main/skills/your-skill
```

也可以显式写成 `install` 子命令：

```bash
npx c-skills install --repo your-org/c-skills --path skills/your-skill --ref main
```

安装到当前项目：

```bash
npx c-skills install --repo your-org/c-skills --path skills/your-skill --ref main --project
```

安装完成后需要重启 Codex。

### Windows PowerShell

安装包内置 skill：

```powershell
npx c-skills codex-account-config
```

安装到当前项目：

```powershell
npx c-skills codex-account-config --project
```

从 GitHub 安装 skill：

```powershell
npx c-skills your-org/c-skills skills/your-skill
npx c-skills your-org/c-skills skills/your-skill --project
```

或者：

```powershell
npx c-skills https://github.com/your-org/c-skills/tree/main/skills/your-skill
```

## 发布这个 CLI

1. 将 skill 放到 `skills/<skill-name>/`
2. 推送仓库到 GitHub
3. 登录 npm
4. 发布包

```bash
npm publish --registry https://registry.npmjs.org
```

## 本地检查

```bash
node ./bin/c-skills.js --help
node ./bin/c-skills.js list
node ./bin/c-skills.js codex-account-config --dry-run
node ./bin/c-skills.js codex-account-config --project --dry-run
node ./bin/c-skills.js your-org/c-skills skills/your-skill --dry-run
```
