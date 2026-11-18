"""The device hint of a login session (J8): which browser on which system, from the
User-Agent header, never a version (a version says little to the person and much to
someone who fingerprints). Kept short; anything else of the header is dropped."""

import re

HINT_MAX = 40  # the longest name of a client that is no browser

# Order matters: Edge and Opera also say Chrome, Chrome also says Safari.
_BROWSERS = (
    ("Edg/", "Edge"),
    ("EdgA/", "Edge"),
    ("EdgiOS/", "Edge"),
    ("OPR/", "Opera"),
    ("Firefox/", "Firefox"),
    ("FxiOS/", "Firefox"),
    ("CriOS/", "Chrome"),
    ("Chrome/", "Chrome"),
    ("Safari/", "Safari"),
)
_SYSTEMS = (
    ("iPhone", "iOS"),
    ("iPad", "iOS"),
    ("Android", "Android"),
    ("CrOS", "ChromeOS"),
    ("Windows", "Windows"),
    ("Mac OS X", "macOS"),
    ("Macintosh", "macOS"),
    ("Linux", "Linux"),
)
_PRODUCT = re.compile(r"[A-Za-z][A-Za-z0-9._-]*")


def device_hint(user_agent: str | None) -> str | None:
    """`Firefox · Linux`, `Safari · iOS`; a client that is no browser by its product
    name alone (`curl`); None without a usable header."""
    if not user_agent:
        return None
    browser = next((name for token, name in _BROWSERS if token in user_agent), None)
    if browser is None or not user_agent.startswith("Mozilla/"):
        product = _PRODUCT.match(user_agent)
        return product.group(0)[:HINT_MAX] if product else None
    system = next((name for token, name in _SYSTEMS if token in user_agent), None)
    return f"{browser} · {system}" if system else browser
