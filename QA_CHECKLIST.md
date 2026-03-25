# QA Checklist — CV Format Tool
> **Phiên bản:** v2.0.0 · Commit: `2da2a26`
> **Test plan:** 5 giai đoạn — Smoke → Functional → Usability → QC → Load
> **Exit criteria:** 90% text-based CVs qua full flow, 0 permission bug, staff mới dùng được sau 1 SOP

---

## Tài khoản test

| Role | Email | Password | Quyền đặc biệt |
|------|-------|----------|----------------|
| **admin** | `admin@ns.vn` | `admin123` | Full (override export, manage all) |
| **qc** | `qc@ns.vn` | `qc123` | Override export, approve with errors |
| **staff** | `staff@ns.vn` | `staff123` | Upload, self-review; **không** override |

> ⚠️ **Lưu ý:** Staff chỉ phê duyệt được khi **0 ERROR** validation. Có WARNING vẫn OK.

---

## Validation rules cần biết trước khi test

### 🔴 ERROR (chặn export cho staff)
- `MISSING_EMAIL` — thiếu email
- `INVALID_EMAIL` — email sai format
- `EMAIL_TYPO` — email có lỗi chính tả (@gmial.com, @gmal.com…)
- `MISSING_NAME` — thiếu họ tên
- `MISSING_PHONE` — thiếu số điện thoại
- `PERIOD_ORDER` — ngày kết thúc ≤ ngày bắt đầu
- `MISSING_REQUIRED_FIELD` — thiếu field bắt buộc

### 🟡 WARNING (cho phép export)
- `WEAK_EMAIL` — email có thể là spam (maildrop, tempmail…)
- `TITLE_CASE` — tên công ty/institution >70% IN HOA
- `BULLET_POINTS` — job entry có < 2 bullet points
- `DUPLICATE_ENTRY` — entry trùng tên (case-insensitive)
- `PHONE_MISMATCH` — country code không khớp format

### 🔵 INFO (thông tin)
- `VN_PHONE_INTL` — số VN có prefix +84 nhưng thiếu 0

---

## ───────────────────────────────────────────
# GIAI ĐOẠN 1: SMOKE TEST (5 CVs)
## ───────────────────────────────────────────

**Mục tiêu:** Xác nhận core flow hoạt động end-to-end
**Thời gian:** ~30 phút
**Số lượng:** 5 CVs (2 DOCX clean + 2 PDF text + 1 edge case)

### ✅ TC-S01: Upload + Parse — DOCX clean
- [ ] Upload file `Test_01_JohnDoe_5y_PM.docx`
- [ ] System parse thành công, hiển thị ReviewPanel
- [ ] Validation hiện 0 ERROR (có thể có WARNING)

### ✅ TC-S02: Upload + Parse — PDF text
- [ ] Upload file `Test_02_NguyenVanA_SDE_3y.pdf`
- [ ] System parse thành công, hiển thị ReviewPanel
- [ ] Data được extract đầy đủ (name, email, phone, career)

### ✅ TC-S03: Review — Sửa lỗi validation
- [ ] Upload CV có lỗi `EMAIL_TYPO` (vd: john.doe@gmial.com)
- [ ] Nhấn "💾 Lưu & tiếp tục" sau khi sửa email
- [ ] Lỗi biến mất khỏi danh sách

### ✅ TC-S04: Approve — Staff approve không có lỗi
- [ ] Login as `staff@ns.vn`
- [ ] Upload CV clean (0 ERROR)
- [ ] Nhấn "✅ Phê duyệt & Export"
- [ ] Export thành công (download .docx)

### ✅ TC-S05: Export — Staff bị chặn khi có ERROR
- [ ] Login as `staff@ns.vn`
- [ ] Upload CV có 1+ ERROR
- [ ] Nút approve bị **disabled** (hiển thị "🔒 Cần QC/Admin phê duyệt")
- [ ] Không có way nào để staff force-export

> **Giai đoạn 1 exit:** 5/5 pass → chuyển Giai đoạn 2

---

## ───────────────────────────────────────────
# GIAI ĐOẠN 2: FUNCTIONAL TEST (20 CVs)
## ───────────────────────────────────────────

**Mục tiêu:** Kiểm tra toàn bộ feature theo từng nhóm CV
**Thời gian:** ~2–3 giờ
**Nhóm 1 (5 CVs clean):** 0–1 minor warning

### ✅ TC-F01–TC-F05: Clean CV flow
- [ ] TC-F01: DOCX, < 1 năm kinh nghiệm
- [ ] TC-F02: DOCX, 5+ năm kinh nghiệm, nhiều jobs
- [ ] TC-F03: PDF text, có education + career
- [ ] TC-F04: PDF text, có gaps (không liên tục)
- [ ] TC-F05: PDF text, có certifications/skills section

**Expected:** Tất cả → 0 ERROR → approve thành công

---

**Nhóm 2 (5 CVs messy):** Cần sửa 1–3 fields

### ✅ TC-F06–TC-F10: Messy CV flow
- [ ] TC-F06: Email typo → sửa được trong ReviewPanel
- [ ] TC-F07: Thiếu phone → thêm được
- [ ] TC-F08: Company name IN HOA → warning (vẫn export được)
- [ ] TC-F09: Period ngược (end < start) → ERROR chặn staff
- [ ] TC-F10: Thiếu email hoàn toàn → ERROR, staff bị chặn

**Expected:** TC-F06 to F08 → export thành công sau sửa. TC-F09–F10 → staff bị chặn

---

**Nhóm 3 (5 CVs difficult):** Complex structure

### ✅ TC-F11–TC-F15: Difficult CV flow
- [ ] TC-F11: Nhiều positions trong 1 job (career_summary[0].positions[])
- [ ] TC-F12: Nested responsibilities/achievements (multiline bullet)
- [ ] TC-F13: Multiple education entries (3+ trường)
- [ ] TC-F14: Other info sections (skills, languages, certifications)
- [ ] TC-F15: CV không có career_summary (mới tốt nghiệp)

**Expected:** Edit được tất cả nested fields. TC-F15 → exportable nếu name + email OK

---

**Nhóm 4 (5 CVs edge cases):**

### ✅ TC-F16–TC-F20: Edge cases
- [ ] TC-F16: Số điện thoại VN format `+84 9x.xxx.xxxx` → INFO warning
- [ ] TC-F17: Email `john@tempmail.com` → WARNING
- [ ] TC-F18: 2 jobs trùng tên công ty → DUPLICATE_ENTRY warning
- [ ] TC-F19: Job chỉ có 1 bullet point → BULLET_POINTS warning
- [ ] TC-F20: Upload cùng file 2 lần → xử lý hợp lý (hoặc error rõ ràng)

**Expected:** All edge cases handled gracefully, no crash

---

## Giai đoạn 2 exit criteria:
- [ ] ≥ 17/20 CVs (85%) parse + export thành công
- [ ] 0 crash / 0 500 error
- [ ] Permission flow đúng: staff bị chặn khi có ERROR

---

## ───────────────────────────────────────────
# GIAI ĐOẠN 3: USABILITY TEST — STAFF MỚI
## ───────────────────────────────────────────

**Mục tiêu:** Staff mới (chưa đọc code, chỉ có SOP) dùng được sau 1 lần đọc
**Thời gian:** ~1 giờ
**Số lượng:** 10 CVs
**Người test:** Staff mới (không phải developer)

### SOP cơ bản (đính kèm checklist này)
```
1. Login → Upload CV
2. Chờ ReviewPanel mở
3. Đọc tab "⚠️ Validation" — nếu có 🔴 ERROR:
   → Chuyển tab "📝 Chỉnh sửa fields"
   → Sửa field bị lỗi
   → Nhấn "💾 Lưu & tiếp tục"
4. Nếu 0 🔴 ERROR:
   → Nhấn "✅ Phê duyệt & Export"
5. Download file .docx
```

### ✅ TC-U01–TC-U10: Staff usability
- [ ] TC-U01–TC-U05: Staff làm theo SOP, 5 CVs clean → pass
- [ ] TC-U06–TC-U08: Staff gặp lỗi (email typo) → tự sửa được
- [ ] TC-U09: Staff gặp ERROR → nhấn "🔒 Cần QC/Admin" → gọi QC (pass)
- [ ] TC-U10: Staff hiểu được badge màu (🔴🟡🔵) không cần giải thích

### ✅ Additional usability checks
- [ ] Staff không cần hướng dẫn để sửa nested field (vd: career[0].positions[1].responsibilities)
- [ ] Staff hiểu multiline = bullet points (mỗi dòng = 1 bullet)
- [ ] Tab "👁️ Preview data" hữu ích khi cần xem JSON
- [ ] Không có confusion giữa "Lưu & tiếp tục" vs "Phê duyệt & Export"

> **Giai đoạn 3 exit:** ≥ 7/10 CVs (70%) staff tự làm được sau 1 lần đọc SOP
> **Target:** ≥ 9/10 (90%) — staff mới không cần hỗ trợ

---

## ───────────────────────────────────────────
# GIAI ĐOẠN 4: QC TEST
## ───────────────────────────────────────────

**Mục tiêu:** QC kiểm tra override flow + data integrity
**Thời gian:** ~1 giờ
**Số lượng:** 10 CVs (đã bị staff review + export)
**Người test:** 1 QC

### ✅ Override flow — QC
- [ ] Login as `qc@ns.vn`
- [ ] Upload CV có ERROR (vd: email typo)
- [ ] Nhấn "⚠️ Phê duyệt & Export (override)"
- [ ] Export thành công dù có ERROR
- [ ] Kiểm tra exported DOCX: đúng data đã sửa

### ✅ Override flow — Admin
- [ ] Login as `admin@ns.vn`
- [ ] Repeat test trên → admin cũng override được

### ✅ QC random audit (5 CVs)
- [ ] QC chọn ngẫu nhiên 5 CVs đã export
- [ ] So sánh exported DOCX với ReviewPanel data → 100% match
- [ ] Không có field bị mất / sai khi export

### ✅ Batch review list
- [ ] QC xem danh sách jobs
- [ ] Filter: `status=qc` → thấy jobs đang chờ QC
- [ ] Filter: `status=exported` → thấy jobs đã export

> **Giai đoạn 4 exit:**
> - [ ] Override flow hoạt động đúng cho QC + Admin
> - [ ] 5/5 exported DOCX match ReviewPanel data
> - [ ] 0 data corruption

---

## ───────────────────────────────────────────
# GIAI ĐOẠN 5: BATCH / LOAD TEST
## ───────────────────────────────────────────

**Mục tiêu:** Xử lý đồng thời 30–50 CVs không crash
**Thời gian:** ~1–2 giờ (tùy số lượng + size)
**Số lượng:** 30–50 CVs across 3 batches

### ✅ Batch 1 — 10 CVs (10 staff uploads)
- [ ] Tạo batch mới
- [ ] Upload 10 files (DOCX + PDF mixed)
- [ ] Batch status: "processing" → "completed"
- [ ] Kiểm tra mỗi job có `status`, `parsed_data`, `validation_result`
- [ ] 0 crash trong quá trình xử lý

### ✅ Batch 2 — 20 CVs (20 staff uploads)
- [ ] Tạo batch thứ 2
- [ ] Upload 20 files
- [ ] Kiểm tra batch summary: số pass / fail
- [ ] Mỗi job có file_path đúng (nếu cần reprocess)

### ✅ Batch 3 — 10–20 CVs (mixed sizes)
- [ ] Upload mix: 5 small (< 500KB) + 5 large (> 2MB) CVs
- [ ] Verify large files không gây timeout
- [ ] Verify all files processed (no silent failure)

### ✅ Batch ownership security
- [ ] Staff A tạo batch → Staff B **không** thấy batch của A
- [ ] Staff A tạo batch → Admin thấy batch của A
- [ ] Staff A không thể cancel batch của Staff B

### ✅ Batch cancel
- [ ] Cancel batch đang processing
- [ ] Verify jobs đang chạy dừng lại
- [ ] Batch status → "cancelled"

> **Giai đoạn 5 exit:**
> - [ ] 3/3 batches processed không crash
> - [ ] 30–50/30–50 CVs có kết quả (parsed + validated)
> - [ ] 0 timeout / 0 OOM error
> - [ ] Batch ownership isolation hoạt động

---

## ───────────────────────────────────────────
# PERMISSION REGRESSION CHECKLIST
## ───────────────────────────────────────────

Chạy lại sau mỗi giai đoạn (5 phút):

### Auth
- [ ] Đăng nhập sai password 3 lần → không có leak thông tin
- [ ] Không có token → call API → 401 Unauthorized
- [ ] Token hết hạn → call API → 401 Unauthorized
- [ ] JWT_SECRET missing khi start server → crash với message rõ ràng

### Role: Staff
- [ ] Upload CV → ✓
- [ ] Xem job của mình → ✓
- [ ] Xem job của người khác → ✗ (403)
- [ ] Override export khi có ERROR → ✗ (button disabled)
- [ ] Xem batch của người khác → ✗ (403)
- [ ] Cancel batch của người khác → ✗ (403)

### Role: QC
- [ ] Override export khi có ERROR → ✓
- [ ] Xem tất cả jobs (không chỉ của mình) → ✓
- [ ] Xem tất cả batches → ✓

### Role: Admin
- [ ] Override export → ✓
- [ ] Xem + cancel bất kỳ batch nào → ✓
- [ ] Access control panel (nếu có) → ✓

---

## ───────────────────────────────────────────
# BUG TRACKING TEMPLATE
## ───────────────────────────────────────────

```
Bug ID: BUG-___
Severity: 🔴 Critical / 🟡 Medium / 🔵 Low
Title:
Steps to reproduce:
1.
2.
3.

Expected:
Actual:

Evidence (screenshot / log):
Assignee:
Status: Open / Fixed / Won't Fix
```

### Known issues (fixed in v2.0.0):
- ~~Batch staff isolation~~ → Fixed commit `2da2a26`
- ~~Duplicate `job.reviewed_data` line~~ → Fixed commit `2da2a26`
- ~~Validation chạy trước khi assign cv_data~~ → Fixed commit `2da2a26`
- ~~bcrypt hash not salted~~ → Fixed commit `be2f125`
- ~~Nested path parser broken~~ → Fixed commit `be2f125`
- ~~Staff có thể override export~~ → Fixed commit `be2f125`

---

## FINAL SIGN-OFF

| Giai đoạn | Kết quả | Tester | Ngày |
|-----------|---------|--------|------|
| Giai đoạn 1 — Smoke (5 CVs) | ___/5 pass | | |
| Giai đoạn 2 — Functional (20 CVs) | ___/20 pass | | |
| Giai đoạn 3 — Usability (10 CVs) | ___/10 pass | | |
| Giai đoạn 4 — QC (10 CVs) | ___/10 pass | | |
| Giai đoạn 5 — Batch (30–50 CVs) | ___/___ pass | | |
| Permission regression | PASS / FAIL | | |

**Overall: ⬜ PASS** — Sẵn sàng production
**Date:** _______________
**Sign-off by:** _______________
