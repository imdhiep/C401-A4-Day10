# Báo cáo cá nhân - Lab Day 10

**Họ và tên:** Hoàng Thái Dương  
**Vai trò:** Monitoring / Docs Owner  
**Ngày nộp:** 04/15/2026  
**Độ dài:** khoảng 500 từ

---

## 1. Tôi phụ trách phần nào?

Trong Day 10, tôi phụ trách nhóm công việc thuộc Sprint 4, tập trung vào monitoring và hoàn thiện tài liệu nộp bài. Cụ thể, tôi làm trên các file `docs/runbook.md` và `reports/group_report.md`, đồng thời đọc lại các artifact mà nhóm đã tạo ở ba sprint đầu để bảo đảm phần tài liệu phản ánh đúng trạng thái thực tế của repo thay vì chỉ lặp lại yêu cầu trong slide. Tôi cũng là người tổng hợp các bằng chứng từ manifest, eval CSV và grading JSONL để giải thích vì sao pipeline của nhóm đạt yêu cầu ở phần clean/validate/embed nhưng freshness vẫn fail do dữ liệu nguồn cũ.

Phần việc của tôi kết nối trực tiếp với các thành viên khác. Tôi lấy số liệu từ run sạch `2026-04-15T10-09Z`, so sánh với các run `sprint3_before` và `sprint3_final_v2`, rồi chuyển các kết quả kỹ thuật đó thành tài liệu dễ hiểu hơn trong runbook và group report. Tôi cũng dựa vào `artifacts/eval/eval_before.csv`, `artifacts/eval/eval_after.csv` và `artifacts/eval/grading_run.jsonl` để viết phần evidence before/after và phần grading của nhóm.

**Bằng chứng:** `docs/runbook.md`, `reports/group_report.md`, `artifacts/manifests/manifest_2026-04-15T10-09Z.json`, `artifacts/eval/grading_run.jsonl`.

---

## 2. Một quyết định kỹ thuật

Quyết định kỹ thuật quan trọng nhất mà tôi ghi nhận và diễn giải trong phần monitoring là cách tách bạch giữa “pipeline fail” và “freshness fail”. Khi đọc `monitoring/freshness_check.py` và manifest của run sạch, tôi thấy nhóm đang đo freshness tại boundary publish, dựa trên trường `latest_exported_at`. Với run `2026-04-15T10-09Z`, manifest ghi `latest_exported_at = 2026-04-10T08:00:00Z`, nên `age_hours = 122.163`, vượt quá `FRESHNESS_SLA_HOURS = 24`. Điều này dẫn đến `freshness_check=FAIL`.

Tôi chọn diễn giải trong runbook rằng đây không phải lỗi của logic clean/validate/embed. Trái lại, pipeline vẫn kết thúc bằng `PIPELINE_OK`, các expectation mức `halt` đều pass, và index vẫn được cập nhật bình thường. Vì vậy, tôi phân biệt ba mức theo hướng vận hành: `PASS` khi dữ liệu còn trong SLA, `WARN` khi manifest hoặc timestamp có vấn đề định dạng, và `FAIL` khi dữ liệu quá cũ. Cách viết này quan trọng vì nếu gom tất cả vào một loại “fail”, người đọc sẽ rất dễ hiểu sai rằng pipeline bị lỗi, trong khi vấn đề thật sự nằm ở freshness của snapshot nguồn.

---

## 3. Một lỗi hoặc anomaly đã xử lý

Anomaly rõ nhất mà tôi xử lý ở góc nhìn monitoring/docs là trường hợp pipeline chạy thành công nhưng dữ liệu vẫn không đạt yêu cầu freshness. Ban đầu, nếu chỉ nhìn kết quả cuối cùng `PIPELINE_OK`, nhóm rất dễ kết luận run sạch đã “ổn hoàn toàn”. Tuy nhiên, khi tôi đọc `artifacts/manifests/manifest_2026-04-15T10-09Z.json`, tôi thấy `latest_exported_at` vẫn là `2026-04-10T08:00:00Z`, tức snapshot nguồn đã cũ hơn 5 ngày so với thời điểm chạy pipeline.

Tôi dùng phát hiện này để viết lại `docs/runbook.md` theo đúng cấu trúc incident: symptom, detection, diagnosis, mitigation, prevention. Trong đó, tôi mô tả rõ symptom là dữ liệu stale dù pipeline vẫn chạy xong; detection là đọc freshness từ manifest; diagnosis là so sánh các run `sprint3_before`, `sprint3_final_v2` và `2026-04-15T10-09Z`; mitigation là yêu cầu raw export mới thay vì chỉ rerun pipeline trên cùng dữ liệu. Nhờ vậy, phần monitoring của nhóm không chỉ dừng ở việc “có script freshness”, mà còn giải thích được cách dùng nó để ra quyết định publish.

---

## 4. Bằng chứng trước / sau

Tôi sử dụng cả CSV eval và grading JSONL để chứng minh trước/sau. Ở `artifacts/eval/eval_before.csv`, câu `q_refund_window` có `hits_forbidden=yes`, nghĩa là top-k vẫn còn chunk stale “14 ngày làm việc”. Sang `artifacts/eval/eval_after.csv`, cùng câu hỏi này chuyển sang `hits_forbidden=no`, preview top-1 đổi thành “7 ngày làm việc”. Với `q_pii_masking`, before còn lộ `admin_backup@company.com`, còn after đã thành `[MASKED_EMAIL]`. Đây là bằng chứng trực tiếp cho việc dữ liệu sau clean tốt hơn dữ liệu trước clean.

Ở lớp grading chính thức, `artifacts/eval/grading_run.jsonl` cho thấy cả ba câu `gq_d10_01`, `gq_d10_02`, `gq_d10_03` đều có `contains_expected=true`; riêng `gq_d10_03` còn có `top1_doc_matches=true`. Tôi đã đưa các bằng chứng này vào `reports/group_report.md` để phần báo cáo nhóm khớp hoàn toàn với artifact thật.

---

## 5. Cải tiến tiếp theo

Nếu có thêm khoảng 2 giờ, tôi muốn mở rộng monitoring theo hướng đo freshness ở hai boundary thay vì một boundary. Hiện tại nhóm mới đo freshness ở publish boundary thông qua `latest_exported_at` trong manifest. Nếu bổ sung thêm ingest boundary, ví dụ ghi riêng thời điểm nhận raw export và so sánh với thời điểm publish, nhóm sẽ dễ phân biệt hơn giữa “nguồn vào cũ” và “pipeline xử lý chậm”. Đây cũng là hướng cải tiến có thể giúp nhóm tiến gần hơn tới mức Distinction hoặc bonus theo rubric.
