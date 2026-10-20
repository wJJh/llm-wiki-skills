#!/usr/bin/env python3
"""调用 Cloudflare Browser Rendering API 获取网页 Markdown。

环境变量（会从技能附近的 .env 自动加载，也可用 --env-file 指定）：
    CF_BROWSER_RENDERING_TOKEN - Cloudflare API Token
    CF_ACCOUNT_ID              - Cloudflare Account ID
    HTTPS_PROXY / HTTP_PROXY   - 可选；部分网络访问 Cloudflare 需要代理 IP

用法：
    python fetch_markdown.py <url> [<url> ...]
    python fetch_markdown.py <url> -o article.md
    python fetch_markdown.py --proxy http://127.0.0.1:7890 <url>
    python fetch_markdown.py --env-file ../../.env https://example.com
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request

from env_loader import configure_stdio, load_env


def fetch_markdown(
    url: str,
    token: str | None = None,
    account_id: str | None = None,
    timeout: int = 60,
    proxy: str | None = None,
) -> str:
    """调用 Cloudflare Browser Rendering /markdown 端点，返回 Markdown。

    proxy 为空时使用 urllib 默认行为（会读取 HTTPS_PROXY / HTTP_PROXY）。
    """
    token = token or os.environ.get("CF_BROWSER_RENDERING_TOKEN")
    account_id = account_id or os.environ.get("CF_ACCOUNT_ID")

    if not token:
        raise RuntimeError(
            "缺少 Cloudflare API Token。请在 .env 中设置 "
            "CF_BROWSER_RENDERING_TOKEN，或使用 --env-file 指定配置文件。"
        )
    if not account_id:
        raise RuntimeError(
            "缺少 Cloudflare Account ID。请在 .env 中设置 CF_ACCOUNT_ID，"
            "或使用 --env-file 指定配置文件。"
        )

    if proxy and "://" not in proxy:
        proxy = "http://" + proxy
    if proxy and proxy.lower().startswith(("socks5://", "socks5h://", "socks4://")):
        raise RuntimeError(
            "不支持 SOCKS5/SOCKS4 代理；请先在代理客户端开启本地 HTTP 混合端口，"
            "再把 http://127.0.0.1:<port> 填入 HTTPS_PROXY 或 --proxy。"
        )

    api_url = (
        f"https://api.cloudflare.com/client/v4/accounts/{account_id}"
        "/browser-rendering/markdown"
    )
    payload = json.dumps({"url": url}).encode("utf-8")
    request = urllib.request.Request(
        api_url,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
        method="POST",
    )

    if proxy:
        opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({"http": proxy, "https": proxy})
        )
    else:
        # 默认 opener 会读取 HTTPS_PROXY / HTTP_PROXY。
        opener = urllib.request.build_opener()

    try:
        with opener.open(request, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:500]
        if exc.code == 401:
            raise RuntimeError(
                "Cloudflare 返回 401：Token 无效或已过期，请更新 "
                "CF_BROWSER_RENDERING_TOKEN。"
            ) from exc
        if exc.code == 403:
            raise RuntimeError(
                "Cloudflare 返回 403：Token 缺少 Account > Browser Rendering > Edit 权限；"
                "若权限无误，也可能是当前出口 IP 被 Cloudflare 限制，请更换代理 IP。"
            ) from exc
        if exc.code == 429:
            raise RuntimeError(
                "Cloudflare 返回 429：Browser Rendering 配额或速率限制，请稍后重试。"
            ) from exc
        raise RuntimeError(f"Cloudflare 返回 HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(
            f"网络错误：{exc.reason}。若所在网络无法直连 api.cloudflare.com"
            "（常见于国内网络或 IP 受限），请在 .env 设置 HTTPS_PROXY，"
            "或使用 --proxy http://127.0.0.1:7890。"
        ) from exc
    except TimeoutError as exc:
        raise RuntimeError(
            f"请求超时（{timeout}s）。可调大 --timeout；若无法直连 Cloudflare，"
            "请配置 HTTPS_PROXY 或 --proxy 后重试。"
        ) from exc

    if not data.get("success"):
        errors = data.get("errors") or data.get("messages") or data
        raise RuntimeError(f"Cloudflare API 调用失败：{errors}")

    return data.get("result", "")


def main() -> int:
    configure_stdio()
    parser = argparse.ArgumentParser(
        description="把网页渲染并转换为 Markdown（Cloudflare Browser Rendering）"
    )
    parser.add_argument("urls", nargs="+", help="一个或多个 http(s) URL")
    parser.add_argument("-o", "--output", help="输出文件（仅支持单个 URL）")
    parser.add_argument("--timeout", type=int, default=60, help="单次请求超时秒数（默认 60）")
    parser.add_argument(
        "--proxy",
        help="HTTP/HTTPS 代理，如 http://127.0.0.1:7890；默认读取 HTTPS_PROXY/HTTP_PROXY",
    )
    parser.add_argument("--env-file", help="指定 .env 文件路径")
    parser.add_argument("--verbose-env", action="store_true", help="打印实际加载的 env 文件")
    args = parser.parse_args()

    load_env(explicit=args.env_file, verbose=args.verbose_env)

    proxy = args.proxy or os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY")

    if args.output and len(args.urls) > 1:
        parser.error("--output 只能与单个 URL 一起使用")

    chunks: list[str] = []
    for index, url in enumerate(args.urls, start=1):
        try:
            markdown = fetch_markdown(url, timeout=args.timeout, proxy=proxy)
        except RuntimeError as exc:
            print(f"[错误] {url}: {exc}", file=sys.stderr)
            return 1
        if len(args.urls) > 1:
            chunks.append(f"<!-- source: {url} -->\n\n{markdown}")
        else:
            chunks.append(markdown)
        print(f"[完成] {index}/{len(args.urls)} {url}", file=sys.stderr)

    content = "\n\n---\n\n".join(chunks)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as handle:
            handle.write(content)
        print(f"[保存] {args.output}", file=sys.stderr)
    else:
        print(content)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
