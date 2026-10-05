"""Test rules schema and validation."""

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker, ValidationError


def test_rules_schema_valid() -> None:
    """Done when: packages/rules/schema.json passes Draft202012Validator.check_schema."""
    schema_path = Path(__file__).parent.parent.parent.parent / "packages" / "rules" / "schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    # This raises if the schema is invalid
    Draft202012Validator.check_schema(schema)


def test_all_rule_files_validate() -> None:
    """Done when: every packages/rules/*.json (except schema.json) validates."""
    schema_path = Path(__file__).parent.parent.parent.parent / "packages" / "rules" / "schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema, format_checker=FormatChecker())

    rules_dir = schema_path.parent
    rule_files = sorted(rules_dir.glob("*.json"))
    rule_files = [f for f in rule_files if f.name != "schema.json"]

    for rule_file in rule_files:
        rule = json.loads(rule_file.read_text(encoding="utf-8"))
        try:
            validator.validate(rule)
        except ValidationError as e:
            raise AssertionError(f"{rule_file.name} failed validation: {e.message}") from e


def test_sample_valid_rule() -> None:
    """Done when: a filled-in sample rule with all required fields passes."""
    schema_path = Path(__file__).parent.parent.parent.parent / "packages" / "rules" / "schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema, format_checker=FormatChecker())

    sample_rule = {
        "id": "sample-rule",
        "layer": 1,
        "applies_to": "goods",
        "market": "EU",
        "hs_prefixes": [],
        "title": "Sample Rule",
        "body": "This is a sample rule for testing.",
        "mandatory": True,
        "status_logic": "always_todo",
        "source": {
            "name": "Example Authority",
            "url": "https://example.com/rule",
            "reference": "REF-001",
        },
        "checked_on": "2026-10-05",
        "review_by": "2027-10-05",
        "review_state": "verified",
    }

    # This should not raise
    validator.validate(sample_rule)


def test_rule_missing_source_fails() -> None:
    """Done when: a rule missing 'source' field fails validation."""
    schema_path = Path(__file__).parent.parent.parent.parent / "packages" / "rules" / "schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema, format_checker=FormatChecker())

    invalid_rule = {
        "id": "no-source",
        "layer": 1,
        "applies_to": "goods",
        "market": "EU",
        "hs_prefixes": [],
        "title": "No Source Rule",
        "body": "This rule is missing the source field.",
        "mandatory": True,
        "status_logic": "always_todo",
        "checked_on": "2026-10-05",
        "review_by": "2027-10-05",
        "review_state": "verified",
    }

    with pytest.raises(ValidationError):
        validator.validate(invalid_rule)


def test_rule_bad_date_fails() -> None:
    """Done when: a rule with a bad date in checked_on fails validation."""
    schema_path = Path(__file__).parent.parent.parent.parent / "packages" / "rules" / "schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema, format_checker=FormatChecker())

    invalid_rule = {
        "id": "bad-date",
        "layer": 1,
        "applies_to": "goods",
        "market": "EU",
        "hs_prefixes": [],
        "title": "Bad Date Rule",
        "body": "This rule has an invalid date.",
        "mandatory": True,
        "status_logic": "always_todo",
        "source": {
            "name": "Example Authority",
            "url": "https://example.com/rule",
            "reference": "REF-001",
        },
        "checked_on": "2026-13-45",  # Invalid date
        "review_by": "2027-10-05",
        "review_state": "verified",
    }

    with pytest.raises(ValidationError):
        validator.validate(invalid_rule)
