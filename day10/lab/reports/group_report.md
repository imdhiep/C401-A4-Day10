# Báo Cáo Nhóm — Lab Day 10: Data Pipeline & Data Observability

**Tên nhóm:** Nhóm C401-A4  
**Thành viên:**
| Tên | Vai trò (Day 10) | Email |
|-----|------------------|-------|
| ___ | Ingestion / Raw Owner | ___ |
| ___ | Cleaning & Quality Owner | ___ |
| ___ | Embed & Idempotency Owner | ___ |
| ___ | Monitoring / Docs Owner | ___ |

**Ngày nộp:** ___________  
**Repo:** ___________  
**Độ dài khuyến nghị:** 600–1000 từ

---

> **Nộp tại:** `reports/group_report.md`  
> **Deadline commit:** xem `SCORING.md` (code/trace sớm; report có thể muộn hơn nếu được phép).  
> Phải có **run_id**, **đường dẫn artifact**, và **bằng chứng before/after** (CSV eval hoặc screenshot).

---

## 1. Pipeline tổng quan (150–200 từ)

> Nguồn raw là gì (CSV mẫu / export thật)? Chuỗi lệnh chạy end-to-end? `run_id` lấy ở đâu trong log?

**Tóm tắt luồng:**

_________________

**Lệnh chạy một dòng (copy từ README thực tế của nhóm):**

_________________

---

## 2. Cleaning & expectation (150–200 từ)

> Baseline đã có nhiều rule (allowlist, ngày ISO, HR stale, refund, dedupe…). Nhóm thêm **≥3 rule mới** + **≥2 expectation mới**. Khai báo expectation nào **halt**.

### 2a. Bảng metric_impact (bắt buộc — chống trivial)

| Rule / Expectation mới (tên ngắn) | Trước (số liệu) | Sau / khi inject (số liệu) | Chứng cứ (log / CSV / commit) |
|-----------------------------------|------------------|-----------------------------|-------------------------------|
| **Rule 7** `strip_editorial_prefix` | Row 10: chunk_text bắt đầu bằng "FAQ bổ sung: đổi mật khẩu..." (prefix biên tập lọt vào vector store) | Sau rule 7: "đổi mật khẩu qua portal self-service..." — prefix stripped; E7 FAIL nếu rule bị bỏ | `artifacts/cleaned/cleaned_2026-04-15T08-32Z.csv` row it_helpdesk_faq chunk 2 |
| **Rule 8** `strip_operational_notes` | Row 3: chunk_text chứa "(ghi chú: bản sync cũ policy-v3 — lỗi migration)" — ghi chú vận hành lọt vào embed | Sau rule 8: note stripped → text sạch "…14 ngày làm việc kể từ xác nhận đơn." rồi rule 6 fix → 7 ngày; E7 FAIL nếu rule bị bỏ | `artifacts/cleaned/cleaned_2026-04-15T08-32Z.csv` row policy_refund_v4 |
| **Rule 9** `normalize_exported_at` | Tất cả row raw có exported_at="2026-04-10T08:00:00" (thiếu timezone); inject row exported_at="" → 0 quarantine thêm trên baseline | Sau rule 9: cleaned rows có exported_at="2026-04-10T08:00:00Z"; inject exported_at="" → +1 quarantine (reason: missing_exported_at); E8 FAIL nếu rule bị bỏ qua | `artifacts/quarantine/quarantine_2026-04-15T08-32Z.csv` khi inject |
| **Rule 10** `strip_internal_markers` | Inject chunk_text chứa "[cleaned: stale_refund_window]" → marker rò rỉ vào vector store nếu không có rule 10 | Sau rule 10: "[cleaned: stale_refund_window]" stripped trước publish; text sạch; E7 FAIL nếu rule bị bỏ | inject test: thêm dòng raw với text "[cleaned: ...]" và chạy pipeline |
| **E7** `published_text_no_operational_noise` | Không có rule 7/8/10: violations=2 (row 3 có operational note, row 10 có editorial prefix) → halt | Sau rules 7/8/10: violations=0 → PASS | log `expectation[published_text_no_operational_noise] OK (halt)` |
| **E8** `exported_at_iso8601_utc_z` | Không có rule 9: cleaned rows có exported_at không có "Z" → violations=6 → halt | Sau rule 9: violations=0 → PASS | log `expectation[exported_at_iso8601_utc_z] OK (halt)` |

**Rule chính (baseline + mở rộng):**

- **R1** `allowlist_doc_id`: `legacy_catalog_xyz_zzz` → quarantine `unknown_doc_id`
- **R2** `normalize_effective_date`: `01/02/2026` → `2026-02-01` (DD/MM/YYYY → ISO)
- **R3** `hr_stale_version`: `hr_leave_policy` effective_date=`2025-01-01` → quarantine
- **R4** `empty_chunk_text`: row 5 chunk_text="" → quarantine `missing_chunk_text`
- **R5** `dedupe`: row 2 trùng row 1 → quarantine `duplicate_chunk_text`
- **R6** `fix_refund_window`: `14 ngày làm việc` → `7 ngày làm việc` trong policy_refund_v4
- **R7** `strip_editorial_prefix`: `"FAQ bổ sung:"` stripped (row 10)
- **R8** `strip_operational_notes`: parenthetical chứa `migration`/`ghi chú`/`sync cũ`/`policy-v3` stripped (row 3)
- **R9** `normalize_exported_at`: `2026-04-10T08:00:00` → `2026-04-10T08:00:00Z`; quarantine nếu thiếu/invalid
- **R10** `strip_internal_markers`: `[cleaned: ...]` stripped trước publish

**Ví dụ 1 lần expectation fail và cách xử lý:**

Khi chạy `python etl_pipeline.py run --no-refund-fix --skip-validate` (Sprint 3 inject):
- E3 `refund_no_stale_14d_window` FAIL: policy_refund_v4 còn "14 ngày làm việc" → violations=1
- E7 `published_text_no_operational_noise` FAIL: row 3 chưa qua rule 8 đúng (nếu inject dữ liệu bẩn)
- Pipeline log: `WARN: expectation failed but --skip-validate → tiếp tục embed (chỉ dùng cho demo Sprint 3)`
- Fix: chạy lại `python etl_pipeline.py run` (không flag) → cả hai expectation PASS

---

## 3. Before / after ảnh hưởng retrieval hoặc agent (200–250 từ)

> Bắt buộc: inject corruption (Sprint 3) — mô tả + dẫn `artifacts/eval/…` hoặc log.

**Kịch bản inject:**

_________________

**Kết quả định lượng (từ CSV / bảng):**

_________________

---

## 4. Freshness & monitoring (100–150 từ)

> SLA bạn chọn, ý nghĩa PASS/WARN/FAIL trên manifest mẫu.

_________________

---

## 5. Liên hệ Day 09 (50–100 từ)

> Dữ liệu sau embed có phục vụ lại multi-agent Day 09 không? Nếu có, mô tả tích hợp; nếu không, giải thích vì sao tách collection.

_________________

---

## 6. Rủi ro còn lại & việc chưa làm

- …
