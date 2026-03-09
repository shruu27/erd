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

# Load environment variables FIRST, before other imports that may rely on them
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
    operation: Optional[str] = ""  # "CREATE" | "MODIFY" | "" (auto-classify)
    existing_model: Optional[Dict[str, Any]] = None  # for MODIFY


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
    sql_output: Dict[str, Any]  # Contains combined_sql, relational_sql, analytical_sql
    format: str = "svg"  # "svg" | "png" | "pdf"


# ── Health ────────────────────────────────────────────────────────────────────
@app.get("/health")
def health():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}


# ── Step 1: Generate data model JSON ─────────────────────────────────────────
@app.post("/workflow/generate")
def generate(req: GenerateRequest):
    """
    Generate a structured JSON data model (relational + analytical).
    This is the first step for both CREATE and MODIFY operations.

    For MODIFY, supply `existing_model` with the current model JSON.
    The `operation` field may be left empty to auto-classify.
    """
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


# ── Step 2a (AUTO): Validate model with LLM → generate SQL if valid ──────────
@app.post("/workflow/validate")
def validate(req: ValidateRequest):
    """
    AUTO validation mode.
    LLM validates the data model JSON.
    If valid → SQL is generated and returned.
    If invalid → validation errors are returned for the UI to retry.
    """
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
    """
    MANUAL validation mode — user approved the model as-is.
    Generates and returns SQL DDL scripts.
    """
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
    """
    MANUAL validation mode — user provided change requests.
    Updates the data model based on feedback then generates SQL.
    Returns both the updated model and SQL.
    """
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


# ── Step 3: Generate ERD from SQL ──────────────────────────────────────────────
@app.post("/workflow/generate-erd")
def generate_erd_diagram(req: ERDRequest):
    """
    Generate an Entity Relationship Diagram from the SQL output.
    Takes the combined SQL script and renders it as SVG/PNG/PDF.
    Returns the diagram as base64-encoded data.
    """
    try:
        # Extract the combined SQL (fallback to relational if combined not available)
        sql_text = req.sql_output.get("combined_sql") or req.sql_output.get("relational_sql", "")
        
        if not sql_text:
            raise ValueError("No SQL content available to generate ERD")
        
        # Generate the ERD; generate_erd may raise ValueError if parsing fails
        dot_obj, dot_src = generate_erd([sql_text], fmt=req.format)
        
        # Render to a temporary file
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "erd_output")
            render_path = dot_obj.render(output_path, format=req.format, cleanup=True)
            
            # Read the file and encode as base64
            with open(render_path, "rb") as f:
                diagram_data = base64.b64encode(f.read()).decode("utf-8")
        
        return {
            "status": "success",
            "timestamp": datetime.utcnow().isoformat(),
            "diagram_data": diagram_data,
            "format": req.format,
            "dot_source": dot_src,  # Include DOT source for reference
        }
    except ValueError as e:
        # Client-side error (likely bad/empty SQL) → 400
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        # Unhandled server error
        raise HTTPException(status_code=500, detail=str(e))