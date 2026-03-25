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

def validate_cv_data(cv_data: dict[str, Any], strict: bool = False) -> ValidationResult:
    """
    Validate a full parsed CV data object.

    Args:
        cv_data: Parsed CV data from AI/extraction
        strict: If True, warnings also block export
    """
    errors: list[ValidationError] = []
    warnings: list[ValidationError] = []
    info: list[ValidationError] = []

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
    valid_marital = {"single", "married", "married", "độc thân", "đã kết hôn", "có gia đình"}
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


# ── Sanitization helpers ─────────────────────────────────────────

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
