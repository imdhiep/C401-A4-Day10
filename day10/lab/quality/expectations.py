"""
Expectation suite đơn giản (không bắt buộc Great Expectations).

Sinh viên có thể thay bằng GE / pydantic / custom — miễn là có halt có kiểm soát.

Baseline (E1–E6, nhận từ sprint 1):
  E1. min_one_row                     — halt: ≥1 dòng sau clean
  E2. no_empty_doc_id                 — halt: không doc_id rỗng
  E3. refund_no_stale_14d_window      — halt: không còn cửa sổ 14 ngày trong policy_refund_v4
  E4. chunk_min_length_8              — warn: chunk_text ≥ 8 ký tự
  E5. effective_date_iso_yyyy_mm_dd   — halt: effective_date đúng YYYY-MM-DD sau clean
  E6. hr_leave_no_stale_10d_annual    — halt: không còn "10 ngày phép năm" trong HR doc

Mở rộng nhóm Sprint 2 (E7–E8):
  E7. published_text_no_operational_noise — halt
      Chunk publish không được chứa prefix biên tập ("FAQ bổ sung:"), ghi chú vận hành
      ("ghi chú", "migration", "sync cũ"), hoặc marker nội bộ ("[cleaned:").
      Pairs với rules 7, 8, 10 — FAIL nếu các rule text-clean bị tắt/bỏ qua.
      metric_impact: inject row 3 (bản gốc, không qua rule 8) → violations=1 → halt.

  E8. exported_at_iso8601_utc_z — halt
      exported_at phải khớp "YYYY-MM-DDTHH:MM:SSZ" (UTC).
      Pairs với rule 9 — FAIL nếu normalize exported_at bị bỏ qua hoặc giá trị thiếu.
      metric_impact: inject row exported_at="" → thoát ở rule 9 (quarantine) trước E8;
      inject cleaned row với exported_at="2026-04-10T08:00:00" (không Z) → E8 violations=1.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple


@dataclass
class ExpectationResult:
    name: str
    passed: bool
    severity: str  # "warn" | "halt"
    detail: str


# E7: markers vận hành/biên tập không được tồn tại trong text publish
_OPERATIONAL_NOISE_MARKERS = ("faq bổ sung:", "ghi chú", "migration", "sync cũ", "[cleaned:")

# E8: exported_at phải đúng ISO-8601 UTC với hậu tố Z
_EXPORTED_AT_UTC_Z = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


def _contains_operational_noise(text: str) -> bool:
    """Kiểm tra chunk_text có chứa noise vận hành/biên tập không (case-insensitive)."""
    lowered = (text or "").strip().lower()
    return any(marker in lowered for marker in _OPERATIONAL_NOISE_MARKERS)


def run_expectations(cleaned_rows: List[Dict[str, Any]]) -> Tuple[List[ExpectationResult], bool]:
    """
    Trả về (results, should_halt).
    should_halt = True nếu có bất kỳ expectation severity='halt' nào fail.
    """
    results: List[ExpectationResult] = []

    # E1: có ít nhất 1 dòng sau clean
    ok = len(cleaned_rows) >= 1
    results.append(
        ExpectationResult("min_one_row", ok, "halt", f"cleaned_rows={len(cleaned_rows)}")
    )

    # E2: không doc_id rỗng
    bad_doc = [r for r in cleaned_rows if not (r.get("doc_id") or "").strip()]
    results.append(
        ExpectationResult(
            "no_empty_doc_id",
            len(bad_doc) == 0,
            "halt",
            f"empty_doc_id_count={len(bad_doc)}",
        )
    )

    # E3: policy refund không được chứa cửa sổ sai 14 ngày (sau khi đã fix)
    bad_refund = [
        r
        for r in cleaned_rows
        if r.get("doc_id") == "policy_refund_v4"
        and "14 ngày làm việc" in (r.get("chunk_text") or "")
    ]
    results.append(
        ExpectationResult(
            "refund_no_stale_14d_window",
            len(bad_refund) == 0,
            "halt",
            f"violations={len(bad_refund)}",
        )
    )

    # E4: chunk_text đủ dài (warn — không halt)
    short = [r for r in cleaned_rows if len((r.get("chunk_text") or "")) < 8]
    results.append(
        ExpectationResult(
            "chunk_min_length_8",
            len(short) == 0,
            "warn",
            f"short_chunks={len(short)}",
        )
    )

    # E5: effective_date đúng định dạng ISO sau clean (phát hiện parser lỏng)
    iso_bad = [
        r
        for r in cleaned_rows
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", (r.get("effective_date") or "").strip())
    ]
    results.append(
        ExpectationResult(
            "effective_date_iso_yyyy_mm_dd",
            len(iso_bad) == 0,
            "halt",
            f"non_iso_rows={len(iso_bad)}",
        )
    )

    # E6: không còn marker phép năm cũ 10 ngày trên doc HR (conflict version sau clean)
    bad_hr_annual = [
        r
        for r in cleaned_rows
        if r.get("doc_id") == "hr_leave_policy"
        and "10 ngày phép năm" in (r.get("chunk_text") or "")
    ]
    results.append(
        ExpectationResult(
            "hr_leave_no_stale_10d_annual",
            len(bad_hr_annual) == 0,
            "halt",
            f"violations={len(bad_hr_annual)}",
        )
    )

    # E7 (mới — halt): chunk publish không còn noise vận hành/biên tập/marker nội bộ.
    # Pairs với rules 7, 8, 10. Fail nếu các rule text-clean bị tắt hoặc bỏ qua.
    noisy_rows = [
        r for r in cleaned_rows if _contains_operational_noise(r.get("chunk_text") or "")
    ]
    results.append(
        ExpectationResult(
            "published_text_no_operational_noise",
            len(noisy_rows) == 0,
            "halt",
            f"violations={len(noisy_rows)}",
        )
    )

    # E8 (mới — halt): exported_at phải đúng ISO-8601 UTC có đuôi Z.
    # Pairs với rule 9. Fail nếu normalize exported_at bị bỏ qua.
    bad_exported_at = [
        r
        for r in cleaned_rows
        if not _EXPORTED_AT_UTC_Z.match((r.get("exported_at") or "").strip())
    ]
    results.append(
        ExpectationResult(
            "exported_at_iso8601_utc_z",
            len(bad_exported_at) == 0,
            "halt",
            f"violations={len(bad_exported_at)}",
        )
    )

    halt = any(not r.passed and r.severity == "halt" for r in results)
    return results, halt
