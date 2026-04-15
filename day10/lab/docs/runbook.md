# Runbook — Lab Day 10 (incident tối giản)

---

## Symptom

Người dùng hoặc agent có thể nhận câu trả lời sai version dữ liệu, ví dụ:
- refund window trả về "14 ngày làm việc" thay vì "7 ngày làm việc"
- kết quả retrieval làm lộ email nội bộ `admin_backup@company.com`
- text trả về còn nhiễu vận hành như "FAQ bổ sung:" hoặc cách gọi chưa chuẩn như "phòng máy tính"
- pipeline chạy xong nhưng dữ liệu vẫn bị đánh dấu stale do freshness SLA fail

## Detection

Dùng các artifact sau để phát hiện sự cố:
- `artifacts/eval/eval_before.csv`: câu `q_refund_window` có `hits_forbidden=yes`, cho thấy top-k vẫn chứa chunk stale 14 ngày
- `artifacts/eval/eval_before.csv`: `q_pii_masking` có `contains_expected=no`, `hits_forbidden=yes`
- `artifacts/eval/eval_before.csv`: `q_term_norm` có `contains_expected=no`, `hits_forbidden=yes`
- `artifacts/manifests/manifest_sprint3_final_v2.json`: `latest_exported_at=2026-04-10T08:00:00Z`; với SLA 24 giờ thì freshness check phải FAIL

## Diagnosis

| Bước | Việc làm | Kết quả mong đợi |
|------|----------|------------------|
| 1 | Mở `artifacts/manifests/manifest_sprint3_before.json` và `manifest_sprint3_final_v2.json` | Xác định run inject (`no_refund_fix=true`, `skipped_validate=true`) và run sạch |
| 2 | Mở `artifacts/quarantine/quarantine_sprint3_before.csv` | Thấy các lý do quarantine như `duplicate_chunk_text`, `missing_effective_date`, `stale_hr_policy_effective_date`, `unknown_doc_id`, `invalid_effective_date_format` |
| 3 | Mở `artifacts/cleaned/cleaned_sprint3_final_v2.csv` | Xác nhận text publish đã được sửa thành `7 ngày`, email đã mask, term đã chuẩn hoá thành `IT Helpdesk`, `exported_at` có hậu tố `Z` |
| 4 | So sánh `artifacts/eval/eval_before.csv` và `artifacts/eval/eval_after.csv` | Xác nhận retrieval sau clean không còn stale/noise/PII trong top-k |

## Mitigation

- Nếu phát hiện refund stale hoặc PII/noise trong retrieval, chạy lại pipeline chuẩn bằng `python etl_pipeline.py run` thay vì run inject.
- Không dùng `--skip-validate` trong run publish chính thức.
- Nếu freshness fail, đánh dấu snapshot là stale và yêu cầu raw export mới trước khi coi dữ liệu là production-ready.
- Nếu quarantine tăng bất thường, đọc file quarantine để sửa lỗi nguồn hoặc cập nhật cleaning rules trước khi publish lại.

## Prevention

- Giữ expectation `refund_no_stale_14d_window`, `published_text_no_operational_noise`, `exported_at_iso8601_utc_z` ở mức `halt`.
- Theo dõi `run_id`, `raw_records`, `cleaned_records`, `quarantine_records` qua manifest/log để truy vết.
- Luôn chạy eval before/after trước khi chốt run publish.
- Duy trì source of truth theo `policy_refund_v4` và `hr_leave_policy` hiện hành để tránh stale version quay lại.
