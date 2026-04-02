#!/usr/bin/env bash

set -euo pipefail

# 这个脚本用于创建可复用的多账号 Codex 根目录，目标是把最容易出错的部分
# 统一收口：独立的 CODEX_HOME 目录、一致的包装脚本，以及可选的 shell 注入。

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

write_script_codex_account() {
  cat > "$ROOT/bin/codex-account" <<'EOF'
#!/bin/zsh

set -euo pipefail

BASE_DIR="${0:A:h:h}"
ACCOUNTS_FILE="$BASE_DIR/accounts.tsv"

if [[ $# -lt 1 ]]; then
  echo "用法: $(basename "$0") <account> [codex args...]" >&2
  exit 1
fi

ACCOUNT="$1"
shift

if ! awk -F'\t' -v account="$ACCOUNT" '$1 == account { found = 1 } END { exit(found ? 0 : 1) }' "$ACCOUNTS_FILE"; then
  echo "未知账号: $ACCOUNT" >&2
  echo "可用账号请查看 $ACCOUNTS_FILE。" >&2
  exit 1
fi

export CODEX_HOME="$BASE_DIR/$ACCOUNT"

if [[ ! -f "$CODEX_HOME/config.toml" ]]; then
  echo "缺少配置文件: $CODEX_HOME/config.toml" >&2
  exit 1
fi

exec codex "$@"
EOF
}

write_script_codex_login() {
  cat > "$ROOT/bin/codex-login" <<'EOF'
#!/bin/zsh

set -euo pipefail

BASE_DIR="${0:A:h:h}"
ACCOUNTS_FILE="$BASE_DIR/accounts.tsv"

if [[ $# -lt 1 ]]; then
  echo "用法: $(basename "$0") <account> [codex login args...]" >&2
  exit 1
fi

ACCOUNT="$1"
shift

LOGIN_MODE="$(awk -F'\t' -v account="$ACCOUNT" '$1 == account { print $2 }' "$ACCOUNTS_FILE")"

if [[ -z "$LOGIN_MODE" ]]; then
  echo "未知账号: $ACCOUNT" >&2
  echo "可用账号请查看 $ACCOUNTS_FILE。" >&2
  exit 1
fi

export CODEX_HOME="$BASE_DIR/$ACCOUNT"

if [[ "$LOGIN_MODE" == "api" ]]; then
  SAFE_ACCOUNT="$(print -r -- "$ACCOUNT" | tr '[:lower:]' '[:upper:]' | tr -c 'A-Z0-9' '_')"
  KEY_VAR="OPENAI_API_KEY_${SAFE_ACCOUNT}"
  KEY_VALUE="${(P)KEY_VAR:-}"

  if [[ -z "$KEY_VALUE" ]]; then
    echo "环境变量 $KEY_VAR 为空或未设置。" >&2
    echo "请先 export $KEY_VAR，然后重新执行此命令。" >&2
    exit 1
  fi

  print -r -- "$KEY_VALUE" | codex login --with-api-key "$@"
  exit $?
fi

exec codex login "$@"
EOF
}

write_script_simple_passthrough() {
  local target_name="$1"
  local codex_subcommand="$2"

  cat > "$ROOT/bin/$target_name" <<EOF
#!/bin/zsh

set -euo pipefail

BASE_DIR="\${0:A:h:h}"
ACCOUNTS_FILE="\$BASE_DIR/accounts.tsv"

if [[ \$# -lt 1 ]]; then
  echo "用法: \$(basename "\$0") <account>${codex_subcommand:+ [args...]}" >&2
  exit 1
fi

ACCOUNT="\$1"
shift

if ! awk -F'\\t' -v account="\$ACCOUNT" '\$1 == account { found = 1 } END { exit(found ? 0 : 1) }' "\$ACCOUNTS_FILE"; then
  echo "未知账号: \$ACCOUNT" >&2
  echo "可用账号请查看 \$ACCOUNTS_FILE。" >&2
  exit 1
fi

export CODEX_HOME="\$BASE_DIR/\$ACCOUNT"

exec codex ${codex_subcommand} "\$@"
EOF
}

write_zsh_loader() {
  {
    echo '# 由 codex-account-config scaffold_root.sh 生成'
    echo "export CODEX_ACCOUNTS_ROOT=\"$ROOT\""
    echo

    while IFS=$'\t' read -r account login_mode; do
      if [[ -z "$account" || -z "$login_mode" ]]; then
        continue
      fi

      suffix="$(printf '%s' "$account" | tr '[:upper:]' '[:lower:]' | tr -cs '[:alnum:]' '-')"

      cat <<EOF
codex-$suffix() {
  "\$CODEX_ACCOUNTS_ROOT/bin/codex-account" "$account" "\$@"
}

codex-login-$suffix() {
  "\$CODEX_ACCOUNTS_ROOT/bin/codex-login" "$account" "\$@"
}

codex-status-$suffix() {
  "\$CODEX_ACCOUNTS_ROOT/bin/codex-status" "$account"
}

codex-logout-$suffix() {
  "\$CODEX_ACCOUNTS_ROOT/bin/codex-logout" "$account"
}

codex-app-$suffix() {
  "\$CODEX_ACCOUNTS_ROOT/bin/codex-app" "$account" "\$@"
}

EOF
    done < "$ACCOUNTS_FILE"
  } > "$ROOT/codex-accounts.zsh"
}

append_zshrc_if_needed() {
  local zshrc_path="$HOME/.zshrc"
  local source_line="source $ROOT/codex-accounts.zsh"

  if [[ ! -e "$zshrc_path" ]]; then
    printf '# Codex 多账号入口\n%s\n' "$source_line" >> "$zshrc_path"
    return
  fi

  if grep -Fqx "$source_line" "$zshrc_path"; then
    return
  fi

  printf '\n# Codex 多账号入口\n%s\n' "$source_line" >> "$zshrc_path"
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

write_script_codex_account
write_script_codex_login
write_script_simple_passthrough "codex-status" "login status"
write_script_simple_passthrough "codex-logout" "logout"
write_script_simple_passthrough "codex-app" "app"
write_zsh_loader

chmod +x \
  "$ROOT/bin/codex-account" \
  "$ROOT/bin/codex-login" \
  "$ROOT/bin/codex-status" \
  "$ROOT/bin/codex-logout" \
  "$ROOT/bin/codex-app"

if [[ "$APPEND_ZSHRC" -eq 1 ]]; then
  append_zshrc_if_needed
fi
