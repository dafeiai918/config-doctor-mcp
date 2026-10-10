#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""config-doctor-mcp · 本机 AI 客户端配置诊断 MCP
扫描本机客户端配置：找到了吗 / 配的哪个地址 / /v1 对不对 / 有没有明文密钥风险
零依赖 stdio MCP 服务器
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

__version__ = "1.0.0"
PROTOCOL_VERSION = "2025-06-18"

KEY_PATTERN = re.compile(r"\b(sk-[A-Za-z0-9_\-]{8,}|github_pat_[A-Za-z0-9_]{20,}|ghp_[A-Za-z0-9]{20,})")


# ================= MCP 内核 =================

class MCPServer:
    def __init__(self, name: str, version: str, tools: list):
        self.name, self.version, self.tools = name, version, tools

    def _send(self, msg: dict) -> None:
        sys.stdout.write(json.dumps(msg, ensure_ascii=False) + "\n")
        sys.stdout.flush()

    def _result(self, id_, result) -> None:
        self._send({"jsonrpc": "2.0", "id": id_, "result": result})

    def _error(self, id_, code: int, message: str) -> None:
        self._send({"jsonrpc": "2.0", "id": id_, "error": {"code": code, "message": message}})

    def handle(self, msg: dict) -> None:
        if not isinstance(msg, dict):
            return
        method, id_ = msg.get("method"), msg.get("id")
        if method == "initialize":
            self._result(id_, {"protocolVersion": PROTOCOL_VERSION,
                               "capabilities": {"tools": {"listChanged": False}},
                               "serverInfo": {"name": self.name, "version": self.version}})
        elif method in ("notifications/initialized", "initialized", "notifications/cancelled"):
            return
        elif method == "ping":
            self._result(id_, {})
        elif method == "tools/list":
            self._result(id_, {"tools": [
                {"name": t["name"], "description": t["description"],
                 "inputSchema": t.get("inputSchema") or {"type": "object", "properties": {}}}
                for t in self.tools]})
        elif method == "tools/call":
            params = msg.get("params") or {}
            tool = next((t for t in self.tools if t["name"] == params.get("name")), None)
            if tool is None:
                self._error(id_, -32602, f"未知工具: {params.get('name')}")
                return
            try:
                out = tool["handler"](params.get("arguments") or {})
                self._result(id_, {"content": [{"type": "text", "text": str(out)}], "isError": False})
            except Exception as exc:
                self._result(id_, {"content": [{"type": "text",
                                                "text": f"错误: {type(exc).__name__}: {exc}"}],
                                   "isError": True})
        elif id_ is not None:
            self._error(id_, -32601, f"不支持的方法: {method}")

    def serve(self) -> None:
        for raw in sys.stdin:
            raw = raw.strip()
            if not raw:
                continue
            try:
                msg = json.loads(raw)
            except Exception:
                continue
            for item in (msg if isinstance(msg, list) else [msg]):
                self.handle(item)


# ================= 客户端清单 =================

HOME = Path.home()
APPDATA = Path(os.environ.get("APPDATA", HOME / "AppData/Roaming"))
LOCALAPPDATA = Path(os.environ.get("LOCALAPPDATA", HOME / "AppData/Local"))

CLIENTS = [
    {"id": "cherry", "name": "Cherry Studio", "v1_rule": "no",
     "paths": [APPDATA / "CherryStudio" / "Data" / "cherrystudio.sqlite"],
     "note": "配置在 SQLite 里，需用工具查看"},
    {"id": "nextchat", "name": "NextChat", "v1_rule": "yes",
     "paths": [APPDATA / "NextChat", LOCALAPPDATA / "NextChat"],
     "note": "自定义接口三字段"},
    {"id": "chatbox", "name": "Chatbox", "v1_rule": "split",
     "paths": [APPDATA / "xyz.chatboxapp.app", APPDATA / "Chatbox",
               LOCALAPPDATA / "Programs" / "Chatbox"],
     "note": "域名与路径分开填"},
    {"id": "codex", "name": "ChatGPT 桌面版 / Codex", "v1_rule": "yes",
     "paths": [HOME / ".codex" / "config.toml", HOME / ".codex" / "auth.json"],
     "note": "改 config.toml 不要整体覆盖"},
    {"id": "continue", "name": "Continue (VSCode)", "v1_rule": "yes",
     "paths": [HOME / ".continue" / "config.json", HOME / ".continue" / "config.yaml"],
     "note": "models 数组里配 apiBase"},
    {"id": "aider", "name": "Aider", "v1_rule": "yes",
     "paths": [HOME / ".aider.conf.yml", HOME / ".aider.env", Path.cwd() / ".env"],
     "note": "OPENAI_API_BASE 环境变量"},
    {"id": "lobe", "name": "LobeChat", "v1_rule": "yes",
     "paths": [Path.cwd() / ".env", Path.cwd() / ".env.local"],
     "note": "OPENAI_PROXY_URL"},
    {"id": "openwebui", "name": "Open WebUI", "v1_rule": "yes",
     "paths": [Path.cwd() / ".env", HOME / ".open-webui"],
     "note": "OPENAI_API_BASE_URL"},
    {"id": "vscode", "name": "VS Code (Cline 等)", "v1_rule": "yes",
     "paths": [APPDATA / "Code" / "User" / "settings.json"],
     "note": "cline.openAiBaseUrl"},
]


def scan_client(client: dict) -> dict:
    found = []
    for path in client["paths"]:
        try:
            if path.exists():
                size = path.stat().st_size if path.is_file() else 0
                found.append({"path": str(path), "is_file": path.is_file(), "size": size})
        except Exception:
            continue
    return {**client, "found": found, "installed": bool(found)}


def read_text_safe(path: Path, limit: int = 200_000) -> str:
    try:
        if path.is_file() and path.stat().st_size <= limit:
            return path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        pass
    return ""


def analyze_text(text: str, v1_rule: str) -> list[str]:
    issues = []
    if not text:
        return issues
    urls = re.findall(r"https?://[^\s\"'`,)]+", text)
    api_urls = [u for u in urls if "/v1" in u or "api" in u.lower()]
    if api_urls:
        if v1_rule == "no":
            bad = [u for u in api_urls if u.rstrip("/").endswith("/v1")]
            if bad:
                issues.append(f"地址带了 /v1，该客户端不能带：{bad[0]}")
        elif v1_rule == "yes":
            none_v1 = [u for u in api_urls if "/v1" not in u and "openai.com" not in u]
            if none_v1:
                issues.append(f"地址似乎缺少 /v1：{none_v1[0]}")
    keys = KEY_PATTERN.findall(text)
    if keys:
        issues.append(f"发现 {len(keys)} 处明文密钥（注意不要提交到公开仓库）")
    if "api.openai.com" in text:
        issues.append("仍指向官方 api.openai.com，未配置中转站")
    return issues


def inspect_client(client_id: str) -> dict:
    client = next((c for c in CLIENTS if c["id"] == client_id), None)
    if client is None:
        return {"error": f"未知客户端 {client_id}"}
    scanned = scan_client(client)
    issues: list[str] = []
    for item in scanned["found"]:
        if item["is_file"]:
            issues += analyze_text(read_text_safe(Path(item["path"])), client["v1_rule"])
    return {**scanned, "issues": issues}


# ================= 工具 =================

def tool_scan_clients(args: dict) -> str:
    lines = ["本机 AI 客户端扫描结果：", ""]
    installed = 0
    for client in CLIENTS:
        scanned = scan_client(client)
        if scanned["installed"]:
            installed += 1
            lines.append(f"✓ {scanned['name']}")
            for item in scanned["found"]:
                lines.append(f"    {item['path']}")
        else:
            lines.append(f"✗ {scanned['name']}  (未找到配置)")
    lines += ["", f"共发现 {installed} / {len(CLIENTS)} 个客户端的配置。",
              "想细看某个用 diagnose，查密钥风险用 check_keys。"]
    return "\n".join(lines)


def tool_diagnose(args: dict) -> str:
    client_id = (args.get("client") or "").strip().lower()
    if not client_id:
        return ("请指定 client。可选：" + ", ".join(c["id"] for c in CLIENTS))
    result = inspect_client(client_id)
    if "error" in result:
        return result["error"] + "。可选：" + ", ".join(c["id"] for c in CLIENTS)
    lines = [f"【{result['name']}】诊断结果", f"地址规则：{_v1_text(result['v1_rule'])}", ""]
    if not result["installed"]:
        lines += ["未找到配置文件。可能：", "- 客户端未安装",
                  "- 首次运行后才会生成配置",
                  "- 配置在数据库里（如 Cherry Studio 用 SQLite）"]
        return "\n".join(lines)
    lines.append("找到的配置文件：")
    for item in result["found"]:
        lines.append(f"  - {item['path']}  ({item['size']} 字节)")
    lines.append("")
    if result["issues"]:
        lines.append("发现的问题：")
        for issue in result["issues"]:
            lines.append(f"  ⚠ {issue}")
    else:
        lines.append("未发现明显问题（仅检查了文本型配置文件）。")
    lines += ["", f"提示：{result['note']}"]
    return "\n".join(lines)


def tool_check_keys(args: dict) -> str:
    hits = []
    for client in CLIENTS:
        for path in client["paths"]:
            if not path.is_file():
                continue
            text = read_text_safe(path)
            keys = KEY_PATTERN.findall(text)
            if keys:
                hits.append((client["name"], str(path), len(keys)))
    if not hits:
        return "未在常见客户端配置文件里发现明文 API 密钥。\n（注意：Cherry Studio 等用数据库存储的未做检查）"
    lines = ["发现明文密钥的位置：", ""]
    for name, path, count in hits:
        lines.append(f"- {name}：{count} 处  {path}")
    lines += ["", "建议：",
              "1. 这些文件不要提交到公开仓库（检查 .gitignore）",
              "2. 密钥若曾进过 git 历史，应视为已泄露，去站点后台轮换",
              "3. 想让密钥不出本机，可用 relay-proxy 做本地代理"]
    return "\n".join(lines)


def tool_v1_rule(args: dict) -> str:
    client_id = (args.get("client") or "").strip().lower()
    if client_id:
        client = next((c for c in CLIENTS if c["id"] == client_id), None)
        if not client:
            return f"未知客户端。可选：{', '.join(c['id'] for c in CLIENTS)}"
        return f"{client['name']}：{_v1_text(client['v1_rule'])}"
    lines = ["各客户端对 /v1 的要求：", ""]
    for client in CLIENTS:
        lines.append(f"- {client['id']:<10} {client['name']:<22} {_v1_text(client['v1_rule'])}")
    return "\n".join(lines)


def _v1_text(rule: str) -> str:
    if rule == "no":
        return "地址不要带 /v1"
    if rule == "split":
        return "域名和路径分开填"
    return "地址要带 /v1"


TOOLS = [
    {"name": "scan_clients",
     "description": "扫描本机安装了哪些 AI 客户端、配置文件在哪。"
                    "用户问「我电脑上装了哪些 AI 客户端」「配置在哪」时使用。",
     "inputSchema": {"type": "object", "properties": {}},
     "handler": tool_scan_clients},
    {"name": "diagnose",
     "description": "诊断某个客户端的配置：地址对不对、/v1 有没有错、是否还指向官方。"
                    "用户说「我的客户端配置有问题」「帮我看看配置」时使用。",
     "inputSchema": {"type": "object", "properties": {
         "client": {"type": "string", "description": "客户端 id，如 cherry / chatbox / codex"}},
         "required": ["client"]},
     "handler": tool_diagnose},
    {"name": "check_keys",
     "description": "检查本机配置文件里的明文 API 密钥，给出安全建议。"
                    "用户问「我的密钥安全吗」「会不会泄露」时使用。",
     "inputSchema": {"type": "object", "properties": {}},
     "handler": tool_check_keys},
    {"name": "v1_rule",
     "description": "查各客户端地址要不要带 /v1。不传 client 则列出全部。",
     "inputSchema": {"type": "object", "properties": {
         "client": {"type": "string"}}},
     "handler": tool_v1_rule},
]


def main() -> int:
    if os.name == "nt":
        try:
            sys.stdin.reconfigure(encoding="utf-8")
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass
    MCPServer("config-doctor-mcp", __version__, TOOLS).serve()
    return 0


if __name__ == "__main__":
    sys.exit(main())
