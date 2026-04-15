# Báo Cáo Cá Nhân — Lab Day 10: Data Pipeline & Observability

**Họ và tên:** Dương Văn Hiệp  
**Vai trò:** Cleaning & Quality Owner  
**Ngày nộp:** 2026-04-15

---

## 1. Phụ trách

Tôi phụ trách phần quan trọng nhất của tầng dữ liệu: biến raw export thành cleaned data đủ tin cậy để publish vào vector store. Cụ thể, tôi làm trực tiếp trên `transform/cleaning_rules.py` và `quality/expectations.py`.

Ở `cleaning_rules.py`, tôi chịu trách nhiệm tổ chức luồng `clean_rows()` và các helper dùng trong pipeline: `_normalize_effective_date()`, `_normalize_exported_at()`, `_strip_editorial_prefix()`, `_strip_operational_notes()`, `_strip_internal_markers()` và `_canonicalize_chunk_text()`. Những phần này xử lý cả lỗi cấu trúc lẫn lỗi ngữ nghĩa trong text: `doc_id` lạ bị quarantine, `effective_date` không đúng chuẩn bị loại, bản HR cũ bị chặn, `exported_at` được chuẩn hóa về ISO-8601 UTC có hậu tố `Z`, còn text publish được làm sạch để không mang theo prefix biên tập, ghi chú migration hay marker nội bộ.

Ở `expectations.py`, tôi triển khai và hoàn thiện hai expectation mới có tính kiểm soát chất lượng rõ ràng là `published_text_no_operational_noise` và `exported_at_iso8601_utc_z`. Tôi cũng giữ `chunk_min_length_8` ở mức `warn` thay vì `halt`, vì đây là chỉ báo chất lượng chứ không phải lỗi phá vỡ toàn bộ pipeline.

**Bằng chứng cụ thể:** manifest `artifacts/manifests/manifest_2026-04-15T08-32Z.json` ghi `raw_records=10`, `cleaned_records=6`, `quarantine_records=4`, đúng với phạm vi tôi phụ trách trong bước clean + validate.

---

## 2. Quyết định kỹ thuật

Quyết định kỹ thuật quan trọng nhất tôi đưa ra là tách rõ ba mức xử lý: `quarantine`, `warn`, và `halt`.

Tôi chọn **quarantine ở bước cleaning** cho các lỗi làm bẩn dữ liệu gốc nhưng có thể cô lập từng dòng, ví dụ `unknown_doc_id`, `missing_effective_date`, `invalid_effective_date_format`, `stale_hr_policy_effective_date`, hoặc `missing/invalid_exported_at`. Cách này giúp giữ pipeline có khả năng tiếp tục với phần dữ liệu còn tốt thay vì “đổ bể” toàn bộ batch.

Tôi chọn **halt ở expectation** cho những trường hợp nếu lọt vào publish sẽ làm retrieval sai bản chất. E7 là ví dụ điển hình: nếu chunk vẫn chứa `"FAQ bổ sung:"`, `"ghi chú"`, `"migration"` hoặc `"[cleaned:"`, agent downstream có thể lấy đúng doc nhưng sai ngữ cảnh. E8 cũng được đặt là `halt` vì timestamp không chuẩn UTC sẽ làm freshness check mất ý nghĩa.

Ngược lại, tôi giữ E4 `chunk_min_length_8` là **warn**. Khi tự chạy lại pipeline với `run_id=hiep-report`, log cho thấy `short_chunks=1` nhưng toàn bộ expectation quan trọng khác vẫn pass. Dòng ngắn kiểu `SLA P1.` là tín hiệu cần xem lại, nhưng chưa đủ cơ sở để chặn publish ngay.

---

## 3. Sự cố / anomaly

Sự cố tôi thấy rõ nhất trong quá trình làm là dữ liệu raw có vấn đề về **clock semantics**: `exported_at` ban đầu có dạng `2026-04-10T08:00:00`, tức là có ngày giờ nhưng không nói rõ timezone. Nếu để nguyên, freshness monitoring rất dễ bị hiểu sai giữa local time và UTC.

Tôi xử lý việc này bằng `_normalize_exported_at()`: chấp nhận cả dạng không timezone, dạng có `Z`, và dạng có offset; sau đó chuẩn hóa tất cả về UTC chuẩn với hậu tố `Z`. Nếu giá trị trống hoặc sai format thì không cho lọt qua cleaned mà đưa thẳng vào quarantine.

Hiệu quả của quyết định này thể hiện ở manifest tốt `manifest_2026-04-15T08-32Z.json`, nơi `latest_exported_at` đã thành `2026-04-10T08:00:00Z` thay vì chuỗi mơ hồ. Đồng thời expectation `exported_at_iso8601_utc_z` có `violations=0`, tức là rule cleaning và rule kiểm tra đang pair với nhau đúng như thiết kế.

---

## 4. Before/after

Phần tôi thấy thuyết phục nhất là ảnh hưởng trực tiếp lên retrieval, không chỉ lên log.

Trong `artifacts/eval/eval_before.csv`, câu `q_refund_window` trả về top-1 là policy refund nhưng preview vẫn còn nội dung sai: “`14 ngày làm việc`”, và cột `hits_forbidden=yes`. Sau khi clean đúng và publish lại, `artifacts/eval/eval_after.csv` cho cùng câu hỏi top-1 preview là “`7 ngày làm việc`” và `hits_forbidden=no`. Đây là bằng chứng rõ nhất cho việc cleaning rule không chỉ “đẹp dữ liệu” mà còn sửa đúng hành vi truy hồi.

Ngoài ra, hai thay đổi tôi bổ sung trong canonicalization cũng tạo tác động đo được. Với `q_pii_masking`, kết quả chuyển từ `contains_expected=no, hits_forbidden=yes` sang `contains_expected=yes, hits_forbidden=no` nhờ email được mask thành `[MASKED_EMAIL]`. Với `q_term_norm`, câu trả lời chuyển từ cách diễn đạt nhiễu như “phòng máy tính / đội kỹ thuật” sang chuẩn hóa thành `IT Helpdesk`, giúp retrieval nhất quán hơn trên cùng domain.

---

## 5. Cải tiến thêm 2 giờ

Nếu có thêm 2 giờ, tôi sẽ bỏ hard-code các ngưỡng và keyword trong Python, đặc biệt là cutoff HR `2026-01-01`, danh sách editorial prefixes và noise markers. Tôi muốn đọc chúng từ `contracts/data_contract.yaml` hoặc `.env` để rule versioning trở thành cấu hình dữ liệu thay vì logic cứng trong code. Việc này vừa giúp maintain tốt hơn khi policy đổi version, vừa đưa pipeline tiến gần tiêu chí Distinction vì chứng minh được rule clean thay đổi theo contract chứ không phụ thuộc vào một mốc ngày viết tay.
