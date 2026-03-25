"""
CV Format Tool — Validation Engine Tests
CEO TEST PLAN: Validates error detection before CV reaches client.
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from validation import (
    validate_email, validate_phone, validate_date_format,
    validate_year_of_birth, validate_cv_data, validate_required_string,
    sanitize_for_export, validate_batch, ValidationSeverity,
    ValidationError,
    validate_period_order, validate_bullet_points,
    validate_title_case, validate_duplicate_entries,
)


# ═══════════════════════════════════════════════════════════════
# TC-1: VALID EMAIL
# ═══════════════════════════════════════════════════════════════
class TestEmailValidation:
    def test_valid_email_standard(self):
        assert validate_email("nguyenvana@gmail.com") is None

    def test_valid_email_company_domain(self):
        assert validate_email("john.doe@navigos.com.vn") is None

    def test_valid_email_subdomain(self):
        assert validate_email("user@mail.company.co.uk") is None

    def test_email_none_returns_none(self):
        """Empty email should return None (handled separately as required field)."""
        assert validate_email(None) is None
        assert validate_email("") is None

    # ── TC-2: INVALID EMAIL ──
    def test_invalid_email_no_at(self):
        err = validate_email("notanemail")
        assert err is not None
        assert err.code == "INVALID_EMAIL_FORMAT"
        assert err.severity == ValidationSeverity.ERROR

    def test_invalid_email_no_domain(self):
        err = validate_email("user@")
        assert err is not None
        assert err.code == "INVALID_EMAIL_FORMAT"

    def test_invalid_email_no_tld(self):
        err = validate_email("user@gmail")
        assert err is not None
        assert err.code == "INVALID_EMAIL_FORMAT"

    def test_invalid_email_spaces(self):
        err = validate_email("user name@gmail.com")
        assert err is not None
        assert err.code == "INVALID_EMAIL_FORMAT"

    # ── TC-3: EMAIL TYPO WARNINGS ──
    def test_email_typo_gmail(self):
        err = validate_email("user@gmial.com")
        assert err is not None
        assert err.code == "EMAIL_TYPO"
        assert err.severity == ValidationSeverity.ERROR  # typos are blocking
        assert "gmail.com" in err.suggestion

    def test_email_typo_hotmail(self):
        err = validate_email("user@hotmal.com")
        assert err is not None
        assert err.code == "EMAIL_TYPO"
        assert "hotmail.com" in err.suggestion


# ═══════════════════════════════════════════════════════════════
# TC-4: VALID PHONE
# ═══════════════════════════════════════════════════════════════
class TestPhoneValidation:
    def test_valid_phone_vietnam_10digit(self):
        assert validate_phone("0912 345 678") is None

    def test_valid_phone_vietnam_mobile(self):
        assert validate_phone("+84 912 345 678") is None

    def test_valid_phone_us(self):
        assert validate_phone("+1 (555) 123-4567", country="auto") is None

    def test_valid_phone_uk(self):
        assert validate_phone("+44 20 7946 0958") is None

    def test_phone_none_returns_none(self):
        assert validate_phone(None) is None
        assert validate_phone("") is None

    # ── TC-5: INVALID PHONE ──
    def test_phone_too_short(self):
        err = validate_phone("123456")
        assert err is not None
        assert err.code == "PHONE_TOO_SHORT"
        assert err.severity == ValidationSeverity.ERROR

    def test_phone_too_long(self):
        err = validate_phone("1" * 20)
        assert err is not None
        assert err.code == "PHONE_TOO_LONG"
        assert err.severity == ValidationSeverity.ERROR

    def test_phone_missing_country_code_warning(self):
        """10-digit number without country code gets warning."""
        err = validate_phone("5551234567", country="us")
        assert err is not None
        assert err.code == "PHONE_MISSING_COUNTRY_CODE"
        assert err.severity == ValidationSeverity.WARNING


# ═══════════════════════════════════════════════════════════════
# TC-6: VALID DATE FORMATS
# ═══════════════════════════════════════════════════════════════
class TestDateValidation:
    def test_valid_period_present(self):
        assert validate_date_format("01/2020 - Present") is None

    def test_valid_period_vietnam(self):
        assert validate_date_format("01/2020 - 12/2023") is None

    def test_valid_period_year_only(self):
        assert validate_date_format("2020 - 2023") is None

    def test_valid_single_month_year(self):
        assert validate_date_format("06/2015") is None

    def test_date_none_returns_none(self):
        assert validate_date_format(None) is None

    # ── TC-7: INVALID DATE FORMATS ──
    def test_invalid_month_over_12(self):
        err = validate_date_format("13/2020 - Present")
        assert err is not None
        assert err.code == "INVALID_MONTH"
        assert "13" in err.value

    def test_invalid_year_out_of_range(self):
        err = validate_date_format("01/1800 - Present")
        assert err is not None
        assert err.code == "YEAR_OUT_OF_RANGE"

    def test_invalid_year_future(self):
        err = validate_date_format("01/2050 - Present")
        assert err is not None
        assert err.code == "YEAR_OUT_OF_RANGE"


# ═══════════════════════════════════════════════════════════════
# TC-8: YEAR OF BIRTH
# ═══════════════════════════════════════════════════════════════
class TestYearOfBirth:
    def test_valid_yob_reasonable(self):
        assert validate_year_of_birth("1995") is None

    def test_valid_yob_edge_early(self):
        assert validate_year_of_birth("1940") is None

    def test_valid_yob_edge_late(self):
        assert validate_year_of_birth("2010") is None

    def test_invalid_yob_too_early(self):
        err = validate_year_of_birth("1930")
        assert err is not None
        assert err.code == "YEAR_OF_BIRTH_UNREASONABLE"

    def test_invalid_yob_future(self):
        err = validate_year_of_birth("2030")
        assert err is not None
        assert err.code == "YEAR_OF_BIRTH_UNREASONABLE"


# ═══════════════════════════════════════════════════════════════
# TC-9: REQUIRED FIELDS
# ═══════════════════════════════════════════════════════════════
class TestRequiredFields:
    def test_required_missing_string(self):
        err = validate_required_string("", "full_name")
        assert err is not None
        assert err.code == "FIELD_EMPTY"

    def test_required_none(self):
        err = validate_required_string(None, "email")
        assert err is not None
        assert err.code == "FIELD_REQUIRED"

    def test_required_whitespace_only(self):
        err = validate_required_string("   ", "full_name")
        assert err is not None
        assert err.code == "FIELD_EMPTY"

    def test_required_ok(self):
        assert validate_required_string("Nguyen Van A", "full_name") is None


# ═══════════════════════════════════════════════════════════════
# TC-10: FULL CV VALIDATION — BASELINE (CLEAN CV)
# ═══════════════════════════════════════════════════════════════
class TestCVValidationClean:
    @pytest.fixture
    def clean_cv(self):
        return {
            "full_name": "Nguyen Van A",
            "gender": "Male",
            "year_of_birth": "1992",
            "marital_status": "Single",
            "address": "123 Nguyen Trai, Hanoi",
            "email": "nguyenvana@gmail.com",
            "phone": "+84 912 345 678",
            "career_summary": [
                {
                    "period": "01/2020 - Present",
                    "company": "FPT SOFTWARE",
                    "positions": [
                        {
                            "title": "Senior Software Engineer",
                            "period": "01/2020 - Present",
                            "responsibilities": ["Developed backend APIs", "Led team of 5"],
                            "achievements": ["Reduced latency by 40%"],
                        }
                    ],
                },
                {
                    "period": "06/2018 - 12/2019",
                    "company": "Viettel Solutions",
                    "positions": [
                        {
                            "title": "Software Engineer",
                            "responsibilities": ["Built microservices"],
                        }
                    ],
                },
            ],
            "education": [
                {
                    "period": "2014 - 2018",
                    "institution": "Hanoi University of Science and Technology",
                    "details": ["Bachelor of Computer Science", "GPA: 3.5/4.0"],
                }
            ],
            "other_info": [
                {"section_title": "Skills", "items": ["Python", "Java", "AWS", "Docker"]},
                {"section_title": "Languages", "items": ["English - IELTS 7.0", "Vietnamese - Native"]},
            ],
        }

    def test_clean_cv_is_valid(self, clean_cv):
        result = validate_cv_data(clean_cv)
        assert result.is_valid is True
        assert result.is_exportable is True
        assert result.error_count == 0

    def test_clean_cv_summary(self, clean_cv):
        result = validate_cv_data(clean_cv)
        assert result.summary is not None
        assert isinstance(result.summary, str)
        assert len(result.summary) > 0


# ═══════════════════════════════════════════════════════════════
# TC-11: FULL CV VALIDATION — DIRTY CV (REAL WORLD)
# ═══════════════════════════════════════════════════════════════
class TestCVValidationDirty:
    @pytest.fixture
    def dirty_cv(self):
        """Simulates a real-world dirty CV with multiple issues."""
        return {
            "full_name": "",  # MISSING — ERROR
            "email": "user@gmial.com",  # TYPO — WARNING
            "phone": "123456",  # TOO SHORT — ERROR
            "year_of_birth": "2025",  # UNREASONABLE — WARNING
            "gender": "unknown",
            "marital_status": "",
            "career_summary": [
                {
                    "period": "01/2020 - 13/2025",  # INVALID MONTH
                    "company": "",  # MISSING COMPANY
                    "positions": [
                        {
                            "title": "",  # MISSING TITLE
                            "responsibilities": [],
                        }
                    ],
                }
            ],
            "education": [
                {
                    "period": "2000 - 2004",
                    "institution": "A",  # TOO SHORT
                    "details": [],
                }
            ],
        }

    def test_dirty_cv_detects_errors(self, dirty_cv):
        result = validate_cv_data(dirty_cv)
        assert result.is_valid is False  # Has errors
        assert result.error_count >= 3  # At least: full_name, phone, period month

    def test_dirty_cv_detects_warnings(self, dirty_cv):
        result = validate_cv_data(dirty_cv)
        assert result.warning_count >= 4  # email typo, yob, company, title, institution

    def test_dirty_cv_not_exportable(self, dirty_cv):
        result = validate_cv_data(dirty_cv)
        assert result.is_exportable is False

    def test_specific_error_codes_present(self, dirty_cv):
        result = validate_cv_data(dirty_cv)
        codes = {e.code for e in result.errors}
        assert "FIELD_EMPTY" in codes  # full_name
        assert "PHONE_TOO_SHORT" in codes  # phone

    def test_warning_codes_present(self, dirty_cv):
        result = validate_cv_data(dirty_cv)
        # EMAIL_TYPO is now ERROR severity (email typos are blocking)
        error_codes = {e.code for e in result.errors}
        assert "EMAIL_TYPO" in error_codes
        # YEAR_OF_BIRTH_UNREASONABLE is WARNING
        warn_codes = {e.code for e in result.warnings}
        assert "YEAR_OF_BIRTH_UNREASONABLE" in warn_codes


# ═══════════════════════════════════════════════════════════════
# TC-12: EMPTY / NEARLY EMPTY CV
# ═══════════════════════════════════════════════════════════════
class TestNearlyEmptyCV:
    def test_completely_empty_cv(self):
        result = validate_cv_data({})
        assert result.is_valid is False
        assert result.error_count >= 1  # full_name + email required

    def test_nearly_empty_cv_flagged(self):
        """If a CV has less than 3 non-empty fields, flag as possibly failed OCR."""
        result = validate_cv_data({"full_name": "Test"})
        codes = {e.code for e in result.errors}
        assert "CV_NEARLY_EMPTY" in codes or result.error_count >= 1


# ═══════════════════════════════════════════════════════════════
# TC-13: BATCH VALIDATION
# ═══════════════════════════════════════════════════════════════
class TestBatchValidation:
    def test_batch_validates_multiple(self):
        cvs = [
            {"full_name": "A", "email": "a@b.com"},
            {"full_name": "", "email": "bad"},
            {"full_name": "C", "email": "c@d.com"},
        ]
        results = validate_batch(cvs)
        assert len(results) == 3
        assert results[0].is_valid is True
        assert results[1].is_valid is False  # missing name + bad email
        assert results[2].is_valid is True

    def test_batch_summary(self):
        cvs = [{"full_name": "Test", "email": "test@test.com"}]
        results = validate_batch(cvs)
        assert results[0].summary is not None
        assert isinstance(results[0].summary, str)
        assert len(results[0].summary) > 0


# ═══════════════════════════════════════════════════════════════
# TC-14: SANITIZATION
# ═══════════════════════════════════════════════════════════════
class TestSanitization:
    def test_sanitize_removes_extra_spaces(self):
        data = {"full_name": "  Nguyen   Van   A  "}
        result = sanitize_for_export(data)
        assert "  " not in result["full_name"]

    def test_sanitize_trims_lines(self):
        data = {"address": "  123 Main St  \n  Hanoi  "}
        result = sanitize_for_export(data)
        assert result["address"] == "123 Main St\nHanoi"

    def test_sanitize_deep_nested(self):
        data = {
            "career_summary": [
                {
                    "company": "  FPT  ",
                    "positions": [
                        {"title": "  Engineer  "}
                    ]
                }
            ]
        }
        result = sanitize_for_export(data)
        assert "  " not in result["career_summary"][0]["company"]


# ═══════════════════════════════════════════════════════════════
# TC-15: STRICT MODE
# ═══════════════════════════════════════════════════════════════
class TestStrictMode:
    def test_warnings_block_export_in_strict(self):
        data = {
            "full_name": "Test",
            "email": "test@gmail.com",
            "year_of_birth": "1900",  # unreasonable → warning
        }
        result = validate_cv_data(data, strict=True)
        assert result.is_exportable is False  # warnings block in strict

    def test_warnings_allow_export_in_lenient(self):
        data = {
            "full_name": "Test",
            "email": "test@gmail.com",
            "year_of_birth": "1900",
        }
        result = validate_cv_data(data, strict=False)
        assert result.is_exportable is True  # warnings OK in lenient mode


# ═══════════════════════════════════════════════════════════════
# TC-16: SCALE TEST — 50 CVS AT ONCE
# ═══════════════════════════════════════════════════════════════
class TestScale50CVs:
    def test_batch_50_cvs_performance(self):
        """Validate 50 CVs — should complete in < 1 second."""
        import time
        cvs = [
            {
                "full_name": f"Candidate {i}",
                "email": f"user{i}@company.com",
                "phone": f"+84 912 {i:06d}",
                "career_summary": [
                    {
                        "period": "01/2020 - Present",
                        "company": f"Company {i}",
                        "positions": [{"title": f"Engineer {i}"}],
                    }
                ],
            }
            for i in range(50)
        ]
        start = time.time()
        results = validate_batch(cvs)
        elapsed = time.time() - start
        assert elapsed < 1.0, f"50 CVs took {elapsed:.2f}s — too slow"
        assert len(results) == 50
        assert all(r.is_valid for r in results)


# ═══════════════════════════════════════════════════════════════
# TC-17: PERIOD ORDER (chronological validation)
# ═══════════════════════════════════════════════════════════════
class TestPeriodOrder:
    def test_valid_period_chronological(self):
        assert validate_period_order("01/2020", "12/2022", "period") is None

    def test_valid_period_present(self):
        assert validate_period_order("06/2019", "Present", "period") is None

    def test_end_before_start_returns_error(self):
        err = validate_period_order("2022", "2020", "period")
        assert err is not None
        assert err.code == "PERIOD_END_BEFORE_START"
        assert err.severity == ValidationSeverity.ERROR

    def test_same_month_year_is_error(self):
        """Same month = not strictly after start → should be error."""
        err = validate_period_order("2020", "2020", "period")
        assert err is not None
        assert err.code == "PERIOD_END_BEFORE_START"

    def test_start_before_end_valid(self):
        err = validate_period_order("2020", "2022", "period")
        assert err is None


# ═══════════════════════════════════════════════════════════════
# TC-18: BULLET POINT COUNT
# ═══════════════════════════════════════════════════════════════
class TestBulletPoints:
    def test_enough_bullets_returns_none(self):
        text = "- First point\n- Second point\n- Third point"
        assert validate_bullet_points(text, "responsibilities", min_count=2) is None

    def test_too_few_bullets_returns_warning(self):
        text = "- Only one"
        err = validate_bullet_points(text, "responsibilities", min_count=2)
        assert err is not None
        assert err.code == "TOO_FEW_BULLET_POINTS"
        assert err.severity == ValidationSeverity.WARNING

    def test_numbered_list_counts(self):
        text = "1. First\n2. Second"
        assert validate_bullet_points(text, "details", min_count=2) is None

    def test_empty_text_returns_none(self):
        assert validate_bullet_points("", "content") is None
        assert validate_bullet_points(None, "content") is None


# ═══════════════════════════════════════════════════════════════
# TC-19: TITLE CASE (ALL-CAPS detection)
# ═══════════════════════════════════════════════════════════════
class TestTitleCase:
    def test_title_case_valid(self):
        assert validate_title_case("Software Engineer", "title") is None

    def test_all_caps_returns_warning(self):
        err = validate_title_case("SOFTWARE ENGINEER MANAGER DIRECTOR", "title")
        assert err is not None
        assert err.code == "TITLE_ALL_CAPS"
        assert err.severity == ValidationSeverity.WARNING

    def test_mixed_case_valid(self):
        assert validate_title_case("Sr. Software Engineer", "title") is None

    def test_short_all_caps_ignored(self):
        """< 3 alpha chars = too short to judge."""
        assert validate_title_case("CEO", "title") is None


# ═══════════════════════════════════════════════════════════════
# TC-20: DUPLICATE ENTRY DETECTION
# ═══════════════════════════════════════════════════════════════
class TestDuplicateEntries:
    def test_no_duplicates_returns_none(self):
        entries = [
            {"company": "FPT"},
            {"company": "Viettel"},
            {"company": "VNPT"},
        ]
        assert validate_duplicate_entries(entries, "career_summary", "company") is None

    def test_duplicate_company_returns_warning(self):
        entries = [
            {"company": "FPT Software"},
            {"company": "FPT Software"},
            {"company": "Viettel"},
        ]
        err = validate_duplicate_entries(entries, "career_summary", "company")
        assert err is not None
        assert err.code == "DUPLICATE_ENTRIES"
        assert err.severity == ValidationSeverity.WARNING

    def test_duplicate_case_insensitive(self):
        entries = [
            {"company": "fpt software"},
            {"company": "FPT Software"},
        ]
        err = validate_duplicate_entries(entries, "career_summary", "company")
        assert err is not None  # case-insensitive match

    def test_empty_list_returns_none(self):
        assert validate_duplicate_entries([], "career_summary") is None


# ═══════════════════════════════════════════════════════════════
# TC-21: to_dict INCLUDES SUMMARY
# ═══════════════════════════════════════════════════════════════
class TestValidationResultToDict:
    def test_to_dict_has_summary_field(self):
        result = validate_cv_data({
            "full_name": "Test",
            "email": "test@test.com",
        })
        d = result.to_dict()
        assert "summary" in d
        assert isinstance(d["summary"], str)
        assert len(d["summary"]) > 0

    def test_to_dict_with_errors_has_summary(self):
        result = validate_cv_data({})  # missing required fields
        d = result.to_dict()
        assert "summary" in d
        assert "error" in d["summary"].lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
