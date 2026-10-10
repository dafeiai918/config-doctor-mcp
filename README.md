# config-doctor-mcp · 客户端配置诊断 MCP

**让 AI 直接说：「你的 Cherry Studio 地址多了个 /v1，所以连不上。」**

零依赖 · 单文件 · stdio MCP 服务器 · 只读安全 · 中文

---

## 它让 AI 能做什么

> 「我电脑上装了哪些 AI 客户端？配置在哪？」
> → AI 调用 `scan_clients`，扫描常见客户端配置路径

> 「帮我看看 Cherry Studio 的配置有没有问题」
> → AI 调用 `diagnose`，检查地址格式、`/v1` 规则、是否还指向官方

> 「我的密钥会不会泄露？」
> → AI 调用 `check_keys`，找出明文密钥位置并给安全建议

> 「Chatbox 的地址要不要带 /v1？」
> → AI 调用 `v1_rule`，直接给答案

---

## 提供的工具

| 工具 | 作用 | 是否联网 |
|---|---|---|
| `scan_clients` | 扫描本机客户端配置位置 | 否 |
| `diagnose` | 诊断指定客户端的配置问题 | 否 |
| `check_keys` | 找明文密钥 + 安全建议 | 否 |
| `v1_rule` | 查 `/v1` 规则（单个或全部） | 否 |

**全部只读**，不修改任何文件，不联网。

---

## 诊断什么

| 检查项 | 说明 |
|---|---|
| 配置文件是否存在 | 找不到时给出可能原因 |
| 地址是否带错 `/v1` | 按客户端各自的规则判断 |
| 是否仍指向 `api.openai.com` | 提示未配置中转站 |
| 是否含明文密钥 | 提示 git 泄露风险 + 轮换建议 |

支持的客户端配置位置：Cherry Studio、NextChat、Chatbox、Codex CLI、Continue、Aider、LobeChat、Open WebUI、VS Code（Cline 等）。

---

## 安装

```json
{
  "mcpServers": {
    "config-doctor-mcp": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/dafeiai918/config-doctor-mcp", "config-doctor-mcp"]
    }
  }
}
```

或本地文件（零依赖，Python 3.9+）：

```json
{
  "mcpServers": {
    "config-doctor-mcp": {
      "command": "python",
      "args": ["/绝对路径/config-doctor-mcp/config_doctor_mcp.py"]
    }
  }
}
```

---

## 常见问题对照

| 现象 | 真实原因 | 本工具怎么帮你 |
|---|---|---|
| 404 Not Found | 地址多了或少了 `/v1` | `diagnose` 指出具体哪个客户端错了 |
| 401 Unauthorized | 密钥错误/过期 | `check_keys` 确认配置里到底填了什么 |
| 连不上但配置看着对 | 地址指向官方 API | `diagnose` 提示「仍指向 api.openai.com」 |

---

## 安全

- 只读：不写文件、不改配置
- 不联网：密钥不会离开你的机器
- 报告里密钥一律打码

---

## 相关项目

| 项目 | 用途 |
|---|---|
| [llm-config-mcp](https://github.com/dafeiai918/llm-config-mcp) | 生成正确的客户端配置 |
| [relay-converter](https://github.com/dafeiai918/relay-converter) | 命令行版配置转换器 |
| [OneClickRelay](https://github.com/dafeiai918/oneclickrelay) | 一键自动写入配置 |
| [key-watch](https://github.com/dafeiai918/key-watch) | 多站余额监控 |

---

## License

MIT
