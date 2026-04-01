"""
CV Format Tool — Validation Engine
Validates parsed CV data: email, phone, date format, required fields.
Used BEFORE template fill to prevent bad CVs from reaching clients.
"""

import re
from typing import Any
from dataclasses import dataclass, field
from enum import Enum


# ── Error severity ───────────────────────────────────────────────
class ValidationSeverity(str, Enum):
    ERROR = "error"      # Must fix before export
    WARNING = "warning"  # Should fix but not blocking
    INFO = "info"        # FYI only


@dataclass
class ValidationError:
    field: str              # e.g. "email", "career_summary[0].period"
    code: str               # e.g. "INVALID_EMAIL_FORMAT"
    message: str            # Human-readable
    severity: str           # error | warning | info
    value: Any = None       # The invalid value (for display)
    suggestion: str = ""    # How to fix it


@dataclass
class ValidationResult:
    is_valid: bool          # True if no ERROR-level issues
    is_exportable: bool    # True if all required fields present + no errors
    errors: list[ValidationError] = field(default_factory=list)
    warnings: list[ValidationError] = field(default_factory=list)
    info: list[ValidationError] = field(default_factory=list)

    @property
    def error_count(self) -> int:
        return len(self.errors)

    @property
    def warning_count(self) -> int:
        return len(self.warnings)

    def to_dict(self) -> dict[str, Any]:
        def err_dict(e: ValidationError) -> dict[str, Any]:
            return {
                "field": e.field,
                "code": e.code,
                "message": e.message,
                "severity": e.severity,
                "value": e.value,
                "suggestion": e.suggestion,
            }
        return {
            "is_valid": self.is_valid,
            "is_exportable": self.is_exportable,
            "errors": [err_dict(e) for e in self.errors],
            "warnings": [err_dict(w) for w in self.warnings],
            "info": [err_dict(i) for i in self.info],
            "error_count": len(self.errors),
            "warning_count": len(self.warnings),
            "summary": self.summary,
        }

    @property
    def summary(self) -> str:
        parts = []
        if self.errors:
            parts.append(f"{len(self.errors)} error(s)")
        if self.warnings:
            parts.append(f"{len(self.warnings)} warning(s)")
        if self.info:
            parts.append(f"{len(self.info)} info")
        return ", ".join(parts) if parts else "All clear"


# ── Validators ────────────────────────────────────────────────────

def validate_email(value: str) -> ValidationError | None:
    if not value or not value.strip():
        return None  # Missing handled separately
    pattern = r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$"
    if not re.match(pattern, value.strip()):
        return ValidationError(
            field="email",
            code="INVALID_EMAIL_FORMAT",
            message=f"Email không hợp lệ: '{value}'",
            severity=ValidationSeverity.ERROR,
            value=value,
            suggestion="Ví dụ: nguyenvana@company.com",
        )
    # Check for common typos
    common_typos = {
        "gmial.com": "gmail.com",
        "gmal.com": "gmail.com",
        "gmai.com": "gmail.com",
        "gmaiil.com": "gmail.com",
        "hotmal.com": "hotmail.com",
        "outloo.com": "outlook.com",
        "yahooo.com": "yahoo.com",
    }
    lower = value.lower()
    for typo, fix in common_typos.items():
        if typo in lower:
            return ValidationError(
                field="email",
                code="EMAIL_TYPO",
                message=f"Email có thể bị đánh máy: '{value}' — ý bạn là {fix}?",
                severity=ValidationSeverity.ERROR,
                value=value,
                suggestion=f"Sửa thành: {value.lower().replace(typo, fix)}",
            )
    return None


def validate_phone(value: str, country: str = "auto") -> ValidationError | None:
    if not value or not value.strip():
        return None  # Missing handled separately

    # Strip all non-digit except + at start
    digits_only = re.sub(r"[^\d]", "", value)
    original = value.strip()

    # Length checks
    if len(digits_only) < 7:
        return ValidationError(
            field="phone",
            code="PHONE_TOO_SHORT",
            message=f"Số điện thoại quá ngắn ({len(digits_only)} số): '{original}'",
            severity=ValidationSeverity.ERROR,
            value=original,
            suggestion="Số điện thoại cần ít nhất 7-15 chữ số",
        )

    if len(digits_only) > 15:
        return ValidationError(
            field="phone",
            code="PHONE_TOO_LONG",
            message=f"Số điện thoại quá dài ({len(digits_only)} chữ số): '{original}'",
            severity=ValidationSeverity.ERROR,
            value=original,
            suggestion="Kiểm tra lại số điện thoại",
        )

    # Check country code presence
    has_country_code = original.startswith("+") or original.startswith("0")

    # Skip VN auto-check for numbers with a known non-VN country code
    NON_VN_PREFIXES = ("+1", "+44", "+65", "+61", "+49", "+33", "+81", "+82", "+86", "+7")
    if country == "auto" and original.strip().startswith(NON_VN_PREFIXES):
        country = "us"  # treat as non-VN

    # Vietnam format: 0xxx xxx xxx or +84 xxx xxx xxx
    if country == "vn" or (country == "auto" and len(digits_only) in (10, 11)):
        if not re.match(r"^(\+?84|0)\d{9,10}$", re.sub(r"[.\s\-()]", "", original)):
            return ValidationError(
                field="phone",
                code="PHONE_FORMAT_VN",
                message=f"Số điện thoại VN có vẻ không đúng: '{original}'",
                severity=ValidationSeverity.WARNING,
                value=original,
                suggestion="Định dạng VN: 0xxx xxx xxx hoặc +84 xxx xxx xxx",
            )

    # US/International
    if len(digits_only) in (10, 11) and not has_country_code:
        return ValidationError(
            field="phone",
            code="PHONE_MISSING_COUNTRY_CODE",
            message=f"Thiếu mã quốc gia: '{original}'",
            severity=ValidationSeverity.WARNING,
            value=original,
            suggestion="Thêm +84 (VN) hoặc +1 (US) vào đầu số",
        )

    return None


def validate_date_format(value: str, field_path: str = "period") -> ValidationError | None:
    if not value or not value.strip():
        return None

    # Pattern: MM/YYYY – MM/YYYY or Present, MM/YYYY – Present, YYYY - YYYY
    period_pattern = r"^(?:(?:\d{2}/\d{4})|\d{4})\s*[-–]\s*(?:(?:\d{2}/\d{4})|Present|Tới nay|Hiện tại|now|Current)$"
    year_only = r"^\d{4}\s*[-–]\s*(?:\d{4}|Present|Tới nay|Hiện tại)$"
    single_date = r"^(?:\d{2}/\d{4}|\d{4})$"

    if re.match(period_pattern, value.strip()):
        # Check month/year validity
        months = re.findall(r"\d{2}/\d{4}", value)
        for m in months:
            month, year = m.split("/")
            if not (1 <= int(month) <= 12):
                return ValidationError(
                    field=field_path,
                    code="INVALID_MONTH",
                    message=f"Tháng không hợp lệ trong '{value}': tháng = {month}",
                    severity=ValidationSeverity.ERROR,
                    value=value,
                    suggestion=f"Tháng phải từ 01 đến 12",
                )
            year_int = int(year)
            if year_int < 1950 or year_int > 2030:
                return ValidationError(
                    field=field_path,
                    code="YEAR_OUT_OF_RANGE",
                    message=f"Năm không hợp lệ trong '{value}': năm = {year}",
                    severity=ValidationSeverity.WARNING,
                    value=value,
                    suggestion="Năm phải từ 1950 đến 2030",
                )
        return None

    if re.match(year_only, value.strip()):
        years = re.findall(r"\d{4}", value)
        for y in years:
            yi = int(y)
            if yi < 1950 or yi > 2030:
                return ValidationError(
                    field=field_path,
                    code="YEAR_OUT_OF_RANGE",
                    message=f"Năm không hợp lệ: {yi} trong '{value}'",
                    severity=ValidationSeverity.WARNING,
                    value=value,
                    suggestion="Năm phải từ 1950 đến 2030",
                )
        return None

    if not (re.match(single_date, value.strip())):
        return ValidationError(
            field=field_path,
            code="INVALID_DATE_FORMAT",
            message=f"Định dạng ngày không nhận diện được: '{value}'",
            severity=ValidationSeverity.WARNING,
            value=value,
            suggestion="Dùng: MM/YYYY hoặc YYYY - YYYY hoặc MM/YYYY - Present",
        )
    return None


def validate_year_of_birth(value: str) -> ValidationError | None:
    if not value or not str(value).strip():
        return None
    try:
        y = int(str(value).strip())
        if y < 1940 or y > 2010:
            return ValidationError(
                field="year_of_birth",
                code="YEAR_OF_BIRTH_UNREASONABLE",
                message=f"Năm sinh không hợp lý: {y}",
                severity=ValidationSeverity.WARNING,
                value=value,
                suggestion="Năm sinh nên từ 1940 đến 2010",
            )
    except ValueError:
        return ValidationError(
            field="year_of_birth",
            code="YEAR_OF_BIRTH_NOT_NUMBER",
            message=f"Năm sinh phải là số: '{value}'",
            severity=ValidationSeverity.ERROR,
            value=value,
        )
    return None


def validate_required_string(value: Any, field_name: str) -> ValidationError | None:
    """Generic required-field check."""
    if value is None:
        return ValidationError(
            field=field_name,
            code="FIELD_REQUIRED",
            message=f"Trường bắt buộc bị trống: {field_name}",
            severity=ValidationSeverity.ERROR,
            value=None,
            suggestion=f"Điền thông tin {field_name}",
        )
    if isinstance(value, str) and not value.strip():
        return ValidationError(
            field=field_name,
            code="FIELD_EMPTY",
            message=f"Trường bắt buộc bị trống: {field_name}",
            severity=ValidationSeverity.ERROR,
            value="",
            suggestion=f"Điền thông tin {field_name}",
        )
    return None


def validate_url(value: str, field_name: str = "linkedin_url") -> ValidationError | None:
    if not value or not value.strip():
        return None
    pattern = r"^https?://"
    if not re.match(pattern, value.strip()):
        return ValidationError(
            field=field_name,
            code="INVALID_URL",
            message=f"URL phải bắt đầu bằng http:// hoặc https://: '{value}'",
            severity=ValidationSeverity.ERROR,
            value=value,
            suggestion="Ví dụ: https://linkedin.com/in/username",
        )
    return None


# ── Business-rule validators ──────────────────────────────────────

def validate_period_order(
    start_str: str, end_str: str, field_path: str = "period"
) -> ValidationError | None:
    """
    Check that period end date is AFTER start date.
    Accepts MM/YYYY or YYYY formats.
    Returns ERROR if end ≤ start (chronological inversion).
    """
    if not start_str or not end_str:
        return None

    def parse_date(s: str) -> tuple[int, int] | None:
        s = s.strip()
        # MM/YYYY
        m = re.match(r"^(\d{2})/(\d{4})$", s)
        if m:
            return (int(m.group(2)), int(m.group(1)))  # (year, month)
        # YYYY
        m = re.match(r"^(\d{4})$", s)
        if m:
            return (int(m.group(1)), 1)
        return None

    def is_present(s: str) -> bool:
        return s.strip().lower() in {
            "present", "tới nay", "hiện tại", "now", "current",
        }

    start = parse_date(start_str)
    end_raw = end_str.strip()

    # Present is always valid as end
    if is_present(end_raw):
        return None

    end = parse_date(end_raw)
    if start is None:
        return None  # let validate_date_format catch bad format
    if end is None:
        return None  # let validate_date_format catch bad format
    if end <= start:
        return ValidationError(
            field=field_path,
            code="PERIOD_END_BEFORE_START",
            message=(
                f"Thời gian không hợp lý: bắt đầu '{start_str}' "
                f"nhưng kết thúc '{end_str}' (kết thúc phải sau bắt đầu)"
            ),
            severity=ValidationSeverity.ERROR,
            value=f"{start_str} → {end_str}",
            suggestion=f"Đổi thứ tự: dùng '{start_str} – Present' nếu đang làm",
        )
    return None


def validate_bullet_points(
    text: str, field_path: str = "content", min_count: int = 2
) -> ValidationError | None:
    """
    Check that a free-text field contains at least `min_count` bullet points.
    Bullet markers detected: • - * — and numbered lists (1. 2.)
    Returns WARNING if too few bullets found.
    """
    if not text or not isinstance(text, str):
        return None

    # Count bullet-like lines
    bullet_pattern = r"^\s*(?:[•\-\*–]|\d+\.)\s+"
    count = len(re.findall(bullet_pattern, text, re.MULTILINE))

    if count < min_count:
        return ValidationError(
            field=field_path,
            code="TOO_FEW_BULLET_POINTS",
            message=(
                f"Ít bullet points: chỉ có {count} bullet "
                f"(nên có ít nhất {min_count})"
            ),
            severity=ValidationSeverity.WARNING,
            value=text[slice(0, 200)],
            suggestion=f"Thêm bullet points để CV đầy đủ chi tiết hơn",
        )
    return None


def validate_title_case(
    value: str, field_path: str = "title"
) -> ValidationError | None:
    """
    Check that a title/name field doesn't use ALL-CAPS.
    ALL-CAPS is discouraged in professional CVs.
    Returns WARNING if >70% of letters are uppercase.
    """
    if not value or not isinstance(value, str):
        return None

    alpha = re.sub(r"[^a-zA-Z]", "", value)
    if len(alpha) < 4:
        return None

    upper_ratio = sum(1 for c in alpha if c.isupper()) / len(alpha)
    if upper_ratio > 0.7:
        return ValidationError(
            field=field_path,
            code="TITLE_ALL_CAPS",
            message=f"Tiêu đề dùng chữ HOA: '{value}' — nên dùng Title Case",
            severity=ValidationSeverity.WARNING,
            value=value,
            suggestion="Dùng 'Software Engineer' thay vì 'SOFTWARE ENGINEER'",
        )
    return None


def validate_duplicate_entries(
    entries: list[dict[str, Any]], field_path: str, key: str = "company"
) -> ValidationError | None:
    """
    Detect duplicate entries in a list (e.g. same company appearing twice).
    Returns WARNING if exact duplicates are found.
    """
    if not entries or not isinstance(entries, list):
        return None

    seen: dict[str, list[int]] = {}
    for i, entry in enumerate(entries):
        if not isinstance(entry, dict):
            continue
        val = entry.get(key, "")
        if not val or not isinstance(val, str):
            continue
        val_clean = val.strip().lower()
        if val_clean not in seen:
            seen[val_clean] = []
        seen[val_clean].append(i)

    duplicates = {v: idxs for v, idxs in seen.items() if len(idxs) > 1}
    if not duplicates:
        return None

    first_key = next(iter(duplicates))
    indices = duplicates[first_key]
    example_val = entries[indices[0]].get(key, "")
    return ValidationError(
        field=field_path,
        code="DUPLICATE_ENTRIES",
        message=(
            f"Phát hiện mục trùng lặp: '{example_val}' xuất hiện "
            f"{len(indices)} lần tại {field_path}"
        ),
        severity=ValidationSeverity.WARNING,
        value=[entries[i].get(key, "") for i in indices],
        suggestion=f"Gộp hoặc xóa các mục trùng lặp trong {field_path}",
    )


# ── Full CV validator ─────────────────────────────────────────────

def validate_cv_data(cv_data: dict[str, Any], strict: bool = False,
                    output_filename: str = "") -> ValidationResult:
    """
    Validate a full parsed CV data object.

    Args:
        cv_data: Parsed CV data from AI/extraction
        strict: If True, warnings also block export
    """
    errors: list[ValidationError] = []
    warnings: list[ValidationError] = []
    info: list[ValidationError] = []

    # 0. BA Rules: Output Filename validation (Rule 1)
    if output_filename:
        err = validate_output_filename(output_filename)
        if err:
            errors.append(err)

    # 0b. BA Rules: Section title branding (Rule 2)
    errs_sections = validate_section_titles(cv_data.get("other_info") or [])
    errors.extend(errs_sections)

    # 0c. BA Rules: Working Experience H1/H2/H3 structure (Rule 3)
    errs_exp = validate_working_experience_structure(cv_data.get("career_summary") or [])
    errors.extend(errs_exp)

    # 0d. BA Rules: Style mapping validation (Rule 4)
    errs_style = validate_style_mapping(cv_data)
    for e in errs_style:
        if e.severity == ValidationSeverity.ERROR:
            errors.append(e)
        else:
            warnings.append(e)

    # 0e. BA Rules: TOC presence validation (Rule 5)
    errs_toc = validate_toc_present(cv_data)
    errors.extend(errs_toc)

    # 1. Required top-level fields
    REQUIRED_FIELDS = [
        ("full_name", cv_data.get("full_name")),
        ("email", cv_data.get("email")),
    ]

    for field_name, value in REQUIRED_FIELDS:
        err = validate_required_string(value, field_name)
        if err:
            errors.append(err)

    # 2. Email format
    email = cv_data.get("email", "")
    if email:
        err = validate_email(email)
        if err:
            errors.append(err)

    # 3. Phone format
    phone = cv_data.get("phone", "")
    if phone:
        err = validate_phone(phone)
        if err:
            if err.severity == ValidationSeverity.ERROR:
                errors.append(err)
            else:
                warnings.append(err)

    # 4. Year of birth
    yob = cv_data.get("year_of_birth", "")
    if yob:
        err = validate_year_of_birth(yob)
        if err:
            warnings.append(err)

    # 5. Career summary — at least one entry recommended
    career = cv_data.get("career_summary", [])
    if not career:
        warnings.append(ValidationError(
            field="career_summary",
            code="NO_CAREER_ENTRIES",
            message="Không tìm thấy kinh nghiệm làm việc (career_summary rỗng)",
            severity=ValidationSeverity.WARNING,
            suggestion="Thêm ít nhất 1 mục kinh nghiệm làm việc",
        ))
    else:
        # Check for duplicate companies across all career entries
        dup_err = validate_duplicate_entries(career, "career_summary", key="company")
        if dup_err:
            warnings.append(dup_err)

        for i, job in enumerate(career):
            job_path = f"career_summary[{i}]"

            # Period format + logical order check
            period = job.get("period", "")
            if period:
                err = validate_date_format(period, f"{job_path}.period")
                if err:
                    warnings.append(err)
                # Extract start/end and check chronological order
                parts = re.split(r"\s*[-–]\s*", period, maxsplit=1)
                if len(parts) == 2:
                    start_s, end_s = parts[0].strip(), parts[1].strip()
                    err = validate_period_order(start_s, end_s, f"{job_path}.period")
                    if err:
                        errors.append(err)

            # Company
            company = job.get("company", "")
            if not company or not company.strip():
                warnings.append(ValidationError(
                    field=f"{job_path}.company",
                    code="COMPANY_NAME_MISSING",
                    message=f"Job #{i+1}: Thiếu tên công ty",
                    severity=ValidationSeverity.WARNING,
                    suggestion=f"Thêm tên công ty cho job #{i+1}",
                ))

            # Title case check on company name
            cap_err = validate_title_case(company, f"{job_path}.company")
            if cap_err:
                warnings.append(cap_err)

            # Positions
            positions = job.get("positions", [])
            if not positions and not job.get("responsibilities"):
                info.append(ValidationError(
                    field=f"{job_path}.positions",
                    code="NO_POSITIONS_IN_JOB",
                    message=f"Job #{i+1}: Không có vị trí/chức danh",
                    severity=ValidationSeverity.INFO,
                    suggestion="Thêm ít nhất 1 vị trí (title) cho job này",
                ))

            for j, pos in enumerate(positions):
                pos_path = f"{job_path}.positions[{j}]"
                pos_title = pos.get("title", "")
                if not pos_title or not pos_title.strip():
                    warnings.append(ValidationError(
                        field=f"{pos_path}.title",
                        code="POSITION_TITLE_MISSING",
                        message=f"Job #{i+1}, Position #{j+1}: Thiếu chức danh",
                        severity=ValidationSeverity.WARNING,
                        suggestion=f"Thêm chức danh (title) cho position #{j+1}",
                    ))

                # Title case check on position title
                cap_err = validate_title_case(pos_title, f"{pos_path}.title")
                if cap_err:
                    warnings.append(cap_err)

                # Period order check
                pos_period = pos.get("period", "")
                if pos_period:
                    err = validate_date_format(pos_period, f"{pos_path}.period")
                    if err:
                        warnings.append(err)
                    parts = re.split(r"\s*[-–]\s*", pos_period, maxsplit=1)
                    if len(parts) == 2:
                        start_s, end_s = parts[0].strip(), parts[1].strip()
                        err = validate_period_order(start_s, end_s, f"{pos_path}.period")
                        if err:
                            errors.append(err)

                # Bullet point count for responsibilities
                responsibilities = pos.get("responsibilities", "")
                if responsibilities and isinstance(responsibilities, str):
                    err = validate_bullet_points(responsibilities, f"{pos_path}.responsibilities", min_count=2)
                    if err:
                        warnings.append(err)

            # Fallback: top-level responsibilities bullet check
            fallback_resp = job.get("responsibilities", "")
            if fallback_resp and isinstance(fallback_resp, str) and (not positions or not any(p.get("responsibilities") for p in positions)):
                err = validate_bullet_points(fallback_resp, f"{job_path}.responsibilities", min_count=2)
                if err:
                    warnings.append(err)

    # 6. Education
    education = cv_data.get("education", [])
    if education:
        for i, edu in enumerate(education):
            edu_path = f"education[{i}]"
            institution = edu.get("institution", "")
            if institution and len(institution) < 3:
                warnings.append(ValidationError(
                    field=f"{edu_path}.institution",
                    code="INSTITUTION_NAME_TOO_SHORT",
                    message=f"Education #{i+1}: Tên trường quá ngắn: '{institution}'",
                    severity=ValidationSeverity.WARNING,
                    value=institution,
                ))

            period = edu.get("period", "")
            if period:
                err = validate_date_format(period, f"{edu_path}.period")
                if err:
                    warnings.append(err)

    # 7. Gender
    gender = cv_data.get("gender", "")
    valid_genders = {"male", "female", "nam", "nữ", "other", "khác"}
    if gender and gender.lower().strip() not in valid_genders:
        info.append(ValidationError(
            field="gender",
            code="GENDER_UNCLEAR",
            message=f"Giới tính không rõ ràng: '{gender}'",
            severity=ValidationSeverity.INFO,
            suggestion="Dùng: Male / Female / Nam / Nữ / Other",
        ))

    # 8. Marital status
    marital = cv_data.get("marital_status", "")
    valid_marital = {"single", "married", "divorced", "độc thân", "đã kết hôn", "có gia đình", "ly hôn"}
    if marital and marital.lower().strip() not in valid_marital:
        info.append(ValidationError(
            field="marital_status",
            code="MARITAL_STATUS_UNCLEAR",
            message=f"Tình trạng hôn nhân không rõ ràng: '{marital}'",
            severity=ValidationSeverity.INFO,
        ))

    # 9. Other info sections
    other_info = cv_data.get("other_info", [])
    for i, section in enumerate(other_info):
        section_title = section.get("section_title", "")
        if section_title and len(section_title.strip()) < 2:
            warnings.append(ValidationError(
                field=f"other_info[{i}].section_title",
                code="SECTION_TITLE_TOO_SHORT",
                message=f"Section title quá ngắn: '{section_title}'",
                severity=ValidationSeverity.INFO,
                value=section_title,
            ))

    # 10. Check for completely empty CV
    all_values = []
    def flatten(d: dict, prefix=""):
        for k, v in d.items():
            if isinstance(v, list):
                for item in v:
                    if isinstance(item, dict):
                        flatten(item, f"{prefix}{k}.")
                    else:
                        all_values.append(v)
            elif isinstance(v, dict):
                flatten(v, f"{prefix}{k}.")
            else:
                all_values.append(v)
    flatten(cv_data)

    non_empty = [v for v in all_values if v and str(v).strip()]
    if len(non_empty) < 3:
        warnings.append(ValidationError(
            field="*",
            code="CV_NEARLY_EMPTY",
            message="CV gần như trống — có thể OCR hoặc extraction thất bại",
            severity=ValidationSeverity.ERROR,
            suggestion="Kiểm tra lại file CV gốc, thử dùng AI mode thay vì offline",
        ))

    # Determine validity
    has_errors = len(errors) > 0
    is_exportable = (not has_errors) and (len(warnings) == 0 if strict else True)

    return ValidationResult(
        is_valid=not has_errors,
        is_exportable=is_exportable,
        errors=errors,
        warnings=warnings,
        info=info,
    )


# ── Batch validation ─────────────────────────────────────────────

def validate_batch(cv_data_list: list[dict[str, Any]]) -> list[ValidationResult]:
    """Validate multiple CVs at once."""
    return [validate_cv_data(cv) for cv in cv_data_list]


# ── BRANDING / CONSTANTS ─────────────────────────────────────────
NAVIGOS_SEARCH_ASSESSMENT = "Navigos Search\u2019s Assessment"
NAVIGOS_SEARCH_ASSESSMENT_UPPER = "NAVIGOS SEARCH\u2019S ASSESSMENT"
OUTPUT_FILENAME_PATTERN = re.compile(r"^[A-Z][A-Z0-9 ]+( [A-Z][A-Z0-9 ]+)* - .+ - .+$")


# ── OUTPUT FILENAME VALIDATION (Rule 1) ──────────────────────────
def validate_output_filename(filename: str) -> ValidationError | None:
    """
    Validate output filename format.
    Required format: CLIENT_UPPER - Position - CandidateName

    Valid:   "NAVIGOS - Developer - John Doe"
    Invalid: "Navigos - Developer - John"   (client not uppercase)
    Invalid: "NAVIGOS - John"               (only 2 parts)
    Invalid: "Developer - John Doe"         (missing client)
    """
    if not filename or not filename.strip():
        return ValidationError(
            field="output_filename",
            code="FILENAME_REQUIRED",
            message="Output filename không được để trống",
            severity=ValidationSeverity.ERROR,
            suggestion="Đặt tên: CLIENT - Vị trí - Tên ứng viên  (CLIENT phải IN HOA)",
        )

    parts = [p.strip() for p in filename.split(" - ")]
    if len(parts) != 3:
        return ValidationError(
            field="output_filename",
            code="FILENAME_FORMAT_WRONG",
            message=f"Filename phải có đúng 3 phần: CLIENT - Position - Name (đang có {len(parts)} phần: '{filename}')",
            severity=ValidationSeverity.ERROR,
            value=filename,
            suggestion="Format: CLIENT_IN_HOA - Vị trí - Tên ứng viên  (ví dụ: NAVIGOS - Software Engineer - Nguyen Van A)",
        )

    client, position, candidate = parts[0], parts[1], parts[2]

    # Rule: CLIENT must be all uppercase (allowing letters, numbers, spaces)
    if client != client.upper():
        return ValidationError(
            field="output_filename",
            code="FILENAME_CLIENT_NOT_UPPERCASE",
            message=f"Tên CLIENT phải IN HOA toàn bộ: '{client}' → '{client.upper()}'",
            severity=ValidationSeverity.ERROR,
            value=filename,
            suggestion=f"Sửa: '{client.upper()} - {position} - {candidate}'",
        )

    if not position.strip():
        return ValidationError(
            field="output_filename",
            code="FILENAME_POSITION_EMPTY",
            message="Phần Position không được trống",
            severity=ValidationSeverity.ERROR,
            value=filename,
            suggestion="Format: CLIENT - Vị trí - Tên  (ví dụ: NAVIGOS - Software Engineer - Nguyen Van A)",
        )

    if not candidate.strip():
        return ValidationError(
            field="output_filename",
            code="FILENAME_CANDIDATE_EMPTY",
            message="Phần Tên ứng viên không được trống",
            severity=ValidationSeverity.ERROR,
            value=filename,
            suggestion="Format: CLIENT - Vị trí - Tên  (ví dụ: NAVIGOS - Software Engineer - Nguyen Van A)",
        )

    # Warn about potential issues
    if " " not in position and len(position) > 3:
        return ValidationError(
            field="output_filename",
            code="FILENAME_POSITION_SUGGESTION",
            message=f"Position có thể chưa đúng: '{position}'",
            severity=ValidationSeverity.WARNING,
            value=filename,
            suggestion="Position nên là tên job title đầy đủ (ví dụ: 'Senior Software Engineer')",
        )

    return None


# ── SECTION TITLE VALIDATION (Rule 2) ───────────────────────────
def validate_section_titles(other_info: list) -> list[ValidationError]:
    """
    Validate that Section II / Assessment uses the EXACT brand name.
    Dev must NOT use: "Assessment", "Navigos Assessment", "Đánh giá", etc.
    Required: "Navigos Search's Assessment"
    """
    errors = []
    for i, section in enumerate(other_info):
        section_title = (section.get("section_title") or "").strip()
        if not section_title:
            continue
        # Normalize for comparison (strip extra spaces)
        norm = re.sub(r"\s+", " ", section_title)

        if norm.upper() in ("ASSESSMENT", "NAVIGOS ASSESSMENT",
                             "NAVIGOS'S ASSESSMENT",
                             "NAVIGOS SEARCH ASSESSMENT",
                             "DANH GIA", "ĐÁNH GIÁ"):
            errors.append(ValidationError(
                field=f"other_info[{i}].section_title",
                code="SECTION_TITLE_WRONG_BRAND",
                message=(
                    f"Section title SAI: '{section_title}'  "
                    f"→ Phải là đúng: '{NAVIGOS_SEARCH_ASSESSMENT}'"
                ),
                severity=ValidationSeverity.ERROR,
                value=section_title,
                suggestion=f"Sửa section title thành: '{NAVIGOS_SEARCH_ASSESSMENT}'  "
                           f"(chữ 's' sau Search có dấu nháy đơn)",
            ))
        # Also catch the uppercase version (AI sometimes outputs all caps)
        if norm == NAVIGOS_SEARCH_ASSESSMENT_UPPER:
            errors.append(ValidationError(
                field=f"other_info[{i}].section_title",
                code="SECTION_TITLE_WRONG_BRAND",
                message=(
                    f"Section title phải đúng: '{section_title}'  "
                    f"→ Viết HOA nhưng phải có dấu nháy: '{NAVIGOS_SEARCH_ASSESSMENT}'"
                ),
                severity=ValidationSeverity.ERROR,
                value=section_title,
                suggestion=f"Đúng: '{NAVIGOS_SEARCH_ASSESSMENT}'  "
                           f"(không phải: '{NAVIGOS_SEARCH_ASSESSMENT_UPPER}')",
            ))
    return errors


# ── WORKING EXPERIENCE STRUCTURE VALIDATION (Rule 3) ─────────────
def validate_working_experience_structure(career_summary: list) -> list[ValidationError]:
    """
    Validate H1/H2/H3 heading structure for Working Experience.

    H1 = Heading 1: "Time + Company"        (e.g. "2020 - Present | ABC CORP")
    H2 = Heading 2: "Time + Position"       (e.g. "2022 - Present | Senior Developer")
    H3 = Heading 3: "Position title only"   (only when position spans sub-periods)

    Rules:
    - career_summary entry must have: company (UPPERCASE), period
    - Each position must have: title (Title Case, NOT UPPERCASE)
    - Period format: MM/YYYY – MM/YYYY or MM/YYYY – Present
    - Company must be UPPERCASE
    """
    errors = []
    warnings = []

    if not career_summary:
        return errors

    for i, job in enumerate(career_summary):
        job_path = f"career_summary[{i}]"
        company = (job.get("company") or "").strip()
        period = (job.get("period") or "").strip()

        # H1: Company must exist and be UPPERCASE
        if not company:
            errors.append(ValidationError(
                field=f"{job_path}.company",
                code="H1_COMPANY_MISSING",
                message=f"[H1] Job #{i+1}: Thiếu tên công ty (Heading 1)",
                severity=ValidationSeverity.ERROR,
                suggestion="Thêm tên công ty và VIẾT HOA (ví dụ: ABC CORPORATION)",
            ))
        elif company != company.upper():
            errors.append(ValidationError(
                field=f"{job_path}.company",
                code="H1_COMPANY_NOT_UPPERCASE",
                message=f"[H1] Tên công ty phải VIẾT HOA: '{company}'",
                severity=ValidationSeverity.ERROR,
                value=company,
                suggestion=f"Viết HOA: '{company.upper()}'",
            ))

        # H1: Period must exist at job level
        if not period:
            errors.append(ValidationError(
                field=f"{job_path}.period",
                code="H1_PERIOD_MISSING",
                message=f"[H1] Job #{i+1}: Thiếu thời gian làm việc (Heading 1 period)",
                severity=ValidationSeverity.ERROR,
                suggestion="Thêm period: MM/YYYY - MM/YYYY  (ví dụ: 2020 - Present)",
            ))

        positions = job.get("positions") or []
        if not positions:
            resp = job.get("responsibilities") or ""
            if isinstance(resp, list) and len(resp) < 2:
                warnings.append(ValidationError(
                    field=f"{job_path}.positions",
                    code="H2_NO_POSITIONS",
                    message=f"[H2] Job #{i+1}: Không có positions — nên tách thành từng chức danh riêng",
                    severity=ValidationSeverity.WARNING,
                    suggestion="Tách thành từng position với title riêng (Senior Developer, Lead Engineer...)",
                ))
            continue

        for j, pos in enumerate(positions):
            pos_path = f"{job_path}.positions[{j}]"
            pos_title = (pos.get("title") or "").strip()

            # H2/H3: Title must exist and NOT be all uppercase
            if not pos_title:
                errors.append(ValidationError(
                    field=f"{pos_path}.title",
                    code="H2_TITLE_MISSING",
                    message=f"[H2] Job #{i+1}, Position #{j+1}: Thiếu chức danh",
                    severity=ValidationSeverity.ERROR,
                    suggestion="Thêm title: ví dụ 'Senior Software Engineer'  (dùng Title Case, KHÔNG VIẾT HOA)",
                ))
            elif pos_title == pos_title.upper() and len(pos_title) > 3:
                warnings.append(ValidationError(
                    field=f"{pos_path}.title",
                    code="H2_TITLE_ALL_CAPS",
                    message=f"[H2] Position title viết HOA: '{pos_title}' — nên dùng Title Case",
                    severity=ValidationSeverity.WARNING,
                    value=pos_title,
                    suggestion=f"Dùng Title Case: '{pos_title.title()}'",
                ))

            responsibilities = pos.get("responsibilities") or []
            if isinstance(responsibilities, list) and len(responsibilities) > 8 and not pos_title:
                warnings.append(ValidationError(
                    field=f"{pos_path}.responsibilities",
                    code="H2_RESPONSIBILITIES_NO_TITLE",
                    message=f"[H2] Job #{i+1}, Position #{j+1}: Quá nhiều bullets nhưng không có title — "
                            f"có thể AI nhét hết vào 1 position",
                    severity=ValidationSeverity.WARNING,
                    suggestion="Chia thành nhiều positions với title riêng: "
                              f"'Software Engineer', 'Senior Engineer', 'Tech Lead'...",
                ))

            pos_period = (pos.get("period") or "").strip()
            if pos_period:
                err = validate_date_format(pos_period, f"{pos_path}.period")
                if err:
                    err.field = f"{pos_path}.period"
                    warnings.append(err)

    return errors


# ── STYLE-BASED VALIDATION (Rule 4) ─────────────────────────────
def validate_style_mapping(cv_data: dict) -> list[ValidationError]:
    """
    Validate that parsed data will map correctly to DOCX styles.

    Style 3 (Description) = company + job descriptions (free text)
    Style 2 (Subject)     = "Responsibilities", "Achievements" labels

    Validates:
    - other_info sections have proper section_title vs items separation
    - responsibilities are in list/bullet form (not one giant paragraph)
    - subject labels are consistent
    """
    errors = []
    warnings = []

    career = cv_data.get("career_summary") or []
    for i, job in enumerate(career):
        positions = job.get("positions") or []
        for j, pos in enumerate(positions):
            pos_path = f"career_summary[{i}].positions[{j}]"
            responsibilities = pos.get("responsibilities") or []
            achievements = pos.get("achievements") or []

            # Style 2: subject labels must be consistent
            if isinstance(responsibilities, str) and len(responsibilities) > 200:
                warnings.append(ValidationError(
                    field=f"{pos_path}.responsibilities",
                    code="STYLE2_LONG_PLAINTEXT",
                    message=f"[Style 2] Responsibilities là 1 đoạn văn dài ({len(responsibilities)} chars) — "
                            f"nên tách thành bullet points riêng",
                    severity=ValidationSeverity.WARNING,
                    suggestion="Tách responsibilities thành: ['- Led team of 5', '- Built REST APIs', ...]  "
                              f"(mỗi bullet 1 dòng ngắn)",
                ))

            if isinstance(achievements, str) and len(achievements) > 200:
                warnings.append(ValidationError(
                    field=f"{pos_path}.achievements",
                    code="STYLE2_ACHIEVEMENTS_LONG",
                    message=f"[Style 2] Achievements là 1 đoạn văn dài ({len(achievements)} chars)",
                    severity=ValidationSeverity.WARNING,
                    suggestion="Tách achievements thành bullet points riêng",
                ))

            if responsibilities and not isinstance(responsibilities, list):
                warnings.append(ValidationError(
                    field=f"{pos_path}.responsibilities",
                    code="STYLE2_RESPONSIBILITIES_NOT_LIST",
                    message=f"[Style 2] Responsibilities phải là LIST (array), không phải text blob",
                    severity=ValidationSeverity.WARNING,
                    value=f"type={type(responsibilities).__name__}",
                    suggestion="Đổi responsibilities thành: ['- Task 1', '- Task 2', ...]",
                ))

    other_info = cv_data.get("other_info") or []
    for i, section in enumerate(other_info):
        section_label = (section.get("section_label") or "").strip()
        if section_label and len(section_label) > 40:
            warnings.append(ValidationError(
                field=f"other_info[{i}].section_label",
                code="STYLE2_SECTION_LABEL_TOO_LONG",
                message=f"[Style 2] Section label quá dài ({len(section_label)} chars): '{section_label}'",
                severity=ValidationSeverity.WARNING,
                suggestion="Section label nên ngắn gọn: 'Responsibilities:', 'Achievements:', 'Duties:'",
            ))

    return errors + warnings


# ── TOC VALIDATION (Rule 5) ─────────────────────────────────────
def validate_toc_present(cv_data: dict) -> list[ValidationError]:
    """
    Validate TOC / Table of Contents is present and synced with content.

    TOC entries come from career_summary positions.
    If career_summary has positions but TOC would be empty → warning.
    """
    errors = []
    career = cv_data.get("career_summary") or []
    positions_count = sum(len(job.get("positions") or []) for job in career)

    if career and positions_count == 0:
        errors.append(ValidationError(
            field="career_summary",
            code="TOC_ENTRIES_ZERO",
            message="TOC sẽ trống — career_summary có job nhưng không có positions (H2/H3 headings)",
            severity=ValidationSeverity.ERROR,
            suggestion="Thêm positions (H2: chức danh) để TOC có nội dung",
        ))

    return errors


# ── ERROR LOGGING SYSTEM (Rule 7) ────────────────────────────────
class CVErrorLog:
    """
    Structured error log for a CV processing run.
    Tracks errors by category for QA and BA reporting.
    """
    def __init__(self):
        self.filename_errors: list[str] = []
        self.heading_errors: list[str] = []
        self.style_errors: list[str] = []
        self.toc_errors: list[str] = []
        self.structure_errors: list[str] = []
        self.ai_errors: list[str] = []
        self.total_errors: int = 0
        self.total_warnings: int = 0

    def add_error(self, category: str, message: str):
        attr_map = {
            "filename": "filename_errors",
            "heading": "heading_errors",
            "style": "style_errors",
            "toc": "toc_errors",
            "structure": "structure_errors",
            "ai": "ai_errors",
        }
        attr = attr_map.get(category, "structure_errors")
        getattr(self, attr).append(message)
        self.total_errors += 1

    def add_warning(self, category: str, message: str):
        attr_map = {
            "filename": "filename_errors",
            "heading": "heading_errors",
            "style": "style_errors",
            "toc": "toc_errors",
            "structure": "structure_errors",
            "ai": "ai_errors",
        }
        attr = attr_map.get(category, "structure_errors")
        getattr(self, attr).append(f"[WARN] {message}")
        self.total_warnings += 1

    def to_dict(self) -> dict:
        return {
            "filename_errors": self.filename_errors,
            "heading_errors": self.heading_errors,
            "style_errors": self.style_errors,
            "toc_errors": self.toc_errors,
            "structure_errors": self.structure_errors,
            "ai_errors": self.ai_errors,
            "total_errors": self.total_errors,
            "total_warnings": self.total_warnings,
            "has_critical_errors": bool(self.filename_errors or self.heading_errors),
        }

    def summary(self) -> str:
        parts = []
        if self.filename_errors:
            parts.append(f"Filename: {len(self.filename_errors)}")
        if self.heading_errors:
            parts.append(f"Headings: {len(self.heading_errors)}")
        if self.style_errors:
            parts.append(f"Styles: {len(self.style_errors)}")
        if self.toc_errors:
            parts.append(f"TOC: {len(self.toc_errors)}")
        if self.structure_errors:
            parts.append(f"Structure: {len(self.structure_errors)}")
        return ", ".join(parts) if parts else "All clear"


# ── Sanitization helpers ──────────────────────────────────────────

def sanitize_for_export(cv_data: dict[str, Any]) -> dict[str, Any]:
    """Clean up data before template fill."""
    import copy
    data = copy.deepcopy(cv_data)

    def clean_str(v):
        if not isinstance(v, str):
            return v
        # Remove multiple spaces
        v = re.sub(r" {2,}", " ", v)
        # Remove leading/trailing whitespace per line
        v = "\n".join(line.strip() for line in v.split("\n"))
        return v.strip()

    def clean(obj):
        if isinstance(obj, dict):
            return {k: clean(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [clean(item) for item in obj]
        if isinstance(obj, str):
            return clean_str(obj)
        return obj

    return clean(data)
