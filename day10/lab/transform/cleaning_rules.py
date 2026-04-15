"""
Cleaning rules — raw export → cleaned rows + quarantine.

Baseline gồm các failure mode mở rộng (allowlist doc_id, parse ngày, HR stale version).
Sinh viên thêm ≥3 rule mới: mỗi rule phải ghi `metric_impact` (xem README — chống trivial).
"""

from __future__ import annotations

import csv
import hashlib
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

# Khớp export hợp lệ trong lab (mở rộng khi nhóm thêm doc mới — phải đồng bộ contract).
ALLOWED_DOC_IDS = frozenset(
    {
        "policy_refund_v4",
        "sla_p1_2026",
        "it_helpdesk_faq",
        "hr_leave_policy",
    }
)

_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_DMY_SLASH = re.compile(r"^(\d{2})/(\d{2})/(\d{4})$")


def _norm_text(s: str) -> str:
    return " ".join((s or "").strip().split()).lower()


def _stable_chunk_id(doc_id: str, chunk_text: str, seq: int) -> str:
    h = hashlib.sha256(f"{doc_id}|{chunk_text}|{seq}".encode("utf-8")).hexdigest()[:16]
    return f"{doc_id}_{seq}_{h}"


def _normalize_effective_date(raw: str) -> Tuple[str, str]:
    """
    Trả về (iso_date, error_reason).
    iso_date rỗng nếu không parse được.
    """
    s = (raw or "").strip()
    if not s:
        return "", "empty_effective_date"
    if _ISO_DATE.match(s):
        return s, ""
    m = _DMY_SLASH.match(s)
    if m:
        dd, mm, yyyy = m.group(1), m.group(2), m.group(3)
        return f"{yyyy}-{mm}-{dd}", ""
    return "", "invalid_effective_date_format"


def load_raw_csv(path: Path) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    with path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append({k: (v or "").strip() for k, v in r.items()})
    return rows


def clean_rows(
    rows: List[Dict[str, str]],
    *,
    apply_refund_window_fix: bool = True,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Trả về (cleaned, quarantine).

    Baseline (mở rộng theo narrative Day 10):
    1) Quarantine: doc_id không thuộc allowlist (export lạ / catalog sai).
    2) Chuẩn hoá effective_date sang YYYY-MM-DD; quarantine nếu không parse được.
    3) Quarantine: chunk hr_leave_policy có effective_date < 2026-01-01 (bản HR cũ / conflict version).
    4) Quarantine: chunk_text rỗng hoặc effective_date rỗng sau chuẩn hoá.
    5) Loại trùng nội dung chunk_text (giữ bản đầu).
    6) Fix stale refund: policy_refund_v4 chứa '14 ngày làm việc' → 7 ngày.
    """
    quarantine: List[Dict[str, Any]] = []
    seen_text: set[str] = set()
    cleaned: List[Dict[str, Any]] = []
    seq = 0

    for raw in rows:
        doc_id = raw.get("doc_id", "")
        text = raw.get("chunk_text", "")
        eff_raw = raw.get("effective_date", "")
        exported_at = raw.get("exported_at", "")

        if doc_id not in ALLOWED_DOC_IDS:
            quarantine.append({**raw, "reason": "unknown_doc_id"})
            continue

        eff_norm, eff_err = _normalize_effective_date(eff_raw)
        if eff_err == "empty_effective_date":
            quarantine.append({**raw, "reason": "missing_effective_date"})
            continue
        if eff_err == "invalid_effective_date_format":
            quarantine.append({**raw, "reason": eff_err, "effective_date_raw": eff_raw})
            continue

        if doc_id == "hr_leave_policy" and eff_norm < "2026-01-01":
            quarantine.append(
                {
                    **raw,
                    "reason": "stale_hr_policy_effective_date",
                    "effective_date_normalized": eff_norm,
                }
            )
            continue

        if not text:
            quarantine.append({**raw, "reason": "missing_chunk_text"})
            continue

        key = _norm_text(text)
        if key in seen_text:
            quarantine.append({**raw, "reason": "duplicate_chunk_text"})
            continue
        seen_text.add(key)

        fixed_text = text
        if apply_refund_window_fix and doc_id == "policy_refund_v4":
            if "14 ngày làm việc" in fixed_text:
                fixed_text = fixed_text.replace(
                    "14 ngày làm việc",
                    "7 ngày làm việc",
                )
                fixed_text += " [cleaned: stale_refund_window]"

        seq += 1
        cleaned.append(
            {
                "chunk_id": _stable_chunk_id(doc_id, fixed_text, seq),
                "doc_id": doc_id,
                "chunk_text": fixed_text,
                "effective_date": eff_norm,
                "exported_at": exported_at or "",
            }
        )

    return cleaned, quarantine


def write_cleaned_csv(path: Path, rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("chunk_id,doc_id,chunk_text,effective_date,exported_at\n", encoding="utf-8")
        return
    fieldnames = ["chunk_id", "doc_id", "chunk_text", "effective_date", "exported_at"]
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fieldnames})


def write_quarantine_csv(path: Path, rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("chunk_id,doc_id,chunk_text,effective_date,exported_at,reason\n", encoding="utf-8")
        return
    keys: List[str] = []
    seen_k: set[str] = set()
    for r in rows:
        for k in r.keys():
            if k not in seen_k:
                seen_k.add(k)
                keys.append(k)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore", restval="")
        w.writeheader()
        for r in rows:
            w.writerow(r)


from datetime import datetime, timezone

# Phan mo rong Day 10:
# Rule moi 1: bo prefix bien tap nhu "FAQ bo sung:" truoc khi publish/embed.
# Rule moi 2: bo ghi chu van hanh/ghi chu migration trong chunk_text.
# Rule moi 3: chuan hoa exported_at ve ISO-8601 UTC co hau to Z de phuc vu freshness.
# Rule moi 4: bo marker noi bo dang [cleaned: ...] de text publish sach.

_INTERNAL_MARKER = re.compile(r"\s*\[cleaned:[^\]]+\]\s*", re.IGNORECASE)
_PAREN_BLOCK = re.compile(r"\s*\(([^()]*)\)")
_NOISE_NOTE_KEYWORDS = ("ghi chú", "migration", "sync cũ", "policy-v3")
_EDITORIAL_PREFIXES = ("FAQ bổ sung:",)


def _squash_ws(text: str) -> str:
    text = " ".join((text or "").strip().split())
    return re.sub(r"\s+([,.;:!?])", r"\1", text)


def _norm_text(text: str) -> str:
    return _squash_ws(text).lower()


def _normalize_exported_at(raw: str) -> Tuple[str, str]:
    value = (raw or "").strip()
    if not value:
        return "", "missing_exported_at"
    try:
        if value.endswith("Z"):
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        else:
            dt = datetime.fromisoformat(value)
    except ValueError:
        return "", "invalid_exported_at"

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.isoformat().replace("+00:00", "Z"), ""


def _strip_editorial_prefix(text: str) -> Tuple[str, bool]:
    # Rule moi 1: bo prefix bien tap o dau chunk, vi day khong phai noi dung policy.
    value = _squash_ws(text)
    lowered = value.lower()
    for prefix in _EDITORIAL_PREFIXES:
        if lowered.startswith(prefix.lower()):
            return _squash_ws(value[len(prefix) :]), True
    return value, False


def _strip_operational_notes(text: str) -> Tuple[str, bool]:
    # Rule moi 2: bo ghi chu migration/ghi chu van hanh lot vao payload publish.
    changed = False

    def replacer(match: re.Match[str]) -> str:
        nonlocal changed
        note_body = match.group(1).strip().lower()
        if any(keyword in note_body for keyword in _NOISE_NOTE_KEYWORDS):
            changed = True
            return ""
        return match.group(0)

    cleaned = _PAREN_BLOCK.sub(replacer, text)
    return _squash_ws(cleaned), changed


def _strip_internal_markers(text: str) -> Tuple[str, bool]:
    # Rule moi 4: bo marker noi bo sinh ra trong qua trinh clean.
    cleaned, count = _INTERNAL_MARKER.subn(" ", text)
    return _squash_ws(cleaned), count > 0


def _canonicalize_chunk_text(
    text: str,
    *,
    doc_id: str,
    apply_refund_window_fix: bool,
) -> str:
    fixed = _squash_ws(text)
    fixed, _ = _strip_editorial_prefix(fixed)
    fixed, _ = _strip_operational_notes(fixed)

    if apply_refund_window_fix and doc_id == "policy_refund_v4" and "14 ngày làm việc" in fixed:
        fixed = fixed.replace("14 ngày làm việc", "7 ngày làm việc")

    fixed, _ = _strip_internal_markers(fixed)
    return _squash_ws(fixed)


def clean_rows(
    rows: List[Dict[str, str]],
    *,
    apply_refund_window_fix: bool = True,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Tra ve (cleaned_rows, quarantine_rows).

    Cac rule moi duoc them tren nen baseline:
    7. Bo prefix bien tap "FAQ bo sung:" truoc khi dua vao cleaned.
    8. Loai bo ghi chu migration/van hanh bi lot vao chunk_text.
    9. Chuan hoa exported_at thanh ISO-8601 UTC co duoi Z.
    10. Loai bo marker noi bo [cleaned: ...] truoc khi publish.
    """
    quarantine: List[Dict[str, Any]] = []
    cleaned: List[Dict[str, Any]] = []
    seen_text: set[str] = set()
    seq = 0

    for raw in rows:
        doc_id = raw.get("doc_id", "")
        text = raw.get("chunk_text", "")
        eff_raw = raw.get("effective_date", "")
        exported_raw = raw.get("exported_at", "")

        if doc_id not in ALLOWED_DOC_IDS:
            quarantine.append({**raw, "reason": "unknown_doc_id"})
            continue

        eff_norm, eff_err = _normalize_effective_date(eff_raw)
        if eff_err == "empty_effective_date":
            quarantine.append({**raw, "reason": "missing_effective_date"})
            continue
        if eff_err == "invalid_effective_date_format":
            quarantine.append({**raw, "reason": eff_err, "effective_date_raw": eff_raw})
            continue

        if doc_id == "hr_leave_policy" and eff_norm < "2026-01-01":
            quarantine.append(
                {
                    **raw,
                    "reason": "stale_hr_policy_effective_date",
                    "effective_date_normalized": eff_norm,
                }
            )
            continue

        # Rule moi 3: exported_at phai duoc chuan hoa de monitoring/freshness doc on dinh.
        exported_at, exported_err = _normalize_exported_at(exported_raw)
        if exported_err:
            quarantine.append({**raw, "reason": exported_err, "exported_at_raw": exported_raw})
            continue

        # Rule moi 1, 2, 4: lam sach text publish truoc khi dedupe va tao chunk_id.
        fixed_text = _canonicalize_chunk_text(
            text,
            doc_id=doc_id,
            apply_refund_window_fix=apply_refund_window_fix,
        )
        if not fixed_text:
            quarantine.append({**raw, "reason": "missing_chunk_text"})
            continue

        key = _norm_text(fixed_text)
        if key in seen_text:
            quarantine.append({**raw, "reason": "duplicate_chunk_text"})
            continue
        seen_text.add(key)

        seq += 1
        cleaned.append(
            {
                "chunk_id": _stable_chunk_id(doc_id, fixed_text, seq),
                "doc_id": doc_id,
                "chunk_text": fixed_text,
                "effective_date": eff_norm,
                "exported_at": exported_at,
            }
        )

    return cleaned, quarantine
