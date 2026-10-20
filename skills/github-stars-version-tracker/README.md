# github-stars-version-tracker · Stars 版本追踪

> 批量扫描 Star 仓库的 Releases，对比上次快照，只报告真正发新版本的仓库。
> 分批防限流，错误不误报，生成通用 Markdown 报告。

[← 返回仓库](../../README.md) · [SKILL.md](SKILL.md)

---

## 它解决什么问题

Star 了几百个仓库后，"哪些最近发了新版本"很难手动追踪。本技能：

1. 读取 `github_stars.json`（可由 `github-stars-sync` 生成）
2. 按 AI/LLM、爬虫/逆向、OCR/文档、知识库/RAG、基础设施分类过滤
3. 分批调用 GitHub Releases API
4. 与 `github_stars_latest.json` 快照对比
5. 输出 `combined.json` 和 `stars_report.md`

**关键安全设计**：403/429/鉴权/网络错误会标记 `incomplete` 并中止，
不会把"没查到"误记为"没有更新"，也不会覆盖旧快照。

---

## 环境变量

| 变量 | 必填 | 说明 |
|---|---|---|
| `GITHUB_TOKEN` | 是 | GitHub Personal Access Token |
| `GITHUB_USERNAME` | 否 | 获取 Stars 时使用；留空自动识别 |
| `GITHUB_PROXY` | 否 | 如 `http://127.0.0.1:7890` |
| `OUTPUT_DIR` | 否 | 默认 `./output` |

Token 获取（经典/细粒度、Starring 与 Contents 权限）见
[GitHub 凭据指南](../../docs/credentials/github-token.md)。

---

## 一键扫描

```bash
python scripts/scan_all.py
```

默认输出：

```text
output/
├── github_stars.json          # Stars 快照（按需刷新）
├── github_stars_latest.json   # 版本快照（下次对比）
├── batch_0.json …             # 每批原始结果
├── combined.json              # 合并后的更新结果
└── stars_report.md            # Markdown 报告
```

常用参数：

```bash
# 强制刷新 Stars
python scripts/scan_all.py --refresh

# 包含所有分类
python scripts/scan_all.py --include-all

# 调整批大小和间隔
python scripts/scan_all.py --batch-size 20 --delay 8

# 使用已有 Stars JSON（显式 --input 不会按年龄自动覆盖；需要刷新加 --refresh）
python scripts/scan_all.py --no-fetch --input output/github_stars.json

# 调试只跑 2 批（不更新快照）
python scripts/scan_all.py --max-batches 2
```

从仓库根运行时，把 `scripts/` 换成
`skills/github-stars-version-tracker/scripts/`。

---

## 手动分批

```bash
python scripts/check_versions.py \
  --input output/github_stars.json \
  --snapshot output/github_stars_latest.json \
  --batch-size 30 --batch-index 0 \
  --output output/batch_0.json
```

结果字段：`updates_found`、`no_update`、`no_release`、`errors`、
`incomplete`、`snapshot_entries`、`batches_total`。

---

## 报告

```bash
python scripts/render_report.py \
  --input output/combined.json \
  --output output/stars_report.md
```

报告按分类分组，包含仓库链接、版本变化、发布日期、Stars 和 300 字 Release 摘要。
需要全文时用 [cf-browser-render](../cf-browser-render/README.md) 抓 `html_url`。

报告是普通 Markdown，不假设 Obsidian 目录；需要归档时复制进你的 vault 即可。

---

## 安装

```text
/plugin marketplace add wJJh/llm-wiki-skills
/plugin install github-stars-version-tracker@llm-wiki-skills
```

手动 / DSH：

```bash
cp -r skills/github-stars-version-tracker ~/.claude/skills/
```

```powershell
New-Item -ItemType Junction `
  -Path "$env:USERPROFILE\.dsh\skills\github-stars-version-tracker" `
  -Target "D:\path\llm-wiki-skills\skills\github-stars-version-tracker"
```

---

## 常见问题

| 问题 | 解决 |
|---|---|
| 403 / 429 | 脚本中止并保留旧快照；降低 `--batch-size`，增大 `--delay` |
| Token 401 | 更新 `GITHUB_TOKEN` |
| 代理不生效 | 在 `.env` 设置 `GITHUB_PROXY` |
| 中文乱码 | 脚本已自动 UTF-8；必要时设 `PYTHONIOENCODING=utf-8` |
| 又出现大量 NEW | 确认快照是新版列表格式，且包含全部扫描仓库 |

---

## 与其它技能

```text
github-stars-sync  ->  github_stars.json
github-stars-version-tracker  ->  combined.json / stars_report.md
cf-browser-render  ->  release 全文
auto-github-star   ->  手动收仓
```

完整说明见[根 README](../../README.md)。
