# Cloudflare Browser Rendering 凭据获取

`cf-browser-render` 需要两个值：

| 变量 | 是什么 | 是否敏感 |
|---|---|---|
| `CF_BROWSER_RENDERING_TOKEN` | Cloudflare API Token | **是**，等同于密码 |
| `CF_ACCOUNT_ID` | Cloudflare Account ID | 否，但建议和 Token 一起放 `.env` |

---

## 第一步：登录 Cloudflare

打开 <https://dash.cloudflare.com/> 并登录你的账号。

> Browser Rendering 的可用性、免费额度和计费方式可能随套餐变化；
> 如果控制台没有该功能，先确认账号套餐或在 Dashboard 中启用。

---

## 网络与代理要求（重要）

`api.cloudflare.com` 在部分网络环境（尤其中国大陆、受限出口 IP）可能**超时、连接重置或被限制**。
即使浏览器能打开 Dashboard，脚本访问 API 仍可能需要代理 IP。

### 在 `.env` 中配置

```dotenv
# Clash/V2Ray 等客户端的本地 HTTP 混合端口
HTTPS_PROXY=http://127.0.0.1:7890
# 可选
HTTP_PROXY=http://127.0.0.1:7890
NO_PROXY=localhost,127.0.0.1
```

### 或命令行指定

```bash
python skills/cf-browser-render/scripts/fetch_markdown.py \
  --proxy http://127.0.0.1:7890 "https://example.com"
```

### 注意事项

- 只支持 **HTTP/HTTPS 代理**。SOCKS5 请先在代理客户端开启本地 HTTP 混合端口
  （例如 Clash 的 mixed-port），再把该端口填进 `HTTPS_PROXY`。
- 代理要能访问 `https://api.cloudflare.com`；有些代理只放行网页、不放行 API。
- 如果持续出现 **403 / 1020**，尝试更换出口 IP；Cloudflare 可能限制数据中心、
  共享或被滥用的代理 IP。
- 使用可信代理。API 走 HTTPS，Token 不会明文传输，但不可信代理若安装根证书仍可能
  解密流量。
- GitHub 技能用 `GITHUB_PROXY`，Cloudflare 用 `HTTPS_PROXY`，两者互不影响。

### 测试代理是否通

bash / macOS / Linux：

```bash
curl -x http://127.0.0.1:7890 -I https://api.cloudflare.com/client/v4/
```

PowerShell：

```powershell
curl.exe -x http://127.0.0.1:7890 -I https://api.cloudflare.com/client/v4/
```

只要不是超时/连接重置，就说明网络层已经通了；返回 200/401/403 都属于 Cloudflare
已经收到请求。再把 Token 和 Account ID 配好即可。

---

## 第二步：找到 Account ID

两种方式任选：

1. Dashboard 首页右侧栏 → **Account ID** → 复制
2. 看浏览器地址栏：`https://dash.cloudflare.com/<account-id>`，中间那段就是 Account ID

Account ID 是 32 位十六进制字符串。

---

## 第三步：创建 API Token

1. 右上角头像 → **My Profile**
2. 左侧 **API Tokens** → **Create Token**
3. 选择 **Create Custom Token**（不要用模板里权限过大的默认项）
4. 填写：
   - **Token name**：`llm-wiki-skills-browser-rendering`
   - **Permissions**：
     - `Account` → `Browser Rendering` → `Edit`
   - **Account Resources**：
     - `Include` → 选择你的账号
   - **TTL**（可选）：按需设置过期时间
5. **Continue to summary** → **Create Token**
6. **立即复制 Token**：页面只显示一次，关闭后无法再次查看

> 如果找不到 `Browser Rendering` 权限，通常是该账号尚未启用 Browser Rendering，
> 或当前套餐不包含该能力；请先在 Dashboard 中确认。

---

## 第四步：写入 `.env`

在仓库根、技能根目录或技能目录创建 `.env`：

```dotenv
CF_BROWSER_RENDERING_TOKEN=<your-cloudflare-token>
CF_ACCOUNT_ID=<your-cloudflare-account-id>
```

`.env` 已被 `.gitignore` 忽略。**不要把真实 Token 写进 README、脚本或提交记录。**

如果你只想给 `cf-browser-render` 一个技能使用，把 `.env` 放在：

```text
~/.claude/skills/cf-browser-render/.env
# 或
~/.dsh/skills/cf-browser-render/.env
```

---

## 第五步：验证

### 方式一：直接运行技能

```bash
python skills/cf-browser-render/scripts/fetch_markdown.py "https://example.com"
```

返回 Markdown 即成功。

### 方式二：curl 直接验证

bash / macOS / Linux：

```bash
curl -sS -X POST \
  "https://api.cloudflare.com/client/v4/accounts/$CF_ACCOUNT_ID/browser-rendering/markdown" \
  -H "Authorization: Bearer $CF_BROWSER_RENDERING_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"url":"https://example.com"}'
```

PowerShell：

```powershell
$body = @{ url = "https://example.com" } | ConvertTo-Json
Invoke-RestMethod -Method Post `
  -Uri "https://api.cloudflare.com/client/v4/accounts/$env:CF_ACCOUNT_ID/browser-rendering/markdown" `
  -Headers @{ Authorization = "Bearer $env:CF_BROWSER_RENDERING_TOKEN" } `
  -ContentType "application/json" `
  -Body $body
```

成功响应中 `"success": true`，正文在 `result` 字段。

> 如果变量只写在 `.env` 里，bash/PowerShell 不会自动加载它。
> 最省事的方式是直接用技能脚本；手动 curl 前可先
> `set -a; source .env; set +a`（bash），或在 PowerShell 中手动设置环境变量。

---

## Token 权限说明

| 权限 | 是否必需 | 说明 |
|---|---|---|
| `Account > Browser Rendering > Edit` | 是 | 调用 `/browser-rendering/markdown` |
| 其它 Account 权限 | 否 | 不要勾选，遵循最小权限 |
| Zone 权限 | 否 | 本技能不需要 |

---

## 常见错误

| 状态 | 可能原因 | 处理 |
|---|---|---|
| `401` | Token 错误、过期、已被删除，或复制时少了字符 | 重新创建 Token，确认完整复制 |
| `403` | Token 缺少 Browser Rendering Edit；账号未启用/套餐不支持；Account ID 不匹配；出口 IP 被限制 | 先检查权限、账号资源和 Account ID；权限无误时更换代理 IP |
| `403 / 1020` | Cloudflare 判定当前出口 IP 风险较高（数据中心/共享代理等） | 更换干净的代理 IP，避免使用被滥用的公共节点 |
| `429` | 配额或速率限制 | 等待后重试；降低并发；查看 Dashboard 配额 |
| 请求超时 / 连接重置 | 本机无法直连 Cloudflare（国内网络常见） | 在 `.env` 设置 `HTTPS_PROXY`，或用 `--proxy`；确认代理能访问 `api.cloudflare.com` |
| `success: false` | URL 不可访问、目标站点拦截、页面需要登录 | 换一个公开可访问的 URL 验证 |

---

## 安全建议

- 只创建**一个专用 Token**，不要复用其它项目的 Token
- 设置过期时间，到期前轮换
- 不要把 Token 发到 Issue、聊天、截图或日志里
- 怀疑泄露：立即在 Cloudflare Dashboard 删除该 Token，重新创建
- Token 只能放在 `.env` 或系统环境变量中，**永远不要硬编码**

---

## 官方文档

- Browser Rendering 概览：<https://developers.cloudflare.com/browser-rendering/>
- Browser Rendering REST API：<https://developers.cloudflare.com/browser-rendering/rest-api/>
- 创建 API Token：<https://developers.cloudflare.com/fundamentals/api/get-started/create-token/>

> 控制台界面、权限名称和配额可能随 Cloudflare 更新而变化；以官方文档和 Dashboard 为准。
