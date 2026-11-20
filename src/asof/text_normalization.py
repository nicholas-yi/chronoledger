"""Declared ingestion normalization for real filing text, applied before windows reach the strict verifier.

Only two benign, well-known artifacts are changed, and every change is counted:
- C1 control characters U+0080-U+009F that are Windows-1252 bytes mis-decoded as Latin-1 become the
  cp1252 character a reader of the filing sees (smart quotes, dashes, bullets, trademark sign).
  The five undefined cp1252 positions are left in place, so the integrity guard still defers them.
- Invisible formatting characters (zero-width space/joiners, word joiner, BOM, soft hyphen) are removed,
  yielding the text as rendered. Vocabulary guards then see words such as "restated" that these
  characters would otherwise split.
Bidirectional controls and other format characters are kept: they change the visible order of text,
so the verifier's text-integrity check still sends such sources to review.
"""

from __future__ import annotations

from collections import Counter

INVISIBLE_FORMAT = frozenset("\u200b\u200c\u200d\u2060\ufeff\u00ad")


def normalize_filing_text(text: str) -> tuple[str, dict[str, int]]:
    counts: Counter = Counter()
    out = []
    for char in text:
        code = ord(char)
        if 0x80 <= code <= 0x9F:
            try:
                out.append(bytes([code]).decode("cp1252"))
                counts["cp1252_c1_repaired"] += 1
            except UnicodeDecodeError:
                out.append(char)
                counts["c1_undefined_kept"] += 1
        elif char in INVISIBLE_FORMAT:
            counts["invisible_format_removed"] += 1
        else:
            out.append(char)
    return "".join(out), dict(counts)
