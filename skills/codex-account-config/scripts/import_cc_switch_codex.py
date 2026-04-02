#!/usr/bin/env python3

import argparse
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
from collections import OrderedDict
from pathlib import Path
from typing import Optional


def parse_args():
    parser = argparse.ArgumentParser(
        description="从 cc-switch 读取 Codex 配置，并导出为独立的多账号 Codex 根目录。"
    )
    parser.add_argument(
        "--db",
        default=str(Path.home() / ".cc-switch" / "cc-switch.db"),
        help="cc-switch SQLite 数据库路径，默认是 ~/.cc-switch/cc-switch.db",
    )
    parser.add_argument(
        "--root",
        help="导出的多账号根目录；如果只想查看 provider 列表，可以不传。",
    )
    parser.add_argument(
        "--provider",
        action="append",
        default=[],
        help="只导出指定 provider，可重复传入。支持 provider id、名称或推断后的账号名。",
    )
    parser.add_argument(
        "--append-shell-profile",
        action="store_true",
        help="导出后把对应 shell 的入口文件追加到 shell profile（如尚未存在）。",
    )
    parser.add_argument(
        "--append-zshrc",
        action="store_true",
        help="兼容旧参数：在 Unix/macOS 上追加到 ~/.zshrc。",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="覆盖已存在的账号级 config.toml。",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="只列出 cc-switch 中可用的 Codex provider，不写文件。",
    )
    parser.add_argument(
        "--platform",
        choices=["auto", "unix", "windows"],
        default="auto",
        help="选择导出目标平台。auto 会按当前操作系统判断。",
    )
    return parser.parse_args()


def slugify(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9]+", "-", value.strip()).strip("-")
    return cleaned.lower() or "account"


def infer_account_name(provider_name: str, category: str, config_text: str) -> str:
    match = re.search(r'^\s*model_provider\s*=\s*"([^"]+)"', config_text, re.MULTILINE)
    if match:
        return match.group(1)

    if category == "official":
        return "Official"

    return slugify(provider_name)


def infer_login_mode(category: str, auth: dict) -> str:
    if auth.get("OPENAI_API_KEY"):
        return "api"

    if category == "official" or auth.get("tokens"):
        return "official"

    return "official"


HEADER_RE = re.compile(r"^\s*(\[\[.*\]\]|\[.*\])\s*(?:#.*)?$")


def split_toml_blocks(text: str):
    root_lines = []
    blocks = []
    current_block = None

    for line in text.splitlines():
        match = HEADER_RE.match(line)
        if match:
            header = match.group(1).strip()
            if current_block:
                blocks.append(current_block)
            current_block = {
                "header": header,
                "kind": "array" if header.startswith("[[") else "table",
                "lines": [line],
            }
            continue

        if current_block:
            current_block["lines"].append(line)
        else:
            root_lines.append(line)

    if current_block:
        blocks.append(current_block)

    return root_lines, blocks


def merge_root_lines(base_lines, override_lines):
    merged = OrderedDict()

    def ingest(lines):
        for line in lines:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if "=" not in line:
                continue
            key = line.split("=", 1)[0].strip()
            merged[key] = line

    ingest(base_lines)
    ingest(override_lines)
    return list(merged.values())


def merge_table_blocks(base_blocks, override_blocks):
    order = []
    base_tables = {}
    override_tables = {}
    base_arrays = OrderedDict()
    override_arrays = OrderedDict()

    def remember(section):
        key = (section["kind"], section["header"])
        if key not in order:
            order.append(key)

    for section in base_blocks:
        remember(section)
        if section["kind"] == "array":
            base_arrays.setdefault(section["header"], []).append(section["lines"])
        else:
            base_tables[section["header"]] = section["lines"]

    for section in override_blocks:
        remember(section)
        if section["kind"] == "array":
            override_arrays.setdefault(section["header"], []).append(section["lines"])
        else:
            override_tables[section["header"]] = section["lines"]

    merged = []
    for kind, header in order:
        if kind == "array":
            selected = override_arrays.get(header, base_arrays.get(header, []))
            merged.extend(selected)
            continue

        selected = override_tables.get(header, base_tables.get(header))
        if selected:
            merged.append(selected)

    return merged


def compose_toml(root_lines, blocks):
    output = []

    if root_lines:
        output.extend(root_lines)

    for block in blocks:
        if output:
            output.append("")
        output.extend(block)

    return "\n".join(output).rstrip() + "\n"


def looks_like_complete_config(config_text: str) -> bool:
    if not config_text.strip():
        return False

    signals = 0
    if "[features]" in config_text:
        signals += 1
    if "[projects" in config_text:
        signals += 1
    if "[sandbox_workspace_write]" in config_text:
        signals += 1
    if config_text.count("[mcp_servers.") >= 3:
        signals += 1

    return signals >= 2


def merge_common_and_provider(common_text: str, provider_text: str) -> str:
    if not common_text.strip():
        return provider_text.rstrip() + "\n"

    if not provider_text.strip():
        return common_text.rstrip() + "\n"

    if looks_like_complete_config(provider_text):
        return provider_text.rstrip() + "\n"

    base_root, base_blocks = split_toml_blocks(common_text)
    override_root, override_blocks = split_toml_blocks(provider_text)
    merged_root = merge_root_lines(base_root, override_root)
    merged_blocks = merge_table_blocks(base_blocks, override_blocks)
    return compose_toml(merged_root, merged_blocks)


def load_common_config(conn) -> str:
    row = conn.execute(
        "select value from settings where key = 'common_config_codex'"
    ).fetchone()
    return row[0] if row and row[0] else ""


def load_providers(conn):
    rows = conn.execute(
        """
        select id, name, category, is_current, settings_config
        from providers
        where app_type = 'codex'
        order by is_current desc, id asc
        """
    ).fetchall()

    providers = []
    for provider_id, name, category, is_current, settings_config in rows:
        payload = json.loads(settings_config)
        config_text = payload.get("config") or ""
        auth = payload.get("auth") or {}
        providers.append(
            {
                "id": provider_id,
                "name": name,
                "category": category or "",
                "is_current": bool(is_current),
                "config_text": config_text,
                "auth": auth,
                "account_name": infer_account_name(name, category or "", config_text),
                "login_mode": infer_login_mode(category or "", auth),
            }
        )

    return providers


def filter_providers(providers, selected):
    if not selected:
        return providers

    wanted = {item.lower() for item in selected}
    result = []
    for provider in providers:
        keys = {
            provider["id"].lower(),
            provider["name"].lower(),
            provider["account_name"].lower(),
        }
        if keys & wanted:
            result.append(provider)
    return result


def resolve_platform(platform: str) -> str:
    if platform != "auto":
        return platform
    return "windows" if os.name == "nt" else "unix"


def find_powershell() -> Optional[str]:
    for candidate in ("pwsh", "powershell", "pwsh.exe", "powershell.exe"):
        found = shutil.which(candidate)
        if found:
            return found
    return None


def ensure_root_with_scaffold(root: Path, providers, append_shell_profile: bool, platform: str):
    if platform == "windows":
        scaffold_script = Path(__file__).with_name("scaffold_root.ps1")
        powershell = find_powershell()
        if not powershell:
            raise RuntimeError("未找到 PowerShell 可执行文件，无法在 Windows 模式下生成脚手架。")

        cmd = [
            powershell,
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(scaffold_script),
            str(root),
        ]

        if append_shell_profile:
            cmd.append("-AppendPowerShellProfile")

        cmd.extend(providers_to_specs(providers))
        subprocess.run(cmd, check=True)
        return

    scaffold_script = Path(__file__).with_name("scaffold_root.sh")
    cmd = ["bash", str(scaffold_script), str(root)]

    if append_shell_profile:
        cmd.append("--append-zshrc")

    for provider in providers:
        cmd.append(f"{provider['account_name']}:{provider['login_mode']}")

    subprocess.run(cmd, check=True)


def providers_to_specs(providers):
    return [f"{provider['account_name']}:{provider['login_mode']}" for provider in providers]


def write_provider_configs(root: Path, providers, common_config: str, force: bool):
    for provider in providers:
        target = root / provider["account_name"] / "config.toml"
        merged_config = merge_common_and_provider(common_config, provider["config_text"])

        if target.exists() and not force:
            existing = target.read_text(encoding="utf-8")
            if "请把这个占位配置替换为真实的账号级 Codex 配置。" not in existing and \
               "Replace this placeholder with the real account-specific Codex configuration." not in existing:
                continue

        target.write_text(merged_config, encoding="utf-8")


def print_provider_list(providers):
    for provider in providers:
        current = "当前" if provider["is_current"] else "备用"
        print(
            f"{provider['account_name']}\t{provider['login_mode']}\t{current}\t{provider['name']}"
        )


def main():
    args = parse_args()
    db_path = Path(args.db).expanduser()
    platform = resolve_platform(args.platform)
    append_shell_profile = args.append_shell_profile or args.append_zshrc

    if not db_path.exists():
        print(f"未找到 cc-switch 数据库: {db_path}", file=sys.stderr)
        return 1

    conn = sqlite3.connect(str(db_path))
    common_config = load_common_config(conn)
    providers = load_providers(conn)
    selected = filter_providers(providers, args.provider)

    if not selected:
        print("没有匹配到任何 Codex provider。", file=sys.stderr)
        return 1

    if args.list or not args.root:
        print_provider_list(selected)
        if not args.root:
            return 0

    root = Path(args.root).expanduser()
    ensure_root_with_scaffold(root, selected, append_shell_profile, platform)
    write_provider_configs(root, selected, common_config, args.force)
    print(f"已导出 {len(selected)} 个账号到: {root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
