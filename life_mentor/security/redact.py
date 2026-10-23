"""PII redaction for logs and journals (LM02).

``redact(text)`` NFKC-normalises the text (so NBSP, full-width digits and other
compatibility forms collapse to plain ASCII), then masks, in this order:

  - email addresses                          -> ``[EMAIL]``
  - Indian PAN (``ABCDE1234F``)              -> ``[PAN]``
  - digit runs of 9+ digits, allowing up to two separator characters
    (whitespace, ``.``, ``-``, ``/``) between digits, classified by count:
      * ``+91`` / ``91`` prefix + 10-digit mobile, 10-digit mobile starting
        6-9, or ``0`` + 10-digit mobile      -> ``[PHONE]``
      * exactly 12 digits                    -> ``[AADHAAR]``
      * anything else with 9+ digits         -> ``[ACCOUNT]`` (bank/card numbers)

Inside ``http(s)://`` URLs the PATH is left alone for digit runs (citations carry
ISBNs and document ids such as ``/item/9789240015128``); emails/PANs are still
masked there. In the query string and fragment, where personal data travels, only
a single ``-`` may join digits and 9+-digit runs are masked (SPEC-GAP LM-G34).

Redaction is deliberately aggressive: a false positive (masking a long
non-sensitive number) is cheap, a false negative leaks PII. If nothing is
masked the ORIGINAL text is returned unchanged (normalisation alone never
alters text). Placeholders contain no digits, so ``redact`` is idempotent.
Dates (``2026-10-11``) and ordinary amounts (< 9 digits, or comma-grouped)
are left alone.
"""

from __future__ import annotations

import re
import unicodedata

__all__ = ["redact"]

_EMAIL = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9\-]+(?:\.[A-Za-z0-9\-]+)+")
_PAN = re.compile(r"(?<![A-Za-z0-9])[A-Z]{5}[0-9]{4}[A-Z](?![A-Za-z0-9])")
# A run of 9+ digits, optionally with a leading "+", allowing up to two
# separator characters between digits. Not glued to letters/digits on either side.
_DIGIT_RUN = re.compile(r"(?<![A-Za-z0-9+])\+?\d(?:[\s.\-/]{0,2}\d){8,}(?![A-Za-z0-9])")
# Inside URLs: only a single hyphen may join digits.
_DIGIT_RUN_URL = re.compile(r"(?<![A-Za-z0-9+])\+?\d(?:-?\d){8,}(?![A-Za-z0-9])")
_URL = re.compile(r"https?://\S+", re.IGNORECASE)


def _classify(match: re.Match[str]) -> str:
    raw = match.group(0)
    digits = re.sub(r"\D", "", raw)
    n = len(digits)
    mobile = re.compile(r"[6-9]\d{9}")
    if n == 10 and mobile.fullmatch(digits):
        return "[PHONE]"
    if n == 11 and digits.startswith("0") and mobile.fullmatch(digits[1:]):
        return "[PHONE]"
    if n == 12 and digits.startswith("91") and mobile.fullmatch(digits[2:]) and (
        raw.startswith("+") or raw[2:3] in (" ", "-")
    ):
        return "[PHONE]"
    if n == 12:
        return "[AADHAAR]"
    return "[ACCOUNT]"


def redact(text: str) -> str:
    """Return *text* with PAN/Aadhaar/phone/email/account numbers masked."""
    if not isinstance(text, str):
        raise TypeError("redact() expects str")
    norm = unicodedata.normalize("NFKC", text)
    pieces: list[str] = []
    pos = 0
    for url in _URL.finditer(norm):
        pieces.append(_mask(norm[pos:url.start()], _DIGIT_RUN))
        pieces.append(_mask_url(url.group(0)))
        pos = url.end()
    pieces.append(_mask(norm[pos:], _DIGIT_RUN))
    out = "".join(pieces)
    return text if out == norm else out


def _mask_url(url: str) -> str:
    """Path keeps numeric identifiers (ISBNs, document ids); query/fragment are masked."""
    cut = min((i for i in (url.find("?"), url.find("#")) if i >= 0), default=len(url))
    path = _PAN.sub("[PAN]", _EMAIL.sub("[EMAIL]", url[:cut]))
    return path + _mask(url[cut:], _DIGIT_RUN_URL)


def _mask(segment: str, digit_run: re.Pattern[str]) -> str:
    out = _EMAIL.sub("[EMAIL]", segment)
    out = _PAN.sub("[PAN]", out)
    return digit_run.sub(_classify, out)
