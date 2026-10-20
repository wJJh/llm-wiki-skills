---
name: auto-github-star
description: >
  手动为 GitHub 仓库点亮 Star 的工具。仅在用户明确要求 star/点赞，
  或明确要求运行本技能时使用；不因为消息中出现链接而自动触发。
  Use this skill only when the user explicitly asks to star a repository.
whenToUse: >
  用户明确说"帮我 star 这个仓库"、"点个星"、"点赞这个仓库"，
  或明确要求运行 auto-github-star 时。
metadata:
  version: 1.0.0
  license: MIT
  repository: https://github.com/wJJh/llm-wiki-skills
---

# Auto GitHub Star

按需为 GitHub 仓库点亮 Star（**手动工具**）。

- 只在用户明确要求时调用
- 支持 `owner/repo`、完整 GitHub URL、批量去重
- 重复 star 返回 `already_starred`，不视为错误
- 零第三方 Python 依赖

---

## 触发边界

**使用**：

1. 用户明确要求「star / 点赞 / 点星」某个仓库
2. 用户明确要求运行 `auto-github-star`

**不使用**：

- 消息里只是出现了一个 GitHub 链接
- `/ingest`、网页抓取、创建笔记等场景
- 用户没有明确表达 star 意图

这是有意的隐私/同意边界：Star 会公开出现在用户账号下。

---

## 前置配置

| 变量 | 必填 | 说明 |
|---|---|---|
| `GITHUB_TOKEN` | 是（`--dry-run` 除外） | GitHub Personal Access Token |

Token 权限：

- 经典 Token：勾选 `public_repo`
- 细粒度 Token：授予 **Starring** 读写权限

完整步骤见 [GitHub 凭据指南](../../docs/credentials/github-token.md)。

`.env` 放在技能目录、技能根目录或仓库根均可；系统环境变量优先。

---

## 使用方式

```bash
# 单个仓库
python skills/auto-github-star/scripts/star_repo.py owner/repo

# 批量
python skills/auto-github-star/scripts/star_repo.py owner1/repo1 owner2/repo2

# 完整 URL
python skills/auto-github-star/scripts/star_repo.py https://github.com/owner/repo

# 只解析，不调用 API
python skills/auto-github-star/scripts/star_repo.py --dry-run owner/repo
```

输出 JSON 到 stdout，进度到 stderr：

```json
{
  "owner/repo": "starred",
  "owner2/repo2": "already_starred",
  "owner3/repo3": "error: 404 not found"
}
```

状态值：

| 状态 | 含义 |
|---|---|
| `starred` | 成功点亮 |
| `already_starred` | 之前已 star |
| `would_star` | `--dry-run` 模拟结果 |
| `error: ...` | 404 / 401 / 403 / 网络错误等 |

---

## 与其它技能联动

`auto-github-star` 是手动入口，不自动串联：

```text
cf-browser-render 研究仓库  ->  用户明确说"star 它"  ->  auto-github-star
auto-github-star  ->  GitHub Stars  ->  github-stars-sync  ->  version-tracker
```

---

## 单独安装

```text
/plugin marketplace add wJJh/llm-wiki-skills
/plugin install auto-github-star@llm-wiki-skills
```

手动安装：

```bash
git clone https://github.com/wJJh/llm-wiki-skills.git
cp -r llm-wiki-skills/skills/auto-github-star ~/.claude/skills/
```

DSH：

```powershell
New-Item -ItemType Junction `
  -Path "$env:USERPROFILE\.dsh\skills\auto-github-star" `
  -Target "D:\path\llm-wiki-skills\skills\auto-github-star"
```

---

## 注意事项

1. **静默失败** — 网络错误或限流时返回错误字符串，不阻塞主流程。
2. **不 star 非仓库路径** — `settings/profile`、`marketplace/foo` 等一级路径会被拒绝。
3. **Token 安全** — 只从 `.env` 或环境变量读取，不硬编码、不打印。
4. **代理** — 在 `.env` 设置 `GITHUB_PROXY`；脚本会自动映射到当前进程。
