#!/usr/bin/env python3
"""导出 GitHub Stars：JSON / Markdown / 语言统计。

零第三方依赖（stdlib urllib）。环境变量可从技能附近的 .env 自动加载：
    GITHUB_TOKEN     - 必填（使用 --input 离线模式时可不填）
    GITHUB_USERNAME  - 可选；留空则调用 GET /user 获取当前账号
    GITHUB_PROXY     - 可选；映射为当前进程的 HTTP(S)_PROXY
    OUTPUT_DIR       - 可选；默认 ./output

用法：
    python fetch_stars.py
    python fetch_stars.py --stdout --format json
    python fetch_stars.py --input stars.json --stdout --format markdown
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

from env_loader import load_env

API_ROOT = "https://api.github.com"
PER_PAGE = 100
USER_AGENT = "llm-wiki-skills/github-stars-sync"


def _headers(token: str | None) -> dict[str, str]:
    headers = {
        "Accept": "application/vnd.github.star+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": USER_AGENT,
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def github_get(path: str, token: str | None, timeout: int = 30):
    """调用 GitHub REST API，返回解析后的 JSON。"""
    request = urllib.request.Request(f"{API_ROOT}{path}", headers=_headers(token))
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code == 401:
            raise RuntimeError("GitHub 返回 401：Token 无效或已过期。") from exc
        if exc.code == 403:
            remaining = exc.headers.get("X-RateLimit-Remaining", "?")
            reset_at = exc.headers.get("X-RateLimit-Reset", "?")
            raise RuntimeError(
                f"GitHub 返回 403：可能触发限流（剩余 {remaining}，重置时间戳 {reset_at}）。"
            ) from exc
        if exc.code == 404:
            raise RuntimeError("GitHub 返回 404：用户不存在或没有访问权限。") from exc
        detail = exc.read().decode("utf-8", "replace")[:300]
        raise RuntimeError(f"GitHub 返回 HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"网络错误：{exc.reason}（如需要代理，请在 .env 设置 GITHUB_PROXY）") from exc
    except TimeoutError as exc:
        raise RuntimeError("请求 GitHub 超时，请检查网络或代理。") from exc


def resolve_username(token: str) -> str:
    username = os.environ.get("GITHUB_USERNAME", "").strip()
    if username:
        return username
    data = github_get("/user", token)
    login = data.get("login") if isinstance(data, dict) else None
    if not login:
        raise RuntimeError("无法从 /user 获取用户名，请显式设置 GITHUB_USERNAME。")
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


def normalize_repo(item: dict) -> dict:
    repo = item.get("repo", item)
    full_name = repo.get("full_name") or repo.get("name") or ""
    return {
        "full_name": full_name,
        "name": full_name,
        "url": repo.get("html_url") or repo.get("url") or "",
        "description": repo.get("description") or "",
        "stars": repo.get("stargazers_count", repo.get("stars", 0)) or 0,
        "language": repo.get("language") or "Others",
        "starred_at": item.get("starred_at", repo.get("starred_at", "N/A")),
        "owner": _owner_login(repo, full_name),
        "topics": repo.get("topics") or [],
    }


def get_all_starred_repos(username: str, token: str, per_page: int = PER_PAGE) -> list[dict]:
    repos: list[dict] = []
    page = 1
    while True:
        data = github_get(
            f"/users/{urllib.parse.quote(username)}/starred"
            f"?per_page={per_page}&page={page}",
            token,
        )
        if not isinstance(data, list) or not data:
            break
        for item in data:
            repos.append(normalize_repo(item))
        print(f"[分页] 第 {page} 页：{len(data)} 个，累计 {len(repos)}", file=sys.stderr)
        if len(data) < per_page:
            break
        page += 1
    return repos


def load_repos_from_file(path: str) -> list[dict]:
    with open(path, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    if isinstance(data, dict):
        data = data.get("repos") or data.get("items") or data.get("stars") or []
    if not isinstance(data, list):
        raise RuntimeError(f"{path} 不是合法的 Stars JSON（应为数组）")
    return [normalize_repo(item) for item in data if isinstance(item, dict)]


def export_json(repos: list[dict]) -> str:
    return json.dumps(repos, indent=2, ensure_ascii=False)


def export_markdown(repos: list[dict]) -> str:
    by_language: dict[str, list[dict]] = {}
    for repo in repos:
        by_language.setdefault(repo["language"], []).append(repo)

    lines = ["# GitHub Stars", ""]
    lines.append(f"总计：{len(repos)} 个仓库 | 导出时间：{datetime.now().isoformat(timespec='seconds')}")
    lines.append("")
    for language in sorted(by_language, key=lambda x: (x == "Others", x)):
        lines.append(f"## {language}")
        lines.append("")
        for repo in sorted(by_language[language], key=lambda x: x["stars"], reverse=True):
            line = f"- [{repo['full_name']}]({repo['url']}) ⭐{repo['stars']}"
            if repo["description"]:
                line += f" — {repo['description']}"
            lines.append(line)
        lines.append("")
    return "\n".join(lines)


def export_stats(repos: list[dict]) -> str:
    stats: dict[str, dict[str, int]] = {}
    for repo in repos:
        entry = stats.setdefault(repo["language"], {"count": 0, "stars": 0})
        entry["count"] += 1
        entry["stars"] += repo["stars"]

    lines = ["# GitHub Stars 语言统计", "", f"总计：{len(repos)} 个仓库", ""]
    lines.append("| 语言 | 数量 | 总 Stars |")
    lines.append("|------|------|----------|")
    for language, entry in sorted(stats.items(), key=lambda x: x[1]["count"], reverse=True):
        lines.append(f"| {language} | {entry['count']} | {entry['stars']} |")
    return "\n".join(lines)


def write_exports(repos: list[dict], output_dir: str) -> list[str]:
    target = Path(output_dir).expanduser()
    target.mkdir(parents=True, exist_ok=True)
    files = {
        "github_stars.json": export_json(repos),
        "github_stars.md": export_markdown(repos),
        "github_stars_stats.md": export_stats(repos),
    }
    written = []
    for name, content in files.items():
        path = target / name
        path.write_text(content, encoding="utf-8")
        written.append(str(path))
        print(f"[保存] {path}", file=sys.stderr)
    return written


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="导出 GitHub Stars 仓库")
    parser.add_argument("--stdout", action="store_true", help="输出到 stdout，不写文件")
    parser.add_argument(
        "--format",
        choices=["json", "markdown", "stats", "all"],
        default="all",
        help="--stdout 时的输出格式（默认 all）",
    )
    parser.add_argument("--input", help="离线模式：从已有 Stars JSON 读取，不调用 GitHub API")
    parser.add_argument("--output-dir", help="输出目录（默认取 OUTPUT_DIR，未设置则为 ./output）")
    parser.add_argument("--env-file", help="指定 .env 文件路径")
    parser.add_argument("--verbose-env", action="store_true", help="打印实际加载的 env 文件")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    load_env(explicit=args.env_file, verbose=args.verbose_env)

    try:
        if args.input:
            repos = load_repos_from_file(args.input)
        else:
            token = os.environ.get("GITHUB_TOKEN", "").strip()
            if not token:
                print(
                    "[错误] 未设置 GITHUB_TOKEN。请在 .env 中填写，"
                    "或使用 --input 读取已有 JSON。",
                    file=sys.stderr,
                )
                return 1
            username = resolve_username(token)
            print(f"[信息] 正在获取 {username} 的 Starred 仓库...", file=sys.stderr)
            repos = get_all_starred_repos(username, token)

        if not repos:
            print("[警告] 未获取到任何仓库，请检查用户名与 Token 权限。", file=sys.stderr)
            return 1

        if args.stdout:
            payloads = {
                "json": export_json(repos),
                "markdown": export_markdown(repos),
                "stats": export_stats(repos),
            }
            if args.format == "all":
                print("\n\n---\n\n".join(payloads.values()))
            else:
                print(payloads[args.format])
        else:
            output_dir = args.output_dir or os.environ.get("OUTPUT_DIR") or "./output"
            write_exports(repos, output_dir)

        print(f"[完成] 共 {len(repos)} 个 starred 仓库", file=sys.stderr)
        return 0
    except (RuntimeError, OSError, json.JSONDecodeError) as exc:
        print(f"[错误] {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
