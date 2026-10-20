#!/usr/bin/env python3
"""把 scan_all.py 生成的 combined.json 渲染成 Markdown 报告。

不依赖 Obsidian/LLM Wiki 的目录结构；需要归档到知识库时，把生成的
stars_report.md 复制进你的 vault 即可。

用法：
    python render_report.py --input output/combined.json
    python render_report.py --input output/combined.json -o output/report.md
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

from env_loader import configure_stdio, load_env

CATEGORY_ORDER = ["AI/LLM", "爬虫/逆向", "OCR/文档", "知识库/RAG", "基础设施", "其他"]


def escape_cell(value: object) -> str:
    return str(value or "").replace("|", "\\|").replace("\n", " ").strip()


def load_combined(path: str) -> tuple[list[dict], dict]:
    with open(path, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)], {}
    if isinstance(data, dict):
        updates = data.get("updates_found") or data.get("updates") or []
        return [item for item in updates if isinstance(item, dict)], data
    return [], {}


def version_cell(item: dict) -> str:
    latest = item.get("latest_tag") or "—"
    previous = item.get("previous_tag") or ""
    if previous and previous != latest:
        return f"`{previous}` → `{latest}`"
    return f"`{latest}`"


def summary_cell(item: dict) -> str:
    text = item.get("latest_name") or item.get("body_preview") or ""
    text = escape_cell(text)
    if len(text) > 140:
        text = text[:137].rstrip() + "..."
    return text or "—"


def render(updates: list[dict], meta: dict, title: str) -> str:
    scanned_at = meta.get("scanned_at") or datetime.now().isoformat(timespec="seconds")
    total = meta.get("total_stars", "?")
    filtered = meta.get("filtered_count", "?")
    recent = meta.get("recent_count", sum(1 for item in updates if item.get("is_recent")))

    lines = [f"# {title}", ""]
    lines.append(f"> 扫描时间：{scanned_at}")
    lines.append(f"> Stars 总数：{total} | 分类匹配：{filtered} | 发现更新：{len(updates)}（近期 {recent}）")
    if meta.get("incomplete"):
        lines.append("")
        lines.append("> ⚠️ 本次扫描不完整：存在限流/网络/鉴权错误，快照未更新。")

    if meta.get("errors"):
        lines.extend(["", "## 扫描错误", "", "| 仓库 | 类型 | 信息 |", "|---|---|---|"])
        for error in meta["errors"]:
            lines.append(
                "| {repo} | {kind} | {message} |".format(
                    repo=escape_cell(error.get("full_name")),
                    kind=escape_cell(error.get("kind")),
                    message=escape_cell(error.get("message")),
                )
            )

    if not updates:
        lines.extend(["", "本次没有发现版本更新。", ""])
        return "\n".join(lines)

    by_category: dict[str, list[dict]] = {}
    for item in updates:
        by_category.setdefault(item.get("category") or "其他", []).append(item)

    categories = [c for c in CATEGORY_ORDER if c in by_category]
    categories += [c for c in by_category if c not in categories]

    for category in categories:
        items = sorted(
            by_category[category],
            key=lambda item: item.get("latest_date") or "",
            reverse=True,
        )
        lines.extend(["", f"## {category}", ""])
        lines.append("| 仓库 | 最新版本 | 发布日期 | Stars | 说明 |")
        lines.append("|---|---|---|---|---|")
        for item in items:
            full_name = item.get("full_name") or ""
            url = item.get("html_url") or (f"https://github.com/{full_name}" if full_name else "")
            repo = f"[{full_name}]({url})" if url else full_name
            lines.append(
                "| {repo} | {version} | {date} | {stars} | {summary} |".format(
                    repo=repo,
                    version=version_cell(item),
                    date=escape_cell(item.get("latest_date")),
                    stars=item.get("stars", 0),
                    summary=summary_cell(item),
                )
            )

    lines.extend(
        [
            "",
            "---",
            "",
            "> 报告由 `github-stars-version-tracker` 生成。",
            "> Release 摘要仅保留前 300 字；需要全文时可用 `cf-browser-render` 抓取 release 页面。",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    configure_stdio()
    parser = argparse.ArgumentParser(description="把版本扫描结果渲染成 Markdown")
    parser.add_argument("--input", required=True, help="combined.json 或更新列表 JSON")
    parser.add_argument("-o", "--output", help="输出 Markdown 文件")
    parser.add_argument("--title", default="GitHub Stars 版本更新报告")
    parser.add_argument("--env-file", help="指定 .env 文件路径")
    parser.add_argument("--verbose-env", action="store_true", help="打印实际加载的 env 文件")
    args = parser.parse_args()

    load_env(explicit=args.env_file, verbose=args.verbose_env)

    try:
        updates, meta = load_combined(args.input)
        content = render(updates, meta, args.title)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"[错误] 读取 {args.input} 失败：{exc}", file=sys.stderr)
        return 1

    if args.output:
        target = Path(args.output).expanduser()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        print(f"[保存] {target}", file=sys.stderr)
    else:
        output_dir = Path(os.environ.get("OUTPUT_DIR") or "./output").expanduser()
        output_dir.mkdir(parents=True, exist_ok=True)
        target = output_dir / "stars_report.md"
        target.write_text(content, encoding="utf-8")
        print(f"[保存] {target}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
