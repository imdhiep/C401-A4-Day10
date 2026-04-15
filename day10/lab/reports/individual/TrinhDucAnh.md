# Báo cáo cá nhân — Lab Day 10

**Họ và tên:** Trịnh Đức Anh  
**Vai trò:** Monitoring / Docs Owner  
**Độ dài:** ~450 từ

---

## 1. Phụ trách

Tôi phụ trách phần tài liệu và theo dõi freshness trong Sprint 4. Các file chính tôi làm là `docs/pipeline_architecture.md`, `docs/data_contract.md`, `docs/runbook.md`, và phối hợp kiểm tra `monitoring/freshness_check.py`.

Công việc trọng tâm là chuẩn hóa mô tả pipeline theo đúng luồng thật (`ingest -> clean -> validate -> embed -> manifest -> freshness`), thống nhất định nghĩa `cleaned` và `quarantine`, và ghi rõ ai chịu trách nhiệm ở từng thành phần để nhóm dùng chung khi debug.

Tôi kết nối với bạn phụ trách cleaning/quality để lấy expectation và quarantine reasons, sau đó đưa vào docs để embed owner và report owner đọc cùng một ngữ nghĩa.

**Bằng chứng:** nội dung đã cập nhật trong `docs/pipeline_architecture.md`, `docs/data_contract.md`, và phần freshness trong `docs/quality_report.md` với `run_id=sprint3_final_v2`.

---

## 2. Quyết định kỹ thuật

Quyết định kỹ thuật của tôi là giữ freshness check theo manifest thay vì đọc trực tiếp từ DB watermark. Lý do: manifest luôn được ghi sau mỗi lần chạy `etl_pipeline.py run`, nên dễ tái lập và phù hợp phạm vi lab.

Trong `monitoring/freshness_check.py`, tôi giữ ba trạng thái rõ ràng:

- `PASS`: `age_hours <= sla_hours`
- `FAIL`: vượt SLA
- `WARN`: manifest không có timestamp hợp lệ

Tôi chọn cách này vì giúp phân biệt hai loại sự cố: lỗi dữ liệu stale thực sự (FAIL) và lỗi thiếu dữ liệu quan sát (WARN). Về vận hành, đây là điểm quan trọng để không tốn thời gian rerun sai hướng. Tôi cũng giữ SLA mặc định 24h theo lab để cả nhóm đo cùng một mốc.

---

## 3. Sự cố / anomaly

Anomaly tôi gặp là: pipeline chạy xong, expectation pass, retrieval đã tốt hơn nhưng freshness vẫn FAIL. Nếu chỉ nhìn kết quả cuối, team dễ hiểu nhầm transform hoặc embed còn lỗi.

Tôi kiểm tra bằng lệnh:

`python etl_pipeline.py freshness --manifest artifacts/manifests/manifest_sprint3_final_v2.json`

Sau đó đối chiếu `docs/quality_report.md`:

- `latest_exported_at = 2026-04-10T08:00:00Z`
- `age_hours` lớn hơn 120
- SLA = 24h

Kết luận: lỗi nằm ở dữ liệu nguồn cũ, không nằm ở clean/validate/embed. Cách xử lý của tôi là cập nhật runbook và quality report để nêu rõ nguyên nhân, tránh team rerun nhiều lần mà không thay dữ liệu raw.

---

## 4. Before/after

**Run đối chiếu:** `sprint3_before` vs `sprint3_final_v2`.

**Retrieval evidence:**

- Trước (`artifacts/eval/eval_before.csv`, `q_refund_window`): top1 còn cụm `"14 ngày làm việc"`, `hits_forbidden=yes`.
- Sau (`artifacts/eval/eval_after.csv`, `q_refund_window`): top1 thành `"7 ngày làm việc"`, `hits_forbidden=no`.

**Freshness evidence:**

- Manifest sau run chuẩn vẫn ghi `latest_exported_at=2026-04-10T08:00:00Z`.
- Freshness trả `FAIL` vì vượt SLA 24h.

Điều này cho thấy chất lượng nội dung đã được sửa đúng, nhưng độ tươi dữ liệu vẫn cần raw export mới để pass hoàn toàn ở Sprint 4.

---

## 5. Cải tiến thêm 2 giờ

Nếu có thêm 2 giờ, tôi sẽ thêm một script monitor ngắn đọc manifest mới nhất và ghi trạng thái `PASS/WARN/FAIL + age_hours` vào `artifacts/logs/`, kèm ngưỡng cảnh báo sớm (ví dụ 80% SLA). Như vậy team sẽ thấy xu hướng stale trước khi chạm FAIL.

