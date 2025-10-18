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
    background_tasks: BackgroundTasks,
    request: SummarizationRequest
):
    """
    Create a summary from transcription and optional screenshots
    """
    # Generate unique ID for this summary
    summary_id = str(uuid.uuid4())
    
    try:
        # Process in background to avoid blocking
        background_tasks.add_task(
            generate_qa_notes,
            summary_id=summary_id,
            transcription_id=request.transcription_id,
            session_id=request.session_id,
            screenshot_ids=request.screenshot_ids,
            format=request.format,
            qa_type=request.qa_type
        )
        
        return SummarizationResponse(
            summary_id=summary_id,
            status="processing",
            session_id=request.session_id
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{summary_id}", response_model=SummarizationResponse)
async def get_summary(summary_id: str):
    """
    Get the status or result of a summary
    """
    try:
        # This would need to be implemented in the service
        # For now, return a placeholder
        raise HTTPException(status_code=501, detail="Not implemented yet")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))