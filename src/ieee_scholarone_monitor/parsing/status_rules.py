from __future__ import annotations

import re


STATUS_KEYWORDS = (
    "submitted",
    "review",
    "decision",
    "revision",
    "editor",
    "awaiting",
    "processing",
    "accept",
    "accepted",
    "reject",
    "rejected",
    "withdrawn",
    "published",
    "transferred",
    "completed",
    "with reviewer",
    "with editor",
    "with associate editor",
    "with editor-in-chief",
)

TERMINAL_STATUS_KEYWORDS = (
    "accept",
    "accepted",
    "published",
    "reject",
    "rejected",
    "withdrawn",
    "transferred",
    "completed",
)


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def has_status_signal(value: str) -> bool:
    lowered = value.lower()
    return any(keyword in lowered for keyword in STATUS_KEYWORDS)


def is_terminal_status(value: str) -> bool:
    lowered = value.strip().lower()
    return any(keyword in lowered for keyword in TERMINAL_STATUS_KEYWORDS)


def status_score(value: str) -> int:
    lowered = value.lower()
    return sum(1 for keyword in STATUS_KEYWORDS if keyword in lowered)


def normalize_title(value: str) -> str:
    text = clean_text(value)
    text = re.sub(r"\bView Submission\b.*$", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\bSubmitting Author\b.*$", "", text, flags=re.IGNORECASE)
    return text.strip(" -|")


def identity_title(value: str) -> str:
    text = normalize_title(value).lower()
    text = re.sub(r"[^\w\s:;-]", "", text)
    return clean_text(text)


def looks_like_date_token(value: str) -> bool:
    text = value.strip().lower()
    months = r"jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec"
    patterns = [
        rf"(?:{months})[-_ ]?\d{{2,4}}",
        rf"\d{{1,2}}[-_ ](?:{months})[-_ ]\d{{2,4}}",
        r"\d{4}[-_/]\d{1,2}[-_/]\d{1,2}",
    ]
    return any(re.fullmatch(pattern, text) for pattern in patterns)
