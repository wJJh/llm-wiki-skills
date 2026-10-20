---
name: cf-browser-render
description: >
  使用 Cloudflare Browser Rendering API 将任意网页抓取并转换为 Markdown。
  当用户提到"抓网页"、"转 markdown"、"网页剪藏"、"提取文章内容"、
  "公众号文章"、"获取链接内容"、"把网页转成文本"、"网页内容提取"、
  "文章归档"、"剪藏网页"、"保存网页"、"爬取这个页面"，
  或者提供任何以 http/https 开头的 URL 并要求获取其内容时，务必使用此技能。
  Use this skill to render web pages, WeChat articles, docs, SPAs, or GitHub
  pages into clean Markdown.
whenToUse: >
  用户给出网页链接并要求抓取、剪藏、提取正文、转 Markdown，或需要研究网页内容时。
metadata:
  version: 1.0.0
  license: MIT
  repository: https://github.com/wJJh/llm-wiki-skills
---

# Cloudflare Browser Rendering → Markdown

通过 Cloudflare Browser Rendering API 获取真实浏览器渲染结果，再把网页转成 Markdown。
适合微信公众号文章、技术博客、文档站点、SPA 页面和 GitHub 页面。

- 零第三方 Python 依赖（只用标准库 `urllib`）
- 自动读取技能附近的 `.env`，不要求配置全局环境变量
- Windows 控制台自动切换 UTF-8，避免中文/符号编码错误

## 适用场景（不止知识库）

- 微信公众号文章、GitHub 仓库主页、技术博客、官方文档、SPA 页面
- 输出 Markdown，保留标题、列表、表格、代码块和链接，适合 AI 阅读、RAG 和归档
- 可按自己的场景修改触发词、输出方式、API 端点和后处理（见文末“按场景微调”）

---

## 前置配置

在 `.env` 中填写：

| 变量 | 说明 | 获取方式 |
|---|---|---|
| `CF_BROWSER_RENDERING_TOKEN` | Cloudflare API Token | Dashboard → My Profile → API Tokens |
| `CF_ACCOUNT_ID` | Cloudflare Account ID | Dashboard 右侧栏的 Account ID |

Token 权限要求：**Account > Browser Rendering > Edit**。
完整步骤（含 Account ID、验证和 401/403/429 排查）见
[Cloudflare 凭据指南](../../docs/credentials/cloudflare-browser-rendering.md)。

`.env` 放在以下任一位置即可（按优先级从高到低）：

1. 技能目录 `.env`（单技能安装推荐）
2. 技能根目录 `.env`，如 `~/.claude/skills/.env` 或 `~/.dsh/skills/.env`
3. 仓库根 `.env`（clone 全量安装）
4. `--env-file /path/to/.env` 显式指定

系统环境变量优先；`.env` 只补充未设置的键。技能不会读取宿主项目的其它 `.env`。

> **网络要求（重要）**：`api.cloudflare.com` 在部分网络（尤其中国大陆、受限出口 IP）
> 可能超时、连接重置或被限制，需要代理 IP。请在 `.env` 设置
> `HTTPS_PROXY=http://127.0.0.1:7890`，或使用 `--proxy`。详见
> [Cloudflare 凭据指南的“网络与代理要求”](../../docs/credentials/cloudflare-browser-rendering.md#网络与代理要求重要)。

---

## 使用方式

### 从仓库根运行

```bash
python skills/cf-browser-render/scripts/fetch_markdown.py "https://example.com"
python skills/cf-browser-render/scripts/fetch_markdown.py "https://example.com" -o article.md
```

### 在技能目录内运行

```bash
cd skills/cf-browser-render
python scripts/fetch_markdown.py "https://mp.weixin.qq.com/s/xxxxx"
```

### 使用代理

```bash
# 命令行显式指定
python skills/cf-browser-render/scripts/fetch_markdown.py \
  --proxy http://127.0.0.1:7890 "https://example.com"

# 或写入 .env
# HTTPS_PROXY=http://127.0.0.1:7890
```

> 只支持 HTTP/HTTPS 代理；SOCKS5 请先在客户端开启本地 HTTP 混合端口。

### 多个 URL

```bash
python skills/cf-browser-render/scripts/fetch_markdown.py url1 url2 url3
```

多个 URL 会按顺序输出，并用 `<!-- source: ... -->` 标注来源；`-o` 只支持单个 URL。

### 在 Python 中调用

```python
from fetch_markdown import fetch_markdown

markdown = fetch_markdown("https://example.com")
print(markdown)
```

### 直接调用 API（不经过脚本）

```bash
curl -s -X POST \
  "https://api.cloudflare.com/client/v4/accounts/$CF_ACCOUNT_ID/browser-rendering/markdown" \
  -H "Authorization: Bearer $CF_BROWSER_RENDERING_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com"}'
```

---

## 工作流程

1. **确认凭证** — 检查 `.env` 或 `--env-file` 中的两个 Cloudflare 变量。
2. **提取 URL** — 从用户消息中提取所有 http/https 链接。
3. **调用 API** — 默认超时 60 秒；需要时用 `--timeout` 调整。
4. **处理结果** — Markdown 输出到 stdout，或用 `-o` 写入文件。
5. **可选归档** — 需要进知识库时，把 Markdown 保存到你的 raw/剪藏目录，再按你的笔记流程处理。

---

## 单独安装

### Claude Code 插件市场

```text
/plugin marketplace add wJJh/llm-wiki-skills
/plugin install cf-browser-render@llm-wiki-skills
```

### 手动复制

```bash
git clone https://github.com/wJJh/llm-wiki-skills.git
cp -r llm-wiki-skills/skills/cf-browser-render ~/.claude/skills/
```

### DSH

```powershell
New-Item -ItemType Junction `
  -Path "$env:USERPROFILE\.dsh\skills\cf-browser-render" `
  -Target "D:\path\llm-wiki-skills\skills\cf-browser-render"
```

---

## 典型场景

| 场景 | 示例请求 |
|---|---|
| 公众号文章 | "帮我抓一下这篇公众号文章 https://mp.weixin.qq.com/s/xxx" |
| 技术博客 | "把这篇文章转成 markdown https://blog.example.com/post" |
| 批量剪藏 | "这几个链接都帮我提取正文：url1, url2, url3" |
| 知识库归档 | "剪藏这个页面到我的 raw/剪藏 目录" |
| 内容预览 | "帮我看看这个网页讲了什么 https://..." |
| GitHub 页面 | "抓取这个仓库的 README https://github.com/owner/repo" |

> 抓 GitHub 页面时，返回内容开头可能是导航栏 chrome；README 正文通常在中后段，不要误判为失败。

---

## 注意事项

1. **速率限制** — Cloudflare Browser Rendering 有配额和速率限制；批量抓取时建议串行并留间隔。
2. **动态内容** — 使用真实浏览器渲染，能处理 SPA 和 JavaScript 页面。
3. **敏感信息** — Token 只放在 `.env`，不要硬编码或提交到仓库。
4. **长页面** — 返回的 Markdown 可能很大，建议用 `-o` 保存到文件。
5. **代理** — 如访问 Cloudflare 需要代理，在 `.env` 中取消注释 `HTTPS_PROXY`。
6. **401/403/429** — 分别代表 Token 无效、权限不足、配额/限流；脚本会给出中文提示。
7. **网络限制** — 国内/受限网络直连 `api.cloudflare.com` 可能超时或连接重置，需配置
   `HTTPS_PROXY` 或 `--proxy`；持续 403/1020 时更换出口 IP。

---

## 按场景微调

技能是 MIT，可以直接改：

- **触发词**：编辑 frontmatter 的 `description` / `whenToUse`
- **输出**：`-o article.md`、多个 URL 串行、`--timeout`
- **端点**：把 `/browser-rendering/markdown` 换成 `/screenshot`、`/pdf`、
  `/content`、`/scrape` 等（进阶，需要改 `scripts/fetch_markdown.py`）
- **后处理**：加 frontmatter、按网页标题命名、清理导航栏、生成批量清单
- **环境隔离**：不同 `.env` + `--env-file` 区分工作/个人/测试场景

---

## 输出示例

```markdown
# 文章标题

正文内容...

## 小标题

- 列表项 1
- 列表项 2

> 引用块

[链接文本](https://example.com)
```
