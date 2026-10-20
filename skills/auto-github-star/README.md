# auto-github-star · 手动 Star 工具

> 只在用户明确要求时，为 GitHub 仓库点亮 Star。
> 不会因为消息里出现链接就自动执行。

[← 返回仓库](../../README.md) · [SKILL.md](SKILL.md)

---

## 为什么是手动工具

Star 会公开出现在你的 GitHub 账号下，属于有外部可见副作用的操作。
因此本技能只在两种情况下使用：

1. 用户明确说「star / 点赞 / 点星」某个仓库
2. 用户明确要求运行 `auto-github-star`

`/ingest`、网页抓取、写笔记等场景**不会**自动 star。

---

## 环境变量

| 变量 | 必填 | 说明 |
|---|---|---|
| `GITHUB_TOKEN` | 是（`--dry-run` 除外） | GitHub Personal Access Token |

Token 权限：

- 经典 Token：`public_repo`
- 细粒度 Token：**Starring** 读写

完整步骤见 [GitHub 凭据指南](../../docs/credentials/github-token.md)。

---

## 用法

```bash
# 单个
python scripts/star_repo.py owner/repo

# 批量
python scripts/star_repo.py owner1/repo1 owner2/repo2

# 完整 URL
python scripts/star_repo.py https://github.com/owner/repo

# 只解析，不调用 API
python scripts/star_repo.py --dry-run owner/repo
```

从仓库根运行时，把 `scripts/` 换成 `skills/auto-github-star/scripts/`。

---

## 输出

```json
{
  "owner/repo": "starred",
  "owner2/repo2": "already_starred",
  "owner3/repo3": "error: 404 not found"
}
```

| 状态 | 含义 |
|---|---|
| `starred` | 成功 |
| `already_starred` | 已 star |
| `would_star` | dry-run 模拟 |
| `error: ...` | 404 / 401 / 403 / 网络错误 |

进度输出到 stderr，JSON 输出到 stdout。

---

## 安装

```text
/plugin marketplace add wJJh/llm-wiki-skills
/plugin install auto-github-star@llm-wiki-skills
```

手动 / DSH：

```bash
cp -r skills/auto-github-star ~/.claude/skills/
```

```powershell
New-Item -ItemType Junction `
  -Path "$env:USERPROFILE\.dsh\skills\auto-github-star" `
  -Target "D:\path\llm-wiki-skills\skills\auto-github-star"
```

---

## 注意

- 非仓库路径（`settings/profile`、`marketplace/foo` 等）会被拒绝
- 网络错误/限流只返回错误字符串，不阻塞其它仓库
- Token 只从 `.env` 或环境变量读取，不打印、不写入输出
- `GITHUB_PROXY` 会自动映射到当前进程的 `HTTP(S)_PROXY`

---

## 与其它技能

```text
cf-browser-render 研究仓库
  -> 用户明确说"star 它"
  -> auto-github-star
  -> github-stars-sync 导出
  -> github-stars-version-tracker 追踪版本
```

完整说明见[根 README](../../README.md)。
