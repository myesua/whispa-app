from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import uuid

from app.services.screen_capture_service import (
    process_screen_capture,
    get_capture_status,
    get_captures_by_session,
    start_periodic_capture as start_periodic_capture_service,
    stop_periodic_capture as stop_periodic_capture_service
)

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
    thumbnail_url: Optional[str] = None
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
        # Process in background to avoid blocking
        background_tasks.add_task(
            process_screen_capture,
            capture_id=capture_id,
            file=file,
            ocr_enabled=request.ocr_enabled,
            session_id=request.session_id
        )
        
        return ScreenCaptureResponse(
            capture_id=capture_id,
            status="processing",
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
        result = get_capture_status(capture_id)
        if result is None:
            raise HTTPException(status_code=404, detail="Screen capture not found")
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving screen capture: {str(e)}")

@router.get("/session/{session_id}", response_model=List[Dict[str, Any]])
async def get_session_captures(session_id: str):
    """
    Get all captures for a session
    """
    try:
        return get_captures_by_session(session_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving session captures: {str(e)}")

@router.post("/periodic")
async def start_periodic_capture(request: ScreenCaptureRequest):
    """
    Start periodic screen capture at specified intervals
    """
    if not request.capture_interval or request.capture_interval < 1:
        raise HTTPException(status_code=400, detail="Valid capture interval required")
    
    if not request.session_id:
        request.session_id = str(uuid.uuid4())
    
    try:
        result = await start_periodic_capture_service(
            session_id=request.session_id,
            capture_interval=request.capture_interval,
            ocr_enabled=request.ocr_enabled
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start periodic capture: {str(e)}")

@router.delete("/periodic/{session_id}")
async def stop_periodic_capture(session_id: str):
    """
    Stop periodic screen capture for a session
    """
    try:
        result = await stop_periodic_capture_service(session_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to stop periodic capture: {str(e)}")

@router.post("/batch", response_model=Dict[str, Any])
async def process_batch_captures(files: List[UploadFile] = File(...), request: ScreenCaptureRequest = None):
    """
    Process multiple screen captures at once
    """
    if request is None:
        request = ScreenCaptureRequest()
    
    if not request.session_id:
        request.session_id = str(uuid.uuid4())
    
    try:
        capture_ids = []
        background_tasks = BackgroundTasks()
        
        for file in files:
            if not file.filename.endswith(('.png', '.jpg', '.jpeg')):
                continue
                
            capture_id = str(uuid.uuid4())
            capture_ids.append(capture_id)
            
            background_tasks.add_task(
                process_screen_capture,
                capture_id=capture_id,
                file=file,
                ocr_enabled=request.ocr_enabled,
                session_id=request.session_id
            )
        
        return {
            "message": f"Processing {len(capture_ids)} captures",
            "capture_ids": capture_ids,
            "session_id": request.session_id
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Batch processing failed: {str(e)}")