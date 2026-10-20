# github-stars-sync · GitHub Stars 导出与统计

> 分页导出个人 GitHub Stars，生成 JSON、Markdown 和语言统计报告。
> 零第三方依赖，输出字段可直接交给版本追踪技能。

[← 返回仓库](../../README.md) · [SKILL.md](SKILL.md)

---

## 功能

- 通过 GitHub REST API 分页获取所有 Starred 仓库
- 三种输出：JSON / 按语言分组的 Markdown / 语言统计表
- `--stdout` 直接输出到对话，进度走 stderr，不污染 JSON
- `--input` 离线模式：从已有 JSON 重新导出，不消耗 API 配额
- 用户名留空时自动调用 `GET /user`

---

## 环境变量

| 变量 | 必填 | 说明 |
|---|---|---|
| `GITHUB_TOKEN` | 是 | GitHub Personal Access Token |
| `GITHUB_USERNAME` | 否 | 留空自动识别 |
| `GITHUB_PROXY` | 否 | 如 `http://127.0.0.1:7890` |
| `OUTPUT_DIR` | 否 | 默认 `./output` |

Token 获取：<https://github.com/settings/tokens>（经典 Token 勾选 `public_repo`）。
完整步骤（经典/细粒度 Token、权限、限流排查）见
[GitHub 凭据指南](../../docs/credentials/github-token.md)。

---

## 用法

```bash
# 保存三份文件到 output/
python scripts/fetch_stars.py

# 直接输出 JSON 到 stdout
python scripts/fetch_stars.py --stdout --format json

# 只输出 Markdown / 统计
python scripts/fetch_stars.py --stdout --format markdown
python scripts/fetch_stars.py --stdout --format stats

# 离线重导出
python scripts/fetch_stars.py --input stars.json --stdout --format json
```

从仓库根运行时，把 `scripts/` 换成 `skills/github-stars-sync/scripts/`。

---

## 输出

| 文件 | 内容 |
|---|---|
| `github_stars.json` | 完整数据，含 `starred_at` |
| `github_stars.md` | 按语言分组、按 Stars 排序 |
| `github_stars_stats.md` | 语言分布统计 |

JSON 字段：`full_name`、`name`、`url`、`description`、`stars`、`language`、
`starred_at`、`owner`、`topics`。

---

## 安装

```text
/plugin marketplace add wJJh/llm-wiki-skills
/plugin install github-stars-sync@llm-wiki-skills
```

手动 / DSH：

```bash
cp -r skills/github-stars-sync ~/.claude/skills/
```

```powershell
New-Item -ItemType Junction `
  -Path "$env:USERPROFILE\.dsh\skills\github-stars-sync" `
  -Target "D:\path\llm-wiki-skills\skills\github-stars-sync"
```

---

## 限制

- 认证用户约 5000 请求/小时；每页 100 个仓库
- 私有仓库需要 Token 具备相应读取权限
- 代理通过 `GITHUB_PROXY` 映射到当前进程，不影响系统设置

---

## 与其它技能

导出的 `output/github_stars.json` 是
[github-stars-version-tracker](../github-stars-version-tracker/README.md)
的输入。完整联动见[根 README](../../README.md)。
