"""The built frontend (`HERD_STATIC_DIR`), served by the public app.

- Files that exist under the directory are served as they are; every other path
  outside `/api` gets `index.html`, and the client-side router takes over. Under
  `/api` an unknown path stays a JSON 404, and a missing `/assets/*` file is a 404
  (a chunk of an older build must fail visibly, not turn into HTML).
- `/assets/*` names carry a content hash: cached for a year, immutable. Everything
  else (index.html, favicon) is revalidated on every use.
- No path can reach outside the directory: `..` segments are refused and the
  resolved file (symlinks followed) must lie inside it.
- Every response here carries the SPA's Content-Security-Policy (the other security
  headers come from `core.security_headers` for every response). The policy is
  `default-src 'self'` (own scripts, styles, fonts, images and API; no eval) plus
  the one thing the built app was shown to need (Playwright, console clean):
  `<style>` elements, which Radix dialogs and menus inject to lock scrolling, with
  content computed at run time (scrollbar width), so no hash can name them.
"""

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse

from app.core.errors import NotFound

CONTENT_SECURITY_POLICY = "; ".join(
    [
        "default-src 'self'",
        "style-src 'self' 'unsafe-inline'",
        "object-src 'none'",
        "frame-ancestors 'none'",
        "base-uri 'none'",
        "form-action 'self'",
    ]
)
SECURITY_HEADERS = {"Content-Security-Policy": CONTENT_SECURITY_POLICY}
_ALL_METHODS = ["GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]
IMMUTABLE = "public, max-age=31536000, immutable"
REVALIDATE = "no-cache"


def mount_spa(app: FastAPI, static_dir: Path) -> None:
    """Add the catch-all route; call after every other route is included."""
    root = static_dir.resolve()
    index = root / "index.html"
    if not index.is_file():
        raise RuntimeError(f"HERD_STATIC_DIR has no index.html: {root}")

    @app.api_route("/api/{rest:path}", methods=_ALL_METHODS, include_in_schema=False)
    async def api_unknown(rest: str) -> None:
        # Any method: an API client's typo is a 404, not the SPA's 405.
        raise NotFound(code="not_found")

    @app.api_route("/{path:path}", methods=["GET", "HEAD"], include_in_schema=False)
    async def spa(path: str) -> FileResponse:
        if path == "api":
            raise NotFound(code="not_found")
        file = _inside(root, path)
        if file is not None:
            cache = IMMUTABLE if path.startswith("assets/") else REVALIDATE
            return _file(file, cache)
        if path.startswith("assets/"):
            raise NotFound(code="not_found")
        return _file(index, REVALIDATE)


def _inside(root: Path, path: str) -> Path | None:
    """The regular file `path` names inside `root`, or None."""
    parts = path.replace("\\", "/").split("/")
    if any(part in ("..", ".") for part in parts) or "\x00" in path:
        return None
    try:
        file = root.joinpath(*[p for p in parts if p]).resolve()
    except (OSError, ValueError):
        return None
    if not file.is_relative_to(root) or not file.is_file():
        return None
    return file


def _file(file: Path, cache: str) -> FileResponse:
    return FileResponse(file, headers={**SECURITY_HEADERS, "Cache-Control": cache})
