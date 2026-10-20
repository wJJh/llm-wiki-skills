#!/usr/bin/env python3
"""一键串联 Stars 导出 → 分批版本扫描 → 快照 → Markdown 报告。

默认流程：
    1. output/github_stars.json 不存在或超过 3 天 -> 调用 fetch_stars.py
    2. 逐批调用 check_versions.py，批间默认间隔 5 秒
    3. 合并结果，写 output/combined.json
    4. 完整扫描成功时，写 output/github_stars_latest.json
    5. 调用 render_report.py 生成 output/stars_report.md

任何限流/鉴权/网络错误都会中止并且不覆盖旧快照，避免把“没查到”误当成“没有更新”。

用法：
    python scan_all.py
    python scan_all.py --refresh --include-all
    python scan_all.py --input output/github_stars.json --delay 3
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from env_loader import configure_stdio, load_env

HERE = Path(__file__).resolve().parent
FETCH_SCRIPT = HERE / "fetch_stars.py"
CHECK_SCRIPT = HERE / "check_versions.py"
REPORT_SCRIPT = HERE / "render_report.py"


def load_json(path: Path):
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    temp.replace(path)


def age_days(path: Path) -> float:
    if not path.exists():
        return float("inf")
    return (time.time() - path.stat().st_mtime) / 86400


def run_script(command: list[str]) -> int:
    print("[运行] " + " ".join(str(part) for part in command), file=sys.stderr)
    # 子脚本把结果写入文件；抑制 stdout 里的重复 JSON，进度仍走 stderr。
    return subprocess.run(command, check=False, stdout=subprocess.DEVNULL).returncode


def dedupe_updates(items: list[dict]) -> list[dict]:
    merged: dict[str, dict] = {}
    for item in items:
        name = item.get("full_name") or item.get("name") or ""
        if not name:
            continue
        current = merged.get(name)
        if current is None or (item.get("latest_date") or "") > (current.get("latest_date") or ""):
            merged[name] = item
    return sorted(merged.values(), key=lambda item: item.get("latest_date") or "", reverse=True)


def dedupe_snapshot(entries: list[dict]) -> list[dict]:
    merged: dict[str, dict] = {}
    for entry in entries:
        name = entry.get("full_name") or entry.get("name") or ""
        if not name:
            continue
        current = merged.get(name)
        if current is None or (entry.get("checked_at") or "") >= (current.get("checked_at") or ""):
            merged[name] = entry
    return sorted(merged.values(), key=lambda entry: entry.get("full_name") or "")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="一键扫描 GitHub Stars 版本更新")
    parser.add_argument("--output-dir", help="输出目录（默认取 OUTPUT_DIR 或 ./output）")
    parser.add_argument("--input", help="Stars JSON 路径（默认 <输出目录>/github_stars.json）")
    parser.add_argument("--snapshot", help="快照路径（默认 <输出目录>/github_stars_latest.json）")
    parser.add_argument("--batch-size", type=int, default=30, help="每批仓库数（默认 30）")
    parser.add_argument("--delay", type=float, default=5.0, help="批间等待秒数（默认 5）")
    parser.add_argument("--days", type=int, default=60, help="多少天内视为近期更新")
    parser.add_argument("--max-age-days", type=int, default=3, help="Stars 超过多少天自动刷新")
    parser.add_argument("--refresh", action="store_true", help="强制重新获取 Stars")
    parser.add_argument("--no-fetch", action="store_true", help="不自动获取 Stars（文件不存在则报错）")
    parser.add_argument("--include-all", action="store_true", help="不过滤分类")
    parser.add_argument("--no-report", action="store_true", help="不生成 Markdown 报告")
    parser.add_argument(
        "--max-batches",
        type=int,
        default=0,
        help="最多跑几批（0 = 全部；限制批次时视为不完整，不更新快照）",
    )
    parser.add_argument("--env-file", help="指定 .env 文件路径")
    parser.add_argument("--verbose-env", action="store_true", help="打印实际加载的 env 文件")
    return parser.parse_args()


def main() -> int:
    configure_stdio()
    args = parse_args()
    load_env(explicit=args.env_file, verbose=args.verbose_env)

    output_dir = Path(
        args.output_dir or os.environ.get("OUTPUT_DIR") or "./output"
    ).expanduser()
    output_dir.mkdir(parents=True, exist_ok=True)

    input_path = Path(args.input).expanduser() if args.input else output_dir / "github_stars.json"
    snapshot_path = (
        Path(args.snapshot).expanduser()
        if args.snapshot
        else output_dir / "github_stars_latest.json"
    )

    # 显式 --input 时尊重用户给的文件，不按年龄自动覆盖；需要刷新请加 --refresh。
    need_fetch = (
        args.refresh
        or not input_path.exists()
        or (args.input is None and age_days(input_path) > args.max_age_days)
    )
    if need_fetch:
        if args.no_fetch:
            print(
                f"[错误] 需要刷新 Stars，但指定了 --no-fetch：{input_path}",
                file=sys.stderr,
            )
            return 1
        command = [sys.executable, str(FETCH_SCRIPT), "--output", str(input_path)]
        if args.env_file:
            command += ["--env-file", args.env_file]
        if run_script(command) != 0:
            print("[错误] 获取 Stars 失败，已中止。", file=sys.stderr)
            return 1
    else:
        print(f"[信息] 使用现有 Stars 快照：{input_path}", file=sys.stderr)

    updates: list[dict] = []
    snapshot_entries: list[dict] = []
    errors: list[dict] = []
    batch_files: list[Path] = []
    batches_total = 0
    base_meta: dict = {}
    incomplete = False
    stop_reason = ""

    index = 0
    while True:
        if index > 0 and args.delay > 0:
            time.sleep(args.delay)

        batch_path = output_dir / f"batch_{index}.json"
        command = [
            sys.executable,
            str(CHECK_SCRIPT),
            "--input", str(input_path),
            "--batch-size", str(args.batch_size),
            "--batch-index", str(index),
            "--days", str(args.days),
            "--output", str(batch_path),
        ]
        if snapshot_path.exists():
            command += ["--snapshot", str(snapshot_path)]
        if args.include_all:
            command += ["--include-all"]
        if args.env_file:
            command += ["--env-file", args.env_file]

        return_code = run_script(command)
        if not batch_path.exists():
            print(
                f"[错误] 批次 {index} 没有生成结果文件（check_versions 退出码 {return_code}）。",
                file=sys.stderr,
            )
            return 1

        try:
            batch = load_json(batch_path)
        except (OSError, json.JSONDecodeError) as exc:
            print(f"[错误] 读取批次 {index} 失败：{exc}", file=sys.stderr)
            return 1

        if not isinstance(batch, dict):
            print(f"[错误] 批次 {index} 结果不是 JSON 对象。", file=sys.stderr)
            return 1

        if index == 0:
            base_meta = batch
            batches_total = int(batch.get("batches_total") or 0)

        batch_files.append(batch_path)
        updates.extend(batch.get("updates_found") or [])
        snapshot_entries.extend(batch.get("snapshot_entries") or [])
        errors.extend(batch.get("errors") or [])

        if batch.get("incomplete") or return_code == 2:
            incomplete = True
            stop_reason = "本批出现限流/鉴权/网络错误"
            break
        if return_code != 0:
            incomplete = True
            stop_reason = f"check_versions 退出码 {return_code}"
            break
        if batches_total == 0 or index + 1 >= batches_total:
            break
        if args.max_batches and index + 1 >= args.max_batches:
            incomplete = True
            stop_reason = f"已达到 --max-batches={args.max_batches}"
            break

        index += 1

    merged_updates = dedupe_updates(updates)
    merged_snapshot = dedupe_snapshot(snapshot_entries)
    combined = {
        "scanned_at": datetime.now(timezone.utc).isoformat(),
        "total_stars": base_meta.get("total_stars", 0),
        "filtered_count": base_meta.get("filtered_count", 0),
        "batches_total": batches_total,
        "batches_completed": len(batch_files),
        "updates_found": merged_updates,
        "recent_count": sum(1 for item in merged_updates if item.get("is_recent")),
        "errors": errors,
        "incomplete": incomplete,
        "stop_reason": stop_reason,
    }

    combined_path = output_dir / "combined.json"
    write_json(combined_path, combined)
    print(f"[保存] {combined_path}", file=sys.stderr)

    if incomplete:
        print(
            f"[警告] 扫描不完整（{stop_reason}），保留旧快照：{snapshot_path}",
            file=sys.stderr,
        )
    else:
        write_json(snapshot_path, merged_snapshot)
        print(f"[保存] 快照 {snapshot_path}", file=sys.stderr)

    if not args.no_report:
        report_path = output_dir / "stars_report.md"
        command = [
            sys.executable,
            str(REPORT_SCRIPT),
            "--input", str(combined_path),
            "--output", str(report_path),
        ]
        if args.env_file:
            command += ["--env-file", args.env_file]
        if run_script(command) != 0:
            print("[警告] 报告生成失败，但扫描结果已保存。", file=sys.stderr)
            return 1
        print(f"[保存] 报告 {report_path}", file=sys.stderr)

    print(
        f"[完成] 批次 {len(batch_files)}/{max(batches_total, 1)}，"
        f"更新 {len(merged_updates)} 个，错误 {len(errors)} 个，"
        f"状态：{'不完整' if incomplete else '完整'}",
        file=sys.stderr,
    )
    return 2 if incomplete else 0


if __name__ == "__main__":
    raise SystemExit(main())
