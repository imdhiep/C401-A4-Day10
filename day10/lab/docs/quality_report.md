# Quality report — Lab Day 10 (nhóm)

**run_id:** sprint3_final_v2  
**Ngày:** 2026-04-15

---

## 1. Tóm tắt số liệu

| Chỉ số             | Trước                                                    | Sau                        | Ghi chú                                                   |
| ------------------ | -------------------------------------------------------- | -------------------------- | --------------------------------------------------------- |
| raw_records        | 15                                                       | 15                         | cùng nguồn raw                                            |
| cleaned_records    | 10                                                       | 10                         | sau clean/quarantine giữ số dòng ổn định                  |
| quarantine_records | 5                                                        | 5                          | cùng số dòng bị loại, nhưng nội dung khác nhau            |
| Expectation halt?  | Có, `refund_no_stale_14d_window` fail ở `sprint3_before` | Không ở `sprint3_final_v2` | `sprint3_before` dùng `--skip-validate` để tiếp tục embed |

---

## 2. Before / after retrieval (bắt buộc)

> Dữ liệu so sánh lấy từ `artifacts/eval/eval_before.csv` và `artifacts/eval/eval_after.csv`.

**Câu hỏi then chốt:** refund window (`q_refund_window`)  
- Trước: `eval_before.csv` top1 preview trả về câu chứa "14 ngày làm việc" và `hits_forbidden=yes`, cho thấy chunk stale refund vẫn nằm trong top-k.  
- Sau: `eval_after.csv` top1 preview trả về câu sửa thành "7 ngày làm việc" và `hits_forbidden=no`, chứng tỏ rule fix stale refund window đã được áp dụng thành công.

**Merit:** versioning HR — `q_leave_version`  
- Trước: `eval_before.csv` top1 trả về doc HR hiện hành `hr_leave_policy` với nội dung `12 ngày phép năm`, `contains_expected=yes`, `hits_forbidden=no`.
- Sau: `eval_after.csv` tiếp tục trả về doc đúng và `hits_forbidden=no`, chứng tỏ stale HR 2025 (`10 ngày phép năm`) đã bị loại khỏi cleaned export.

**Bổ sung PII / normalization:**  
- Trước: `eval_before.csv` với `q_pii_masking` trả về preview chứa email thật `admin_backup@company.com`, `hits_forbidden=yes`.
- Sau: `eval_after.csv` trả về preview đã mask email thành `[MASKED_EMAIL]`, `hits_forbidden=no`, chứng minh cơ chế xử lý sensitive content hoạt động.
- Trước: `eval_before.csv` với `q_term_norm` trả về preview không chính xác (`phòng máy tính`), `hits_forbidden=yes`.
- Sau: `eval_after.csv` trả về preview chuẩn `IT Helpdesk`, `hits_forbidden=no`, cho thấy dữ liệu sau clean đã giảm nhiễu routing đáng kể.

---

## 3. Freshness & monitor

> Kết quả `freshness_check` vẫn FAIL do dữ liệu nguồn cũ.

- `manifest_sprint3_final_v2.json` chứa `latest_exported_at: 2026-04-10T08:00:00Z`.
- `age_hours` lớn hơn 120 so với SLA 24 giờ.
- Kết luận: pipeline `sprint3_final_v2` chạy đúng về logic clean/validation/embed, nhưng raw export mẫu không tươi nên observability freshness vẫn fail.

---

## 4. Corruption inject (Sprint 3)

> Mô tả cố ý làm hỏng dữ liệu và cách pipeline phát hiện.

- Cách inject:
  - Thêm khoảng trắng thừa vào đoạn text để test rule normalize/strip whitespace.
  - Chèn policy HR 2025 (`10 ngày phép năm`) cạnh bản HR 2026 (`12 ngày`) để test stale HR version rule.
  - Chèn email admin thật vào text để test rule ẩn danh/sensitive content.
- Mục tiêu: tạo dữ liệu xấu dạng "stale policy", "noisy text", "PII" và chứng minh pipeline có thể phát hiện hoặc làm sạch.
- Kết quả `sprint3_before`: `--no-refund-fix --skip-validate` giữ nguyên các lỗi input để đánh giá, nhưng expectation `refund_no_stale_14d_window` fail, chứng tỏ rule vẫn hoạt động.
- Kết quả `sprint3_final_v2`: lỗi stale refund đã được fix, HR cũ/invalid date đã bị quarantine, email nhạy cảm đã được mask trong cleaned output.

---

## 5. Hạn chế & việc chưa làm

- `freshness_check` chưa pass do `exported_at` trong raw quá cũ; cần raw mới để hoàn tất Sprint 4.
- Cần bổ sung báo cáo `before_after_eval.csv` chi tiết hơn cho câu `q_refund_window` và `q_leave_version` nếu muốn minh chứng full top-k.
- Nếu cần, có thể mở rộng rule để xử lý thêm các dạng PII khác ngoài email và chuẩn hoá thêm các câu quá ngắn.
