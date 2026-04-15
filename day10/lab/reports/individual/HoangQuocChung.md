# Báo Cáo Cá Nhân — Lab Day 10: Data Pipeline & Observability

**Họ và tên:** Hoàng Quốc Chung  
**Vai trò:** Cleaning & Quality Owner  
**Ngày nộp:** 2026-04-15

---

## 1. Tôi phụ trách phần nào?

Tôi chịu trách nhiệm toàn bộ tầng **clean + validate** trong Sprint 2:

- **`transform/cleaning_rules.py`** — update 4 rule (R7–R10) vào phần mở rộng của `clean_rows()`, gồm các helper `_strip_editorial_prefix()` (dòng 133), `_strip_operational_notes()` (dòng 147), `_normalize_exported_at()` (dòng 101), `_strip_internal_markers()` (dòng 167), và hàm `_canonicalize_chunk_text()` điều phối thứ tự áp dụng.
- **`quality/expectations.py`** — sửa 2 expectation mới (E7, E8) vào `run_expectations()`: `published_text_no_operational_noise` (dòng 138) và `exported_at_iso8601_utc_z` (dòng 152).
- Đồng thời dọn dẹp lỗi **duplicate function definition** (xem mục 3).

Kết nối với **Embed Owner** qua trường `cleaned_csv` trong manifest và giá trị `cleaned_records=6` / `quarantine_records=4` trong log run `sprint2`. Embed owner đọc đúng file cleaned và có thể kiểm `embed_prune_removed` trong log để xác nhận prune hoạt động.

---

## 2. Một quyết định kỹ thuật

**Chọn halt cho cả E7 và E8, không phải warn.**

Ban đầu tôi cân nhắc đặt E8 (`exported_at_iso8601_utc_z`) là `warn` vì thiếu timezone chỉ ảnh hưởng freshness check, không ảnh hưởng nội dung chunk. Tuy nhiên tôi quyết định giữ `halt` vì hai lý do:

1. **Quan hệ pair rule–expectation**: E8 là "test" kiểm tra R9 có đang chạy không. Nếu R9 bị comment out hoặc bỏ qua, E8 sẽ thấy `violations=6` (toàn bộ 6 cleaned rows có exported_at không có `Z`). Đặt là warn thì pipeline vẫn embed dữ liệu có exported_at không chuẩn → freshness check bị sai clock.

2. **Tính nhất quán**: Nếu ai inject row với `exported_at=""` thì R9 đã quarantine trước khi đến E8 (reason: `missing_exported_at`). E8 chỉ kích hoạt khi có row bypass R9 bằng cách nào đó — đây là case nghiêm trọng, xứng đáng halt.

Tương tự, E7 (`published_text_no_operational_noise`) là `halt` vì nếu chunk publish còn `"FAQ bổ sung:"` hoặc `"migration"`, agent downstream sẽ nhận context nhiễu — ảnh hưởng trực tiếp chất lượng retrieval.

---

## 3. Một lỗi / anomaly đã xử lý

**Triệu chứng:** File `cleaning_rules.py` ban đầu có **hai định nghĩa trùng** cho `clean_rows()` và `_norm_text()`. Python không báo lỗi — nó silently dùng định nghĩa thứ hai, khiến baseline `clean_rows()` trở thành dead code.

**Phát hiện:** Khi review lại file để thêm rule mới, tôi nhận ra phần code từ dòng 65–144 (baseline `clean_rows`) không bao giờ được gọi vì bị override bởi định nghĩa dòng 270. Nếu để nguyên, GV đếm rule theo file sẽ thấy 2 phiên bản `clean_rows` chồng nhau và khó xác định rule nào thực sự chạy.

**Fix:** Tôi consolidate thành **một file sạch duy nhất** — xóa bản đầu, giữ bản mở rộng (rules 7–10), tổ chức theo section (constants → helpers → I/O → main). Sau fix, `from transform.cleaning_rules import clean_rows` trong `etl_pipeline.py` import đúng phiên bản có rules 7–10.

---

## 4. Bằng chứng trước / sau

**Kịch bản:** chạy với rules 7/8 bị comment out (simulate trước khi có rule) → E7 FAIL halt:

```
expectation[published_text_no_operational_noise] FAIL (halt) :: violations=2
PIPELINE_HALT: expectation suite failed (halt).
```

**Sau khi áp dụng rules 7, 8 (run_id=sprint2):**

```
expectation[published_text_no_operational_noise] OK (halt) :: violations=0
expectation[exported_at_iso8601_utc_z] OK (halt) :: violations=0
cleaned_records=6
quarantine_records=4
PIPELINE_OK
```

Hai violations trước đó là: row 3 còn `"ghi chú: bản sync cũ policy-v3"` và row 10 còn `"FAQ bổ sung:"`. Sau khi R8 và R7 chạy, cả hai stripped → violations=0.

---

## 5. Cải tiến tiếp theo

Nếu có thêm 2 giờ, tôi sẽ đọc `hr_leave_min_effective_date` và danh sách `_EDITORIAL_PREFIXES`, `_NOISE_NOTE_KEYWORDS` trực tiếp từ `contracts/data_contract.yaml` thay vì hard-code trong Python. Hiện tại cutoff `"2026-01-01"` và các keyword noise được viết cứng trong code — nếu policy thay đổi, phải sửa code. Đọc từ contract giúp rule versioning không hard-code và đáp ứng tiêu chí Distinction (d) trong SCORING.
