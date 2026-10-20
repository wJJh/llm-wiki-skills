---
name: github-stars-sync
description: >
  导出和统计 GitHub Stars 仓库，支持 JSON、Markdown、语言统计报告和可选文件保存。
  当用户说"同步 stars"、"导出 stars"、"我的 stars"、"我 star 了哪些"、
  "GitHub 收藏"、"starred repos"，或要求分析 GitHub Stars 时使用此技能。
  Use this skill to export, sync, or analyze GitHub starred repositories.
whenToUse: >
  用户要求导出、查看、统计或分析自己的 GitHub Stars 仓库时。
metadata:
  version: 1.0.0
  license: MIT
  repository: https://github.com/wJJh/llm-wiki-skills
---

# github-stars-sync

通过 GitHub REST API 分页获取个人 Starred 仓库，生成 JSON、Markdown 和语言统计。

- 零第三方 Python 依赖（标准库 `urllib`）
- 自动读取技能附近的 `.env`
- 输出统一字段 `full_name` + `name`，可直接交给 `github-stars-version-tracker`
- 新增 `--input` 离线模式，可从已有 JSON 重新导出，不消耗 API 配额

---

## 前置配置

| 变量 | 必填 | 说明 |
|---|---|---|
| `GITHUB_TOKEN` | 是（`--input` 模式除外） | GitHub Personal Access Token |
| `GITHUB_USERNAME` | 否 | 留空则调用 `GET /user` 自动识别 |
| `GITHUB_PROXY` | 否 | 如 `http://127.0.0.1:7890`；仅作用于当前进程 |
| `OUTPUT_DIR` | 否 | 默认 `./output` |

Token 获取：<https://github.com/settings/tokens>

- 经典 Token：勾选 `public_repo`
- 细粒度 Token：Public repositories 读取权限即可

完整步骤见 [GitHub 凭据指南](../../docs/credentials/github-token.md)。

`.env` 放在技能目录、技能根目录或仓库根均可；系统环境变量优先。

---

## 使用方式

### 默认：保存三份文件

```bash
python skills/github-stars-sync/scripts/fetch_stars.py
```

写入 `OUTPUT_DIR`：

| 文件 | 内容 |
|---|---|
| `github_stars.json` | 完整结构化数据，含 `starred_at` |
| `github_stars.md` | 按语言分组、按 Stars 排序的列表 |
| `github_stars_stats.md` | 语言分布统计表 |

### 直接输出到对话

```bash
python skills/github-stars-sync/scripts/fetch_stars.py --stdout
python skills/github-stars-sync/scripts/fetch_stars.py --stdout --format json
python skills/github-stars-sync/scripts/fetch_stars.py --stdout --format markdown
python skills/github-stars-sync/scripts/fetch_stars.py --stdout --format stats
```

进度信息全部走 stderr，因此 `--format json` 的 stdout 可以直接管道给 `jq` 或其它程序。

### 离线模式

```bash
python skills/github-stars-sync/scripts/fetch_stars.py \
  --input evals/fixtures/sample_stars.json --stdout --format json
```

适合重导出、测试或在不联网时生成报告。

---

## 输出字段

```json
{
  "full_name": "owner/repo",
  "name": "owner/repo",
  "url": "https://github.com/owner/repo",
  "description": "...",
  "stars": 12345,
  "language": "Python",
  "starred_at": "2026-01-01T00:00:00Z",
  "owner": "owner",
  "topics": ["..."]
}
```

---

## 与其它技能联动

```text
github-stars-sync
  -> output/github_stars.json
  -> github-stars-version-tracker（版本扫描）
  -> render_report.py（Markdown 报告）
  -> cf-browser-render（需要时抓取 release 全文）
```

`auto-github-star` 负责把新发现的仓库手动加入 Stars，再由本技能导出。详见仓库根 README 的联动章节。

---

## 单独安装

```text
/plugin marketplace add wJJh/llm-wiki-skills
/plugin install github-stars-sync@llm-wiki-skills
```

手动安装：

```bash
git clone https://github.com/wJJh/llm-wiki-skills.git
cp -r llm-wiki-skills/skills/github-stars-sync ~/.claude/skills/
```

DSH：

```powershell
New-Item -ItemType Junction `
  -Path "$env:USERPROFILE\.dsh\skills\github-stars-sync" `
  -Target "D:\path\llm-wiki-skills\skills\github-stars-sync"
```

---

## 注意事项

1. **速率限制** — 认证用户约 5000 次/小时；大量 Stars 会分页，脚本每次请求 100 个。
2. **私有仓库** — 需要 Token 具备对应仓库读取权限。
3. **代理** — 在 `.env` 设置 `GITHUB_PROXY`；脚本会自动映射为当前进程的 `HTTP(S)_PROXY`。
4. **Token 安全** — 只读 `.env` 或环境变量，不写入输出文件。
5. **输出目录** — 默认 `./output`，已被 `.gitignore` 忽略。
