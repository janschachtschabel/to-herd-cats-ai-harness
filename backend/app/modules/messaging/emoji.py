"""One emoji, as a reaction (spec 6.1): exactly one emoji grapheme, checked against
Unicode properties, never free text.

Accepted (UTS #51): a pictographic character (`Extended_Pictographic`), optionally
with the emoji presentation selector (U+FE0F), a skin tone (U+1F3FB..U+1F3FF) or a
tag sequence (subdivision flags); several of those joined by ZERO WIDTH JOINER; a
pair of regional indicators (a flag); a keycap (`0`-`9`, `#`, `*`, U+FE0F, U+20E3).

`EXTENDED_PICTOGRAPHIC` is the property's table of Unicode 15.0 (emoji-data.txt),
generated with Perl's Unicode database; the standard library knows no emoji
properties, and a dependency for one table is not worth it.
"""

from bisect import bisect_right

MAX_EMOJI_CHARS = 32  # code points: the longest family sequences stay well below

EXTENDED_PICTOGRAPHIC: tuple[tuple[int, int], ...] = (
    (0xA9, 0xA9),
    (0xAE, 0xAE),
    (0x203C, 0x203C),
    (0x2049, 0x2049),
    (0x2122, 0x2122),
    (0x2139, 0x2139),
    (0x2194, 0x2199),
    (0x21A9, 0x21AA),
    (0x231A, 0x231B),
    (0x2328, 0x2328),
    (0x2388, 0x2388),
    (0x23CF, 0x23CF),
    (0x23E9, 0x23F3),
    (0x23F8, 0x23FA),
    (0x24C2, 0x24C2),
    (0x25AA, 0x25AB),
    (0x25B6, 0x25B6),
    (0x25C0, 0x25C0),
    (0x25FB, 0x25FE),
    (0x2600, 0x2605),
    (0x2607, 0x2612),
    (0x2614, 0x2685),
    (0x2690, 0x2705),
    (0x2708, 0x2712),
    (0x2714, 0x2714),
    (0x2716, 0x2716),
    (0x271D, 0x271D),
    (0x2721, 0x2721),
    (0x2728, 0x2728),
    (0x2733, 0x2734),
    (0x2744, 0x2744),
    (0x2747, 0x2747),
    (0x274C, 0x274C),
    (0x274E, 0x274E),
    (0x2753, 0x2755),
    (0x2757, 0x2757),
    (0x2763, 0x2767),
    (0x2795, 0x2797),
    (0x27A1, 0x27A1),
    (0x27B0, 0x27B0),
    (0x27BF, 0x27BF),
    (0x2934, 0x2935),
    (0x2B05, 0x2B07),
    (0x2B1B, 0x2B1C),
    (0x2B50, 0x2B50),
    (0x2B55, 0x2B55),
    (0x3030, 0x3030),
    (0x303D, 0x303D),
    (0x3297, 0x3297),
    (0x3299, 0x3299),
    (0x1F000, 0x1F0FF),
    (0x1F10D, 0x1F10F),
    (0x1F12F, 0x1F12F),
    (0x1F16C, 0x1F171),
    (0x1F17E, 0x1F17F),
    (0x1F18E, 0x1F18E),
    (0x1F191, 0x1F19A),
    (0x1F1AD, 0x1F1E5),
    (0x1F201, 0x1F20F),
    (0x1F21A, 0x1F21A),
    (0x1F22F, 0x1F22F),
    (0x1F232, 0x1F23A),
    (0x1F23C, 0x1F23F),
    (0x1F249, 0x1F3FA),
    (0x1F400, 0x1F53D),
    (0x1F546, 0x1F64F),
    (0x1F680, 0x1F6FF),
    (0x1F774, 0x1F77F),
    (0x1F7D5, 0x1F7FF),
    (0x1F80C, 0x1F80F),
    (0x1F848, 0x1F84F),
    (0x1F85A, 0x1F85F),
    (0x1F888, 0x1F88F),
    (0x1F8AE, 0x1F8FF),
    (0x1F90C, 0x1F93A),
    (0x1F93C, 0x1F945),
    (0x1F947, 0x1FAFF),
    (0x1FC00, 0x1FFFD),
)
_STARTS = [start for start, _ in EXTENDED_PICTOGRAPHIC]

ZWJ = 0x200D
PRESENTATION = 0xFE0F
KEYCAP = 0x20E3
KEYCAP_BASES = frozenset(map(ord, "0123456789#*"))
SKIN_TONES = range(0x1F3FB, 0x1F400)
REGIONAL_INDICATORS = range(0x1F1E6, 0x1F200)
BLACK_FLAG = 0x1F3F4
TAG_CHARACTERS = range(0xE0020, 0xE007F)
CANCEL_TAG = 0xE007F


def _pictographic(code: int) -> bool:
    i = bisect_right(_STARTS, code) - 1
    return i >= 0 and code <= EXTENDED_PICTOGRAPHIC[i][1]


def _element(codes: list[int], i: int) -> int:
    """The end of the emoji element starting at `i`, or -1 if there is none."""
    if i >= len(codes) or not _pictographic(codes[i]):
        return -1
    base, i = codes[i], i + 1
    if i < len(codes) and codes[i] == PRESENTATION:
        i += 1
    if i < len(codes) and codes[i] in SKIN_TONES:
        i += 1
    if base == BLACK_FLAG and i < len(codes) and codes[i] in TAG_CHARACTERS:
        while i < len(codes) and codes[i] in TAG_CHARACTERS:
            i += 1
        if i >= len(codes) or codes[i] != CANCEL_TAG:
            return -1
        i += 1
    return i


def is_emoji(text: str) -> bool:
    """Whether `text` is exactly one emoji."""
    codes = [ord(c) for c in text]
    if not codes or len(codes) > MAX_EMOJI_CHARS:
        return False
    if len(codes) == 2 and all(c in REGIONAL_INDICATORS for c in codes):
        return True
    if codes[0] in KEYCAP_BASES:
        return codes[1:] in ([KEYCAP], [PRESENTATION, KEYCAP])
    i = _element(codes, 0)
    while 0 < i < len(codes):
        if codes[i] != ZWJ:
            return False
        i = _element(codes, i + 1)
    return i == len(codes)
