# GitHub Personal Access Token 获取

Stars 相关的三个技能需要 `GITHUB_TOKEN`：

| 技能 | 需要的能力 |
|---|---|
| `github-stars-sync` | 读取当前账号的 Starred 仓库 |
| `github-stars-version-tracker` | 读取 Starred 仓库 + 查询 Releases |
| `auto-github-star` | 写入 Star（Starring） |

推荐使用 **Fine-grained Token**；如果嫌步骤多，经典 Token 也能用。

---

## 方案一：Classic Token（步骤最少）

1. 登录 GitHub → 右上角头像 → **Settings**
2. 左侧最下方 → **Developer settings**
3. **Personal access tokens** → **Tokens (classic)**
4. **Generate new token** → **Generate new token (classic)**
5. 填写：
   - **Note**：`llm-wiki-skills`
   - **Expiration**：建议 90 天（或按你的安全策略）
   - **Scopes**：
     - 只看/操作公开仓库：勾选 `public_repo`
     - 需要读取私有仓库：勾选 `repo`
6. **Generate token** → 立即复制（只显示一次）

> `public_repo` 已经覆盖公开仓库的 Star 读取与 Starring 写入。
> 不需要勾选 `admin`、`delete_repo` 等高风险权限。

---

## 方案二：Fine-grained Token（推荐，权限更小）

1. 登录 GitHub → **Settings** → **Developer settings**
2. **Personal access tokens** → **Fine-grained tokens**
3. **Generate new token**
4. 填写：
   - **Token name**：`llm-wiki-skills`
   - **Expiration**：建议 90 天
   - **Resource owner**：你的账号
   - **Repository access**：
     - 只处理公开仓库：**Public repositories (read-only)**
     - 需要私有仓库：**All repositories**（或选择具体仓库）
5. **Permissions**：
   - **User permissions** → `Starring`
     - 导出 Stars：`Read-only`
     - 需要 `auto-github-star`：`Read and write`
   - **Repository permissions** → `Contents` → `Read-only`
     - 版本追踪要查询 Releases
     - `Metadata` 通常会自动包含为只读
6. **Generate token** → 立即复制

> 如果只使用 `github-stars-sync` 导出 Stars，不跑版本追踪，也不 star，
> 理论上只需要 `Starring: Read-only`。但为了让三个技能都能用，建议按上表授予。

---

## 写入 `.env`

```dotenv
GITHUB_TOKEN=<your-github-token>
# 可选；留空则自动调用 GET /user；不要填占位符
GITHUB_USERNAME=
```

`.env` 放在仓库根、技能根目录或技能目录均可；系统环境变量优先。
模板见仓库根 [`.env.example`](../../.env.example)。

---

## 验证

```bash
# 当前账号
curl -sS -H "Authorization: Bearer $GITHUB_TOKEN" \
  https://api.github.com/user

# 能否读取 Starred 仓库
curl -sS -H "Authorization: Bearer $GITHUB_TOKEN" \
  "https://api.github.com/user/starred?per_page=1"
```

PowerShell：

```powershell
curl.exe -sS -H "Authorization: Bearer $env:GITHUB_TOKEN" `
  https://api.github.com/user
```

也可以直接跑技能：

```bash
python skills/github-stars-sync/scripts/fetch_stars.py --stdout --format stats
```

> 如果变量只写在 `.env` 里，bash/PowerShell 不会自动加载它。
> 技能脚本会自动读取 `.env`；手动 curl 前可先
> `set -a; source .env; set +a`（bash），或在 PowerShell 中手动设置环境变量。

---

## 权限与技能对应

| 能力 | `github-stars-sync` | `github-stars-version-tracker` | `auto-github-star` |
|---|---|---|---|
| 读取 Starred 列表 | 需要 | 需要 | 不需要 |
| 读取 Releases | 不需要 | 需要 | 不需要 |
| 写入 Star | 不需要 | 不需要 | 需要 |

经典 Token 用 `public_repo`（公开）或 `repo`（含私有）即可覆盖。
细粒度 Token 按下表授予：

| 权限 | 用途 |
|---|---|
| User → Starring → Read | 导出 Stars |
| User → Starring → Read and write | 手动 Star |
| Repository → Contents → Read | 查询 Releases |
| Repository → Metadata → Read | 仓库元数据（通常默认包含） |

---

## 常见错误

| 状态 | 可能原因 | 处理 |
|---|---|---|
| `401` | Token 错误、过期、被撤销 | 重新生成并更新 `.env` |
| `403` | 触发限流，或缺少对应权限 | 查看 `X-RateLimit-Remaining`；降低频率；检查权限 |
| `404` | 私有仓库无访问权限，或用户名写错 | 检查 `GITHUB_USERNAME`；私有仓库需要 `repo` / All repositories |
| 代理错误 | 本机无法直连 GitHub | 在 `.env` 设置 `GITHUB_PROXY` |

GitHub 认证用户的 REST API 限额通常约为 **5000 请求/小时**；
版本追踪会分批扫描，建议保留默认的 30 个/批和 5 秒间隔。

---

## 安全建议

- 使用 Fine-grained Token，只授予需要的权限
- 设置过期时间，到期轮换
- 不要把 Token 发到 Issue、聊天、截图、日志
- 怀疑泄露：立即在 GitHub Settings → Developer settings 撤销
- `.env` 已被 `.gitignore` 忽略；手动上传 GitHub 时仍要确认没有把 `.env` 拖进去

---

## 官方文档

- Personal Access Token 管理：<https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens>
- Fine-grained PAT 权限：<https://docs.github.com/en/rest/authentication/permissions-required-for-fine-grained-personal-access-tokens>
- REST API 速率限制：<https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api>
- Starred 仓库 API：<https://docs.github.com/en/rest/activity/starring>
