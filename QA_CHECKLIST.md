# CV Format Tool — QA Test Checklist

> Version: 2.1.0
> Date: 2026-03-25
> Exit Criteria: 90% text-based CV pass full flow, no auth/export bugs, batch 30 CV stable

---

## Phase 1 — Smoke Test (5 CV)

### Test Data
| # | File | Type | Purpose |
|---|------|------|---------|
| 1 | CV sach 1 | DOCX | Happy path |
| 2 | CV sach 2 | DOCX | Happy path |
| 3 | CV text-based 1 | PDF text | PDF extraction |
| 4 | CV text-based 2 | PDF text | PDF extraction |
| 5 | CV scan | PDF scan | OCR / fail cleanly |

### 1.1 Auth Tests
- [ ] **Login admin**: `POST /auth/login` email=`admin@cvformat.local` password=`admin123` -> token OK
- [ ] **Login staff**: `POST /auth/login` email=`staff@cvformat.local` password=`staff123` -> token OK
- [ ] **Login QC**: `POST /auth/login` email=`qc@cvformat.local` password=`qc123` -> token OK
- [ ] **Login sai password** -> 401 "Invalid email or password"
- [ ] **Truy cap /jobs khong token** -> 401
- [ ] **Staff truy cap /users** -> 403
- [ ] **GET /auth/me** -> tra dung user info

### 1.2 Upload + Parse
- [ ] **Upload DOCX** (staff): `POST /jobs` file=CV1.docx -> `job_id`, `status: "review"`, `parsed_data` co data
- [ ] **Upload PDF text-based** (staff): `POST /jobs` -> parse OK
- [ ] **Upload PDF scan** (staff): `POST /jobs` -> tra loi loi ro rang (422), khong treo
- [ ] **Upload file khong hop le** (.txt, .jpg): -> 400 "Only PDF and DOCX supported"
- [ ] **Upload file rong** -> error ro rang

### 1.3 Review Flow
- [ ] **GET /jobs/{id}** -> tra parsed_data + validation_errors
- [ ] **PATCH /jobs/{id}/review** (staff): gui reviewed_data -> OK, version tang
- [ ] **GET /jobs/{id}/versions** -> co 2 version (initial + review)

### 1.4 QC Flow
- [ ] **PATCH /jobs/{id}/qc** (qc): result="pass" -> status="approved"
- [ ] **PATCH /jobs/{id}/qc** (qc): result="needs_revision" -> status="review"
- [ ] **PATCH /jobs/{id}/qc** (qc): result="fail" -> status="error"

### 1.5 Export
- [ ] **POST /jobs/{id}/export** (staff, status=approved) -> download_url, DOCX OK
- [ ] **GET /download/{id}** -> file DOCX download duoc, mo duoc trong Word/LibreOffice
- [ ] **Export khi con validation errors** (staff) -> 403 "blocking validation errors"
- [ ] **Export khi con errors** (QC/admin voi override) -> OK (override)

### 1.6 Health Check
- [ ] **GET /health** -> `status: "ok"`, kiem tra `components.ocr`

### Smoke Test Pass Criteria
- [ ] Khong crash
- [ ] Loi hien thi ro rang
- [ ] DOCX output mo duoc
- [ ] PDF scan fail sach, khong treo

---

## Phase 2 — Functional Test (20 CV)

### Test Data Groups

**Nhom A — CV sach (5 CV)**
| # | Profile | Type |
|---|---------|------|
| A1 | Software Engineer | DOCX |
| A2 | Accountant | DOCX |
| A3 | HR Manager | PDF |
| A4 | Marketing Specialist | PDF |
| A5 | Sales Director | DOCX |

**Nhom B — CV lon xon (5 CV)**
| # | Description | Type |
|---|-------------|------|
| B1 | Canva resume (nhieu cot) | PDF |
| B2 | Design nang, icon nhieu | PDF |
| B3 | Template fancy (2 cot) | PDF |
| B4 | CV scan chup anh | PDF scan |
| B5 | CV handwritten | PDF scan |

**Nhom C — CV kho (5 CV)**
| # | Description | Type |
|---|-------------|------|
| C1 | Thieu email | DOCX |
| C2 | Thieu phone | PDF |
| C3 | Date format la (2020 thay vi 01/2020) | DOCX |
| C4 | CV tieng Viet | DOCX |
| C5 | CV mixed VN/EN | PDF |

**Nhom D — Edge cases (5 CV)**
| # | Description | Type |
|---|-------------|------|
| D1 | Period nguoc (end < start) | DOCX |
| D2 | Title ALL CAPS | PDF |
| D3 | Cong ty trung lap | DOCX |
| D4 | Bullet qua it (<2) | PDF |
| D5 | Email typo (gmial.com) | DOCX |

### Test Log Template
| File | Type | Role | Upload | Parse | Errors | Warnings | Review | QC | Export | Output OK | Time | Notes |
|------|------|------|--------|-------|--------|----------|--------|----|--------|-----------|------|-------|
| A1   | DOCX | staff | | | | | | | | | | |
| A2   | DOCX | staff | | | | | | | | | | |
| ...  | ... | ... | | | | | | | | | | |

### Kiem tra Validation
- [ ] **CV thieu email** -> error FIELD_REQUIRED
- [ ] **CV email typo** (gmial.com) -> error EMAIL_TYPO voi suggestion
- [ ] **Phone qua ngan** (<7 so) -> error PHONE_TOO_SHORT
- [ ] **Phone VN sai format** -> warning PHONE_FORMAT_VN
- [ ] **Period nguoc** (end < start) -> error PERIOD_END_BEFORE_START
- [ ] **Nam sinh < 1940 hoac > 2010** -> warning YEAR_OF_BIRTH_UNREASONABLE
- [ ] **Title ALL CAPS** -> warning TITLE_ALL_CAPS
- [ ] **Cong ty trung lap** -> warning DUPLICATE_ENTRIES
- [ ] **Bullet qua it** -> warning TOO_FEW_BULLET_POINTS
- [ ] **CV gan rong** (<3 field) -> error CV_NEARLY_EMPTY

### Pass Criteria
- [ ] 80-90% CV text-based di het flow
- [ ] Toan bo loi chan duoc phat hien (errors block export)
- [ ] CV scan fail sach, khong tao output rac
- [ ] Validation errors/warnings dung loai

---

## Phase 3 — OCR Test (6 scanned PDF)

### Pre-requisite
- [ ] **GET /health** -> kiem tra `components.ocr` = "ok", `ocr_backend` = "tesseract"
- [ ] Neu ocr = "unavailable" -> deploy chua cai Tesseract system binary -> fix truoc khi test

### Test Data
| # | File | Description |
|---|------|-------------|
| O1 | PDF scan sach (300 DPI) | 1-2 trang, text ro |
| O2 | PDF scan mo (150 DPI) | Chat luong thap |
| O3 | PDF chup bang dien thoai | Nghieng, bong |
| O4 | PDF tieng Viet scan | Dau tieng Viet |
| O5 | PDF mixed (trang 1 text, trang 2 scan) | Kiem tra hybrid |
| O6 | PDF image-only (poster/infographic) | Khong phai CV |

### Test Cases
- [ ] **O1** upload -> OCR extract text -> parse co data -> validation chay
- [ ] **O2** upload -> OCR co text nhung chat luong kem -> validation co warnings
- [ ] **O3** upload -> OCR fail hoac rat it text -> error ro rang
- [ ] **O4** upload -> OCR voi tieng Viet -> dau dung khong
- [ ] **O5** upload -> text + OCR ket hop -> parse OK
- [ ] **O6** upload -> fail sach voi message "could not extract text"

### OCR Quality Log
| File | OCR chars | Parse OK | Validation | Usable? | Notes |
|------|-----------|----------|------------|---------|-------|
| O1 | | | | | |
| O2 | | | | | |
| O3 | | | | | |
| O4 | | | | | |
| O5 | | | | | |
| O6 | | | | | |

### Pass Criteria
- [ ] OCR thanh cong it nhat 2/6 file scan
- [ ] Tat ca fail case co error message ro rang
- [ ] Khong co case treo/crash
- [ ] /health report dung OCR status

---

## Phase 4 — Usability Test (1 staff moi)

### Setup
- Tao 1 user staff moi: `POST /users` (admin)
- Chuan bi 10 CV + SOP ngan

### Quan sat
- [ ] Staff moi login duoc
- [ ] Staff moi hieu flow upload -> review -> QC
- [ ] Staff moi phan biet duoc error vs warning
- [ ] Staff moi biet luc nao can QC/Admin
- [ ] Staff moi tu xu ly duoc it nhat 7/10 CV
- [ ] Ghi nhan cho vuong thanh bug/UI issue

### Questions to Ask
1. Flow co de hieu khong?
2. Bi ket o dau?
3. Co biet sai so nao can sua?
4. Mat bao lau / CV?

---

## Phase 5 — QC Workflow Test (10 CV)

### Chuan bi
- 10 CV da qua review boi staff
- 1 QC user

### Test Cases
- [ ] QC xem validation result cua tung CV
- [ ] QC xem version history (GET /jobs/{id}/versions)
- [ ] QC approve CV tot -> status="approved"
- [ ] QC reject CV xau -> status="error"
- [ ] QC yeu cau sua lai -> status="review" (staff thay va sua tiep)
- [ ] QC override export khi co warnings (khong co errors)
- [ ] QC co cv:override_export -> co the export khi co errors

### Do luong
| Metric | Value |
|--------|-------|
| Avg time QC / CV | ___s |
| Reject rate | ___% |
| Ly do reject pho bien | ___ |
| UI du thong tin? | Y/N |

---

## Phase 6 — Batch / Load Test (30-50 CV)

### Test Setup
- Chuan bi 30-50 CV text-based (DOCX + PDF mix)
- Chia 2-3 batch: batch A (15 CV), batch B (15 CV), batch C (20 CV)

### Test Cases
- [ ] **POST /batch** 15 files -> batch_id, status="running"
- [ ] **GET /batch/{id}** polling -> progress tang dan
- [ ] **GET /batch/{id}/jobs** -> tung job co status rieng
- [ ] **Batch hoan tat** -> status="completed" hoac "completed_with_errors"
- [ ] **Batch 2 (staff khac)** -> staff 1 KHONG thay batch cua staff 2
- [ ] **Cancel batch** -> status="cancelled", jobs pending -> cancelled
- [ ] **Staff cancel batch nguoi khac** -> 403

### Do luong
| Metric | Value |
|--------|-------|
| Total time batch 15 CV | ___s |
| Total time batch 20 CV | ___s |
| So job fail | ___ |
| Loai loi | ___ |
| Co batch nao doc sai owner? | Y/N |
| Server co crash/treo? | Y/N |

---

## Bug Focus List

Soi ky cac diem nay (dua tren review code):

### Auth
- [ ] Login voi password moi (bcrypt) -> OK
- [ ] Login voi password cu (PBKDF2 fallback) -> OK
- [ ] Login voi password HMAC legacy -> REJECTED (phai re-hash)
- [ ] Token expired -> 401 "Token expired"
- [ ] Refresh token -> new access token

### Export
- [ ] Export khi con errors -> block (staff), allow (QC/admin override)
- [ ] Export tu status "review" -> allowed
- [ ] Export tu status "error" -> blocked
- [ ] DOCX output KHONG con text cu dinh lai (kiem tra _set_tab fix)

### Review
- [ ] Review save voi nested array fields (career_summary.positions.responsibilities)
- [ ] Review tao version moi, khong ghi de version cu
- [ ] Validation re-run sau review

### Batch
- [ ] Batch ownership giua cac staff
- [ ] Cancel batch chi cho owner hoac admin
- [ ] Batch 30 CV khong crash
- [ ] Job status chuyen dung: queued -> processing -> parsed -> validated -> completed/failed

### JSON Parser
- [ ] AI tra JSON sach -> parse OK
- [ ] AI tra JSON trong ``` block -> parse OK
- [ ] AI tra malformed JSON (trailing comma) -> parse OK (cleanup)
- [ ] AI tra text khong co JSON -> error message ro rang

### OCR (neu co)
- [ ] PDF scan co OCR installed -> extract text
- [ ] PDF scan khong co OCR -> error message chi dan cai OCR
- [ ] GET /health -> hien thi OCR status + backend name

### Legacy Endpoint
- [ ] POST /process van hoat dong (backward compat)
- [ ] POST /process hien deprecated trong /docs (Swagger)

---

## Exit Criteria Summary

| Criteria | Target | Actual | Pass? |
|----------|--------|--------|-------|
| CV text-based full flow | >= 90% | | |
| Bug quyen truy cap nghiem trong | 0 | | |
| Bug export sai noi dung | 0 | | |
| Batch 30 CV khong crash | Yes | | |
| Staff moi dung duoc sau SOP | Yes | | |
| QC duyet duoc trong he thong | Yes | | |

---

## Appendix: API Quick Reference

```
# Auth
POST   /auth/login          — Login, get tokens
POST   /auth/refresh         — Refresh access token
GET    /auth/me              — Current user info

# Users (admin only)
GET    /users                — List users
POST   /users                — Create user
PATCH  /users/{id}           — Update user

# Jobs (main workflow)
POST   /jobs                 — Upload + parse CV
GET    /jobs                 — List jobs
GET    /jobs/{id}            — Get job detail
PATCH  /jobs/{id}/review     — Staff review/correct
PATCH  /jobs/{id}/qc         — QC approve/reject
POST   /jobs/{id}/export     — Export to DOCX
GET    /jobs/{id}/versions   — Version history

# Batch
POST   /batch                — Upload batch
GET    /batch                — List batches
GET    /batch/{id}           — Batch status
GET    /batch/{id}/jobs      — Jobs in batch
DELETE /batch/{id}           — Cancel batch

# Other
POST   /validate             — Standalone validation
GET    /audit                — Audit log
GET    /stats                — KPI dashboard
GET    /health               — System health
GET    /download/{id}        — Download DOCX

# Legacy (DEPRECATED)
POST   /process              — Old process endpoint (use /jobs instead)
```

---

## Appendix B: Step-by-Step Tester Guide

> Huong dan cho tester thao tac tung buoc. Copy phan nay ra de test.

### B.1 Setup

```bash
# Base URL (thay bang URL Render thuc te)
BASE=https://cv-format-api.onrender.com

# 1. Kiem tra health
curl $BASE/health | python3 -m json.tool

# 2. Login admin
curl -X POST $BASE/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@cvformat.local","password":"admin123"}' \
  | python3 -m json.tool

# Luu access_token vao bien
ADMIN_TOKEN="<paste token here>"

# 3. Login staff
curl -X POST $BASE/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"staff@cvformat.local","password":"staff123"}'

STAFF_TOKEN="<paste token here>"

# 4. Login QC
curl -X POST $BASE/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"qc@cvformat.local","password":"qc123"}'

QC_TOKEN="<paste token here>"
```

### B.2 Upload + Parse (staff)

```bash
# Upload 1 CV
curl -X POST $BASE/jobs \
  -H "Authorization: Bearer $STAFF_TOKEN" \
  -F "file=@/path/to/cv.docx" \
  -F "extraction_mode=offline" \
  | python3 -m json.tool

# Luu job_id
JOB_ID="<paste job_id here>"

# Xem job detail
curl $BASE/jobs/$JOB_ID \
  -H "Authorization: Bearer $STAFF_TOKEN" \
  | python3 -m json.tool
```

### B.3 Review (staff)

```bash
# Xem validation errors truoc
curl $BASE/jobs/$JOB_ID \
  -H "Authorization: Bearer $STAFF_TOKEN" \
  | python3 -m json.tool | grep -A5 validation

# Gui review data (sua lai du lieu)
curl -X PATCH $BASE/jobs/$JOB_ID/review \
  -H "Authorization: Bearer $STAFF_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "reviewed_data": {
      "full_name": "Nguyen Van A",
      "email": "nguyenvana@gmail.com",
      "phone": "+84 912 345 678",
      "career_summary": [],
      "education": [],
      "other_info": []
    },
    "notes": "Fixed email and phone"
  }' | python3 -m json.tool

# Kiem tra version history
curl $BASE/jobs/$JOB_ID/versions \
  -H "Authorization: Bearer $STAFF_TOKEN" \
  | python3 -m json.tool
```

### B.4 QC (qc user)

```bash
# QC approve
curl -X PATCH $BASE/jobs/$JOB_ID/qc \
  -H "Authorization: Bearer $QC_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"result":"pass","notes":"Looks good"}' \
  | python3 -m json.tool

# Hoac reject
curl -X PATCH $BASE/jobs/$JOB_ID/qc \
  -H "Authorization: Bearer $QC_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"result":"needs_revision","notes":"Email sai"}' \
  | python3 -m json.tool
```

### B.5 Export + Download (staff)

```bash
# Export (chi khi status=approved)
curl -X POST $BASE/jobs/$JOB_ID/export \
  -H "Authorization: Bearer $STAFF_TOKEN" \
  -F "client_name=ABC Corp" \
  -F "position=Software Engineer" \
  | python3 -m json.tool

# Download DOCX
DOWNLOAD_ID="<paste download_id>"
curl -o output.docx $BASE/download/$DOWNLOAD_ID

# Mo file kiem tra
# macOS: open output.docx
# Linux: libreoffice output.docx
```

### B.6 Batch Upload (staff)

```bash
# Upload nhieu file
curl -X POST $BASE/batch \
  -H "Authorization: Bearer $STAFF_TOKEN" \
  -F "files=@cv1.docx" \
  -F "files=@cv2.pdf" \
  -F "files=@cv3.docx" \
  -F "extraction_mode=offline" \
  -F "batch_name=Test batch 1" \
  | python3 -m json.tool

BATCH_ID="<paste batch_id>"

# Polling status
curl $BASE/batch/$BATCH_ID \
  -H "Authorization: Bearer $STAFF_TOKEN" \
  | python3 -m json.tool

# Xem tung job
curl $BASE/batch/$BATCH_ID/jobs \
  -H "Authorization: Bearer $STAFF_TOKEN" \
  | python3 -m json.tool
```

### B.7 Permission Tests

```bash
# Staff KHONG duoc xem /users
curl $BASE/users \
  -H "Authorization: Bearer $STAFF_TOKEN"
# Expected: 403

# Staff KHONG duoc cancel batch nguoi khac
curl -X DELETE $BASE/batch/$OTHER_BATCH_ID \
  -H "Authorization: Bearer $STAFF_TOKEN"
# Expected: 403

# Khong token -> 401
curl $BASE/jobs
# Expected: 401

# QC xem tat ca jobs
curl $BASE/jobs \
  -H "Authorization: Bearer $QC_TOKEN" \
  | python3 -m json.tool
# Expected: all jobs visible
```

### B.8 OCR Test

```bash
# Kiem tra OCR status
curl $BASE/health | python3 -m json.tool
# Expected: "ocr": "ok", "ocr_backend": "tesseract"

# Upload scanned PDF
curl -X POST $BASE/jobs \
  -H "Authorization: Bearer $STAFF_TOKEN" \
  -F "file=@scanned_cv.pdf" \
  -F "extraction_mode=offline" \
  | python3 -m json.tool
# Neu OCR ok: parsed_data co data
# Neu OCR fail: 422 voi message ro rang
```
