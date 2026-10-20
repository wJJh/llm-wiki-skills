#!/usr/bin/env python3
"""批量检查 GitHub Stars 仓库的 Releases 版本更新。

特点：
- 与上次快照对比，只报告版本发生变化的仓库
- 按 AI/LLM、爬虫/逆向、OCR/文档、知识库/RAG、基础设施分类过滤
- 支持分批扫描，避免 GitHub API 限流
- 403/429/网络错误不会被误记为“无 release”，而是标记 incomplete 并中止快照更新

环境变量（可从技能附近的 .env 自动加载）：
    GITHUB_TOKEN   - 必填
    GITHUB_PROXY   - 可选；映射为当前进程 HTTP(S)_PROXY

用法：
    python check_versions.py --input output/github_stars.json \
        --snapshot output/github_stars_latest.json \
        --batch-size 30 --batch-index 0 --output output/batch_0.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

from env_loader import load_env

API_ROOT = "https://api.github.com"
USER_AGENT = "llm-wiki-skills/version-tracker"

CATEGORY_KEYWORDS = {
    "AI/LLM": [
        "llm", "gpt", "claude", "agent", "ai-", "chat", "rag", "embedding",
        "prompt", "skill", "mcp", "tool", "memory", "context", "inference",
        "model", "token", "copilot", "coding", "codex", "superpower",
        "compound", "heretic", "massgen", "ecc",
    ],
    "爬虫/逆向": [
        "crawler", "scraper", "spider", "reverse", "captcha", "browser",
        "automation", "proxy", "fingerprint", "js-reverse", "mitm",
        "scrapling", "skyvern", "lightpanda", "flaresolverr", "geekez",
        "jsreverser", "ios-mcp", "android-reverse",
    ],
    "OCR/文档": [
        "ocr", "paddle", "document", "markdown", "pdf", "miner",
        "textract", "markitdown", "label-studio",
    ],
    "知识库/RAG": [
        "knowledge", "wiki", "obsidian", "note", "graph", "rag",
        "lightrag", "weknora", "faiss", "tencentdb", "memory",
    ],
    "基础设施": [
        "docker", "kubernetes", "proxy", "vpn", "git", "terminal",
        "shell", "linux", "windows", "macos",
    ],
}

EXCLUDE_KEYWORDS = [
    "game", "frontend", "css", "react", "vue", "angular", "flutter",
    "android-app", "ios-app", "swift", "kotlin", "music", "video",
    "photo", "image-editor", "social", "blog", "shop", "ecommerce",
    "cms", "theme", "template", "website", "portfolio", "resume",
    "leetcode", "algorithm", "tutorial", "course", "awesome-list",
    "interview", "chinese", "translator", "dict", "dictionary",
    "wechat", "weixin", "mini-program", "admin", "dashboard",
]


def load_json(path: str):
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def github_get(path: str, token: str, timeout: int = 15):
    """返回 (data, error)。error 为 None 或 {kind, status, message}。"""
    request = urllib.request.Request(
        f"{API_ROOT}{path}",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": USER_AGENT,
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8")), None
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None, None
        if exc.code in (403, 429):
            return None, {
                "kind": "rate_limit",
                "status": exc.code,
                "message": (
                    f"GitHub 限流或拒绝访问（剩余 "
                    f"{exc.headers.get('X-RateLimit-Remaining', '?')}）"
                ),
            }
        if exc.code == 401:
            return None, {"kind": "auth", "status": 401, "message": "Token 无效或已过期"}
        detail = exc.read().decode("utf-8", "replace")[:200]
        return None, {"kind": "http", "status": exc.code, "message": detail}
    except urllib.error.URLError as exc:
        return None, {"kind": "network", "status": None, "message": str(exc.reason)}
    except TimeoutError:
        return None, {"kind": "timeout", "status": None, "message": "请求超时"}


def get_latest_release(owner: str, repo_name: str, token: str):
    """返回 (release_dict | None, error | None)。404 视为没有 release。"""
    data, error = github_get(f"/repos/{owner}/{repo_name}/releases?per_page=3", token)
    if error:
        return None, error
    if not isinstance(data, list) or not data:
        return None, None
    latest = data[0]
    return {
        "tag": latest.get("tag_name", ""),
        "date": latest.get("published_at", ""),
        "name": latest.get("name", ""),
        "body": (latest.get("body") or "")[:300],
        "html_url": latest.get("html_url", ""),
        "draft": latest.get("draft", False),
        "prerelease": latest.get("prerelease", False),
    }, None


def format_date(iso_str: str) -> str:
    if not iso_str:
        return ""
    try:
        return datetime.fromisoformat(iso_str.replace("Z", "+00:00")).strftime("%Y-%m-%d")
    except (ValueError, AttributeError):
        return iso_str[:10] if len(iso_str) >= 10 else iso_str


def is_recent(date_str: str, days: int = 60) -> bool:
    if not date_str:
        return False
    try:
        dt = datetime.strptime(date_str[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
        return dt > datetime.now(timezone.utc) - timedelta(days=days)
    except (ValueError, TypeError):
        return False


def match_category(repo: dict) -> str | None:
    haystack = (
        (repo.get("full_name") or repo.get("name") or "")
        + " "
        + (repo.get("description") or "")
    ).lower()
    if any(keyword in haystack for keyword in EXCLUDE_KEYWORDS):
        return None
    for category, keywords in CATEGORY_KEYWORDS.items():
        if any(keyword in haystack for keyword in keywords):
            return category
    return None


def _snapshot_items(data) -> list[dict]:
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if isinstance(data, dict):
        for key in ("snapshot", "updates", "updates_found"):
            value = data.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
    return []


def build_snapshot_map(snapshot_path: str | None) -> dict[str, dict]:
    """兼容 list / {updates:[]} / {updates_found:[]} / {snapshot:[]}。"""
    if not snapshot_path or not os.path.exists(snapshot_path):
        return {}
    try:
        data = load_json(snapshot_path)
    except (json.JSONDecodeError, OSError):
        return {}
    snapshot = {}
    for item in _snapshot_items(data):
        name = item.get("full_name") or item.get("name") or ""
        if not name:
            continue
        snapshot[name] = {
            "tag": item.get("latest_tag") or item.get("tag") or "",
            "date": item.get("latest_date") or item.get("date") or "",
        }
    return snapshot


def load_stars(path: str) -> list[dict]:
    data = load_json(path)
    if isinstance(data, dict):
        data = data.get("repos") or data.get("items") or data.get("stars") or []
    if not isinstance(data, list):
        raise RuntimeError(f"{path} 不是合法的 Stars JSON")
    return [item for item in data if isinstance(item, dict)]


def write_snapshot(path: str, entries: list[dict]) -> None:
    target = Path(path).expanduser()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(entries, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="检查 GitHub Stars 仓库的版本更新")
    parser.add_argument("--input", required=True, help="Stars JSON 路径")
    parser.add_argument("--snapshot", help="上次快照 JSON，用于对比")
    parser.add_argument("--snapshot-out", help="扫描成功后写出完整快照 JSON")
    parser.add_argument("--batch-size", type=int, default=30, help="每批仓库数（默认 30）")
    parser.add_argument("--batch-index", type=int, default=0, help="批次索引，从 0 开始")
    parser.add_argument("--days", type=int, default=60, help="多少天内视为近期更新")
    parser.add_argument("--include-all", action="store_true", help="不做分类过滤")
    parser.add_argument("--output", help="把完整结果 JSON 写入文件")
    parser.add_argument("--env-file", help="指定 .env 文件路径")
    parser.add_argument("--verbose-env", action="store_true", help="打印实际加载的 env 文件")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    load_env(explicit=args.env_file, verbose=args.verbose_env)

    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if not token:
        print("[错误] 未设置 GITHUB_TOKEN。", file=sys.stderr)
        return 1

    try:
        stars = load_stars(args.input)
    except (OSError, json.JSONDecodeError, RuntimeError) as exc:
        print(f"[错误] 读取 Stars 失败：{exc}", file=sys.stderr)
        return 1

    snapshot = build_snapshot_map(args.snapshot)

    classified: list[dict] = []
    for repo in stars:
        name = repo.get("full_name") or repo.get("name") or ""
        if not name:
            continue
        category = "其他" if args.include_all else match_category(repo)
        if category:
            classified.append({**repo, "full_name": name, "category": category})

    total = len(classified)
    start = args.batch_index * args.batch_size
    end = min(start + args.batch_size, total)
    batch = classified[start:end]
    batches_total = (total + args.batch_size - 1) // args.batch_size if total else 0

    print(
        f"[信息] 总 Stars: {len(stars)}, 分类匹配: {total}, "
        f"批次 {args.batch_index + 1}/{max(batches_total, 1)}",
        file=sys.stderr,
    )
    print(f"[信息] 本批: {start + 1}-{end}（{len(batch)} 个仓库）", file=sys.stderr)

    updates: list[dict] = []
    no_update: list[str] = []
    no_release: list[str] = []
    errors: list[dict] = []
    snapshot_entries: list[dict] = []

    for index, repo in enumerate(batch, start=1):
        name = repo["full_name"]
        if "/" not in name:
            errors.append(
                {
                    "full_name": name,
                    "kind": "invalid_name",
                    "status": None,
                    "message": "仓库名不是 owner/repo 格式",
                }
            )
            print(f"[{index}/{len(batch)}] {name} ... 跳过（名称格式错误）", file=sys.stderr)
            continue
        owner, _, repo_name = name.partition("/")
        category = repo["category"]
        print(f"[{index}/{len(batch)}] {name} ... ", end="", file=sys.stderr, flush=True)

        release, error = get_latest_release(owner, repo_name, token)
        checked_at = datetime.now(timezone.utc).isoformat()

        if error:
            errors.append({"full_name": name, **error})
            print(f"错误（{error['kind']}）", file=sys.stderr)
            if error["kind"] in ("rate_limit", "auth", "network", "timeout"):
                print("[中止] 出现限流/鉴权/网络错误，停止本批扫描。", file=sys.stderr)
                break
            continue

        if release is None:
            no_release.append(name)
            snapshot_entries.append(
                {
                    "full_name": name,
                    "latest_tag": "",
                    "latest_date": "",
                    "checked_at": checked_at,
                }
            )
            print("无 release", file=sys.stderr)
            continue

        release_date = format_date(release["date"])
        previous = snapshot.get(name, {})
        has_update = not previous.get("tag") or release["tag"] != previous.get("tag")

        snapshot_entries.append(
            {
                "full_name": name,
                "latest_tag": release["tag"],
                "latest_date": release_date,
                "checked_at": checked_at,
            }
        )

        if has_update:
            updates.append(
                {
                    "full_name": name,
                    "stars": repo.get("stars", repo.get("stargazers_count", 0)) or 0,
                    "language": repo.get("language") or "N/A",
                    "category": category,
                    "latest_tag": release["tag"],
                    "latest_date": release_date,
                    "latest_name": release["name"],
                    "previous_tag": previous.get("tag", ""),
                    "previous_date": previous.get("date", ""),
                    "is_recent": is_recent(release_date, args.days),
                    "is_new": not previous.get("tag"),
                    "body_preview": release["body"],
                    "html_url": release["html_url"],
                }
            )
            status = "NEW" if not previous.get("tag") else f"{previous['tag']} → {release['tag']}"
            print(status, file=sys.stderr)
        else:
            no_update.append(name)
            print(f"未变（{release['tag']}）", file=sys.stderr)

    incomplete = bool(errors)
    result = {
        "scanned_at": datetime.now(timezone.utc).isoformat(),
        "total_stars": len(stars),
        "filtered_count": total,
        "batches_total": batches_total,
        "batch_index": args.batch_index,
        "batch_size": args.batch_size,
        "batch_range": [start, end],
        "updates_found": sorted(
            updates, key=lambda item: item.get("latest_date") or "", reverse=True
        ),
        "recent_count": sum(1 for item in updates if item["is_recent"]),
        "no_update": no_update,
        "no_release": no_release,
        "errors": errors,
        "incomplete": incomplete,
        "snapshot_entries": snapshot_entries,
    }

    output_json = json.dumps(result, indent=2, ensure_ascii=False)
    if args.output:
        target = Path(args.output).expanduser()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(output_json, encoding="utf-8")
        print(f"[保存] {target}", file=sys.stderr)

    if args.snapshot_out:
        if incomplete:
            print(
                "[警告] 本批存在限流/网络错误，跳过快照写入，保留旧快照。",
                file=sys.stderr,
            )
        else:
            write_snapshot(args.snapshot_out, snapshot_entries)
            print(f"[保存] 快照 {args.snapshot_out}", file=sys.stderr)

    print("\n--- JSON OUTPUT ---", file=sys.stderr)
    print(output_json)
    print(
        f"\n[完成] 有更新 {len(updates)} 个，未变化 {len(no_update)} 个，"
        f"无 release {len(no_release)} 个，错误 {len(errors)} 个",
        file=sys.stderr,
    )
    return 2 if incomplete else 0


if __name__ == "__main__":
    raise SystemExit(main())
