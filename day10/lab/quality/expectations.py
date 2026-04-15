"""
Expectation suite đơn giản (không bắt buộc Great Expectations).

Sinh viên có thể thay bằng GE / pydantic / custom — miễn là có halt có kiểm soát.
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


def run_expectations(cleaned_rows: List[Dict[str, Any]]) -> Tuple[List[ExpectationResult], bool]:
    """
    Trả về (results, should_halt).

    should_halt = True nếu có bất kỳ expectation severity halt nào fail.
    """
    results: List[ExpectationResult] = []

    # E1: có ít nhất 1 dòng sau clean
    ok = len(cleaned_rows) >= 1
    results.append(
        ExpectationResult(
            "min_one_row",
            ok,
            "halt",
            f"cleaned_rows={len(cleaned_rows)}",
        )
    )

    # E2: không doc_id rỗng
    bad_doc = [r for r in cleaned_rows if not (r.get("doc_id") or "").strip()]
    ok2 = len(bad_doc) == 0
    results.append(
        ExpectationResult(
            "no_empty_doc_id",
            ok2,
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
    ok3 = len(bad_refund) == 0
    results.append(
        ExpectationResult(
            "refund_no_stale_14d_window",
            ok3,
            "halt",
            f"violations={len(bad_refund)}",
        )
    )

    # E4: chunk_text đủ dài
    short = [r for r in cleaned_rows if len((r.get("chunk_text") or "")) < 8]
    ok4 = len(short) == 0
    results.append(
        ExpectationResult(
            "chunk_min_length_8",
            ok4,
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
    ok5 = len(iso_bad) == 0
    results.append(
        ExpectationResult(
            "effective_date_iso_yyyy_mm_dd",
            ok5,
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
    ok6 = len(bad_hr_annual) == 0
    results.append(
        ExpectationResult(
            "hr_leave_no_stale_10d_annual",
            ok6,
            "halt",
            f"violations={len(bad_hr_annual)}",
        )
    )

    halt = any(not r.passed and r.severity == "halt" for r in results)
    return results, halt


_OPERATIONAL_NOISE_MARKERS = ("faq bổ sung:", "ghi chú", "migration", "sync cũ", "[cleaned:")
# Expectation moi 2:
# exported_at_iso8601_utc_z
# Muc tieu: exported_at tren cleaned phai dong nhat de phuc vu manifest/freshness.
_EXPORTED_AT_UTC_Z = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")

# Expectation moi 1:
# published_text_no_operational_noise
# Muc tieu: chunk publish khong duoc con "FAQ bo sung", "ghi chu", "migration",
# "sync cu" hoac marker noi bo [cleaned: ...].
def _contains_operational_noise(text: str) -> bool:
    lowered = (text or "").strip().lower()
    return any(marker in lowered for marker in _OPERATIONAL_NOISE_MARKERS)


def run_expectations(cleaned_rows: List[Dict[str, Any]]) -> Tuple[List[ExpectationResult], bool]:
    """
    Tra ve (results, should_halt).

    Expectation moi:
    - published_text_no_operational_noise
    - exported_at_iso8601_utc_z
    """
    results: List[ExpectationResult] = []

    ok = len(cleaned_rows) >= 1
    results.append(ExpectationResult("min_one_row", ok, "halt", f"cleaned_rows={len(cleaned_rows)}"))

    bad_doc = [r for r in cleaned_rows if not (r.get("doc_id") or "").strip()]
    results.append(
        ExpectationResult(
            "no_empty_doc_id",
            len(bad_doc) == 0,
            "halt",
            f"empty_doc_id_count={len(bad_doc)}",
        )
    )

    bad_refund = [
        r
        for r in cleaned_rows
        if r.get("doc_id") == "policy_refund_v4" and "14 ngày làm việc" in (r.get("chunk_text") or "")
    ]
    results.append(
        ExpectationResult(
            "refund_no_stale_14d_window",
            len(bad_refund) == 0,
            "halt",
            f"violations={len(bad_refund)}",
        )
    )

    short = [r for r in cleaned_rows if len((r.get("chunk_text") or "")) < 8]
    results.append(
        ExpectationResult(
            "chunk_min_length_8",
            len(short) == 0,
            "warn",
            f"short_chunks={len(short)}",
        )
    )

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

    bad_hr_annual = [
        r
        for r in cleaned_rows
        if r.get("doc_id") == "hr_leave_policy" and "10 ngày phép năm" in (r.get("chunk_text") or "")
    ]
    results.append(
        ExpectationResult(
            "hr_leave_no_stale_10d_annual",
            len(bad_hr_annual) == 0,
            "halt",
            f"violations={len(bad_hr_annual)}",
        )
    )

    # Expectation moi 1: chunk publish phai sach, khong con dau vet van hanh/noise.
    noisy_rows = [r for r in cleaned_rows if _contains_operational_noise(r.get("chunk_text") or "")]
    results.append(
        ExpectationResult(
            "published_text_no_operational_noise",
            len(noisy_rows) == 0,
            "halt",
            f"violations={len(noisy_rows)}",
        )
    )

    # Expectation moi 2: exported_at phai o dang ISO-8601 UTC co duoi Z.
    bad_exported_at = [
        r for r in cleaned_rows if not _EXPORTED_AT_UTC_Z.match((r.get("exported_at") or "").strip())
    ]
    results.append(
        ExpectationResult(
            "exported_at_iso8601_utc_z",
            len(bad_exported_at) == 0,
            "halt",
            f"violations={len(bad_exported_at)}",
        )
    )

    halt = any(not result.passed and result.severity == "halt" for result in results)
    return results, halt
