"""Tests for the code around the model. These need no API key.

Usage: python -m unittest discover tests
"""

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from evaluate import FIELDS, score_case, values_match
from extractor import empty_result, extract


def reply_with(**values):
    result = empty_result("valid")
    result.update(values)
    return lambda text: json.dumps(result)


def no_model_allowed(text):
    raise AssertionError("The model should not be called")


class ExtractTests(unittest.TestCase):
    def test_blank_input_skips_the_model(self):
        self.assertEqual(extract("   ", llm=no_model_allowed)["input_status"], "invalid")

    def test_invented_email_is_removed(self):
        result = extract("I'm Ann Lee.", llm=reply_with(applicant_name="Ann Lee", email="ann@example.com"))
        self.assertIsNone(result["email"])
        self.assertEqual(result["applicant_name"], "Ann Lee")
        self.assertEqual(result["input_status"], "ambiguous")

    def test_phone_formatting_differences_are_allowed(self):
        result = extract("Call 98765 43210", llm=reply_with(phone="9876543210"))
        self.assertEqual(result["phone"], "9876543210")

    def test_url_without_https_in_message_is_kept(self):
        result = extract("See linkedin.com/in/ann", llm=reply_with(linkedin_url="https://linkedin.com/in/ann"))
        self.assertEqual(result["linkedin_url"], "https://linkedin.com/in/ann")

    def test_invalid_status_clears_every_field(self):
        result = extract("Buy now", llm=reply_with(input_status="invalid", applicant_name="Buy"))
        self.assertIsNone(result["applicant_name"])

    def test_bad_reply_is_retried_once(self):
        replies = iter(["not json", json.dumps(empty_result("valid"))])
        result = extract("hello", llm=lambda text: next(replies))
        self.assertEqual(result["input_status"], "valid")

    def test_repeated_bad_replies_raise_an_error(self):
        with self.assertRaises(ValueError):
            extract("hello", llm=lambda text: '{"wrong": true}')


class ScoringTests(unittest.TestCase):
    def test_skills_ignore_order_and_case(self):
        self.assertTrue(values_match("skills", ["SQL", "Go"], ["go", "sql"]))

    def test_null_only_matches_null(self):
        self.assertFalse(values_match("email", None, "a@example.com"))
        self.assertFalse(values_match("email", "a@example.com", None))

    def test_invented_value_is_counted(self):
        case = {"id": "x", "category": "c", "description": "d", "expected": {"input_status": "valid"}}
        actual = empty_result("valid")
        actual["expected_salary"] = "$10"
        row = score_case(case, actual)
        self.assertEqual(row["invented_fields"], ["expected_salary"])
        self.assertEqual(row["fields_correct"], len(FIELDS) - 1)


class TestCaseFileTests(unittest.TestCase):
    def test_coverage_and_field_names(self):
        path = Path(__file__).parent / "test_cases.json"
        cases = json.loads(path.read_text())
        self.assertGreaterEqual(len(cases), 20)
        self.assertEqual(len({c["id"] for c in cases}), len(cases))
        for case in cases:
            self.assertLessEqual(set(case["expected"]) - {"input_status"}, set(FIELDS), case["id"])
            self.assertIn(case["expected"]["input_status"], ("valid", "ambiguous", "invalid"))


if __name__ == "__main__":
    unittest.main()
