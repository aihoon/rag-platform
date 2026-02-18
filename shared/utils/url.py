"""URL parsing helpers shared across services."""

from __future__ import annotations

from urllib.parse import urlparse


def parse_url(url: str) -> tuple[str, int, str]:
    # noinspection HttpUrlsUsage
    normalized_url = url if "://" in url else f"http://{url}"
    parsed = urlparse(normalized_url)
    host = parsed.hostname or "0.0.0.0"
    if parsed.port is not None:
        port = parsed.port
    else:
        port = 443 if parsed.scheme == "https" else 80
    root_path = parsed.path.rstrip("/")
    if root_path == "/":
        root_path = ""
    return host, port, root_path
