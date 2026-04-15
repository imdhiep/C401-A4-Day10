# Báo Cáo Cá Nhân — Lab Day 10: Data Pipeline & Observability

**Họ và tên:** Bùi Văn Đạt - 2A202600355
**Vai trò:** Embed Owner
**Ngày nộp:** 15/04/2026  
**Độ dài yêu cầu:** **400–650 từ**

---

## 1. Tôi phụ trách phần nào? (80–120 từ)

Trong Sprint 3, tôi đảm nhận vai trò Embed Owner nhưng cũng phối hợp chặt với phần data quality để hoàn thiện luồng before/after. Tôi trực tiếp kiểm soát phần `etl_pipeline.py` về việc upsert vector, prune ID cũ và viết manifest cho mỗi run. Tôi còn tham gia đánh giá kết quả qua `eval_retrieval.py` và dữ liệu `artifacts/eval/eval_before.csv` / `artifacts/eval/eval_after.csv`.

Các file chính tôi tương tác:
- `etl_pipeline.py`: lênh chạy chính, viết run_id, log, manifest, và idempotent embed.
- `transform/cleaning_rules.py`: làm việc với dữ liệu được clean và chuẩn hoá trước khi embed.
- `quality/expectations.py`: đảm bảo expectation suite phát hiện stale refund, missing date, và policy conflict.
- `eval_retrieval.py`: đánh giá before/after cho các câu truy vấn then chốt.

---

## 2. Một quyết định kỹ thuật (100–150 từ)

Tôi quyết định upsert vector và prune các ID không còn tồn tại trong cleaned batch. Cụ thể, trước khi upsert, pipeline kiểm tra danh sách IDs hiện tại với IDs trong collection Chroma và xóa những IDs lỗi thời. Quyết định này giúp tránh "dữ liệu ma" khi cùng `doc_id` xuất hiện nhiều phiên bản khác nhau, đặc biệt trong Sprint 3 khi policy stale refund được sửa và HR 2025 cần bị loại. Ngoài ra, tôi giữ `run_id` cho mọi artifacts để tách biệt rõ ràng `sprint3_before`, `sprint3_after`, và `sprint3_final_v2`, điều này tạo hiệu quả cao khi đối soát và debug.

---

## 3. Một lỗi hoặc anomaly đã xử lý (100–150 từ)

Trong Sprint 3, tôi phát hiện một anomaly quan trọng là `q_refund_window` trước khi fix vẫn trả về chunk stale chứa "14 ngày làm việc", và `q_pii_masking` trả về email thật. Triệu chứng được phát hiện qua eval `hits_forbidden=yes` và expectation `refund_no_stale_14d_window` fail ở `sprint3_before`. Nguyên nhân chính là do raw dataset giữ cả bản policy cũ và bản mới, đồng thời vẫn chứa noise và PII chưa mask. Tôi khắc phục bằng cách giữ logic xóa vector cũ trong `etl_pipeline.py` và đảm bảo clean rules sửa đổi đúng câu refund, mask email và loại bỏ HR stale. Kết quả `sprint3_final_v2` trả về `q_refund_window` đúng 7 ngày và `q_pii_masking` đã mask email.

---

## 4. Bằng chứng trước / sau (80–120 từ)

- `sprint3_before`: raw_records=15, cleaned_records=10, quarantine_records=5. Expectation `refund_no_stale_14d_window` fail, nhưng pipeline vẫn tiếp tục embed do flag `--skip-validate`.
- `sprint3_final_v2`: raw_records=15, cleaned_records=10, quarantine_records=5. Expectation tất cả quan trọng pass, và manifest ghi nhận `cleaned_sprint3_final_v2.csv`.
- `artifacts/eval/eval_before.csv`: `q_refund_window` trả về nội dung "14 ngày làm việc", `hits_forbidden=yes`; `q_pii_masking` trả về email `admin_backup@company.com`, `hits_forbidden=yes`.
- `artifacts/eval/eval_after.csv`: `q_refund_window` trả về "7 ngày làm việc", `hits_forbidden=no`; `q_pii_masking` trả về `[MASKED_EMAIL]`, `hits_forbidden=no`; `q_leave_version` duy trì top1 đúng `hr_leave_policy` phiên bản 2026.

---

## 5. Cải tiến tiếp theo (40–80 từ)

Nếu có thêm 2 giờ,thay vì tạo thủ công tôi sẽ xây dựng một script tự động tạo dữ liệu corrupted từ `data/raw/policy_export_dirty.csv`, bao gồm PII, stale policy, invalid date và whitespace thừa. Script này sẽ tạo nhiều kịch bản test tự động cho pipeline và giúp nhóm đánh giá robust của rule clean, expectation và embed mà không cần sửa tay CSV mỗi lần.
