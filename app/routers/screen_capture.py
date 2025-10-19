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
    image_path: Optional[str] = None
    ocr_text: Optional[str] = None
    session_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

@router.post("/", response_model=ScreenCaptureResponse)
async def create_screen_capture(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    request: str = None
):
    """
    Process a screen capture image
    """
    if not file.filename.endswith(('.png', '.jpg', '.jpeg')):
        raise HTTPException(status_code=400, detail="Unsupported file format")
    
    # Parse the request JSON string if provided
    if request:
        import json
        try:
            request_data = json.loads(request)
            request = ScreenCaptureRequest(**request_data)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid JSON in request parameter")
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid request format: {str(e)}")
    else:
        request = ScreenCaptureRequest()
    
    # Generate unique ID for this capture
    capture_id = str(uuid.uuid4())
    
    try:
        # Process in background to avoid blocking
        result = await process_screen_capture(
            capture_id=capture_id,
            file=file,
            ocr_enabled=request.ocr_enabled,
            session_id=request.session_id
        )
        
        # Return the result from the service directly
        return ScreenCaptureResponse(
            capture_id=capture_id,
            status="processing",
            session_id=request.session_id,
            image_path=f"/storage/captures/{capture_id}{file.filename.split('.')[-1]}",  # Construct image path
            ocr_text="",    # Will be populated when OCR completes
            metadata={}     # Empty metadata object instead of null
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{capture_id}", response_model=ScreenCaptureResponse)
async def get_screen_capture(capture_id: str):
    """
    Get the status or result of a screen capture
    """
    try:
        result = get_capture_status(capture_id)
        if result is None:
            raise HTTPException(status_code=404, detail="Screen capture not found")
            
        # Convert the result to match ScreenCaptureResponse model
        response = ScreenCaptureResponse(
            capture_id=result["capture_id"],
            status=result["status"],
            session_id=result["session_id"],
            image_path=result.get("image_url", None),
            ocr_text=result.get("ocr_text", ""),
            metadata=result.get("metadata", {})
        )
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/session/{session_id}", response_model=List[ScreenCaptureResponse])
async def get_session_captures(session_id: str):
    """
    Get all screen captures for a session
    """
    try:
        return get_captures_by_session(session_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/periodic/start")
async def start_periodic_capture(request: ScreenCaptureRequest):
    """
    Start periodic screen capture
    """
    if not request.capture_interval or request.capture_interval < 1:
        raise HTTPException(status_code=400, detail="Invalid capture interval")
    
    try:
        result = start_periodic_capture_service(
            session_id=request.session_id,
            capture_interval=request.capture_interval,
            ocr_enabled=request.ocr_enabled
        )
        return {"status": "started", "session_id": request.session_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/periodic/stop")
async def stop_periodic_capture(session_id: str):
    """
    Stop periodic screen capture
    """
    try:
        stop_periodic_capture_service(session_id)
        return {"status": "stopped", "session_id": session_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))