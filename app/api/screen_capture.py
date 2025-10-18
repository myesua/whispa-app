from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional, List
import uuid

router = APIRouter()

class ScreenCaptureRequest(BaseModel):
    session_id: Optional[str] = None
    ocr_enabled: bool = True
    capture_interval: Optional[int] = None  # In seconds, for periodic capture

class ScreenCaptureResponse(BaseModel):
    capture_id: str
    status: str
    ocr_text: Optional[str] = None
    image_url: Optional[str] = None
    session_id: Optional[str] = None

@router.post("/", response_model=ScreenCaptureResponse)
async def create_screen_capture(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    request: ScreenCaptureRequest = None
):
    """
    Process a screen capture image with optional OCR
    """
    if not file.filename.endswith(('.png', '.jpg', '.jpeg')):
        raise HTTPException(status_code=400, detail="Unsupported file format")
    
    if request is None:
        request = ScreenCaptureRequest()
    
    # Generate unique ID for this capture
    capture_id = str(uuid.uuid4())
    
    try:
        # This would call a service to process the image
        # For now, we'll return a placeholder
        return ScreenCaptureResponse(
            capture_id=capture_id,
            status="completed",
            ocr_text="Sample OCR text from screenshot" if request.ocr_enabled else None,
            image_url=f"/storage/captures/{capture_id}.png",
            session_id=request.session_id
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Screen capture processing failed: {str(e)}")

@router.get("/{capture_id}", response_model=ScreenCaptureResponse)
async def get_screen_capture(capture_id: str):
    """
    Get the status or result of a screen capture
    """
    try:
        # This would call a service to retrieve the capture
        # For now, we'll return a placeholder
        return ScreenCaptureResponse(
            capture_id=capture_id,
            status="completed",
            ocr_text="Sample OCR text from screenshot",
            image_url=f"/storage/captures/{capture_id}.png"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving screen capture: {str(e)}")

@router.post("/periodic")
async def start_periodic_capture(request: ScreenCaptureRequest):
    """
    Start periodic screen capture at specified intervals
    """
    if not request.capture_interval or request.capture_interval < 1:
        raise HTTPException(status_code=400, detail="Valid capture interval required")
    
    # This would start a background task for periodic capture
    return {
        "message": f"Periodic capture started with interval {request.capture_interval}s",
        "session_id": request.session_id,
        "status": "active"
    }

@router.delete("/periodic/{session_id}")
async def stop_periodic_capture(session_id: str):
    """
    Stop periodic screen capture for a session
    """
    # This would stop the background task
    return {"message": f"Periodic capture stopped for session {session_id}", "status": "stopped"}