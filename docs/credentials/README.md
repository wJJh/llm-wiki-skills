# 凭据获取指南

四个技能只使用两类凭据：

| 凭据 | 用于 | 必填 | 指南 |
|---|---|---|---|
| `CF_BROWSER_RENDERING_TOKEN` + `CF_ACCOUNT_ID` | `cf-browser-render` | 是 | [Cloudflare Browser Rendering](cloudflare-browser-rendering.md) |
| `GITHUB_TOKEN` | `github-stars-sync`、`github-stars-version-tracker`、`auto-github-star` | 是 | [GitHub Personal Access Token](github-token.md) |
| `GITHUB_USERNAME` | Stars 两个导出技能 | 否 | 留空自动调用 `GET /user` |
| `GITHUB_PROXY` / `HTTPS_PROXY` | 需要代理时 | 否 | 见下方“代理” |

所有凭据只应保存在本地 `.env` 或系统环境变量中：

- 不写入代码
- 不提交到 Git
- 不粘贴到公开 Issue / 聊天记录
- 不使用来源不明的 Token

---

## `.env` 放哪里

按优先级从高到低：

1. **系统环境变量**（最高；已设置的键不会被 `.env` 覆盖）
2. `--env-file /path/to/.env`
3. 技能目录 `.env`，如 `~/.claude/skills/cf-browser-render/.env`
4. 技能根目录 `.env`，如 `~/.claude/skills/.env`、`~/.dsh/skills/.env`
5. 仓库根 `.env`（clone 全量安装，最低）

技能**不会读取宿主项目的其它 `.env`**，避免串用别的项目凭据。
模板见仓库根 [`.env.example`](../../.env.example)。

### 最小配置示例

```dotenv
# Cloudflare（cf-browser-render）
CF_BROWSER_RENDERING_TOKEN=<your-cloudflare-token>
CF_ACCOUNT_ID=<your-cloudflare-account-id>

# GitHub（stars 三个技能）
GITHUB_TOKEN=<your-github-token>
# 留空自动调用 GET /user；不要填占位符
GITHUB_USERNAME=
```

---

## 代理

### Cloudflare：部分网络必须使用代理 IP

`api.cloudflare.com` 在部分网络环境（尤其中国大陆、受限出口 IP）可能**超时、连接重置或被限制**。
这种情况需要配置可用的 HTTP/HTTPS 代理，否则 `cf-browser-render` 无法稳定调用 API。

```dotenv
# Cloudflare（或其它 urllib 请求）
HTTPS_PROXY=http://127.0.0.1:7890
# 可选
HTTP_PROXY=http://127.0.0.1:7890
NO_PROXY=localhost,127.0.0.1
```

也可以只给单次命令指定：

```bash
python skills/cf-browser-render/scripts/fetch_markdown.py \
  --proxy http://127.0.0.1:7890 "https://example.com"
```

- 只支持 HTTP/HTTPS 代理；SOCKS5 请先在客户端开启本地 HTTP 混合端口。
- 持续 403/1020 时更换出口 IP；Cloudflare 可能限制数据中心或被滥用的代理 IP。
- 见 [Cloudflare 凭据指南的“网络与代理要求”](cloudflare-browser-rendering.md#网络与代理要求重要)。

### GitHub

```dotenv
GITHUB_PROXY=http://127.0.0.1:7890
```

`GITHUB_PROXY` 会被映射为当前进程的 `HTTP_PROXY/HTTPS_PROXY`；Cloudflare 直接用
`HTTPS_PROXY`。脚本只会在**当前进程**内使用代理，不会修改系统设置。

---

## 安全规则

1. **最小权限**：GitHub Token 只需 `public_repo`（或细粒度的 Starring/Contents 读取）；Cloudflare Token 只需 Browser Rendering Edit。
2. **设置过期时间**：GitHub Token 建议 90 天；Cloudflare Token 按需设置 TTL。
3. **定期轮换**：怀疑泄露时立即到控制台撤销并重新生成。
4. **不要用主账号的全局管理员 Token**。
5. **`.env` 已被 `.gitignore` 忽略**；手动上传 GitHub 时仍要确认没有把 `.env` 拖进去。
6. 如果凭据曾出现在截图、日志、聊天记录中，按已泄露处理。

---

## 验证凭据是否生效

### Cloudflare

```bash
python skills/cf-browser-render/scripts/fetch_markdown.py "https://example.com"
```

能返回 Markdown 即成功；401/403/429 的排查见
[Cloudflare 指南](cloudflare-browser-rendering.md#常见错误)。

### GitHub

```bash
python skills/github-stars-sync/scripts/fetch_stars.py --stdout --format stats
```

能输出语言统计即成功；401/403/404 的排查见
[GitHub 指南](github-token.md#常见错误)。

---

## 官方文档

- Cloudflare Browser Rendering：<https://developers.cloudflare.com/browser-rendering/>
- Cloudflare API Token：<https://developers.cloudflare.com/fundamentals/api/get-started/create-token/>
- GitHub Personal Access Token：<https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens>
- GitHub REST API 速率限制：<https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api>

> 各平台的配额、计费和界面可能变化；以控制台和官方文档为准。
