"""
FastAPI backend for FinITR-AI v3.
Run: uvicorn api.main:app --reload --port 8000
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

app = FastAPI(title="FinITR-AI v3", version="3.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

OUTPUTS = Path("outputs")
OUTPUTS.mkdir(parents=True, exist_ok=True)

# In-memory session (single-user demo)
_session: dict = {}


def _save(file: UploadFile, name: str) -> str:
    path = OUTPUTS / name
    with open(path, "wb") as f:
        f.write(file.file.read())
    return str(path)


def check_ollama() -> bool:
    try:
        import ollama
        ollama.list()
        return True
    except Exception:
        return False


@app.get("/health")
async def health():
    return {"status": "ok", "ollama": check_ollama(), "version": "3.0"}


@app.post("/analyze")
async def analyze(
    bank_csv: Optional[UploadFile] = File(None),
    ais_json: Optional[UploadFile] = File(None),
    form16_json: Optional[UploadFile] = File(None),
    gross_income: float = Form(0.0),
    basic_salary: float = Form(0.0),
):
    """Run the full multi-agent pipeline on uploaded documents."""
    bank_path = _save(bank_csv, "api_bank.csv") if bank_csv and bank_csv.filename else None
    ais_path = _save(ais_json, "api_ais.json") if ais_json and ais_json.filename else None
    form16_path = _save(form16_json, "api_form16.json") if form16_json and form16_json.filename else None

    try:
        from agents.orchestrator import Orchestrator
        orch = Orchestrator(verbose=False)
        report = orch.run(
            bank_csv=bank_path,
            ais_json=ais_path,
            form16_json=form16_path,
            gross_income=gross_income,
            basic_salary=basic_salary,
            interview_answers=_session.get("interview_answers", {}),
        )
        _session["last_report"] = report
        return JSONResponse(content=report)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class InterviewAnswers(BaseModel):
    answers: dict


@app.post("/interview/answer")
async def answer_interview(body: InterviewAnswers):
    """Submit interview answers and re-run pipeline."""
    _session["interview_answers"] = body.answers

    report = _session.get("last_report")
    if not report:
        raise HTTPException(status_code=400, detail="No pipeline run found. Call /analyze first.")

    try:
        bank = str(OUTPUTS / "api_bank.csv") if (OUTPUTS / "api_bank.csv").exists() else None
        ais = str(OUTPUTS / "api_ais.json") if (OUTPUTS / "api_ais.json").exists() else None
        f16 = str(OUTPUTS / "api_form16.json") if (OUTPUTS / "api_form16.json").exists() else None

        from agents.orchestrator import Orchestrator
        orch = Orchestrator(verbose=False)
        updated = orch.run(
            bank_csv=bank,
            ais_json=ais,
            form16_json=f16,
            gross_income=report.get("gross_income", 0),
            basic_salary=report.get("basic_salary", 0),
            interview_answers=body.answers,
        )
        _session["last_report"] = updated
        return JSONResponse(content=updated)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/report/ca-brief")
async def get_ca_brief(fmt: str = "pdf"):
    """Download CA Brief as PDF."""
    report = _session.get("last_report")
    if not report:
        raise HTTPException(status_code=404, detail="No report. Call /analyze first.")

    pdf_path = str(OUTPUTS / "ca_brief_api.pdf")
    try:
        from outputs.ca_brief_generator import CABriefGenerator
        CABriefGenerator().generate_pdf(report, pdf_path)
        return FileResponse(
            path=pdf_path,
            media_type="application/pdf",
            filename=f"CA_Brief_{report.get('assessment_year', '2026-27')}.pdf",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/report/itr-json")
async def get_itr_json():
    """Download ITR-2 JSON for e-filing portal."""
    report = _session.get("last_report")
    if not report:
        raise HTTPException(status_code=404, detail="No report. Call /analyze first.")

    try:
        from outputs.itr_json_generator import ITRJsonGenerator
        itr_json = ITRJsonGenerator().generate(report)
        return JSONResponse(content=itr_json)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/report/full")
async def get_full_report():
    """Get full pipeline report as JSON."""
    report = _session.get("last_report")
    if not report:
        raise HTTPException(status_code=404, detail="No report. Call /analyze first.")
    return JSONResponse(content=report)
