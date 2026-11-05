"""Connects the React page to the extractor.

Start it with: uvicorn api:app --reload
"""

import json
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from extractor import extract

SAMPLE_CASES = {
    "Complete application": "complete_01",
    "Missing details": "missing_02",
    "Conflicting details": "ambiguous_01",
    "Not a job application": "invalid_02",
}

cases = json.loads((Path(__file__).parent / "tests" / "test_cases.json").read_text())
inputs_by_id = {case["id"]: case["input"] for case in cases}

app = FastAPI(title="Job Application Extractor")


class ExtractRequest(BaseModel):
    text: str


@app.get("/api/samples")
def samples():
    return [
        {"label": label, "text": inputs_by_id[case_id]}
        for label, case_id in SAMPLE_CASES.items()
    ]


@app.post("/api/extract")
def extract_details(request: ExtractRequest):
    try:
        return extract(request.text)
    except Exception as error:
        print(f"Extraction failed: {error}")
        raise HTTPException(
            status_code=502,
            detail="We couldn't read that message just now. Please try again in a minute.",
        ) from error


# In production, serve the built React page from the same server.
frontend_dist = Path(__file__).parent / "frontend" / "dist"
if frontend_dist.is_dir():
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")
