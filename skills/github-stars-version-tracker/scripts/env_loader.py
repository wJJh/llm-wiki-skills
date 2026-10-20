"""本地 .env 加载器（四个技能各自内置一份，内容保持一致）。

设计目标
--------
1. 不要求用户配置系统级/全局环境变量；技能只读取自己附近的 .env。
2. 单技能安装也能工作：技能目录、技能根目录、仓库根目录都会检查。
3. 系统环境变量始终优先，方便临时覆盖；.env 只补充尚未设置的键。
4. 只加载白名单键，绝不把宿主项目 .env 里的 ANTHROPIC_* 等无关变量注入技能进程。
5. 不扫描当前工作目录及无关父目录，避免误读其它项目的凭据。

查找顺序（低 -> 高，后者覆盖前者）：
    包根/.env  ->  <skills根>/.env  ->  技能目录/.env  ->  --env-file / SKILL_ENV_FILE

系统环境变量优先级高于以上所有文件。
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# 技能允许读取的键。新增变量时请同步更新四份 env_loader.py。
ALLOWED_KEYS = {
    "GITHUB_TOKEN",
    "GITHUB_USERNAME",
    "GITHUB_PROXY",
    "CF_BROWSER_RENDERING_TOKEN",
    "CF_ACCOUNT_ID",
    "OUTPUT_DIR",
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "NO_PROXY",
}


def configure_stdio() -> None:
    """在 Windows GBK 控制台下强制 UTF-8，避免中文/符号输出崩溃。"""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError, OSError):
            pass


def _skill_dir() -> Path:
    # scripts/env_loader.py -> 技能目录
    return Path(__file__).resolve().parent.parent


def _package_root(skill_dir: Path) -> Path | None:
    """识别 clone 安装的仓库根：同时含 package.json 与 skills/ 的祖先目录。"""
    for parent in (skill_dir.parent.parent, skill_dir.parent.parent.parent):
        if (parent / "package.json").is_file() and (parent / "skills").is_dir():
            return parent
    return None


def _parse_env_file(path: Path) -> dict[str, str]:
    """解析简单的 KEY=VALUE .env；支持 export、引号、行内注释与 UTF-8 BOM。"""
    values: dict[str, str] = {}
    try:
        text = path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError):
        return values

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].lstrip()
        if "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key or key.startswith("#"):
            continue

        # 只去掉“空白 + #”形式的行内注释，避免误伤值里的 #。
        hash_pos = value.find("#")
        if hash_pos > 0 and value[hash_pos - 1].isspace():
            value = value[:hash_pos].rstrip()

        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]

        values[key] = value

    return values


def candidate_files(explicit: str | None = None) -> list[Path]:
    """返回按优先级从低到高排列的候选 .env 路径。"""
    skill_dir = _skill_dir()
    candidates: list[Path] = []

    package_root = _package_root(skill_dir)
    if package_root is not None:
        candidates.append(package_root / ".env")

    skills_root = skill_dir.parent
    if skills_root.name == "skills":
        candidates.append(skills_root / ".env")

    candidates.append(skill_dir / ".env")

    explicit_path = explicit or os.environ.get("SKILL_ENV_FILE")
    if explicit_path:
        candidates.append(Path(explicit_path).expanduser())

    # 去重并保持顺序（Path.resolve 可能因文件不存在而失败，退回原路径）。
    seen: set[str] = set()
    unique: list[Path] = []
    for path in candidates:
        try:
            marker = str(path.resolve())
        except OSError:
            marker = str(path)
        if marker in seen:
            continue
        seen.add(marker)
        unique.append(path)
    return unique


def load_env(explicit: str | None = None, verbose: bool = False) -> list[tuple[str, list[str]]]:
    """加载 .env 到当前进程；返回 [(文件路径, 实际写入的键)]。

    - 系统环境变量优先：已存在的键不会被 .env 覆盖。
    - 多个 .env 文件之间，高优先级覆盖低优先级。
    - 只写入 ALLOWED_KEYS。
    """
    configure_stdio()

    baseline = {key for key in ALLOWED_KEYS if key in os.environ}
    merged: dict[str, str] = {}
    sources: dict[str, str] = {}

    for path in candidate_files(explicit):
        if not path.is_file():
            continue
        for key, value in _parse_env_file(path).items():
            if key not in ALLOWED_KEYS:
                continue
            merged[key] = value
            sources[key] = str(path)

    applied: dict[str, list[str]] = {}
    for key, value in merged.items():
        if key in baseline:
            continue
        os.environ[key] = value
        applied.setdefault(sources[key], []).append(key)

    # GITHUB_PROXY 只映射到当前进程，方便 urllib 使用；不写系统环境。
    proxy = os.environ.get("GITHUB_PROXY", "").strip()
    if proxy:
        for key in ("HTTP_PROXY", "HTTPS_PROXY"):
            if key not in baseline and not os.environ.get(key):
                os.environ[key] = proxy

    result = [(path, keys) for path, keys in applied.items()]
    if verbose:
        if not result:
            print("[env] 未找到可用的 .env（将使用系统环境变量）", file=sys.stderr)
        for path, keys in result:
            print(f"[env] {path}: {', '.join(keys)}", file=sys.stderr)
    return result
