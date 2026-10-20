# cf-browser-render · 网页转 Markdown

> 用 Cloudflare Browser Rendering 把任意网页渲染成干净 Markdown。
> 微信公众号、SPA、文档站、GitHub 页面都能处理，且零第三方 Python 依赖。

[← 返回仓库](../../README.md) · [SKILL.md](SKILL.md)

---

## 为什么单独装它

- **真实浏览器渲染**：不是简单 HTTP 抓取，能拿到 JavaScript 渲染后的正文
- **零依赖**：只要 Python 3.10+，不需要 `pip install`
- **一条命令**：`python scripts/fetch_markdown.py <url> -o article.md`
- **Windows 友好**：自动 UTF-8，不踩 GBK 编码坑
- **本地 .env**：不需要配置全局环境变量

---

## 不止知识库

`cf-browser-render` 不是知识库专属工具。凡是“把网页变成 AI 能读的文本”的场景都能用：

| 场景 | 说明 |
|---|---|
| **微信公众号文章** | 公开可访问的文章 → 干净 Markdown，方便总结、归档、二次创作 |
| **GitHub 仓库主页** | README、Release、文档页 → Markdown，方便让 AI 对比仓库、写调研报告 |
| **技术博客 / 官方文档** | 保留标题、列表、表格、代码块和链接 |
| **SPA / JavaScript 页面** | 真实浏览器渲染，不是简单 HTTP 抓取 |
| **批量剪藏** | 多个 URL 串行抓取，统一保存为 `.md` |
| **AI 工作流** | 直接喂给 RAG、知识库、代码助手、摘要/翻译流程 |

### 为什么 Markdown 对 AI 友好

- **结构保留**：标题层级、列表、表格、代码块、引用、链接都在
- **噪声更少**：比 HTML 少掉大量标签、脚本、样式，context 更省
- **易切分**：按标题层级做 chunk，适合 RAG 和长文总结
- **易溯源**：链接和代码块保留，方便回查原文
- **易存储**：纯文本，Git / Obsidian / 任意编辑器都能直接读

---

## 30 秒开始

```bash
git clone https://github.com/wJJh/llm-wiki-skills.git
cd llm-wiki-skills
cp .env.example .env
# 编辑 .env，填 CF_BROWSER_RENDERING_TOKEN 与 CF_ACCOUNT_ID
python skills/cf-browser-render/scripts/fetch_markdown.py "https://example.com" -o article.md
```

没有 Token？先去 Cloudflare Dashboard → My Profile → API Tokens 创建，
权限选 **Account > Browser Rendering > Edit**。完整步骤（含 Account ID、验证、
401/403/429 排查）见 [Cloudflare 凭据指南](../../docs/credentials/cloudflare-browser-rendering.md)。

---

## 环境变量

| 变量 | 必填 | 说明 |
|---|---|---|
| `CF_BROWSER_RENDERING_TOKEN` | 是 | Cloudflare API Token |
| `CF_ACCOUNT_ID` | 是 | Cloudflare Account ID |
| `HTTPS_PROXY` | 部分网络必需 | HTTP/HTTPS 代理；国内/受限网络访问 Cloudflare 通常需要 |

`.env` 可以放在：

- 仓库根 `.env`（clone 全量安装）
- `~/.claude/skills/.env` / `~/.dsh/skills/.env`（多个技能共用）
- 技能目录 `.env`（单技能安装）
- 或运行 `--env-file /path/to/.env`

系统环境变量优先，`.env` 只补充未设置的键。完整说明见
[凭据获取指南](../../docs/credentials/README.md)。

---

## 网络与代理（重要）

`api.cloudflare.com` 在部分网络环境（尤其中国大陆、受限出口 IP）可能**超时、连接重置或被限制**，
需要可用的代理 IP 才能稳定调用。

`.env` 中配置：

```dotenv
HTTPS_PROXY=http://127.0.0.1:7890
# 可选
HTTP_PROXY=http://127.0.0.1:7890
NO_PROXY=localhost,127.0.0.1
```

或单次命令指定：

```bash
python scripts/fetch_markdown.py \
  --proxy http://127.0.0.1:7890 "https://example.com"
```

- 只支持 HTTP/HTTPS 代理；SOCKS5 请先在客户端开启本地 HTTP 混合端口。
- 持续 403/1020 时更换出口 IP；Cloudflare 可能限制数据中心或被滥用的代理 IP。
- 代理要能访问 `api.cloudflare.com`；有些代理只放行网页。
- 使用可信代理；API 走 HTTPS，但不可信代理若安装根证书仍可能解密流量。

---

## 用法

```bash
# 输出到 stdout
python scripts/fetch_markdown.py "https://mp.weixin.qq.com/s/xxxxx"

# 保存文件
python scripts/fetch_markdown.py "https://example.com" -o article.md

# 多个 URL
python scripts/fetch_markdown.py url1 url2 url3

# 调整超时
python scripts/fetch_markdown.py "https://example.com" --timeout 120

# 指定代理
python scripts/fetch_markdown.py \
  --proxy http://127.0.0.1:7890 "https://example.com"
```

从仓库根运行时，把 `scripts/` 换成 `skills/cf-browser-render/scripts/`。

---

## 按自己的场景微调

技能是 MIT，可以直接改，不需要另起项目：

- **触发词**：编辑 `SKILL.md` 的 `description` / `whenToUse`
- **输出**：`-o article.md` 保存单文件；多个 URL 串行；`--timeout` 调整超时
- **端点**：把 `/browser-rendering/markdown` 换成 `/screenshot`、`/pdf`、
  `/content`、`/scrape` 等（进阶，需要改 `scripts/fetch_markdown.py`）
- **后处理**：加 frontmatter、按网页标题生成文件名、清理导航栏、生成批量清单
- **环境隔离**：用不同 `.env` + `--env-file` 区分工作/个人/测试场景

> 想改哪个场景，直接改副本即可；原技能目录不受影响。

---

## 安装

### Claude Code（单技能）

```text
/plugin marketplace add wJJh/llm-wiki-skills
/plugin install cf-browser-render@llm-wiki-skills
```

### 手动 / DSH

```bash
# Claude Code 用户级
cp -r skills/cf-browser-render ~/.claude/skills/

# DSH 用户级（Windows Junction）
New-Item -ItemType Junction `
  -Path "$env:USERPROFILE\.dsh\skills\cf-browser-render" `
  -Target "D:\path\llm-wiki-skills\skills\cf-browser-render"
```

---

## 限制与注意

- **国内网络通常需要代理 IP**：直连 `api.cloudflare.com` 可能超时/连接重置，请配置 `HTTPS_PROXY` 或 `--proxy`
- Cloudflare 有配额和速率限制；批量抓取建议串行并留间隔
- Token 不要提交到 Git；`.env` 已被 `.gitignore` 忽略
- 抓 GitHub 页面时开头可能是导航栏，README 正文通常在中后段
- 401 = Token 无效，403 = 权限不足，429 = 配额/限流

---

## 与其它技能

`cf-browser-render` 可以完全独立使用，也可以为
[github-stars-version-tracker](../github-stars-version-tracker/README.md)
的 Release 摘要补全全文。详见[根 README](../../README.md) 的联动章节。
