"""
main.py — FastAPI backend for Agentic Schema Modelling

Workflow (two validation modes):

AUTO mode:
POST /workflow/generate   → generate JSON data model
POST /workflow/validate   → LLM validates model, generates SQL if valid

MANUAL mode:
POST /workflow/generate   → generate JSON data model
POST /workflow/approve    → user approves → generate SQL
POST /workflow/feedback   → user suggests changes → update model → generate SQL
"""

from dotenv import load_dotenv
import os
from datetime import datetime
from typing import Any, Dict, Optional
import base64
import tempfile

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend.graph.langgraph_flow import (
    run_generate_model,
    run_auto_validate_and_sql,
    run_apply_feedback_and_sql,
    run_approve_and_generate_sql,
)
from backend.utils.erd import generate_erd

load_dotenv(r"C:/Users/BM354VJ/OneDrive - EY/Desktop/agentic-data-modelling-backend/backend/.env")

app = FastAPI(title="Agentic Schema Modelling Service", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Request / Response models ─────────────────────────────────────────────────

class GenerateRequest(BaseModel):
    user_query: str
    operation: Optional[str] = ""
    existing_model: Optional[Dict[str, Any]] = None


class ValidateRequest(BaseModel):
    data_model: Dict[str, Any]
    operation: str = "CREATE"


class ApproveRequest(BaseModel):
    data_model: Dict[str, Any]
    operation: str = "CREATE"


class FeedbackRequest(BaseModel):
    data_model: Dict[str, Any]
    feedback: str
    operation: str = "CREATE"


class ERDRequest(BaseModel):
    sql_output: Dict[str, Any]
    format: str = "svg"


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}


# ── Step 1: Generate data model JSON ─────────────────────────────────────────

@app.post("/workflow/generate")
def generate(req: GenerateRequest):
    try:
        result = run_generate_model(
            user_input=req.user_query,
            operation=req.operation or "",
            existing_model=req.existing_model,
        )
        return {
            "status": "success",
            "timestamp": datetime.utcnow().isoformat(),
            **result,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Step 2a (AUTO): Validate model → generate SQL if valid ───────────────────

@app.post("/workflow/validate")
def validate(req: ValidateRequest):
    try:
        result = run_auto_validate_and_sql(req.data_model, req.operation)
        return {
            "status": "success",
            "timestamp": datetime.utcnow().isoformat(),
            **result,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Step 2b (MANUAL): User approves → generate SQL ───────────────────────────

@app.post("/workflow/approve")
def approve(req: ApproveRequest):
    try:
        result = run_approve_and_generate_sql(req.data_model, req.operation)
        return {
            "status": "success",
            "timestamp": datetime.utcnow().isoformat(),
            **result,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Step 2c (MANUAL): User suggests changes → update model → generate SQL ────

@app.post("/workflow/feedback")
def feedback(req: FeedbackRequest):
    try:
        result = run_apply_feedback_and_sql(
            data_model=req.data_model,
            feedback=req.feedback,
            operation=req.operation,
        )
        return {
            "status": "success",
            "timestamp": datetime.utcnow().isoformat(),
            **result,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Step 3: Generate ERD from SQL ────────────────────────────────────────────

@app.post("/workflow/generate-erd")
def generate_erd_diagram(req: ERDRequest):
    """
    Generate an Entity Relationship Diagram from the SQL output.
    Takes the combined SQL script and renders it as SVG/PNG/PDF.
    Returns the diagram as base64-encoded data.
    """
    try:
        # FIX: validate format value before passing to Graphviz to avoid
        # unexpected errors; default to "svg" if an unsupported value arrives.
        fmt = req.format if req.format in ("svg", "png", "pdf") else "svg"

        # Extract SQL — prefer combined_sql, fall back to relational_sql
        sql_text = (
            req.sql_output.get("combined_sql")
            or req.sql_output.get("relational_sql", "")
        )

        if not sql_text or not sql_text.strip():
            raise ValueError("No SQL content available to generate ERD")

        # generate_erd raises ValueError if no CREATE TABLE statements are found
        dot_obj, dot_src = generate_erd([sql_text], fmt=fmt)

        # Render to a temporary file, read bytes, base64-encode for the response
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "erd_output")
            # dot_obj.render() returns the path of the rendered file
            render_path = dot_obj.render(output_path, format=fmt, cleanup=True)

            with open(render_path, "rb") as f:
                diagram_data = base64.b64encode(f.read()).decode("utf-8")

        return {
            "status": "success",
            "timestamp": datetime.utcnow().isoformat(),
            "diagram_data": diagram_data,
            "format": fmt,
            "dot_source": dot_src,
        }

    except ValueError as e:
        # Bad/empty SQL → tell the client clearly (400, not 500)
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
