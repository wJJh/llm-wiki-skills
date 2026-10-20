#!/usr/bin/env python3
"""获取 GitHub Stars 快照（stdlib urllib，零第三方依赖）。

输出字段与 github-stars-sync 保持一致，方便 version-tracker 直接消费。

环境变量（可从技能附近的 .env 自动加载）：
    GITHUB_TOKEN     - 必填
    GITHUB_USERNAME  - 可选；留空则调用 GET /user
    GITHUB_PROXY     - 可选；映射为当前进程 HTTP(S)_PROXY
    OUTPUT_DIR       - 可选；默认 ./output
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from env_loader import configure_stdio, load_env

API_ROOT = "https://api.github.com"
PER_PAGE = 100
USER_AGENT = "llm-wiki-skills/version-tracker-fetch"


def _headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github.star+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": USER_AGENT,
    }


def github_get(path: str, token: str, timeout: int = 30):
    request = urllib.request.Request(f"{API_ROOT}{path}", headers=_headers(token))
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code == 401:
            raise RuntimeError("GitHub 返回 401：Token 无效或已过期。") from exc
        if exc.code == 403:
            remaining = exc.headers.get("X-RateLimit-Remaining", "?")
            raise RuntimeError(f"GitHub 返回 403：可能限流（剩余 {remaining}）。") from exc
        if exc.code == 404:
            raise RuntimeError("GitHub 返回 404：用户不存在。") from exc
        detail = exc.read().decode("utf-8", "replace")[:300]
        raise RuntimeError(f"GitHub 返回 HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"网络错误：{exc.reason}（可在 .env 设置 GITHUB_PROXY）") from exc
    except TimeoutError as exc:
        raise RuntimeError("请求 GitHub 超时。") from exc


def resolve_username(token: str) -> str:
    username = os.environ.get("GITHUB_USERNAME", "").strip()
    if username:
        return username
    data = github_get("/user", token)
    login = data.get("login") if isinstance(data, dict) else None
    if not login:
        raise RuntimeError("无法获取当前账号，请设置 GITHUB_USERNAME。")
    return login


def _owner_login(repo: dict, full_name: str) -> str:
    owner = repo.get("owner")
    if isinstance(owner, dict):
        login = owner.get("login") or ""
        if login:
            return login
    elif isinstance(owner, str) and owner:
        return owner
    return full_name.split("/")[0] if "/" in full_name else ""


def normalize(item: dict) -> dict:
    repo = item.get("repo", item)
    full_name = repo.get("full_name") or repo.get("name") or ""
    return {
        "full_name": full_name,
        "name": full_name,
        "url": repo.get("html_url") or repo.get("url") or "",
        "description": repo.get("description") or "",
        "stars": repo.get("stargazers_count", repo.get("stars", 0)) or 0,
        "language": repo.get("language") or "N/A",
        "starred_at": item.get("starred_at", repo.get("starred_at", "N/A")),
        "owner": _owner_login(repo, full_name),
        "topics": repo.get("topics") or [],
    }


def fetch_all(username: str, token: str) -> list[dict]:
    repos: list[dict] = []
    page = 1
    while True:
        data = github_get(
            f"/users/{urllib.parse.quote(username)}/starred"
            f"?per_page={PER_PAGE}&page={page}",
            token,
        )
        if not isinstance(data, list) or not data:
            break
        repos.extend(normalize(item) for item in data)
        print(f"[分页] 第 {page} 页：{len(data)} 个，累计 {len(repos)}", file=sys.stderr)
        if len(data) < PER_PAGE:
            break
        page += 1
    return repos


def main() -> int:
    configure_stdio()
    parser = argparse.ArgumentParser(description="获取 GitHub Stars（urllib 版）")
    parser.add_argument("--output", help="保存到文件；不指定则输出到 stdout")
    parser.add_argument("--env-file", help="指定 .env 文件路径")
    parser.add_argument("--verbose-env", action="store_true", help="打印实际加载的 env 文件")
    args = parser.parse_args()

    load_env(explicit=args.env_file, verbose=args.verbose_env)

    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if not token:
        print("[错误] 未设置 GITHUB_TOKEN。", file=sys.stderr)
        return 1

    try:
        username = resolve_username(token)
        print(f"[信息] 获取 {username} 的 Stars...", file=sys.stderr)
        repos = fetch_all(username, token)
        if not repos:
            print("[警告] 未获取到仓库。", file=sys.stderr)
            return 1

        payload = json.dumps(repos, indent=2, ensure_ascii=False)
        if args.output:
            output = Path(args.output).expanduser()
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(payload, encoding="utf-8")
            print(f"[保存] {output}（{len(repos)} 个）", file=sys.stderr)
        else:
            print(payload)
        print(f"[完成] 共 {len(repos)} 个 starred 仓库", file=sys.stderr)
        return 0
    except (RuntimeError, OSError) as exc:
        print(f"[错误] {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
