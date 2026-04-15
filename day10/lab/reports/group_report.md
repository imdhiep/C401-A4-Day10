# Báo Cáo Nhóm - Lab Day 10: Data Pipeline & Data Observability

**Tên nhóm:** Nhóm C401-A4  
**Thành viên:**
| Tên | Vai trò (Day 10) | Email |
|-----|------------------|-------|
| Nguyễn Minh Quân | Ingestion / Raw Owner | 26ai.quannm@vinuni.edu |
| Dương Văn Hiệp | Cleaning & Quality Owner | 26ai.hiepdv@vinuni.edu.vn |
| Hoàng Quốc Chung | Cleaning & Quality Owner | 26ai.chunghq@vinuni.edu |
| Bùi Văn Đạt | Embed & Idempotency Owner | 26ai.datbv@vinuni.edu |
| Hoàng Thái Dương | Monitoring / Docs Owner | 26ai.duonght@vinuni.edu.vn |
| Trịnh Đức Anh | Monitoring / Docs Owner | 26ai.anhtd@vinuni.edu |

**Ngày nộp:** 04/15/2026  
**Repo:** https://github.com/imdhiep/C401-A4-Day10.git  
**Độ dài khuyến nghị:** 600-1000 từ

---

> **Nộp tại:** `reports/group_report.md`  
> **Deadline commit:** xem `SCORING.md` (code/trace sớm; report có thể muộn hơn nếu được phép).  
> Phải có **run_id**, **đường dẫn artifact**, và **bằng chứng before/after** (CSV eval hoặc screenshot).

---

## 1. Pipeline tổng quan (150-200 từ)

> Nguồn raw là gì (CSV mẫu / export thật)? Chuỗi lệnh chạy end-to-end? `run_id` lấy ở đâu trong log?

**Tóm tắt luồng:**

Nhóm sử dụng nguồn raw chính là `data/raw/policy_export_dirty.csv`, đóng vai trò như một bản export ingestion từ hệ nguồn trước khi publish sang vector store. Pipeline được chạy qua `etl_pipeline.py` theo chuỗi ingest -> clean -> validate -> embed -> manifest/freshness. Ở bước clean, nhóm giữ các baseline rule như allowlist `doc_id`, chuẩn hoá `effective_date`, loại duplicate, quarantine HR stale version, fix refund window `14 -> 7`, đồng thời mở rộng thêm các rule làm sạch text publish như bỏ prefix biên tập, bỏ ghi chú vận hành, chuẩn hoá `exported_at`, loại marker nội bộ, mask email và chuẩn hoá thuật ngữ `IT Helpdesk`.

Mỗi lần chạy pipeline đều sinh `run_id`, cleaned CSV, quarantine CSV và manifest trong `artifacts/`. Nhóm dùng `sprint3_before` làm run inject để chứng minh dữ liệu xấu vẫn có thể chui vào index khi bỏ fix refund và dùng `--skip-validate`; sau đó dùng `sprint3_final_v2` và run sạch gần nhất `2026-04-15T10-09Z` để chứng minh trạng thái publish ổn định hơn. Việc so sánh before/after được thực hiện bằng `eval_retrieval.py`, còn kiểm tra grading chính thức được thực hiện bằng `grading_run.py` trên bộ `grading_questions.json`.

**Lệnh chạy một dòng (copy từ README thực tế của nhóm):**

`uv run etl_pipeline.py run --run-id 2026-04-15T10-09Z`

---

## 2. Cleaning & expectation (150-200 từ)

> Baseline đã có nhiều rule (allowlist, ngày ISO, HR stale, refund, dedupe...). Nhóm thêm >=3 rule mới + >=2 expectation mới. Khai báo expectation nào **halt**.

### 2a. Bảng metric_impact (bắt buộc - chống trivial)

| Rule / Expectation mới (tên ngắn) | Trước (số liệu) | Sau / khi inject (số liệu) | Chứng cứ (log / CSV / commit) |
|-----------------------------------|------------------|-----------------------------|-------------------------------|
| **Rule 7** `strip_editorial_prefix` | Row 10: chunk_text bắt đầu bằng "FAQ bổ sung: đổi mật khẩu..." (prefix biên tập lọt vào vector store) | Sau rule 7: "đổi mật khẩu qua portal self-service..." - prefix stripped; E7 FAIL nếu rule bị bỏ | `artifacts/cleaned/cleaned_2026-04-15T08-32Z.csv` row it_helpdesk_faq chunk 2 |
| **Rule 8** `strip_operational_notes` | Row 3: chunk_text chứa "(ghi chú: bản sync cũ policy-v3 - lỗi migration)" - ghi chú vận hành lọt vào embed | Sau rule 8: note stripped -> text sạch "...14 ngày làm việc kể từ xác nhận đơn." rồi rule 6 fix -> 7 ngày; E7 FAIL nếu rule bị bỏ | `artifacts/cleaned/cleaned_2026-04-15T08-32Z.csv` row policy_refund_v4 |
| **Rule 9** `normalize_exported_at` | Tất cả row raw có exported_at="2026-04-10T08:00:00" (thiếu timezone); inject row exported_at="" -> 0 quarantine thêm trên baseline | Sau rule 9: cleaned rows có exported_at="2026-04-10T08:00:00Z"; inject exported_at="" -> +1 quarantine (reason: missing_exported_at); E8 FAIL nếu rule bị bỏ qua | `artifacts/quarantine/quarantine_2026-04-15T08-32Z.csv` khi inject |
| **Rule 10** `strip_internal_markers` | Inject chunk_text chứa "[cleaned: stale_refund_window]" -> marker rò rỉ vào vector store nếu không có rule 10 | Sau rule 10: "[cleaned: stale_refund_window]" stripped trước publish; text sạch; E7 FAIL nếu rule bị bỏ | inject test: thêm dòng raw với text "[cleaned: ...]" và chạy pipeline |
| **E7** `published_text_no_operational_noise` | Không có rule 7/8/10: violations=2 (row 3 có operational note, row 10 có editorial prefix) -> halt | Sau rules 7/8/10: violations=0 -> PASS | log `expectation[published_text_no_operational_noise] OK (halt)` |
| **E8** `exported_at_iso8601_utc_z` | Không có rule 9: cleaned rows có exported_at không có "Z" -> violations=6 -> halt | Sau rule 9: violations=0 -> PASS | log `expectation[exported_at_iso8601_utc_z] OK (halt)` |

**Rule chính (baseline + mở rộng):**

- **R1** `allowlist_doc_id`: `legacy_catalog_xyz_zzz` -> quarantine `unknown_doc_id`
- **R2** `normalize_effective_date`: `01/02/2026` -> `2026-02-01` (DD/MM/YYYY -> ISO)
- **R3** `hr_stale_version`: `hr_leave_policy` effective_date=`2025-01-01` -> quarantine
- **R4** `empty_chunk_text`: row 5 chunk_text="" -> quarantine `missing_chunk_text`
- **R5** `dedupe`: row 2 trùng row 1 -> quarantine `duplicate_chunk_text`
- **R6** `fix_refund_window`: `14 ngày làm việc` -> `7 ngày làm việc` trong policy_refund_v4
- **R7** `strip_editorial_prefix`: `"FAQ bổ sung:"` stripped (row 10)
- **R8** `strip_operational_notes`: parenthetical chứa `migration`/`ghi chú`/`sync cũ`/`policy-v3` stripped (row 3)
- **R9** `normalize_exported_at`: `2026-04-10T08:00:00` -> `2026-04-10T08:00:00Z`; quarantine nếu thiếu/invalid
- **R10** `strip_internal_markers`: `[cleaned: ...]` stripped trước publish

**Ví dụ 1 lần expectation fail và cách xử lý:**

Khi chạy `python etl_pipeline.py run --no-refund-fix --skip-validate` (Sprint 3 inject):
- E3 `refund_no_stale_14d_window` FAIL: policy_refund_v4 còn "14 ngày làm việc" -> violations=1
- E7 `published_text_no_operational_noise` FAIL: row 3 chưa qua rule 8 đúng (nếu inject dữ liệu bẩn)
- Pipeline log: `WARN: expectation failed but --skip-validate -> tiếp tục embed (chỉ dùng cho demo Sprint 3)`
- Fix: chạy lại `python etl_pipeline.py run` (không flag) -> cả hai expectation PASS

---

## 3. Before / after ảnh hưởng retrieval hoặc agent (200-250 từ)

> Bắt buộc: inject corruption (Sprint 3) - mô tả + dẫn `artifacts/eval/...` hoặc log.

**Kịch bản inject:**

Nhóm tạo run `sprint3_before` để mô phỏng publish dữ liệu xấu có chủ đích. Ở run này, pipeline được chạy theo chế độ bỏ fix refund window và cho phép tiếp tục embed dù expectation halt, nhằm quan sát khi chunk stale vẫn còn trong top-k thì retrieval bị ảnh hưởng ra sao. Sau đó nhóm chạy lại pipeline chuẩn thành `sprint3_final_v2`, và gần nhất là run sạch `2026-04-15T10-09Z`, để làm mới index bằng snapshot cleaned đúng rules và không dùng `--skip-validate`.

**Kết quả định lượng (từ CSV / bảng):**

So sánh `artifacts/eval/eval_before.csv` và `artifacts/eval/eval_after.csv` cho thấy chất lượng retrieval cải thiện rõ rệt sau khi clean đúng. Ở câu `q_refund_window`, run before vẫn trả về `policy_refund_v4` nhưng `hits_forbidden=yes` vì top-k còn chứa chunk stale `14 ngày làm việc`; sang run after, preview top-1 đổi thành `7 ngày làm việc` và `hits_forbidden=no`. Với `q_pii_masking`, run before làm lộ email thật `admin_backup@company.com` và `contains_expected=no`; sau clean, kết quả trả về `[MASKED_EMAIL]` và `hits_forbidden=no`. Với `q_term_norm`, run before dùng cụm chưa chuẩn `phòng máy tính`, còn run after đã trả về `IT Helpdesk` nên `contains_expected=yes`.

Ở lát cắt versioning, `q_leave_version` đều trả đúng `12 ngày phép năm`, `hits_forbidden=no`, `top1_doc_expected=yes`, cho thấy policy HR 2025 (`10 ngày phép năm`) đã bị quarantine khỏi cleaned export. Kết quả grading chính thức trong `artifacts/eval/grading_run.jsonl` cũng xác nhận cả ba câu `gq_d10_01`, `gq_d10_02`, `gq_d10_03` đều đạt: `contains_expected=true`; riêng `gq_d10_03` còn có `top1_doc_matches=true`. Đây là bằng chứng nhóm không chỉ cải thiện retrieval trên bộ eval thường mà còn đạt đúng bộ câu hỏi grading.

---

## 4. Freshness & monitoring (100-150 từ)

> SLA bạn chọn, ý nghĩa PASS/WARN/FAIL trên manifest mẫu.

Nhóm giữ `FRESHNESS_SLA_HOURS=24` theo `.env.example` và đo freshness tại boundary publish, dựa trên trường `latest_exported_at` trong manifest. Ở run sạch gần nhất `2026-04-15T10-09Z`, manifest ghi `latest_exported_at = 2026-04-10T08:00:00Z`; khi pipeline chạy vào ngày 2026-04-15 thì `age_hours = 122.163`, vượt quá SLA 24 giờ, nên freshness check trả `FAIL`. Nhóm xem đây là tín hiệu đúng của observability: pipeline clean/validate/embed vẫn chạy thành công (`PIPELINE_OK`), nhưng snapshot nguồn đang cũ nên chưa thể coi là "fresh".

Nhóm diễn giải các mức như sau: `PASS` khi `latest_exported_at` còn trong SLA; `WARN` khi manifest thiếu timestamp hoặc timestamp không parse được; `FAIL` khi tuổi dữ liệu vượt SLA hoặc manifest thiếu. Cách tách nghĩa này giúp phân biệt lỗi chất lượng dữ liệu nguồn với lỗi logic xử lý trong pipeline.

---

## 5. Liên hệ Day 09 (50-100 từ)

> Dữ liệu sau embed có phục vụ lại multi-agent Day 09 không? Nếu có, mô tả tích hợp; nếu không, giải thích vì sao tách collection.

Pipeline Day 10 đóng vai trò lớp dữ liệu cho retrieval/multi-agent ở Day 09. Nhóm dùng collection riêng `day10_kb` để dễ theo dõi before/after và tránh lẫn vector cũ với collection của Day 09 trong giai đoạn đánh giá. Tuy nhiên, cleaned output và index này hoàn toàn có thể được tái sử dụng cho flow Day 09 vì các chunk sau clean đã loại stale refund, stale HR version, PII và operational noise. Nói cách khác, Day 10 tạo "publish boundary" để agent Day 09 đọc đúng version dữ liệu hơn.

---

## 6. Rủi ro còn lại & việc chưa làm

- Freshness hiện vẫn `FAIL` vì raw snapshot đang cũ; để đạt trạng thái fresh thực sự, nhóm cần một export mới hơn thay vì chỉ rerun pipeline trên cùng dữ liệu.
- Run sạch gần nhất vẫn còn `chunk_min_length_8` ở mức `warn` với `short_chunks=1`; đây không chặn publish nhưng vẫn là điểm chất lượng dữ liệu có thể cải thiện thêm.
- `contracts/data_contract.yaml` vẫn cần hoàn thiện phần `owner_team` và `alert_channel` để narrative về ownership và monitoring khớp hoàn toàn với phần docs.
- Nhóm mới đo freshness ở boundary publish; nếu có thêm thời gian, có thể mở rộng đo cả ingest boundary để tiến gần hơn mức Distinction/bonus.
