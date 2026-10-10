# -*- coding: utf-8 -*-
"""config-doctor-mcp 测试：协议 + 诊断逻辑，用临时目录模拟客户端配置"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config_doctor_mcp as cd  # noqa: E402


class ProtocolTest(unittest.TestCase):
    def setUp(self):
        self.sent = []
        self.server = cd.MCPServer("t", "1.0", cd.TOOLS)
        self.server._send = lambda m: self.sent.append(m)

    def _call(self, method, **kw):
        msg = {"jsonrpc": "2.0", "id": 1, "method": method}
        if kw:
            msg["params"] = kw
        self.server.handle(msg)
        return self.sent[-1]

    def test_initialize(self):
        self.assertEqual(self._call("initialize")["result"]["serverInfo"]["name"], "t")

    def test_tools_list(self):
        names = [t["name"] for t in self._call("tools/list")["result"]["tools"]]
        self.assertEqual(sorted(names), ["check_keys", "diagnose", "scan_clients", "v1_rule"])

    def test_ping(self):
        self.assertEqual(self._call("ping")["result"], {})

    def test_unknown_tool(self):
        self.assertEqual(self._call("tools/call", name="x", arguments={})["error"]["code"], -32602)


class AnalyzeTest(unittest.TestCase):
    def test_detects_v1_error_for_cherry(self):
        text = 'config: https://api.example.com/v1'
        issues = cd.analyze_text(text, "no")
        self.assertTrue(any("/v1" in i for i in issues))

    def test_no_v1_issue_when_correct(self):
        issues = cd.analyze_text("https://api.example.com", "no")
        self.assertFalse(any("/v1" in i for i in issues))

    def test_detects_missing_v1(self):
        issues = cd.analyze_text("base_url: https://api.example.com/", "yes")
        self.assertTrue(any("缺少 /v1" in i for i in issues))

    def test_ignores_official_openai_url(self):
        issues = cd.analyze_text("https://api.openai.com/v1", "yes")
        self.assertFalse(any("缺少 /v1" in i for i in issues))
        self.assertTrue(any("官方" in i for i in issues))

    def test_detects_plaintext_key(self):
        issues = cd.analyze_text('api_key = "sk-abcdefgh12345678"', "yes")
        self.assertTrue(any("明文密钥" in i for i in issues))

    def test_no_issues_on_clean_text(self):
        self.assertEqual(cd.analyze_text("", "yes"), [])

    def test_v1_text(self):
        self.assertIn("不要带", cd._v1_text("no"))
        self.assertIn("分开填", cd._v1_text("split"))
        self.assertIn("要带", cd._v1_text("yes"))


class DiagnoseTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self._orig = cd.CLIENTS
        self.config = self.root / "config.json"
        cd.CLIENTS = [{"id": "fake", "name": "假客户端", "v1_rule": "no",
                       "paths": [self.config], "note": "测试用"}]

    def tearDown(self):
        cd.CLIENTS = self._orig
        self.tmp.cleanup()

    def test_scan_not_installed(self):
        text = cd.tool_scan_clients({})
        self.assertIn("未找到配置", text)

    def test_diagnose_no_config(self):
        self.assertIn("未找到配置文件", cd.tool_diagnose({"client": "fake"}))

    def test_diagnose_with_bad_config(self):
        self.config.write_text('{"base_url": "https://api.example.com/v1", '
                               '"api_key": "sk-abcdefgh12345678"}', encoding="utf-8")
        text = cd.tool_diagnose({"client": "fake"})
        self.assertIn("发现的问题", text)
        self.assertIn("/v1", text)
        self.assertIn("明文密钥", text)

    def test_diagnose_unknown_client(self):
        text = cd.tool_diagnose({"client": "zzz"})
        self.assertIn("未知客户端", text)

    def test_diagnose_without_client_arg(self):
        self.assertIn("请指定", cd.tool_diagnose({}))

    def test_check_keys_reports(self):
        self.config.write_text('key = "sk-abcdefgh12345678"', encoding="utf-8")
        text = cd.tool_check_keys({})
        self.assertIn("假客户端", text)
        self.assertIn("轮换", text)

    def test_check_keys_clean(self):
        self.config.write_text("nothing here", encoding="utf-8")
        self.assertIn("未在常见客户端", cd.tool_check_keys({}))

    def test_v1_rule_list(self):
        self.assertIn("假客户端", cd.tool_v1_rule({}))
        self.assertIn("不要带", cd.tool_v1_rule({"client": "fake"}))
        self.assertIn("未知客户端", cd.tool_v1_rule({"client": "zzz"}))

    def test_scan_installed(self):
        self.config.write_text("x", encoding="utf-8")
        text = cd.tool_scan_clients({})
        self.assertIn("假客户端", text)
        self.assertIn("1 / 1", text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
