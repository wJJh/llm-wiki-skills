#!/usr/bin/env python3
"""LLM Wiki Skills 仓库校验器。

无网络、无密钥、无第三方依赖。CI 与本地共用。

检查内容：
- 根文件与四个技能目录结构
- SKILL.md frontmatter（name / description / whenToUse）
- marketplace.json / package.json / cordis.patch.yml / index.js
- Python 语法、零 requests 依赖
- 四份 env_loader.py 哈希一致
- 真实 .env、密钥形态、个人路径、缓存与运行产物
- README 本地链接
- 离线 fixtures、报告渲染、脚本 --help
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILLS = [
    "cf-browser-render",
    "github-stars-sync",
    "github-stars-version-tracker",
    "auto-github-star",
]
PLUGINS = ["all-skills", *SKILLS]

errors: list[str] = []
warnings: list[str] = []


def ok(message: str) -> None:
    print(f"[PASS] {message}")


def fail(message: str) -> None:
    errors.append(message)
    print(f"[FAIL] {message}")


def warn(message: str) -> None:
    warnings.append(message)
    print(f"[WARN] {message}")


def check(condition: bool, message: str) -> None:
    if condition:
        ok(message)
    else:
        fail(message)


def run_python(args: list[str], **kwargs) -> subprocess.CompletedProcess:
    """运行 Python 子进程，并禁止写入 __pycache__。"""
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    kwargs.setdefault("encoding", "utf-8")
    kwargs.setdefault("errors", "replace")
    return subprocess.run(args, env=env, **kwargs)


def parse_frontmatter(text: str) -> dict[str, str]:
    text = text.lstrip("\uFEFF").replace("\r\n", "\n").replace("\r", "\n")
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        return {}
    try:
        closing = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
    except StopIteration:
        return {}

    meta: dict[str, str] = {}
    index = 1
    while index < closing:
        match = re.match(r"^([A-Za-z0-9_-]+):\s*(.*)$", lines[index])
        if not match:
            index += 1
            continue
        key, value = match.group(1), match.group(2).strip()
        if value in (">", "|", ">-", "|-"):
            folded = value.startswith(">")
            block: list[str] = []
            index += 1
            while index < closing and (
                lines[index].strip() == "" or lines[index].startswith((" ", "\t"))
            ):
                block.append(lines[index].strip())
                index += 1
            value = (" " if folded else "\n").join(block).strip()
        else:
            if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
                value = value[1:-1]
            index += 1
        meta[key] = value
    return meta


def text_files() -> list[Path]:
    suffixes = {
        ".md", ".py", ".js", ".json", ".yml", ".yaml", ".txt", ".example",
        ".gitignore", ".bat", ".ps1",
    }
    files: list[Path] = []
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        if any(
            part in {".git", "__pycache__", ".ruff_cache", "node_modules", "output"}
            for part in path.parts
        ):
            continue
        if path.name in {"LICENSE"} or path.suffix in suffixes:
            files.append(path)
    return files


def check_structure() -> None:
    required = [
        "README.md", "README.en.md", "LICENSE", ".env.example", ".gitignore",
        ".npmignore", "package.json", "cordis.patch.yml", "index.js",
        ".claude-plugin/marketplace.json", ".github/workflows/verify.yml",
        "docs/credentials/README.md",
        "docs/credentials/cloudflare-browser-rendering.md",
        "docs/credentials/github-token.md",
    ]
    missing = [name for name in required if not (ROOT / name).exists()]
    check(not missing, f"根文件完整（缺失：{', '.join(missing) or '无'}）")

    root_readme = (ROOT / "README.md").read_text(encoding="utf-8")
    check(
        "docs/credentials/README.md" in root_readme,
        "README 链接凭据获取指南",
    )
    check("微信公众号" in root_readme and "微调" in root_readme, "README 包含 cf 场景宣传与微调说明")
    check("## 使用前提" in root_readme, "README 包含使用前提")
    check("Python 3.10" in root_readme, "README 说明 Python 版本要求")
    check(
        "HTTPS_PROXY" in root_readme and "代理 IP" in root_readme,
        "README 说明 Cloudflare 代理 IP 要求",
    )

    en_readme = (ROOT / "README.en.md").read_text(encoding="utf-8")
    check("## Prerequisites" in en_readme, "README.en 包含 Prerequisites")
    check("Python 3.10" in en_readme, "README.en 说明 Python 版本要求")
    check("HTTPS_PROXY" in en_readme, "README.en 说明 Cloudflare 代理")

    cf_readme = (ROOT / "skills" / "cf-browser-render" / "README.md").read_text(encoding="utf-8")
    check("微信公众号" in cf_readme, "cf README 宣传微信公众号场景")
    check("微调" in cf_readme, "cf README 说明可按场景微调")
    check("docs/credentials" in cf_readme, "cf README 链接凭据指南")
    check(
        "HTTPS_PROXY" in cf_readme and "代理 IP" in cf_readme,
        "cf README 说明 Cloudflare 代理 IP 要求",
    )

    for skill in SKILLS:
        base = ROOT / "skills" / skill
        check(base.is_dir(), f"{skill}: 目录存在")
        check((base / "SKILL.md").is_file(), f"{skill}: SKILL.md 存在")
        check((base / "README.md").is_file(), f"{skill}: README.md 存在")
        scripts = list((base / "scripts").glob("*.py")) if (base / "scripts").is_dir() else []
        check(bool(scripts), f"{skill}: scripts/*.py 存在")
        if scripts:
            check((base / "scripts" / "env_loader.py").is_file(), f"{skill}: env_loader.py 存在")

        skill_text = (base / "SKILL.md").read_text(encoding="utf-8") if (base / "SKILL.md").is_file() else ""
        meta = parse_frontmatter(skill_text)
        check(meta.get("name") == skill, f"{skill}: frontmatter name 与目录一致")
        check(bool(meta.get("description", "").strip()), f"{skill}: description 非空")
        check(bool(meta.get("whenToUse", "").strip()), f"{skill}: whenToUse 非空")


def check_marketplace() -> None:
    path = ROOT / ".claude-plugin" / "marketplace.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"marketplace.json 无法解析：{exc}")
        return

    check(data.get("name") == "llm-wiki-skills", "marketplace: name 正确")
    check(isinstance(data.get("owner"), dict) and bool(data["owner"].get("name")), "marketplace: owner 存在")
    plugins = data.get("plugins")
    check(isinstance(plugins, list) and len(plugins) == 5, "marketplace: 5 个插件")

    if not isinstance(plugins, list):
        return
    names = [plugin.get("name") for plugin in plugins if isinstance(plugin, dict)]
    check(len(names) == len(set(names)), "marketplace: 插件名唯一")
    check(set(names) == set(PLUGINS), "marketplace: 插件集合正确")

    for plugin in plugins:
        if not isinstance(plugin, dict):
            continue
        name = plugin.get("name", "?")
        check(plugin.get("source") == "./", f"marketplace/{name}: source=./")
        check(plugin.get("strict") is False, f"marketplace/{name}: strict=false")
        skills = plugin.get("skills")
        check(isinstance(skills, list) and bool(skills), f"marketplace/{name}: skills 非空")
        if isinstance(skills, list):
            for relative in skills:
                target = (ROOT / relative).resolve()
                check(
                    target.is_dir() and (target / "SKILL.md").is_file(),
                    f"marketplace/{name}: {relative} 存在且含 SKILL.md",
                )
            if name == "all-skills":
                check(len(skills) == 4, "marketplace/all-skills: 包含全部四个技能")

    package = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
    check(package.get("name") == "dsh-llm-wiki-skills", "package.json: name 正确")
    check(package.get("license") == "MIT", "package.json: license=MIT")
    patch = package.get("dsh", {}).get("bundle", {}).get("patch")
    check(patch == "./cordis.patch.yml", "package.json: dsh.bundle.patch 正确")
    check((ROOT / "cordis.patch.yml").is_file(), "cordis.patch.yml 存在")


def check_scripts() -> None:
    for path in sorted(ROOT.glob("skills/*/scripts/*.py")):
        try:
            source = path.read_text(encoding="utf-8")
            compile(source, str(path), "exec")
            ok(f"{path.relative_to(ROOT)}: 语法正确")
        except (OSError, SyntaxError) as exc:
            fail(f"{path.relative_to(ROOT)}: 语法错误 {exc}")
        if re.search(r"^\s*(import\s+requests|from\s+requests\s+import)", source, re.MULTILINE):
            fail(f"{path.relative_to(ROOT)}: 不应依赖 requests")
        if "wJJ" + "h" in source:
            fail(f"{path.relative_to(ROOT)}: 脚本不应硬编码用户名")

    loaders = [ROOT / "skills" / skill / "scripts" / "env_loader.py" for skill in SKILLS]
    hashes = {hashlib.sha256(path.read_bytes()).hexdigest() for path in loaders if path.is_file()}
    check(len(hashes) == 1, "四份 env_loader.py 内容一致")


def check_node() -> None:
    node = shutil.which("node")
    if not node:
        warn("未找到 node，跳过 index.js 检查")
        return
    result = subprocess.run(
        [node, "--check", str(ROOT / "index.js")],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    check(result.returncode == 0, "index.js: node --check 通过")

    code = (
        "import {discoverSkills, splitSkillDocument} from './index.js';"
        "import {readFileSync} from 'node:fs';"
        "const skills=discoverSkills();"
        "const names=skills.map(s=>s.name).sort();"
        "const parsed=skills.map(s=>splitSkillDocument(readFileSync(s.skillFile,'utf8')).meta);"
        "console.log(JSON.stringify({names, descriptions: parsed.map(m=>!!m.description), whenToUse: parsed.map(m=>!!m.whenToUse)}));"
    )
    result = subprocess.run(
        [node, "--input-type=module", "-e", code],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        fail(f"index.js: 技能发现失败 {result.stderr.strip()[:300]}")
        return
    data = json.loads(result.stdout.strip())
    check(data["names"] == sorted(SKILLS), "index.js: 发现 4 个技能")
    check(all(data["descriptions"]), "index.js: 四个 description 均可解析")
    check(all(data["whenToUse"]), "index.js: 四个 whenToUse 均可解析")


def check_privacy() -> None:
    env_files = [
        path for path in ROOT.rglob(".env*")
        if path.is_file() and path.name not in {".env.example"}
    ]
    check(not env_files, f"没有真实 .env 文件（发现：{', '.join(str(p) for p in env_files) or '无'}）")

    patterns = {
        "GitHub Token": re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}"),
        "GitHub fine-grained Token": re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}"),
        "Anthropic Key": re.compile(r"\bsk-ant-[A-Za-z0-9_-]{20,}"),
        "Generic sk- Key": re.compile(r"\bsk-[A-Za-z0-9]{32,}"),
        "本机项目路径": re.compile(r"[Cc]:[\\/]+codes[\\/]+llm-wiki"),
    }
    hits: list[str] = []
    for path in text_files():
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for label, pattern in patterns.items():
            if pattern.search(content):
                hits.append(f"{path.relative_to(ROOT)} -> {label}")
    check(not hits, f"无密钥/个人路径（命中：{'; '.join(hits) or '无'}）")

    placeholder = "YOUR_" + "GITHUB"
    leftovers = []
    for path in text_files():
        if path.name == "verify.py":
            continue
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if placeholder in content:
            leftovers.append(str(path.relative_to(ROOT)))
    check(not leftovers, f"发布前占位符已替换（残留：{'; '.join(leftovers) or '无'}）")

    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    for pattern in [".env", ".env.*", "!.env.example", "__pycache__", "output/"]:
        check(pattern in gitignore, f".gitignore 包含 {pattern}")

    npmignore = (ROOT / ".npmignore").read_text(encoding="utf-8")
    for pattern in ["__pycache__", "*.pyc", ".env", "/scripts/"]:
        check(pattern in npmignore, f".npmignore 包含 {pattern}")
    bare_scripts = [
        line.strip() for line in npmignore.splitlines()
        if line.strip() == "scripts/"
    ]
    check(not bare_scripts, ".npmignore 不会误排除 skills/*/scripts/")

    caches = (
        list(ROOT.rglob("__pycache__"))
        + list(ROOT.rglob("*.pyc"))
        + list(ROOT.rglob(".ruff_cache"))
    )
    check(not caches, f"无 __pycache__ / .pyc / .ruff_cache（发现 {len(caches)} 个）")
    check(not (ROOT / "output").exists(), "无 output/ 运行产物")
    generated = list(ROOT.glob("github_stars*.json")) + list(ROOT.glob("stars_scan_*"))
    check(not generated, "无 github_stars*.json / stars_scan_* 运行产物")


def check_links() -> None:
    link_pattern = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
    broken: list[str] = []
    for path in [
        ROOT / "README.md",
        ROOT / "README.en.md",
        *ROOT.glob("skills/*/README.md"),
        *ROOT.glob("skills/*/SKILL.md"),
        *ROOT.glob("docs/credentials/*.md"),
    ]:
        if not path.is_file():
            continue
        content = path.read_text(encoding="utf-8")
        for target in link_pattern.findall(content):
            target = target.strip()
            if not target or target.startswith(("#", "http://", "https://", "mailto:")):
                continue
            relative = target.split("#", 1)[0]
            if not relative:
                continue
            destination = (path.parent / relative).resolve()
            if not destination.exists():
                broken.append(f"{path.relative_to(ROOT)} -> {target}")
    check(not broken, f"README 本地链接有效（失效：{'; '.join(broken) or '无'}）")


def check_fixtures_and_scripts() -> None:
    fixtures = {
        "sample_stars.json": ROOT / "evals" / "fixtures" / "sample_stars.json",
        "sample_combined.json": ROOT / "evals" / "fixtures" / "sample_combined.json",
    }
    for label, path in fixtures.items():
        try:
            json.loads(path.read_text(encoding="utf-8"))
            ok(f"fixture {label}: JSON 合法")
        except (OSError, json.JSONDecodeError) as exc:
            fail(f"fixture {label}: {exc}")

    sync = ROOT / "skills" / "github-stars-sync" / "scripts" / "fetch_stars.py"
    result = run_python(
        [sys.executable, str(sync), "--input", str(fixtures["sample_stars.json"]), "--stdout", "--format", "json"],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        data = json.loads(result.stdout)
        check(isinstance(data, list) and len(data) == 4 and data[0].get("full_name"), "sync: 离线模式可导出 JSON")
    else:
        fail(f"sync: 离线模式失败 {result.stderr.strip()[:300]}")

    report = ROOT / "skills" / "github-stars-version-tracker" / "scripts" / "render_report.py"
    with tempfile.TemporaryDirectory() as temp_dir:
        output = Path(temp_dir) / "report.md"
        result = run_python(
            [sys.executable, str(report), "--input", str(fixtures["sample_combined.json"]), "--output", str(output)],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0 and output.is_file():
            content = output.read_text(encoding="utf-8")
            check("AI/LLM" in content and "爬虫/逆向" in content, "report: 分类表格可渲染")
        else:
            fail(f"report: 渲染失败 {result.stderr.strip()[:300]}")

    snapshot_code = (
        "import sys; sys.path.insert(0, 'skills/github-stars-version-tracker/scripts');"
        "import check_versions as c;"
        "m=c.build_snapshot_map('evals/fixtures/sample_combined.json');"
        "assert len(m)==3 and m['openai/whisper']['tag']=='v20240930';"
        "print('ok')"
    )
    result = run_python(
        [sys.executable, "-c", snapshot_code],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    check(result.returncode == 0, "tracker: 兼容旧 combined.json 快照")

    help_scripts = [
        ROOT / "skills" / "cf-browser-render" / "scripts" / "fetch_markdown.py",
        ROOT / "skills" / "github-stars-sync" / "scripts" / "fetch_stars.py",
        ROOT / "skills" / "github-stars-version-tracker" / "scripts" / "check_versions.py",
        ROOT / "skills" / "github-stars-version-tracker" / "scripts" / "scan_all.py",
        ROOT / "skills" / "github-stars-version-tracker" / "scripts" / "render_report.py",
        ROOT / "skills" / "auto-github-star" / "scripts" / "star_repo.py",
    ]
    for script in help_scripts:
        result = run_python([sys.executable, str(script), "--help"], capture_output=True, text=True)
        check(result.returncode == 0, f"{script.name}: --help 正常")

    star = ROOT / "skills" / "auto-github-star" / "scripts" / "star_repo.py"
    result = run_python(
        [sys.executable, str(star), "--dry-run", "owner/repo"],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        data = json.loads(result.stdout)
        check(data.get("owner/repo") == "would_star", "auto-star: --dry-run 无副作用")
    else:
        fail(f"auto-star: --dry-run 失败 {result.stderr.strip()[:300]}")


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError, OSError):
            pass
    print(f"校验目录：{ROOT}")
    print("=" * 60)
    check_structure()
    check_marketplace()
    check_scripts()
    check_node()
    check_privacy()
    check_links()
    check_fixtures_and_scripts()
    print("=" * 60)
    if warnings:
        print(f"警告 {len(warnings)} 条")
    if errors:
        print(f"失败 {len(errors)} 项：")
        for error in errors:
            print(f"  - {error}")
        return 1
    print("全部检查通过 ✔")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
