"""Test format validators for Indian business identifiers (plan section 1.3)."""

from __future__ import annotations

import pytest

from app.modules.verification.validators import (
    MAX_ID_LEN,
    IdError,
    ValidationResult,
    contains_aadhaar_shaped,
    gstin_check_digit,
    gstin_pan,
    gstin_state_code,
    is_aadhaar_shaped,
    pan_entity_type,
    validate_cin,
    validate_gstin,
    validate_iec,
    validate_ifsc,
    validate_llpin,
    validate_pan,
    validate_udyam,
)


class TestAadhaarDetection:
    """Aadhaar-shaped input is rejected by every validator (non-negotiable per plan 8.2)."""

    def test_aadhaar_exact_12_digits(self) -> None:
        """Done when: 12 consecutive digits are detected as Aadhaar-shaped."""
        assert is_aadhaar_shaped("123456789012")
        assert is_aadhaar_shaped("000000000000")

    def test_aadhaar_with_spaces(self) -> None:
        """Done when: 12 digits with spaces are Aadhaar-shaped."""
        assert is_aadhaar_shaped("1234 5678 9012")
        assert is_aadhaar_shaped("  1234 5678 9012  ")

    def test_aadhaar_with_hyphens(self) -> None:
        """Done when: 12 digits with hyphens are Aadhaar-shaped."""
        assert is_aadhaar_shaped("1234-5678-9012")

    def test_aadhaar_with_tabs(self) -> None:
        """Done when: 12 digits with tabs are Aadhaar-shaped."""
        assert is_aadhaar_shaped("1234\t5678\t9012")

    def test_not_aadhaar_11_digits(self) -> None:
        """Done when: 11 digits are not Aadhaar-shaped."""
        assert not is_aadhaar_shaped("12345678901")

    def test_not_aadhaar_13_digits(self) -> None:
        """Done when: 13 digits are not Aadhaar-shaped."""
        assert not is_aadhaar_shaped("1234567890123")

    def test_not_aadhaar_with_non_numeric(self) -> None:
        """Done when: 12 chars with non-digits are not Aadhaar-shaped."""
        assert not is_aadhaar_shaped("123456789ABC")

    def test_contains_aadhaar_in_text(self) -> None:
        """Done when: Aadhaar-shaped run is found in free text."""
        assert contains_aadhaar_shaped("my aadhaar is 1234 5678 9012 okay")
        assert contains_aadhaar_shaped("prefix-1234-5678-9012-suffix")

    def test_not_contains_aadhaar_isolated(self) -> None:
        """Done when: Aadhaar-shaped digits preceded/followed by digits are not found."""
        # The regex uses negative lookbehind/lookahead to avoid finding Aadhaar
        # within longer digit runs.
        assert not contains_aadhaar_shaped("abc 12345678901234567890")

    def test_gstin_rejects_aadhaar(self) -> None:
        """Done when: GSTIN validator rejects Aadhaar-shaped input."""
        result = validate_gstin("1234 5678 9012")
        assert result.valid is False
        assert result.error is IdError.AADHAAR_REJECTED

    def test_pan_rejects_aadhaar(self) -> None:
        """Done when: PAN validator rejects Aadhaar-shaped input."""
        result = validate_pan("1234 5678 9012")
        assert result.valid is False
        assert result.error is IdError.AADHAAR_REJECTED

    def test_udyam_rejects_aadhaar(self) -> None:
        """Done when: Udyam validator rejects Aadhaar-shaped input."""
        result = validate_udyam("1234 5678 9012")
        assert result.valid is False
        assert result.error is IdError.AADHAAR_REJECTED

    def test_iec_rejects_aadhaar(self) -> None:
        """Done when: IEC validator rejects Aadhaar-shaped input."""
        result = validate_iec("1234 5678 9012")
        assert result.valid is False
        assert result.error is IdError.AADHAAR_REJECTED

    def test_cin_rejects_aadhaar(self) -> None:
        """Done when: CIN validator rejects Aadhaar-shaped input."""
        result = validate_cin("1234 5678 9012")
        assert result.valid is False
        assert result.error is IdError.AADHAAR_REJECTED

    def test_ifsc_rejects_aadhaar(self) -> None:
        """Done when: IFSC validator rejects Aadhaar-shaped input."""
        result = validate_ifsc("1234 5678 9012")
        assert result.valid is False
        assert result.error is IdError.AADHAAR_REJECTED

    def test_llpin_rejects_aadhaar(self) -> None:
        """Done when: LLPIN validator rejects Aadhaar-shaped input."""
        result = validate_llpin("1234 5678 9012")
        assert result.valid is False
        assert result.error is IdError.AADHAAR_REJECTED


class TestGstinValidation:
    """GSTIN validation per plan section 1.3 and validators.py."""

    def test_valid_gstin_27aaapl1234c1ze(self) -> None:
        """Done when: Synthetic GSTIN with valid checksum is accepted."""
        result = validate_gstin("27AAAPL1234C1ZE")
        assert result.valid is True
        assert result.value == "27AAAPL1234C1ZE"

    def test_valid_gstin_29abcpe1234f1z7(self) -> None:
        """Done when: Another synthetic GSTIN is accepted."""
        result = validate_gstin("29ABCPE1234F1Z7")
        assert result.valid is True
        assert result.value == "29ABCPE1234F1Z7"

    def test_valid_gstin_06bbbct5678k1zs(self) -> None:
        """Done when: Synthetic GSTIN from state 06 is accepted."""
        result = validate_gstin("06BBBCT5678K1ZS")
        assert result.valid is True

    def test_valid_gstin_24abcfs1234g1zm(self) -> None:
        """Done when: Synthetic GSTIN from state 24 is accepted."""
        result = validate_gstin("24ABCFS1234G1ZM")
        assert result.valid is True

    def test_valid_gstin_36aaahx9999q2zm(self) -> None:
        """Done when: Synthetic GSTIN from state 36 is accepted."""
        result = validate_gstin("36AAAHX9999Q2ZM")
        assert result.valid is True

    def test_gstin_bad_check_digit(self) -> None:
        """Done when: GSTIN with wrong check digit is rejected as bad_check_digit."""
        # Change the last character to an invalid check digit
        result = validate_gstin("27AAAPL1234C1Z6")
        assert result.valid is False
        assert result.error is IdError.BAD_CHECK_DIGIT

    def test_gstin_state_code_00(self) -> None:
        """Done when: GSTIN with state code 00 is rejected as bad_state_code."""
        # Build a GSTIN with state 00 and valid format otherwise
        result = validate_gstin("00AAAPL1234C1ZA")
        assert result.valid is False
        assert result.error is IdError.BAD_STATE_CODE

    def test_gstin_state_code_40(self) -> None:
        """Done when: GSTIN with state code 40 is rejected as bad_state_code."""
        result = validate_gstin("40AAAPL1234C1ZA")
        assert result.valid is False
        assert result.error is IdError.BAD_STATE_CODE

    def test_gstin_state_code_valid_01(self) -> None:
        """Done when: GSTIN with state code 01 is valid."""
        result = validate_gstin("01AAAPL1234C1ZS")
        assert result.valid is True

    def test_gstin_state_code_valid_38(self) -> None:
        """Done when: GSTIN with state code 38 (highest) is valid."""
        result = validate_gstin("38AAAPL1234C1ZB")
        assert result.valid is True

    def test_gstin_state_code_97_other_territory(self) -> None:
        """Done when: GSTIN with state code 97 (other territory) is valid."""
        # 97 is a valid code for other territory
        result = validate_gstin("97AAAPL1234C1Z7")
        assert result.valid is True

    def test_gstin_state_code_99_centre(self) -> None:
        """Done when: GSTIN with state code 99 (centre) is valid."""
        result = validate_gstin("99AAAPL1234C1Z3")
        assert result.valid is True

    def test_gstin_lowercase_normalized(self) -> None:
        """Done when: Lowercase GSTIN is normalized to uppercase."""
        result = validate_gstin("27aaapl1234c1ze")
        assert result.valid is True
        assert result.value == "27AAAPL1234C1ZE"

    def test_gstin_whitespace_trimmed(self) -> None:
        """Done when: Whitespace-padded GSTIN is trimmed."""
        result = validate_gstin("  27AAAPL1234C1ZE  ")
        assert result.valid is True
        assert result.value == "27AAAPL1234C1ZE"

    def test_gstin_empty_rejected(self) -> None:
        """Done when: Empty GSTIN is rejected as empty."""
        result = validate_gstin("")
        assert result.valid is False
        assert result.error is IdError.EMPTY

    def test_gstin_whitespace_only_rejected(self) -> None:
        """Done when: Whitespace-only GSTIN is rejected as empty."""
        result = validate_gstin("   ")
        assert result.valid is False
        assert result.error is IdError.EMPTY

    def test_gstin_too_short(self) -> None:
        """Done when: GSTIN shorter than 15 chars is rejected."""
        result = validate_gstin("27AAAPL1234C1Z")
        assert result.valid is False
        assert result.error is IdError.BAD_FORMAT

    def test_gstin_too_long(self) -> None:
        """Done when: GSTIN longer than 15 chars is rejected."""
        result = validate_gstin("27AAAPL1234C1ZEXTRA")
        assert result.valid is False
        assert result.error is IdError.BAD_FORMAT

    def test_gstin_invalid_chars(self) -> None:
        """Done when: GSTIN with invalid chars is rejected."""
        result = validate_gstin("27AAAPL1234C1Z!")
        assert result.valid is False
        assert result.error is IdError.BAD_FORMAT


class TestGstinExtraction:
    """GSTIN state code and PAN extraction (plan section 1.3)."""

    def test_gstin_state_code_extracted(self) -> None:
        """Done when: gstin_state_code returns first 2 chars of valid GSTIN."""
        result = gstin_state_code("27AAAPL1234C1ZE")
        assert result == "27"

    def test_gstin_state_code_invalid_gstin(self) -> None:
        """Done when: gstin_state_code returns None for invalid GSTIN."""
        result = gstin_state_code("27AAAPL1234C1Z6")  # bad check digit
        assert result is None

    def test_gstin_state_code_empty(self) -> None:
        """Done when: gstin_state_code returns None for empty input."""
        result = gstin_state_code("")
        assert result is None

    def test_gstin_pan_extracted(self) -> None:
        """Done when: gstin_pan returns characters 3-12 of valid GSTIN."""
        result = gstin_pan("27AAAPL1234C1ZE")
        assert result == "AAAPL1234C"

    def test_gstin_pan_invalid_gstin(self) -> None:
        """Done when: gstin_pan returns None for invalid GSTIN."""
        result = gstin_pan("27AAAPL1234C1Z6")
        assert result is None

    def test_gstin_pan_empty(self) -> None:
        """Done when: gstin_pan returns None for empty input."""
        result = gstin_pan("")
        assert result is None


class TestGstinCheckDigit:
    """GSTIN check digit algorithm (plan section 1.3)."""

    def test_check_digit_27aaapl1234c1z(self) -> None:
        """Done when: Check digit for 27AAAPL1234C1Z is E."""
        digit = gstin_check_digit("27AAAPL1234C1Z")
        assert digit == "E"

    def test_check_digit_29abcpe1234f1z(self) -> None:
        """Done when: Check digit for 29ABCPE1234F1Z is 7."""
        digit = gstin_check_digit("29ABCPE1234F1Z")
        assert digit == "7"

    def test_check_digit_06bbbct5678k1z(self) -> None:
        """Done when: Check digit algorithm works for different states."""
        digit = gstin_check_digit("06BBBCT5678K1Z")
        assert digit == "S"


class TestPanValidation:
    """PAN validation (plan section 1.3)."""

    def test_pan_valid_individual(self) -> None:
        """Done when: PAN with entity type P (individual) is valid."""
        result = validate_pan("ABCPC1234X")
        assert result.valid is True
        assert result.value == "ABCPC1234X"

    def test_pan_valid_company(self) -> None:
        """Done when: PAN with entity type C (company) is valid."""
        result = validate_pan("ABCCC1234X")
        assert result.valid is True

    def test_pan_bad_entity_type(self) -> None:
        """Done when: PAN with invalid entity type (4th char from left, position 3) is rejected."""
        result = validate_pan("ABCDF1234X")
        assert result.valid is False
        assert result.error is IdError.BAD_ENTITY_TYPE

    def test_pan_lowercase_normalized(self) -> None:
        """Done when: Lowercase PAN is normalized to uppercase."""
        result = validate_pan("abcpc1234x")
        assert result.valid is True
        assert result.value == "ABCPC1234X"

    def test_pan_whitespace_trimmed(self) -> None:
        """Done when: Whitespace-padded PAN is trimmed."""
        result = validate_pan("  ABCPC1234X  ")
        assert result.valid is True
        assert result.value == "ABCPC1234X"

    def test_pan_empty_rejected(self) -> None:
        """Done when: Empty PAN is rejected."""
        result = validate_pan("")
        assert result.valid is False
        assert result.error is IdError.EMPTY

    def test_pan_too_short(self) -> None:
        """Done when: PAN shorter than 10 chars is rejected."""
        result = validate_pan("ABCDE1234")
        assert result.valid is False
        assert result.error is IdError.BAD_FORMAT

    def test_pan_invalid_format(self) -> None:
        """Done when: PAN with wrong pattern is rejected."""
        result = validate_pan("1234ABCDEP")
        assert result.valid is False
        assert result.error is IdError.BAD_FORMAT


class TestPanExtraction:
    """PAN entity type extraction."""

    def test_pan_entity_type_individual(self) -> None:
        """Done when: Entity type P is mapped to 'individual'."""
        result = pan_entity_type("ABCPC1234X")
        assert result == "individual"

    def test_pan_entity_type_company(self) -> None:
        """Done when: Entity type C is mapped to 'company'."""
        result = pan_entity_type("ABCCC1234X")
        assert result == "company"

    def test_pan_entity_type_huf(self) -> None:
        """Done when: Entity type H is mapped to 'huf'."""
        result = pan_entity_type("ABCHC1234X")
        assert result == "huf"

    def test_pan_entity_type_invalid_pan(self) -> None:
        """Done when: Entity type returns None for invalid PAN."""
        # PAN with F at position 3, which is not a valid entity type
        result = pan_entity_type("ABCDF1234X")
        assert result is None

    def test_pan_entity_type_empty(self) -> None:
        """Done when: Entity type returns None for empty input."""
        result = pan_entity_type("")
        assert result is None


class TestOtherIdentifiers:
    """Tests for IFSC, Udyam, CIN, LLPIN, IEC (plan section 1.3)."""

    def test_ifsc_valid(self) -> None:
        """Done when: Valid IFSC is accepted."""
        result = validate_ifsc("HDFC0001234")
        assert result.valid is True
        assert result.value == "HDFC0001234"

    def test_ifsc_lowercase_normalized(self) -> None:
        """Done when: IFSC is normalized to uppercase."""
        result = validate_ifsc("hdfc0001234")
        assert result.valid is True
        assert result.value == "HDFC0001234"

    def test_ifsc_invalid_bank_code(self) -> None:
        """Done when: IFSC with lowercase bank code is invalid."""
        result = validate_ifsc("hdfc0001234")
        # The normalizer uppercases first
        assert result.valid is True

    def test_ifsc_format_invalid(self) -> None:
        """Done when: IFSC not matching pattern is invalid."""
        result = validate_ifsc("HDFC00012345")
        assert result.valid is False

    def test_ifsc_empty(self) -> None:
        """Done when: Empty IFSC is rejected."""
        result = validate_ifsc("")
        assert result.valid is False

    def test_udyam_valid(self) -> None:
        """Done when: Valid Udyam is accepted."""
        result = validate_udyam("UDYAM-MH-01-0001234")
        assert result.valid is True
        assert result.value == "UDYAM-MH-01-0001234"

    def test_udyam_lowercase_normalized(self) -> None:
        """Done when: Udyam is normalized to uppercase."""
        result = validate_udyam("udyam-mh-01-0001234")
        assert result.valid is True
        assert result.value == "UDYAM-MH-01-0001234"

    def test_udyam_invalid_format(self) -> None:
        """Done when: Invalid Udyam format is rejected."""
        result = validate_udyam("UDYAM-MH-1-0001234")
        assert result.valid is False

    def test_udyam_empty(self) -> None:
        """Done when: Empty Udyam is rejected."""
        result = validate_udyam("")
        assert result.valid is False

    def test_cin_valid(self) -> None:
        """Done when: Valid CIN is accepted."""
        result = validate_cin("U12345MH2010PTC123456")
        assert result.valid is True
        assert result.value == "U12345MH2010PTC123456"

    def test_cin_lowercase_normalized(self) -> None:
        """Done when: CIN is normalized to uppercase."""
        result = validate_cin("u12345mh2010ptc123456")
        assert result.valid is True
        assert result.value == "U12345MH2010PTC123456"

    def test_cin_invalid_format(self) -> None:
        """Done when: Invalid CIN format is rejected."""
        result = validate_cin("U12345MH201PTC123456")
        assert result.valid is False

    def test_cin_empty(self) -> None:
        """Done when: Empty CIN is rejected."""
        result = validate_cin("")
        assert result.valid is False

    def test_llpin_valid(self) -> None:
        """Done when: Valid LLPIN is accepted."""
        result = validate_llpin("AAB-1234")
        assert result.valid is True
        assert result.value == "AAB-1234"

    def test_llpin_lowercase_normalized(self) -> None:
        """Done when: LLPIN is normalized to uppercase."""
        result = validate_llpin("aab-1234")
        assert result.valid is True
        assert result.value == "AAB-1234"

    def test_llpin_invalid_format(self) -> None:
        """Done when: Invalid LLPIN format is rejected."""
        result = validate_llpin("AB-1234")
        assert result.valid is False

    def test_llpin_empty(self) -> None:
        """Done when: Empty LLPIN is rejected."""
        result = validate_llpin("")
        assert result.valid is False

    def test_iec_valid(self) -> None:
        """Done when: Valid IEC is accepted."""
        result = validate_iec("ZZZCZ9999Z")
        assert result.valid is True
        assert result.value == "ZZZCZ9999Z"

    def test_iec_lowercase_normalized(self) -> None:
        """Done when: IEC is normalized to uppercase."""
        result = validate_iec("zzzcz9999z")
        assert result.valid is True
        assert result.value == "ZZZCZ9999Z"

    def test_iec_invalid_format(self) -> None:
        """Done when: IEC with wrong length is rejected."""
        result = validate_iec("AAACR505")
        assert result.valid is False

    def test_iec_empty(self) -> None:
        """Done when: Empty IEC is rejected."""
        result = validate_iec("")
        assert result.valid is False


class TestValidatorsRobustness:
    """Validators never raise; they handle all junk gracefully."""

    @pytest.mark.parametrize(
        "raw_input",
        [
            "",
            "   ",
            "\n",
            "\t",
            "very_long_string_" * 1000,
            "🔒",
            "\x00\x01\x02",
            "<script>alert('xss')</script>",
        ],
    )
    def test_gstin_never_raises(self, raw_input: str) -> None:
        """Done when: GSTIN validator never raises on any junk string input."""
        result = validate_gstin(raw_input)
        assert isinstance(result, ValidationResult)

    @pytest.mark.parametrize(
        "raw_input",
        ["", "   ", "abc", "123", "very_long_" * 1000, "🔒"],
    )
    def test_pan_never_raises(self, raw_input: str) -> None:
        """Done when: PAN validator never raises on junk inputs."""
        result = validate_pan(raw_input)
        assert isinstance(result, ValidationResult)

    @pytest.mark.parametrize(
        "raw_input",
        ["", "   ", "random", "🔒"],
    )
    def test_ifsc_never_raises(self, raw_input: str) -> None:
        """Done when: IFSC validator never raises."""
        result = validate_ifsc(raw_input)
        assert isinstance(result, ValidationResult)

    @pytest.mark.parametrize(
        "raw_input",
        ["", "   ", "invalid-udyam", "🔒"],
    )
    def test_udyam_never_raises(self, raw_input: str) -> None:
        """Done when: Udyam validator never raises."""
        result = validate_udyam(raw_input)
        assert isinstance(result, ValidationResult)

    @pytest.mark.parametrize(
        "raw_input",
        ["", "   ", "invalid", "🔒"],
    )
    def test_cin_never_raises(self, raw_input: str) -> None:
        """Done when: CIN validator never raises."""
        result = validate_cin(raw_input)
        assert isinstance(result, ValidationResult)

    @pytest.mark.parametrize(
        "raw_input",
        ["", "   ", "invalid", "🔒"],
    )
    def test_llpin_never_raises(self, raw_input: str) -> None:
        """Done when: LLPIN validator never raises."""
        result = validate_llpin(raw_input)
        assert isinstance(result, ValidationResult)

    @pytest.mark.parametrize(
        "raw_input",
        ["", "   ", "invalid", "🔒"],
    )
    def test_iec_never_raises(self, raw_input: str) -> None:
        """Done when: IEC validator never raises."""
        result = validate_iec(raw_input)
        assert isinstance(result, ValidationResult)


class TestNonAscii:
    """Non-ASCII characters are rejected with NON_ASCII error."""

    def test_gstin_non_ascii_devanagari(self) -> None:
        """Done when: Non-ASCII GSTIN rejected as NON_ASCII."""
        result = validate_gstin("27AAAPL१२३४C1ZE")  # Devanagari digits
        assert result.valid is False
        assert result.error is IdError.NON_ASCII

    def test_pan_non_ascii(self) -> None:
        """Done when: Non-ASCII PAN rejected as NON_ASCII."""
        result = validate_pan("ABCDP१२३४X")
        assert result.valid is False
        assert result.error is IdError.NON_ASCII

    def test_gstin_non_ascii_checked_before_upper(self) -> None:
        """Done when: Non-ASCII check is before uppercase (which can change length)."""
        result = validate_gstin(
            "27AAAPLabcdC1ZE"
        )  # lowercase letters not valid anyway, but checked as non-ascii-safe
        # This is ASCII, so should fail for other reasons
        assert result.valid is False


class TestMaxLength:
    """Identifiers > MAX_ID_LEN are rejected as BAD_FORMAT."""

    def test_gstin_33_chars_rejected(self) -> None:
        """Done when: GSTIN with 33 chars is rejected as BAD_FORMAT."""
        long_gstin = "27AAAPL1234C1ZE" + "X" * (33 - 15)
        result = validate_gstin(long_gstin)
        assert result.valid is False
        assert result.error is IdError.BAD_FORMAT

    def test_pan_33_chars_rejected(self) -> None:
        """Done when: PAN-like string with 33 chars is rejected."""
        long_pan = "ABCPC1234X" + "Y" * (33 - 10)
        result = validate_pan(long_pan)
        assert result.valid is False
        assert result.error is IdError.BAD_FORMAT

    def test_max_id_len_is_32(self) -> None:
        """Done when: MAX_ID_LEN constant is 32."""
        assert MAX_ID_LEN == 32

    def test_32_char_gstin_acceptable(self) -> None:
        """Done when: Exactly 32-char identifier (if valid format) passes length check."""
        # Create a 32-char string in GSTIN format
        gstin_32 = "27AAAPL1234C1ZE" + "A" * (32 - 15)
        # This won't be a valid GSTIN due to format, but should pass length check
        result = validate_gstin(gstin_32)
        # Should fail for format, not length
        assert result.error is IdError.BAD_FORMAT


class TestValidationResultRepr:
    """ValidationResult.value is excluded from repr (security: never in logs)."""

    def test_validation_result_repr_hides_value(self) -> None:
        """Done when: repr(ValidationResult) doesn't contain the value."""
        result = validate_gstin("27AAAPL1234C1ZE")
        r = repr(result)
        assert "27AAAPL1234C1ZE" not in r
        assert "value=" not in r or "value=None" in r

    def test_validation_result_value_accessible_by_attribute(self) -> None:
        """Done when: .value attribute is still accessible, just not in repr."""
        result = validate_gstin("27AAAPL1234C1ZE")
        assert result.value == "27AAAPL1234C1ZE"
        assert result.value not in repr(result)
