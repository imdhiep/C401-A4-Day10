# Data contract — Lab Day 10

> Bắt đầu từ `contracts/data_contract.yaml` — mở rộng và đồng bộ file này.

---

## 1. Nguồn dữ liệu (source map)

| Nguồn | Phương thức ingest | Failure mode chính | Metric / alert |
|-------|-------------------|-------------------|----------------|
| policy_export_dirty.csv | Batch (đọc từ file CSV định kỳ) | Thiếu cột, sai định dạng (vd: date), trùng lặp dữ liệu, lỗi null | Alert khi % dòng lỗi (quarantine) vượt quá ngưỡng (vd: >5%), Alert thiếu file |
| Các file text Knowledge Base (`data/docs/*.txt`) | File text tĩnh (đọc thủ công hoặc batch) | File không tồn tại, sai định dạng mã hóa (encoding) | Cảnh báo khi file path không khớp với file thực tế, alert đọc lỗi IO |

---

## 2. Schema cleaned

| Cột | Kiểu | Bắt buộc | Ghi chú |
|-----|------|----------|---------|
| chunk_id | string | Có | ID ổn định sau clean (thường là hash hoặc ghép doc_id + seq) |
| doc_id | string | Có | Khóa logic tài liệu nguồn (vd: `policy_refund_v4`, `sla_p1_2026`) |
| chunk_text | string | Có | Nội dung text, có rule kiểm tra độ dài tối thiểu (`min_length: 8`), không được trùng lặp |
| effective_date | date | Có | Ngày bắt đầu có hiệu lực của tài liệu (vd: hr_leave_policy bắt buộc từ 2026-01-01) |
| exported_at | datetime | Có | Thời điểm xuất dữ liệu (dùng để check freshness, SLA 24h) |

---

## 3. Quy tắc quarantine vs drop

> Record bị flag đi đâu? Ai approve merge lại?

- **Quarantine:** Các record lỗi (ví dụ sai định dạng ngày, thiếu nội dung quan trọng nhưng có thể khôi phục, hoặc dính các quality rules `severity: warn`) sẽ bị cô lập và lưu vào thư mục `artifacts/quarantine/` dưới dạng các file log/CSV (ví dụ: `quarantine_ci-smoke.csv`).
- **Drop (Halt):** Các record có `severity: halt` (Ví dụ như vi phạm `no_stale_refund_window`: chứa chính sách cũ 14 ngày thay vì 7 ngày) sẽ bị drop lập tức (hoặc làm fail cả pipeline) vì đây là lỗi dữ liệu nghiêm trọng không được phép lọt vào DB.
- **Quy trình Merge lại:** Cleaning/Quality Owner chịu trách nhiệm theo dõi thư mục quarantine, phân tích nguyên nhân lỗi, làm sạch thủ công hoặc cập nhật script ETL (ví dụ `cleaning_rules.py`). Sau khi khắc phục và approve, họ có thể đưa các record này trở lại nguồn đầu vào để chạy lại pipeline.

---

## 4. Phiên bản & canonical

> Source of truth cho policy refund: file nào / version nào?

- **Source of truth (Canonical Source) cho policy refund:** Là file `data/docs/policy_refund_v4.txt`
- **Version:** Version 4 (`v4`). Đảm bảo cập nhật chính sách hoàn tiền 7 ngày (loại bỏ hoàn toàn các chính sách cũ là 14 ngày).
- **Các Canonical Sources khác được quy định trong contract:**
  - `sla_p1_2026` (từ `data/docs/sla_p1_2026.txt`)
  - `it_helpdesk_faq` (từ `data/docs/it_helpdesk_faq.txt`)
  - `hr_leave_policy` (từ `data/docs/hr_leave_policy.txt` - có điều kiện `effective_date` từ `2026-01-01`)
