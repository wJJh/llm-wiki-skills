"""手动 Star GitHub 仓库（仅在用户明确要求时使用）。

用法：
    python star_repo.py owner/repo [owner/repo ...]
    python star_repo.py https://github.com/owner/repo
    python star_repo.py --dry-run owner/repo

环境变量（可从技能附近的 .env 自动加载）：
    GITHUB_TOKEN - GitHub Personal Access Token（--dry-run 时可不填）
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request

from env_loader import configure_stdio, load_env

# github.com 下这些一级路径不是仓库 owner，避免把 settings/profile 当成仓库。
RESERVED_OWNERS = {
    "settings", "marketplace", "explore", "features", "topics", "collections",
    "sponsors", "login", "notifications", "pulls", "issues", "search",
    "orgs", "users", "about", "pricing", "enterprise", "apps", "codespaces",
}


def star_repo(owner: str, repo: str, token: str) -> str:
    """Star 单个仓库，返回状态字符串。"""
    url = f"https://api.github.com/user/starred/{owner}/{repo}"
    request = urllib.request.Request(url, method="PUT")
    request.add_header("Authorization", f"Bearer {token}")
    request.add_header("Accept", "application/vnd.github+json")
    request.add_header("X-GitHub-Api-Version", "2022-11-28")
    request.add_header("User-Agent", "llm-wiki-skills/auto-github-star")

    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return "starred" if response.status in (200, 204) else f"unexpected_status:{response.status}"
    except urllib.error.HTTPError as exc:
        if exc.code == 304:
            return "already_starred"
        if exc.code == 404:
            return "error: 404 not found"
        if exc.code == 401:
            return "error: 401 bad credentials"
        if exc.code in (403, 429):
            return "error: 403/429 forbidden or rate limited"
        return f"error: HTTP {exc.code}"
    except urllib.error.URLError as exc:
        return f"error: network — {exc.reason}"
    except TimeoutError:
        return "error: timeout"


def parse_repo(arg: str) -> tuple[str, str] | None:
    """解析 GitHub URL 或 owner/repo；拒绝非仓库路径。"""
    match = re.match(r"^https?://github\.com/([^/]+)/([^/\s#?]+)", arg)
    if match:
        owner, repo = match.group(1), match.group(2)
        repo = re.sub(r"\.git$", "", repo)
    else:
        match = re.match(r"^([^/\s]+)/([^/\s]+)$", arg)
        if not match:
            return None
        owner, repo = match.group(1), match.group(2)

    if owner.lower() in RESERVED_OWNERS or owner.startswith("."):
        return None
    if not repo or repo in (".", ".."):
        return None
    return owner, repo


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="手动 Star GitHub 仓库")
    parser.add_argument("repos", nargs="+", help="owner/repo 或 GitHub URL")
    parser.add_argument("--dry-run", action="store_true", help="只解析并输出结果，不调用 API")
    parser.add_argument("--env-file", help="指定 .env 文件路径")
    parser.add_argument("--verbose-env", action="store_true", help="打印实际加载的 env 文件")
    return parser.parse_args()


def main() -> int:
    configure_stdio()
    args = parse_args()
    load_env(explicit=args.env_file, verbose=args.verbose_env)

    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if not token and not args.dry_run:
        print(
            json.dumps({"error": "GITHUB_TOKEN not set"}, ensure_ascii=False),
            file=sys.stdout,
        )
        return 1

    results: dict[str, str] = {}
    parsed_items: list[tuple[str, str]] = []
    seen: set[str] = set()
    for arg in args.repos:
        parsed = parse_repo(arg)
        if not parsed:
            results[arg] = "error: not a github repository"
            continue
        owner, repo = parsed
        full_name = f"{owner}/{repo}"
        if full_name.lower() in seen:
            continue
        seen.add(full_name.lower())
        parsed_items.append((owner, repo))

    for owner, repo in parsed_items:
        full_name = f"{owner}/{repo}"
        if args.dry_run:
            results[full_name] = "would_star"
            continue
        results[full_name] = star_repo(owner, repo, token)

    for repo, status in results.items():
        if status in ("starred", "would_star"):
            print(f"⭐ {repo}" + ("（dry-run）" if status == "would_star" else ""), file=sys.stderr)
        elif status == "already_starred":
            print(f"✔ {repo}（already starred）", file=sys.stderr)
        else:
            print(f"✗ {repo}: {status}", file=sys.stderr)

    print(json.dumps(results, ensure_ascii=False))
    return 0 if all(not status.startswith("error") for status in results.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
