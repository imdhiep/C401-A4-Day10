"""
Cleaning rules — raw export → cleaned rows + quarantine.

Baseline (rules 1–6, nhận từ sprint 1):
  1. Quarantine: doc_id không thuộc allowlist (export lạ / catalog sai).
  2. Chuẩn hoá effective_date → YYYY-MM-DD; quarantine nếu rỗng hoặc sai format.
  3. Quarantine: hr_leave_policy với effective_date < 2026-01-01 (bản cũ / conflict version).
  4. Quarantine: chunk_text rỗng sau khi đã chuẩn hoá text.
  5. Loại trùng chunk_text (giữ bản đầu tiên trong lần run).
  6. Fix stale refund: policy_refund_v4 chứa '14 ngày làm việc' → 7 ngày.

Mở rộng nhóm Sprint 2 (rules 7–10):
  7. Loại bỏ prefix biên tập như "FAQ bổ sung:" trước khi publish/embed.
     metric_impact: 1 chunk trên CSV mẫu (row 10) có text bị transform;
     inject row "FAQ bổ sung: ..." → text gọn hơn; E7 FAIL nếu rule bị bỏ qua.
  8. Loại bỏ ghi chú vận hành/migration bị lọt vào payload (parenthetical chứa keyword nội bộ).
     metric_impact: 1 chunk trên CSV mẫu (row 3) có "(ghi chú: bản sync cũ policy-v3 — lỗi migration)"
     stripped; E7 FAIL trước khi rule 8 áp dụng.
  9. Chuẩn hoá exported_at → ISO-8601 UTC có hậu tố Z; quarantine nếu thiếu/sai format.
     metric_impact: tất cả row cleaned có exported_at nhất quán dạng "…Z";
     inject row exported_at="" → +1 quarantine (reason: missing_exported_at);
     E8 FAIL nếu rule bị bỏ qua.
  10. Loại bỏ marker nội bộ dạng [cleaned: ...] trước khi đưa vào vector store.
      metric_impact: inject row chứa "[cleaned: stale_refund_window]" trong text
      → marker stripped trước publish; text publish sạch; E7 FAIL nếu rule bị bỏ qua.
"""

from __future__ import annotations

import csv
import hashlib
import re
from datetime import datetime, timezone
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

# Rule 10: marker nội bộ dạng [cleaned: ...]
_INTERNAL_MARKER = re.compile(r"\s*\[cleaned:[^\]]+\]\s*", re.IGNORECASE)

# Rule 8: parenthetical chứa keyword noise vận hành
_PAREN_BLOCK = re.compile(r"\s*\(([^()]*)\)")
_NOISE_NOTE_KEYWORDS = ("ghi chú", "migration", "sync cũ", "policy-v3")

# Rule 7: prefix biên tập cần strip trước publish
_EDITORIAL_PREFIXES = ("FAQ bổ sung:",)


# ---------------------------------------------------------------------------
# Helper: chuẩn hoá khoảng trắng
# ---------------------------------------------------------------------------

def _squash_ws(text: str) -> str:
    """Chuẩn hoá khoảng trắng thừa và dấu câu dính vào whitespace."""
    text = " ".join((text or "").strip().split())
    return re.sub(r"\s+([,.;:!?])", r"\1", text)


def _norm_text(text: str) -> str:
    """Chuẩn hoá text để so sánh dedupe (lowercase + squash ws)."""
    return _squash_ws(text).lower()


# ---------------------------------------------------------------------------
# Rule 2 helper: chuẩn hoá effective_date
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Rule 9 helper: chuẩn hoá exported_at → ISO-8601 UTC Z
# ---------------------------------------------------------------------------

def _normalize_exported_at(raw: str) -> Tuple[str, str]:
    """
    Rule 9: Chuẩn hoá exported_at → ISO-8601 UTC có hậu tố Z.
    Trả về (normalized_str, error_reason).

    Chấp nhận:
    - "2026-04-10T08:00:00"    → assume UTC → "2026-04-10T08:00:00Z"
    - "2026-04-10T08:00:00Z"   → "2026-04-10T08:00:00Z"
    - "2026-04-10T08:00:00+07:00" → chuyển UTC
    Quarantine nếu rỗng hoặc sai format (invalid_exported_at / missing_exported_at).
    """
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


# ---------------------------------------------------------------------------
# Rules 7, 8, 10 helpers: làm sạch chunk_text trước publish
# ---------------------------------------------------------------------------

def _strip_editorial_prefix(text: str) -> Tuple[str, bool]:
    """
    Rule 7: Loại bỏ prefix biên tập như "FAQ bổ sung:" ở đầu chunk.
    Những prefix này không phải nội dung policy và không nên đi vào vector store.
    metric_impact: row 10 CSV mẫu — "FAQ bổ sung: đổi mật khẩu..." → "đổi mật khẩu..."
    """
    value = _squash_ws(text)
    lowered = value.lower()
    for prefix in _EDITORIAL_PREFIXES:
        if lowered.startswith(prefix.lower()):
            return _squash_ws(value[len(prefix):]), True
    return value, False


def _strip_operational_notes(text: str) -> Tuple[str, bool]:
    """
    Rule 8: Loại bỏ ghi chú vận hành/migration bị lọt vào payload publish.
    Phát hiện dấu ngoặc đơn chứa keyword nội bộ (migration, ghi chú, sync cũ, policy-v3).
    metric_impact: row 3 CSV mẫu — "(ghi chú: bản sync cũ policy-v3 — lỗi migration)" stripped.
    """
    changed = False

    def replacer(match: re.Match) -> str:
        nonlocal changed
        note_body = match.group(1).strip().lower()
        if any(keyword in note_body for keyword in _NOISE_NOTE_KEYWORDS):
            changed = True
            return ""
        return match.group(0)

    cleaned = _PAREN_BLOCK.sub(replacer, text)
    return _squash_ws(cleaned), changed


def _strip_internal_markers(text: str) -> Tuple[str, bool]:
    """
    Rule 10: Loại bỏ marker nội bộ dạng [cleaned: ...] trước khi đưa vào vector store.
    Ngăn metadata pipeline rò rỉ vào chunk publish.
    metric_impact: inject row chứa "[cleaned: stale_refund_window]" → marker stripped.
    """
    cleaned, count = _INTERNAL_MARKER.subn(" ", text)
    return _squash_ws(cleaned), count > 0


def _canonicalize_chunk_text(
    text: str,
    *,
    doc_id: str,
    apply_refund_window_fix: bool,
) -> str:
    """Áp dụng tất cả text-transform rules (7, 8, 6, 10) theo thứ tự."""
    fixed = _squash_ws(text)
    # Rule 7: strip editorial prefix
    fixed, _ = _strip_editorial_prefix(fixed)
    # Rule 8: strip operational notes
    fixed, _ = _strip_operational_notes(fixed)
    # Rule PII Masking
    email_pattern = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
    fixed = email_pattern.sub("[MASKED_EMAIL]", fixed)

    # Rule Term Normalization (IT Helpdesk)
    terms_to_fix = ["phòng máy tính", "hỗ trợ cntt", "đội kỹ thuật"]
    for term in terms_to_fix:
        if term in fixed.lower():
            pattern = re.compile(re.escape(term), re.IGNORECASE)
            fixed = pattern.sub("IT Helpdesk", fixed)
    # Rule 6 (baseline): fix stale refund window 14→7
    if apply_refund_window_fix and doc_id == "policy_refund_v4" and "14 ngày làm việc" in fixed:
        fixed = fixed.replace("14 ngày làm việc", "7 ngày làm việc")
    # Rule 10: strip internal markers
    fixed, _ = _strip_internal_markers(fixed)
    return _squash_ws(fixed)


# ---------------------------------------------------------------------------
# Stable chunk ID
# ---------------------------------------------------------------------------

def _stable_chunk_id(doc_id: str, chunk_text: str, seq: int) -> str:
    h = hashlib.sha256(f"{doc_id}|{chunk_text}|{seq}".encode("utf-8")).hexdigest()[:16]
    return f"{doc_id}_{seq}_{h}"


# ---------------------------------------------------------------------------
# I/O helpers
# ---------------------------------------------------------------------------

def load_raw_csv(path: Path) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    with path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append({k: (v or "").strip() for k, v in r.items()})
    return rows


def write_cleaned_csv(path: Path, rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text(
            "chunk_id,doc_id,chunk_text,effective_date,exported_at\n", encoding="utf-8"
        )
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
        path.write_text(
            "chunk_id,doc_id,chunk_text,effective_date,exported_at,reason\n", encoding="utf-8"
        )
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


# ---------------------------------------------------------------------------
# Main cleaning function
# ---------------------------------------------------------------------------

def clean_rows(
    rows: List[Dict[str, str]],
    *,
    apply_refund_window_fix: bool = True,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Trả về (cleaned_rows, quarantine_rows).

    Thứ tự kiểm tra:
    1. Allowlist doc_id           → quarantine reason: unknown_doc_id
    2. Chuẩn hoá effective_date   → quarantine reason: missing_effective_date /
                                     invalid_effective_date_format
    3. HR stale version           → quarantine reason: stale_hr_policy_effective_date
    4. (Rule 9) Chuẩn hoá exported_at → quarantine reason: missing_exported_at /
                                         invalid_exported_at
    5. Text canonicalize (rules 7, 8, 6, 10)
    6. Empty text after transform  → quarantine reason: missing_chunk_text
    7. Dedupe                     → quarantine reason: duplicate_chunk_text
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

        # Rule 1: allowlist doc_id
        if doc_id not in ALLOWED_DOC_IDS:
            quarantine.append({**raw, "reason": "unknown_doc_id"})
            continue

        # Rule 2: chuẩn hoá effective_date
        eff_norm, eff_err = _normalize_effective_date(eff_raw)
        if eff_err == "empty_effective_date":
            quarantine.append({**raw, "reason": "missing_effective_date"})
            continue
        if eff_err == "invalid_effective_date_format":
            quarantine.append({**raw, "reason": eff_err, "effective_date_raw": eff_raw})
            continue

        # Rule 3: HR stale version
        if doc_id == "hr_leave_policy" and eff_norm < "2026-01-01":
            quarantine.append(
                {
                    **raw,
                    "reason": "stale_hr_policy_effective_date",
                    "effective_date_normalized": eff_norm,
                }
            )
            continue

        # Rule 9 (mới): chuẩn hoá exported_at → ISO-8601 UTC Z
        exported_at, exported_err = _normalize_exported_at(exported_raw)
        if exported_err:
            quarantine.append(
                {**raw, "reason": exported_err, "exported_at_raw": exported_raw}
            )
            continue

        # Rules 7, 8, 6, 10: làm sạch chunk_text trước dedupe/publish
        fixed_text = _canonicalize_chunk_text(
            text,
            doc_id=doc_id,
            apply_refund_window_fix=apply_refund_window_fix,
        )

        # Rule 4: empty text sau transform
        if not fixed_text:
            quarantine.append({**raw, "reason": "missing_chunk_text"})
            continue

        # Rule 5: dedupe theo normalized text
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
