
"""Detect likely wrong-target matches from observed semantic context."""
import re
import unicodedata
from urllib.parse import urljoin, urlsplit

DEFAULT_THRESHOLD = 0.20


def check_link_destination(page_url, recorded_href, candidate_href):
    """Match a read-only link whose destination is part of the recorded task contract."""
    source = urlsplit(page_url)
    recorded = urlsplit(urljoin(page_url, recorded_href))
    candidate = urlsplit(urljoin(page_url, candidate_href))
    matches = bool(recorded_href and candidate_href and source.scheme in ("http", "https")
                   and (source.scheme, source.netloc) == (recorded.scheme, recorded.netloc)
                   and recorded == candidate)
    return {"likely_wrong": not matches,
            "reason": "same_recorded_destination" if matches else "different_recorded_destination"}


def _terms(value):
    normalized = unicodedata.normalize("NFKD", str(value or "").lower())
    normalized = "".join(
        ch for ch in normalized if not unicodedata.combining(ch)
    )
    return {
        x for x in re.findall(r"[a-z0-9]+", normalized)
        if len(x) > 1
        and x not in {"cua", "cho", "voi", "thanh", "nut", "form"}
    }


def check_found(descriptor, candidate, objective="", threshold=DEFAULT_THRESHOLD):
    """Return diagnostics; low objective/context overlap means wrong target is plausible."""
    if not isinstance(descriptor, dict) or not isinstance(candidate, dict):
        raise TypeError("descriptor and candidate must be dictionaries")

    if not 0 <= threshold <= 1:
        raise ValueError("threshold must be between 0 and 1")

    goal = _terms(objective)

    observed = _terms(" ".join(
        str(candidate.get(k, ""))
        for k in ("text", "label", "name", "placeholder", "context_text")
    ))

    descriptor_terms = _terms(" ".join(
        str(descriptor.get(k, ""))
        for k in ("text", "label", "name", "placeholder")
    ))

    # Prefer discriminative descriptor terms.
    generic_terms = {
        "thong", "tin", "luu", "doi", "nhap",
        "so", "khong", "nhan", "vien",
        "them", "tao", "mo", "chon", "cap",
        "nhat", "sua", "xoa", "san", "pham",
    }

    anchors = descriptor_terms - generic_terms

    # If descriptor contains only generic action words,
    # use the positive objective clause as fallback.
    if not anchors:
        positive_clause = re.split(
            r"[,;]|\bkhong\b",
            str(objective or "").lower(),
            maxsplit=1
        )[0]
        anchors = _terms(positive_clause) - generic_terms

    if not anchors:
        return {
            "found": True,
            "score": 0.0,
            "threshold": threshold,
            "likely_wrong": True,
            "reason": "insufficient_evidence",
        }
    score = len(anchors & observed) / len(anchors)

    return {
        "found": True,
        "score": round(score, 4),
        "threshold": threshold,
        "likely_wrong": score < threshold,
        "reason": (
            "context_mismatch"
            if score < threshold
            else "context_supported"
        )
    }
