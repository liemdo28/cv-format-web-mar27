"""
CV Format Tool — FastAPI Backend
Processes PDF/DOCX CV files via Claude API + Ollama fallback,
fills Navigos Search templates.
"""

import os
import re
import json
import shutil
import tempfile
import fitz  # PyMuPDF
from docx import Document
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
import anthropic
import openai
import uuid

app = FastAPI(title="CV Format Tool API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Paths ──────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_EN = os.path.join(BASE_DIR, "templates", "Form EN 2024.docx")
TEMPLATE_VN = os.path.join(BASE_DIR, "templates", "Form VN 2024.docx")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Copy templates from parent project if not present
PARENT_TEMPLATES = os.path.join(BASE_DIR, "..", "..", "..", "inform-resume", "templates")
if os.path.exists(PARENT_TEMPLATES) and not os.path.exists(TEMPLATE_EN):
    os.makedirs(os.path.join(BASE_DIR, "templates"), exist_ok=True)
    for f in os.listdir(PARENT_TEMPLATES):
        shutil.copy2(os.path.join(PARENT_TEMPLATES, f),
                     os.path.join(BASE_DIR, "templates", f))

# ── CV Extraction Prompts ─────────────────────────────────────
EXTRACTION_PROMPT = """You are a CV/Resume parser. Extract structured information from the following CV text and return ONLY valid JSON.

The JSON must have this exact structure:
{
  "full_name": "string or empty",
  "gender": "string or empty",
  "year_of_birth": "string or empty",
  "marital_status": "string or empty",
  "address": "string or empty",
  "career_summary": [
    {
      "period": "MM/YYYY – MM/YYYY or Present",
      "company": "COMPANY NAME IN UPPERCASE",
      "company_description": "Brief company description if available, or empty string",
      "positions": [
        {
          "period": "MM/YYYY – MM/YYYY (if different sub-period, otherwise empty)",
          "title": "Job Title",
          "report_to": "reporting line if mentioned, or empty",
          "section_label": "e.g. 'Accountability:' or 'Duties:' if mentioned, or empty",
          "responsibilities": ["bullet point 1", "bullet point 2"],
          "achievements_label": "e.g. 'Achievements:' if mentioned, or empty",
          "achievements": ["achievement 1", "achievement 2"]
        }
      ]
    }
  ],
  "education": [
    {
      "period": "YYYY - YYYY",
      "institution": "UNIVERSITY NAME IN UPPERCASE",
      "details": ["degree/major line 1", "line 2"]
    }
  ],
  "other_info": [
    {
      "section_title": "SECTION TITLE IN UPPERCASE",
      "items": ["item 1", "item 2"]
    }
  ]
}

IMPORTANT RULES:
- Extract ALL work experiences, education, and other sections
- Keep the original language of the CV content (do not translate)
- Company names should be in UPPERCASE
- If information is not available, use empty string ""
- Do NOT invent or assume information that is not in the CV

CV TEXT:
"""


# ── Text Extraction ────────────────────────────────────────────
def extract_text_from_pdf(pdf_path: str) -> str:
    doc = fitz.open(pdf_path)
    texts = [page.get_text() for page in doc]
    doc.close()
    return "\n".join(texts)


def extract_text_from_docx(docx_path: str) -> str:
    doc = Document(docx_path)
    texts = []
    for p in doc.paragraphs:
        if p.text.strip():
            texts.append(p.text)
    for table in doc.tables:
        for row in table.rows:
            row_text = "\t".join(cell.text.strip() for cell in row.cells if cell.text.strip())
            if row_text:
                texts.append(row_text)
    return "\n".join(texts)


def detect_language_from_text(text: str) -> str:
    vn_chars = set("àáảãạăắằẳẵặâấầẩẫậèéẻẽẹêếềểễệìíỉĩịòóỏõọôốồổỗộơớờởỡợùúủũụưứừửữựỳýỷỹỵđ"
                   "ÀÁẢÃẠĂẮẰẲẴẶÂẤẦẨẪẬÈÉẺẼẸÊẾỀỂỄỆÌÍỈĨỊÒÓỎÕỌÔỐỒỔỖỘƠỚỜỞỠỢÙÚỦŨỤƯỨỪỬỮỰỲÝỶỸỴĐ")
    count = sum(1 for c in text if c in vn_chars)
    total = len(text.replace(" ", "").replace("\n", ""))
    if total == 0:
        return "en"
    return "vi" if (count / total) > 0.02 else "en"


# ── AI Extraction ─────────────────────────────────────────────
def extract_with_claude(cv_text: str, api_key: str, model: str) -> dict:
    client = anthropic.Anthropic(api_key=api_key)
    message = client.messages.create(
        model=model,
        max_tokens=8000,
        messages=[{"role": "user", "content": EXTRACTION_PROMPT + cv_text}]
    )
    response_text = message.content[0].text
    json_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', response_text, re.DOTALL)
    return json.loads(json_match.group(1) if json_match else response_text)


def extract_with_ollama(cv_text: str, model: str = "qwen2.5:14b") -> dict:
    import urllib.request, urllib.error
    payload = json.dumps({
        "model": model,
        "prompt": EXTRACTION_PROMPT + cv_text,
        "stream": False,
        "options": {"temperature": 0.1, "num_predict": 8000}
    }).encode("utf-8")
    req = urllib.request.Request(
        "http://localhost:11434/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            response_text = result.get("response", "")
    except urllib.error.URLError as e:
        raise ConnectionError(f"Ollama unavailable: {e.reason}")

    json_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', response_text, re.DOTALL)
    return json.loads(json_match.group(1) if json_match else response_text)


def extract_cv_data(cv_text: str, api_key: str, model: str, mode: str,
                   openai_key: str = "", openai_model: str = "gpt-4o-mini") -> dict:
    """Auto: Claude → OpenAI → Ollama (cascading fallback)."""
    errors = []

    # Step 1: Claude API
    if mode in ("auto", "claude_api") and api_key:
        try:
            return extract_with_claude(cv_text, api_key, model)
        except Exception as e:
            errors.append(f"Claude: {e}")
            if mode == "claude_api":
                raise ValueError(errors[-1])

    # Step 2: OpenAI API
    if mode in ("auto", "openai_api") and openai_key:
        try:
            return extract_with_openai(cv_text, openai_key, openai_model)
        except Exception as e:
            errors.append(f"OpenAI: {e}")
            if mode == "openai_api":
                raise ValueError(errors[-1])

    # Step 3: Ollama (local)
    if mode in ("auto", "ollama"):
        try:
            return extract_with_ollama(cv_text, model)
        except Exception as e:
            errors.append(f"Ollama: {e}")
            raise ValueError(" | ".join(errors))

    if mode == "cached":
        raise ValueError("No cached data — provide a file to extract")

    raise ValueError(" | ".join(errors) if errors else "No AI provider available")


def extract_with_openai(cv_text: str, api_key: str, model: str) -> dict:
    """Use OpenAI API to extract structured data from CV text."""
    client = openai.OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model=model,
        max_tokens=8000,
        temperature=0.1,
        messages=[
            {"role": "system", "content": "You are a CV/Resume parser. Extract structured information from the provided CV text and return ONLY valid JSON matching the exact structure provided in the user prompt."},
            {"role": "user", "content": EXTRACTION_PROMPT + cv_text}
        ]
    )
    response_text = response.choices[0].message.content or ""
    json_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', response_text, re.DOTALL)
    return json.loads(json_match.group(1) if json_match else response_text)


def build_suggested_name(cv_data: dict) -> str:
    """Build suggested output name: [Company] - [Position] - [Name]"""
    career = cv_data.get("career_summary", [])
    full_name = cv_data.get("full_name", "").strip()

    # Find current/recent job (first with "Present" or most recent)
    current_job = None
    for job in career:
        period = job.get("period", "")
        if "Present" in period or "Hiện tại" in period:
            current_job = job
            break

    # If no current, use most recent (first in list)
    if current_job is None and career:
        current_job = career[0]

    company = (current_job.get("company", "") or "").strip().title()
    positions = current_job.get("positions", []) if current_job else []
    position = ""
    if positions:
        position = (positions[0].get("title", "") or "").strip().title()
    if not position and current_job:
        position = (current_job.get("title", "") or "").strip().title()

    # Build name parts
    parts = []
    if company:
        parts.append(company)
    if position:
        parts.append(position)
    if full_name:
        parts.append(full_name.title())

    return " - ".join(parts) if parts else ""


# ── Template Filling ───────────────────────────────────────────
def _get_style_id(doc, style_name: str) -> str:
    try:
        return doc.styles[style_name].style_id
    except KeyError:
        return "Normal"


def _make_p(text: str, style_id: str) -> OxmlElement:
    p = OxmlElement('w:p')
    pPr = OxmlElement('w:pPr')
    pStyle = OxmlElement('w:pStyle')
    pStyle.set(qn('w:val'), style_id)
    pPr.append(pStyle)
    p.append(pPr)
    if text:
        r = OxmlElement('w:r')
        t = OxmlElement('w:t')
        t.text = text
        t.set(qn('xml:space'), 'preserve')
        r.append(t)
        p.append(r)
    return p


def _set_field(p: object, label: str, value: str):
    """Replace text after label."""
    for run in p.runs:
        run.text = ""
    if p.runs:
        p.runs[0].text = label + " " + value


def _set_tab(p: object, value: str):
    if p.runs:
        full = p.text
        if '\t' in full:
            label = full.split('\t')[0] + '\t'
        else:
            label = full
        p.runs[0].text = label + value


def _populate_toc(body, career_summary: list):
    """Populate TOC SDT with job entries."""
    sdt_el = None
    for child in body:
        tag = child.tag.split('}')[-1]
        if tag == 'sdt':
            sdt_el = child
            break
    if sdt_el is None:
        return

    sdt_content = sdt_el.find(qn('w:sdtContent'))
    if sdt_content is None:
        return

    for child in list(sdt_content):
        sdt_content.remove(child)

    def _toc_rpr():
        rPr = OxmlElement('w:rPr')
        rPr.append(OxmlElement('w:noProof'))
        return rPr

    toc_entries = [j for j in career_summary if not j.get("use_normal_style", False)]
    if not toc_entries:
        return

    is_first = True
    for job in toc_entries:
        period = job.get("period", "")
        company = job.get("company", "")
        positions = job.get("positions", [])

        p = OxmlElement('w:p')
        pPr = OxmlElement('w:pPr')
        pStyle = OxmlElement('w:pStyle')
        pStyle.set(qn('w:val'), 'TOC1')
        pPr.append(pStyle)
        p.append(pPr)

        if is_first:
            for fld_type, instr in [("begin", ""), ("separate", "")]:
                r = OxmlElement('w:r')
                fc = OxmlElement('w:fldChar')
                fc.set(qn('w:fldCharType'), fld_type)
                r.append(fc)
                p.append(r)
            r_instr = OxmlElement('w:r')
            instr_el = OxmlElement('w:instrText')
            instr_el.set(qn('xml:space'), 'preserve')
            instr_el.text = ' TOC \\o "1-3" \\f \\n \\u '
            r_instr.append(instr_el)
            p.append(r_instr)
            is_first = False

        for txt in [period, company]:
            if txt:
                r = OxmlElement('w:r')
                r.append(_toc_rpr())
                t = OxmlElement('w:t')
                t.text = txt
                t.set(qn('xml:space'), 'preserve')
                r.append(t)
                p.append(r)
            r_tab = OxmlElement('w:r')
            r_tab.append(_toc_rpr())
            r_tab.append(OxmlElement('w:tab'))
            p.append(r_tab)

        sdt_content.append(p)

        for pos_data in positions:
            title = pos_data.get("title", "")
            if not title:
                continue
            p2 = OxmlElement('w:p')
            pPr2 = OxmlElement('w:pPr')
            ps2 = OxmlElement('w:pStyle')
            ps2.set(qn('w:val'), 'TOC3')
            pPr2.append(ps2)
            p2.append(pPr2)
            r2 = OxmlElement('w:r')
            r2.append(_toc_rpr())
            t2 = OxmlElement('w:t')
            t2.text = title
            t2.set(qn('xml:space'), 'preserve')
            r2.append(t2)
            p2.append(r2)
            sdt_content.append(p2)

    if sdt_content.getchildren():
        last_p = sdt_content.getchildren()[-1]
        r_end = OxmlElement('w:r')
        fc_end = OxmlElement('w:fldChar')
        fc_end.set(qn('w:fldCharType'), 'end')
        r_end.append(fc_end)
        last_p.append(r_end)


def fill_template(template_path: str, cv_data: dict, client_name: str,
                  position: str, output_path: str):
    doc = Document(template_path)
    body = doc.element.body

    # Fill header fields
    for p in doc.paragraphs:
        text = p.text.strip()
        if text.startswith("For:") or text.startswith("Khách hàng:"):
            _set_field(p, text.split(":")[0] + ":", client_name.upper())
        elif text.startswith("Re:") or text.startswith("Vị trí:"):
            _set_field(p, text.split(":")[0] + ":", position)
        elif text.startswith("Full name:") or text.startswith("Họ tên:"):
            _set_tab(p, cv_data.get("full_name", ""))
        elif text.startswith("Gender:") or text.startswith("Giới tính:"):
            _set_tab(p, cv_data.get("gender", ""))
        elif text.startswith("Year of birth:") or text.startswith("Năm sinh:"):
            _set_tab(p, cv_data.get("year_of_birth", ""))
        elif text.startswith("Marital status:") or text.startswith("Tình trạng hôn nhân:"):
            _set_tab(p, cv_data.get("marital_status", ""))
        elif text.startswith("Address:") or text.startswith("Địa chỉ:"):
            _set_tab(p, cv_data.get("address", ""))

    # TOC
    _populate_toc(body, cv_data.get("career_summary", []))

    # Find section headers
    work_el = edu_el = other_el = None
    for p in doc.paragraphs:
        t = p.text.strip()
        if t in ("Working Experience", "Kinh nghiệm làm việc"):
            work_el = p._element
        elif t in ("Education", "Trình độ chuyên môn"):
            edu_el = p._element
        elif t in ("Other information (if any)", "Thông tin khác (nếu có)"):
            other_el = p._element

    # Remove placeholder content between sections
    def remove_between(start, end):
        if start is None:
            return
        removing = False
        to_remove = []
        for child in body:
            if child is start:
                removing = True
                continue
            if end and child is end:
                break
            if removing:
                tag = child.tag.split('}')[-1]
                if tag == 'p':
                    to_remove.append(child)
        for el in to_remove:
            body.remove(el)

    def remove_after(start):
        if start is None:
            return
        removing = False
        to_remove = []
        for child in body:
            if child is start:
                removing = True
                continue
            if removing:
                tag = child.tag.split('}')[-1]
                if tag == 'sectPr':
                    continue
                if tag == 'p':
                    to_remove.append(child)
        for el in to_remove:
            body.remove(el)

    remove_between(work_el, edu_el)
    remove_between(edu_el, other_el)
    remove_after(other_el)

    sid = lambda name: _get_style_id(doc, name)

    # Insert work experience
    if work_el:
        ins = work_el
        for job in cv_data.get("career_summary", []):
            period = job.get("period", "")
            company = job.get("company", "")
            use_normal = job.get("use_normal_style", False)
            line = f"{period}\t{company}" if period else company
            p = _make_p(line, "Normal" if use_normal else sid("Heading 1"))
            ins.addnext(p)
            ins = p

            for pos in job.get("positions", []):
                pos_title = pos.get("title", "")
                if pos_title:
                    p = _make_p(pos_title, sid("Heading 3"))
                    ins.addnext(p)
                    ins = p
                for resp in pos.get("responsibilities", []):
                    p = _make_p(resp, sid("1.Content"))
                    ins.addnext(p)
                    ins = p
                for ach in pos.get("achievements", []):
                    p = _make_p(ach, sid("1.Content"))
                    ins.addnext(p)
                    ins = p
            p = _make_p("", "Normal")
            ins.addnext(p)
            ins = p

    # Insert education
    if edu_el:
        ins = edu_el
        for edu in cv_data.get("education", []):
            period = edu.get("period", "")
            institution = edu.get("institution", "")
            line = f"{period}\t{institution}" if period and institution else (period or institution)
            p = _make_p(line, "Normal")
            ins.addnext(p)
            ins = p
            for detail in edu.get("details", []):
                p = _make_p(f"\t{detail}", "Normal")
                ins.addnext(p)
                ins = p
            p = _make_p("", "Normal")
            ins.addnext(p)
            ins = p

    # Insert other info
    if other_el:
        ins = other_el
        for section in cv_data.get("other_info", []):
            p = _make_p(section.get("section_title", ""), "Normal")
            ins.addnext(p)
            ins = p
            for item in section.get("items", []):
                p = _make_p(item, sid("1.Content"))
                ins.addnext(p)
                ins = p
            p = _make_p("", "Normal")
            ins.addnext(p)
            ins = p

    doc.save(output_path)


# ── API Routes ─────────────────────────────────────────────────
class ProcessResponse(BaseModel):
    status: str
    message: str
    suggestedName: str | None = None
    downloadId: str | None = None
    downloadUrl: str | None = None


@app.get("/")
async def root():
    return {"name": "CV Format Tool API", "version": "1.0.0"}


@app.get("/health")
async def health(api_key: str = "", openai_api_key: str = ""):
    """Check which AI providers are available."""
    result = {"claude": "unavailable", "openai": "unavailable", "ollama": "unavailable"}

    if api_key:
        try:
            client = anthropic.Anthropic(api_key=api_key)
            client.messages.create(model="claude-sonnet-4-20250514", max_tokens=1, messages=[{"role": "user", "content": "hi"}])
            result["claude"] = "ok"
        except Exception as e:
            err = str(e)
            if "credit" in err.lower():
                result["claude"] = "no_credit"
            elif "401" in err or "authentication" in err.lower() or "invalid" in err.lower():
                result["claude"] = "invalid_key"
            else:
                result["claude"] = f"error: {err[:80]}"

    if openai_api_key:
        try:
            client = openai.OpenAI(api_key=openai_api_key)
            client.chat.completions.create(model="gpt-4o-mini", max_tokens=1, messages=[{"role": "user", "content": "hi"}])
            result["openai"] = "ok"
        except openai.RateLimitError as e:
            result["openai"] = "quota_exceeded"
        except openai.AuthenticationError as e:
            result["openai"] = "invalid_key"
        except Exception as e:
            err = str(e)
            if "incorrect" in err.lower() or "invalid" in err.lower():
                result["openai"] = "invalid_key"
            elif "429" in err or "quota" in err.lower() or "exceeded" in err.lower():
                result["openai"] = "quota_exceeded"
            else:
                result["openai"] = f"error: {err[:80]}"

    try:
        import urllib.request
        req = urllib.request.Request("http://localhost:11434/api/tags", timeout=3)
        with urllib.request.urlopen(req) as resp:
            if resp.status == 200:
                result["ollama"] = "ok"
    except Exception:
        pass

    return result


@app.post("/process", response_model=ProcessResponse)
async def process_cv(
    file: UploadFile = File(...),
    extraction_mode: str = Form("auto"),
    model: str = Form("claude-sonnet-4-20250514"),
    api_key: str = Form(""),
    openai_api_key: str = Form(""),
    openai_model: str = Form("gpt-4o-mini"),
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in (".pdf", ".docx"):
        raise HTTPException(status_code=400, detail="Only PDF and DOCX files are supported")

    # Save to temp file
    suffix = os.path.splitext(file.filename)[1]
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name

    try:
        # Extract text
        if ext == ".pdf":
            cv_text = extract_text_from_pdf(tmp_path)
        else:
            cv_text = extract_text_from_docx(tmp_path)

        if not cv_text.strip():
            return ProcessResponse(
                status="error",
                message="Could not extract text from CV (possibly image-based PDF)"
            )

        lang = detect_language_from_text(cv_text)
        template_path = TEMPLATE_VN if lang == "vi" else TEMPLATE_EN

        # Extract CV data (Claude → OpenAI → Ollama fallback)
        try:
            cv_data = extract_cv_data(
                cv_text, api_key, model, extraction_mode,
                openai_key=openai_api_key, openai_model=openai_model
            )
        except Exception as e:
            return ProcessResponse(
                status="error",
                message=f"AI extraction failed: {str(e)}"
            )

        # Build suggested name: [Company] - [Position] - [Name]
        suggested_name = build_suggested_name(cv_data)

        # Generate unique download ID and path
        download_id = str(uuid.uuid4())[:8]
        safe_name = re.sub(r'[^\w\s.-]', '', file.filename or "cv").strip()
        safe_name = re.sub(r'\s+', '_', safe_name)
        output_dir = os.path.join(OUTPUT_DIR, download_id)
        os.makedirs(output_dir, exist_ok=True)
        output_docx = os.path.join(output_dir, f"{safe_name}{suffix}")

        # Fill template
        try:
            fill_template(template_path, cv_data, "CLIENT", "POSITION", output_docx)
        except Exception as e:
            return ProcessResponse(
                status="error",
                message=f"Template fill failed: {str(e)}"
            )

        return ProcessResponse(
            status="success",
            message=f"Generated ({lang.upper()} template)",
            suggestedName=suggested_name,
            downloadId=download_id,
            downloadUrl=f"/download/{download_id}"
        )

    finally:
        os.unlink(tmp_path)


@app.get("/download/{download_id}")
async def download(download_id: str):
    """Download a processed DOCX file by its ID."""
    path = os.path.join(OUTPUT_DIR, download_id)
    if not os.path.isdir(path):
        raise HTTPException(status_code=404, detail="File not found")

    # Find the .docx file in that directory
    files = [f for f in os.listdir(path) if f.endswith('.docx')]
    if not files:
        raise HTTPException(status_code=404, detail="File not found")

    file_path = os.path.join(path, files[0])
    return FileResponse(
        file_path,
        filename=files[0],
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
