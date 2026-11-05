"""Turns a job application message into JSON that follows a fixed schema.

Steps for each message:
  1. Send the rules, schema and message to Gemini.
  2. Check the reply matches the schema.
  3. Remove any contact detail or name that is not really in the message.
"""

import json
import os
import re
import time
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import errors
from jsonschema import ValidationError, validate

ROOT = Path(__file__).parent
SCHEMA = json.loads((ROOT / "schema" / "job_application.schema.json").read_text())
SYSTEM_PROMPT = (ROOT / "prompts" / "system_prompt.txt").read_text()

load_dotenv(ROOT / ".env")
MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")

# Every field except these two holds extracted data and can be null.
FIELDS = [name for name in SCHEMA["required"] if name not in ("input_status", "ambiguity_notes")]

RETRYABLE_STATUS_CODES = (429, 500, 503)
MAX_ATTEMPTS = 5


def empty_result(status="invalid"):
    result = {field: None for field in FIELDS}
    result["input_status"] = status
    result["ambiguity_notes"] = []
    return result


def call_gemini(text):
    """Sends one message to Gemini and returns the reply as a string."""
    client = genai.Client()
    interaction = client.interactions.create(
        model=MODEL,
        system_instruction=SYSTEM_PROMPT,
        input=f"<message>\n{text}\n</message>",
        generation_config={"temperature": 0},
        response_format={
            "type": "text",
            "mime_type": "application/json",
            "schema": SCHEMA,
        },
    )
    return interaction.output_text


def call_with_retries(text, llm):
    """Waits and retries when the free tier rate limit or a server error is hit."""
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            return llm(text)
        except errors.APIError as error:
            if error.code not in RETRYABLE_STATUS_CODES or attempt == MAX_ATTEMPTS:
                raise
            time.sleep(10 * attempt)


def digits(value):
    return re.sub(r"\D", "", value)


def bare_url(value):
    value = re.sub(r"^https?://(www\.)?", "", value.strip().lower())
    return value.rstrip("/")


def is_in_message(field, value, text):
    """Checks a value appears in the message, so an invented one can be caught."""
    lowered = text.lower()
    if field == "phone":
        return bool(digits(value)) and digits(value) in digits(text)
    if field in ("linkedin_url", "portfolio_url"):
        return bare_url(value) in lowered
    if field == "applicant_name":
        return all(word in lowered for word in value.lower().split())
    return value.lower() in lowered


def apply_safety_checks(result, text):
    """Rules enforced in code, so they hold even if the model ignores the prompt."""
    if result["input_status"] == "invalid":
        return empty_result()

    for field in ("applicant_name", "email", "phone", "linkedin_url", "portfolio_url"):
        value = result[field]
        if value is not None and not is_in_message(field, value, text):
            result[field] = None
            label = field.replace("_", " ")
            result["ambiguity_notes"].append(f"Removed the {label} because it was not in the message.")

    if result["ambiguity_notes"]:
        result["input_status"] = "ambiguous"
    return result


def extract(text, llm=call_gemini):
    """Returns extracted details for one message as a dictionary.

    `llm` can be replaced with a fake function so tests run without an API key.
    """
    if not text or not text.strip():
        return empty_result()

    # A bad reply gets one more try before giving up.
    for attempt in range(2):
        reply = call_with_retries(text, llm)
        try:
            result = json.loads(reply)
            validate(result, SCHEMA)
            return apply_safety_checks(result, text)
        except (json.JSONDecodeError, TypeError, ValidationError) as error:
            if attempt == 1:
                raise ValueError(f"Model reply did not match the schema: {error}") from error
