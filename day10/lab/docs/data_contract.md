# Data contract — Lab Day 10

> Bắt đầu từ `contracts/data_contract.yaml` — mở rộng và đồng bộ file này.

---

## 1. Nguồn dữ liệu (source map)

| Nguồn | Phương thức ingest | Failure mode chính | Metric / alert |
|-------|-------------------|-------------------|----------------|
| `data/raw/policy_export_dirty.csv` | Batch (CLI `python etl_pipeline.py run`) | Thiếu file, `doc_id` lạ, ngày sai format, `exported_at` thiếu/sai, duplicate chunk | Theo dõi `raw_records`, `quarantine_records`; alert khi quarantine rate > 5% hoặc không đọc được file |
| Canonical docs `data/docs/*.txt` | File text tĩnh làm nguồn chuẩn đối chiếu version | Drift nội dung giữa export và canonical source (vd còn refund 14 ngày) | Alert khi expectation halt fail (`refund_no_stale_14d_window`, `hr_leave_no_stale_10d_annual`) |

---

## 2. Schema cleaned

| Cột | Kiểu | Bắt buộc | Ghi chú |
|-----|------|----------|---------|
| `chunk_id` | string | Có | ID ổn định, sinh từ `doc_id + chunk_text + seq` (hash) để hỗ trợ upsert idempotent |
| `doc_id` | string | Có | Thuộc allowlist: `policy_refund_v4`, `sla_p1_2026`, `it_helpdesk_faq`, `hr_leave_policy` |
| `chunk_text` | string | Có | Text đã làm sạch (strip noise + fix policy), không rỗng, không trùng; có check tối thiểu 8 ký tự |
| `effective_date` | date | Có | Chuẩn `YYYY-MM-DD`; hỗ trợ parse `DD/MM/YYYY`; HR policy phải >= `2026-01-01` |
| `exported_at` | datetime | Có | Chuẩn `ISO-8601 UTC` có hậu tố `Z` để dùng freshness SLA |

---

## 3. Quy tắc quarantine vs drop

> Record bị flag đi đâu? Ai approve merge lại?

- **Quarantine:** Row lỗi transform sẽ vào `artifacts/quarantine/quarantine_<run_id>.csv` với reason cụ thể: `unknown_doc_id`, `missing_effective_date`, `invalid_effective_date_format`, `stale_hr_policy_effective_date`, `missing_exported_at`, `invalid_exported_at`, `missing_chunk_text`, `duplicate_chunk_text`.
- **Drop/Halt:** Sau khi đã có cleaned CSV, nếu expectation severity `halt` fail thì pipeline dừng (`PIPELINE_HALT`, exit code 2). Chỉ cho phép bypass khi có `--skip-validate` để demo inject ở Sprint 3.
- **Approve merge lại:** Cleaning/Quality Owner phân tích quarantine + log, sửa source hoặc rule, rồi rerun pipeline để record hợp lệ quay lại cleaned/publish boundary.

---

## 4. Phiên bản & canonical

> Source of truth cho policy refund: file nào / version nào?

- **Source of truth cho refund:** `data/docs/policy_refund_v4.txt` (`doc_id=policy_refund_v4`).
- **Version canonical:** Refund window chuẩn là **7 ngày làm việc**; không chấp nhận stale text 14 ngày trong publish data.
- **Các canonical source khác:**
  - `data/docs/sla_p1_2026.txt` (`doc_id=sla_p1_2026`)
  - `data/docs/it_helpdesk_faq.txt` (`doc_id=it_helpdesk_faq`)
  - `data/docs/hr_leave_policy.txt` (`doc_id=hr_leave_policy`, yêu cầu `effective_date >= 2026-01-01`)
