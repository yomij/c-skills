#!/usr/bin/env bash

set -euo pipefail

# 这个脚本用于创建可复用的多账号 Codex 根目录。
# 对外只暴露一个入口命令：codex-with <名称>。

usage() {
  cat <<'EOF'
用法：
  scaffold_root.sh ROOT [--append-zshrc] account:login_mode [account:login_mode ...]

登录方式：
  api       账号通过 OPENAI_API_KEY_<ACCOUNT_NAME> 和 codex login --with-api-key 登录
  official  账号使用标准 codex login 登录

示例：
  scaffold_root.sh /Users/name/Desktop/codex-accounts --append-zshrc \
    packycode:api codexzh:api Official:official
EOF
}

if [[ $# -lt 2 ]]; then
  usage >&2
  exit 1
fi

ROOT="$1"
shift

APPEND_ZSHRC=0
if [[ "${1:-}" == "--append-zshrc" ]]; then
  APPEND_ZSHRC=1
  shift
fi

if [[ $# -lt 1 ]]; then
  usage >&2
  exit 1
fi

mkdir -p "$ROOT/bin"
ACCOUNTS_FILE="$ROOT/accounts.tsv"
: > "$ACCOUNTS_FILE"

write_placeholder_config() {
  local config_path="$1"

  if [[ -e "$config_path" ]]; then
    return
  fi

  cat > "$config_path" <<'EOF'
# 请把这个占位配置替换为真实的账号级 Codex 配置。
# 脚手架默认只放占位内容，因为 provider URL、模型和 MCP 设置都属于
# 用户自己的决策，不应该在未确认时被静默猜测。
disable_response_storage = true
personality = "pragmatic"
EOF
}

write_codex_with_script() {
  cat > "$ROOT/bin/codex-with" <<'EOF'
#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(cd -- "$SCRIPT_DIR/.." && pwd)"
ACCOUNTS_FILE="$BASE_DIR/accounts.tsv"

usage() {
  cat <<'USAGE'
用法：
  codex-with <名称> [codex 参数...]
  codex-with <名称> -login [codex login 参数...]
  codex-with <名称> -status
  codex-with <名称> -logout
  codex-with <名称> -app [codex app 参数...]
  codex-with -list
  codex-with -help

说明：
  <名称> 必须存在于 accounts.tsv 中。
  默认行为是用指定账号启动 codex，并自动切换到对应的 CODEX_HOME。
USAGE
}

list_accounts() {
  if [[ ! -f "$ACCOUNTS_FILE" ]]; then
    echo "未找到账号清单: $ACCOUNTS_FILE" >&2
    exit 1
  fi

  awk -F'\t' 'NF >= 2 { printf "%-24s %s\n", $1, $2 }' "$ACCOUNTS_FILE"
}

resolve_login_mode() {
  local account="$1"
  awk -F'\t' -v account="$account" '
    $1 == account { print $2; found = 1; exit }
    END { exit(found ? 0 : 1) }
  ' "$ACCOUNTS_FILE"
}

if [[ $# -lt 1 ]]; then
  usage >&2
  exit 1
fi

case "$1" in
  -help)
    usage
    exit 0
    ;;
  -list)
    list_accounts
    exit 0
    ;;
esac

ACCOUNT="$1"
shift

if ! LOGIN_MODE="$(resolve_login_mode "$ACCOUNT")"; then
  echo "未知账号: $ACCOUNT" >&2
  echo "可用账号请执行: codex-with -list" >&2
  exit 1
fi

export CODEX_HOME="$BASE_DIR/$ACCOUNT"

if [[ ! -f "$CODEX_HOME/config.toml" ]]; then
  echo "缺少配置文件: $CODEX_HOME/config.toml" >&2
  exit 1
fi

ACTION="run"
if [[ $# -gt 0 ]]; then
  case "$1" in
    -login)
      ACTION="login"
      shift
      ;;
    -status)
      ACTION="status"
      shift
      ;;
    -logout)
      ACTION="logout"
      shift
      ;;
    -app)
      ACTION="app"
      shift
      ;;
    -help)
      usage
      exit 0
      ;;
  esac
fi

case "$ACTION" in
  run)
    exec codex "$@"
    ;;
  login)
    if [[ "$LOGIN_MODE" == "api" ]]; then
      SAFE_ACCOUNT="$(printf '%s' "$ACCOUNT" | tr '[:lower:]' '[:upper:]' | tr -c 'A-Z0-9' '_')"
      KEY_VAR="OPENAI_API_KEY_${SAFE_ACCOUNT}"
      KEY_VALUE="${!KEY_VAR:-}"

      if [[ -z "$KEY_VALUE" ]]; then
        echo "环境变量 $KEY_VAR 为空或未设置。" >&2
        echo "请先 export $KEY_VAR，然后重新执行此命令。" >&2
        exit 1
      fi

      printf '%s\n' "$KEY_VALUE" | codex login --with-api-key "$@"
      exit $?
    fi

    exec codex login "$@"
    ;;
  status)
    exec codex login status
    ;;
  logout)
    exec codex logout
    ;;
  app)
    exec codex app "$@"
    ;;
esac
EOF
}

write_zsh_loader() {
  cat > "$ROOT/codex-with.zsh" <<EOF
# 由 codex-account-config scaffold_root.sh 生成
export CODEX_ACCOUNTS_ROOT="$ROOT"

codex-with() {
  "\$CODEX_ACCOUNTS_ROOT/bin/codex-with" "\$@"
}
EOF
}

append_zshrc_if_needed() {
  local zshrc_path="$HOME/.zshrc"
  local source_line="source $ROOT/codex-with.zsh"

  if [[ ! -e "$zshrc_path" ]]; then
    printf '# Codex 单命令入口\n%s\n' "$source_line" >> "$zshrc_path"
    return
  fi

  if grep -Fqx "$source_line" "$zshrc_path"; then
    return
  fi

  printf '\n# Codex 单命令入口\n%s\n' "$source_line" >> "$zshrc_path"
}

for spec in "$@"; do
  if [[ "$spec" != *:* ]]; then
    echo "无效的账号定义: $spec" >&2
    echo "期望格式: account:login_mode" >&2
    exit 1
  fi

  account="${spec%%:*}"
  login_mode="${spec##*:}"

  if [[ -z "$account" ]]; then
    echo "账号名不能为空。" >&2
    exit 1
  fi

  if [[ "$login_mode" != "api" && "$login_mode" != "official" ]]; then
    echo "账号 $account 的登录方式不受支持: $login_mode" >&2
    exit 1
  fi

  mkdir -p "$ROOT/$account"
  printf '%s\t%s\n' "$account" "$login_mode" >> "$ACCOUNTS_FILE"
  write_placeholder_config "$ROOT/$account/config.toml"
done

write_codex_with_script
chmod +x "$ROOT/bin/codex-with"
write_zsh_loader

if [[ "$APPEND_ZSHRC" -eq 1 ]]; then
  append_zshrc_if_needed
fi
