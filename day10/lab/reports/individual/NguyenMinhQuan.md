# Báo Cáo Cá Nhân — Lab Day 10: Data Pipeline & Observability

**Họ và tên:** Nguyễn Minh Quân - 2A202600181
**Vai trò:** Ingestion /  Embed Owner
**Ngày nộp:** 15/04/2026  
**Độ dài yêu cầu:** **400–650 từ** (ngắn hơn Day 09 vì rubric slide cá nhân ~10% — vẫn phải đủ bằng chứng)

---

## 1. Tôi phụ trách phần nào? (80–120 từ)

**File / module:**
> Tôi đảm nhận vai trò Ingestion và Evaluation Owner (phụ trách Sprint 1 và 3). Tôi trực tiếp xây dựng luồng nạp dữ liệu thô từ `policy_export_dirty.csv`, thiết lập cấu trúc log và run_id. Ở giai đoạn cuối, tôi thiết kế kịch bản kiểm thử trong `test_questions.json` và sử dụng script `eval_retrieval.py` để đo lường chất lượng hệ thống thông qua phương pháp so sánh Before/After.

> File / module: 
- `etl_pipeline.py` (Quản lý luồng chạy chính và Log).

- `data/raw/policy_export_dirty.csv` (Inject dữ liệu lỗi).

- `eval_retrieval.py` & `test_questions.json` (Đánh giá Retrieval).

**Bằng chứng (commit / comment trong code):**

> Commit/file trong repo:
> https://github.com/imdhiep/C401-A4-Day10/tree/main/day10/lab/data
> https://github.com/imdhiep/C401-A4-Day10/tree/main/day10/lab/docs

---

## 2. Một quyết định kỹ thuật (100–150 từ)

> VD: chọn halt vs warn, chiến lược idempotency, cách đo freshness, format quarantine.

> Chiến lược Run-ID: Tôi quyết định bắt buộc gắn run_id vào mọi Artifacts (Log, CSV, Eval). Việc này giúp tách biệt hoàn toàn dữ liệu giữa các phiên bản "bẩn" và "sạch", đảm bảo tính Reproducibility (khả năng tái lập) khi cần đối soát lại lỗi.

> Idempotency & Pruning: Tôi ủng hộ việc thực hiện Prune (xóa các vector ID cũ không còn trong batch mới) thay vì chỉ Upsert. Quyết định này cực kỳ quan trọng để giải quyết triệt để tình trạng "dữ liệu ma" (stale data), tránh trường hợp kết quả Top-k vẫn trả về thông tin "14 ngày" cũ sau khi đã thực hiện Inject corruption ở Sprint 3.
---

## 3. Một lỗi hoặc anomaly đã xử lý (100–150 từ)

> Mô tả triệu chứng → metric/check nào phát hiện → fix.

> Trong Sprint 3, sau khi chạy bản "After Fix", kết quả đánh giá vẫn báo hits_forbidden=yes cho câu hỏi hoàn tiền.

> Nguyên nhân: Vector DB vẫn còn lưu lại các chunk cũ từ lần chạy "Before Fix" do cùng doc_id nhưng khác nội dung, khiến ChromaDB không tự động ghi đè.

> Khắc phục: Tôi đã phối hợp bổ sung logic col.delete(ids=...) trong etl_pipeline.py để dọn dẹp các ID lỗi thời dựa trên so sánh tập hợp ID hiện tại và ID trong DB. Kết quả sau đó đã chuyển về no như kỳ vọng.

---

## 4. Bằng chứng trước / sau (80–120 từ)

> Log: run_id=sprint3_after | raw_records=15 | cleaned_records=8 | quarantine_records=7. Hệ thống báo expectation[refund_no_stale_14d_window] OK.

> CSV: Trong file `artifacts/eval/eval_after.csv`, dòng q_refund_window đã đạt contains_expected=yes và hits_forbidden=no. Đặc biệt, dòng q_leave_version đạt top1_doc_expected=yes, chứng minh Pipeline đã phân biệt được phiên bản 2026.

---

## 5. Cải tiến tiếp theo (40–80 từ)

> Nếu có thêm 2 giờ — một việc cụ thể (không chung chung).

> Xây dựng một Automated Corruption Generator. Thay vì sửa file CSV thủ công, tôi sẽ viết script tự động tạo dữ liệu lỗi (PII, sai định dạng, stale date) dựa trên bộ quy tắc trong data_contract.md. Điều này giúp Stress-test Pipeline một cách khách quan và giúp đội ngũ Cleaning có bộ dữ liệu thử nghiệm phong phú hơn.
