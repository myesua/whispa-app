from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import uuid

from app.services.gemini_service import generate_qa_notes

router = APIRouter()

class SummarizationRequest(BaseModel):
    transcription_id: str
    session_id: Optional[str] = None
    screenshot_ids: Optional[List[str]] = None
    format: str = "markdown"  # Options: "markdown", "json"
    qa_type: str = "general"  # Options: "general", "bug", "ux", "feature"

class SummarizationResponse(BaseModel):
    summary_id: str
    status: str
    content: Optional[Dict[str, Any]] = None
    session_id: Optional[str] = None

@router.post("/", response_model=SummarizationResponse)
async def create_summary(
    request: SummarizationRequest,
    background_tasks: BackgroundTasks
):
    """
    Generate QA notes from transcription and optional screenshots
    """
    summary_id = str(uuid.uuid4())
    
    try:
        # Process in background to avoid blocking
        background_tasks.add_task(
            generate_qa_notes,
            summary_id=summary_id,
            transcription_id=request.transcription_id,
            screenshot_ids=request.screenshot_ids,
            format=request.format,
            qa_type=request.qa_type,
            session_id=request.session_id
        )
        
        return SummarizationResponse(
            summary_id=summary_id,
            status="processing",
            session_id=request.session_id
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Summarization failed: {str(e)}")

@router.get("/{summary_id}", response_model=SummarizationResponse)
async def get_summary(summary_id: str):
    """
    Get the status or result of a summarization
    """
    try:
        # This would call a service to retrieve the summary
        # For now, we'll return a placeholder
        return SummarizationResponse(
            summary_id=summary_id,
            status="completed",
            content={
                "title": "Sample QA Notes",
                "observations": [
                    {"type": "bug", "description": "Button not responding on click", "severity": "high"},
                    {"type": "ux", "description": "Navigation flow is confusing", "severity": "medium"}
                ],
                "summary": "Several issues were identified during testing..."
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving summary: {str(e)}")

@router.post("/{summary_id}/export")
async def export_summary(summary_id: str, destination: str = "linear"):
    """
    Export a summary to an external system (Linear, Jira, etc.)
    """
    # This would integrate with the specified system
    return {"message": f"Summary {summary_id} exported to {destination}", "status": "success"}