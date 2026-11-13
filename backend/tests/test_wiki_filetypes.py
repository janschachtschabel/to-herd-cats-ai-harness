"""Type detection reads a bounded prefix and never parses a whole file (review M2 R6):
JSON is text by the same rules as TXT, Markdown and CSV."""

import io
import tracemalloc

from app.modules.wiki import filetypes

FLAT = 4 * 1024 * 1024


def _detect(data: bytes, name: str) -> tuple[filetypes.FileType, int]:
    tracemalloc.start()
    try:
        found = filetypes.detect(data[:4096], True, io.BytesIO(data), name)
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    return found, peak


def test_a_large_json_file_is_not_parsed() -> None:
    data = b"[" + b"[]," * 8_000_000 + b"[]]"  # 24 MB of nested empties
    found, peak = _detect(data, "x.json")
    assert found is filetypes.JSON
    assert peak < FLAT, peak


def test_json_is_text_by_the_text_rules() -> None:
    assert _detect(b"{not json", "daten.json")[0] is filetypes.JSON  # served as a download
    assert _detect(b'{"a": [1, 2]}', "daten.json")[0] is filetypes.JSON
