"""Pure helpers for the page tree: slugs among siblings and materialised paths."""

from app.core.slug import slugify
from app.modules.wiki.models import MAX_SLUG_CHARS

# Room for a numeric suffix (`-12345`) inside the slug column.
_BASE_SLUG_CHARS = MAX_SLUG_CHARS - 6


def unique_slug(title: str, taken: set[str]) -> str:
    """`onboarding`, then `onboarding-2`, `onboarding-3`, … among siblings."""
    base = slugify(title, max_length=_BASE_SLUG_CHARS)
    if base not in taken:
        return base
    counter = 2
    while f"{base}-{counter}" in taken:
        counter += 1
    return f"{base}-{counter}"


def child_path(parent_path: str | None, slug: str) -> str:
    return f"{parent_path}/{slug}" if parent_path else slug


def depth_of(path: str) -> int:
    """The number of segments: `a` is 1, `a/b` is 2."""
    return path.count("/") + 1
