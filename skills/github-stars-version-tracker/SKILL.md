---
name: github-stars-version-tracker
description: >
  批量扫描 GitHub Stars 仓库的版本更新，对比上次快照发现新版本，
  按 AI/LLM、爬虫/逆向、OCR/文档、知识库/RAG、基础设施等类别过滤，
  并生成 Markdown 报告。当用户说"检查 stars 更新"、"扫描版本"、
  "仓库有没有新版本"、"stars 版本追踪"、"看看我收藏的仓库最近有什么更新"时使用。
  Use this skill to track new releases across starred GitHub repositories.
whenToUse: >
  用户想批量检查自己 Star 的仓库最近有没有发新版本，或需要月度版本更新报告时。
metadata:
  version: 1.0.0
  license: MIT
  repository: https://github.com/wJJh/llm-wiki-skills
---

# github-stars-version-tracker

扫描个人 GitHub Stars 仓库的 Releases，与上次快照对比，只报告版本发生变化的仓库。

- 分批扫描，避免 GitHub API 限流
- 403/429/鉴权/网络错误会标记 `incomplete` 并中止，绝不会误当成"没有更新"
- 快照包含本批全部已扫描仓库（含无更新、无 release），第二次运行不会把旧仓库误报为 NEW
- 生成通用 Markdown 报告；有 Obsidian/LLM Wiki 时可自行归档
- 零第三方 Python 依赖

---

## 前置配置

| 变量 | 必填 | 说明 |
|---|---|---|
| `GITHUB_TOKEN` | 是 | GitHub Personal Access Token |
| `GITHUB_USERNAME` | 否 | 获取 Stars 时使用；留空则调用 `GET /user` |
| `GITHUB_PROXY` | 否 | 如 `http://127.0.0.1:7890` |
| `OUTPUT_DIR` | 否 | 默认 `./output` |

Token 获取：<https://github.com/settings/tokens>（经典 Token 勾选 `public_repo`）。
完整步骤见 [GitHub 凭据指南](../../docs/credentials/github-token.md)。

`.env` 放在技能目录、技能根目录或仓库根均可；系统环境变量优先。

---

## 一键扫描（推荐）

```bash
python skills/github-stars-version-tracker/scripts/scan_all.py
```

默认流程：

1. `output/github_stars.json` 不存在或超过 3 天 → 调用 `fetch_stars.py` 获取
2. 逐批调用 `check_versions.py`（默认每批 30 个，批间 5 秒）
3. 写 `output/combined.json`
4. 完整成功时写 `output/github_stars_latest.json`（下次对比用）
5. 调用 `render_report.py` 生成 `output/stars_report.md`

常用参数：

```bash
# 强制刷新 Stars，并包含所有分类
python skills/github-stars-version-tracker/scripts/scan_all.py --refresh --include-all

# 调整批大小和间隔
python skills/github-stars-version-tracker/scripts/scan_all.py --batch-size 20 --delay 8

# 使用已有 Stars JSON，不联网获取
python skills/github-stars-version-tracker/scripts/scan_all.py --input output/github_stars.json --no-fetch

# 只跑前 2 批（调试；视为不完整，不更新快照）
python skills/github-stars-version-tracker/scripts/scan_all.py --max-batches 2
```

---

## 手动分批扫描

只想检查某一批时：

```bash
python skills/github-stars-version-tracker/scripts/check_versions.py \
  --input output/github_stars.json \
  --snapshot output/github_stars_latest.json \
  --batch-size 30 \
  --batch-index 0 \
  --output output/batch_0.json
```

输出 JSON 包括：

| 字段 | 含义 |
|---|---|
| `updates_found` | 本批发现的新版本 |
| `no_update` | 版本未变化 |
| `no_release` | 仓库没有 Release |
| `errors` | 限流、鉴权、网络等错误 |
| `incomplete` | 是否因错误中止 |
| `snapshot_entries` | 本批全部已扫描仓库的最新 tag/date |
| `batches_total` | 总批次数 |

**快照语义**：`github_stars_latest.json` 是一个列表，包含所有已扫描仓库
（包括无更新和无 release 的仓库）。`scan_all.py` 只在完整扫描成功后覆盖它；
出现错误时会保留旧快照。

---

## 生成报告

```bash
python skills/github-stars-version-tracker/scripts/render_report.py \
  --input output/combined.json \
  --output output/stars_report.md
```

报告按分类分组，包含仓库链接、版本变化、发布日期、Stars 和 Release 摘要。
摘要只有前 300 字；需要全文时，用 `cf-browser-render` 抓取 `html_url`。

### 可选：归档到 Obsidian / LLM Wiki

报告是普通 Markdown，不含任何 vault 硬编码。需要归档时：

1. 把 `stars_report.md` 复制到你的 vault（例如 `分析/` 目录）
2. 按你的页面规范补 frontmatter
3. 如果使用 LLM Wiki，按你的流程重建索引、记录日志

---

## 与其它技能联动

```text
github-stars-sync -> output/github_stars.json
                  -> scan_all.py -> output/combined.json
                                 -> output/stars_report.md
                                 -> output/github_stars_latest.json
cf-browser-render -> 抓取 release 全文 / README（补全 300 字摘要）
auto-github-star  -> 手动把新发现的仓库加入 Stars（不自动触发）
```

---

## 单独安装

```text
/plugin marketplace add wJJh/llm-wiki-skills
/plugin install github-stars-version-tracker@llm-wiki-skills
```

手动安装：

```bash
git clone https://github.com/wJJh/llm-wiki-skills.git
cp -r llm-wiki-skills/skills/github-stars-version-tracker ~/.claude/skills/
```

DSH：

```powershell
New-Item -ItemType Junction `
  -Path "$env:USERPROFILE\.dsh\skills\github-stars-version-tracker" `
  -Target "D:\path\llm-wiki-skills\skills\github-stars-version-tracker"
```

---

## 常见问题

| 问题 | 解决 |
|---|---|
| GitHub 403 / 429 | `scan_all.py` 会中止并保留旧快照；降低 `--batch-size` 或增大 `--delay` 后重试 |
| Token 401 | 更新 `.env` 中的 `GITHUB_TOKEN` |
| 代理不生效 | 在 `.env` 设置 `GITHUB_PROXY`，脚本会映射到当前进程 |
| 中文乱码 | 脚本已自动 UTF-8；仍异常时设置 `PYTHONIOENCODING=utf-8` |
| 第二次运行又全是 NEW | 确认使用的是新版 `scan_all.py` 写出的快照（列表格式，包含全部扫描仓库） |
