from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, List
import uuid

from app.services.transcription_service import transcribe_audio, get_transcription_status

router = APIRouter()

class TranscriptionRequest(BaseModel):
    session_id: Optional[str] = None
    language: Optional[str] = "en"
    model: str = "gemini"  # Options: "gemini", "web_speech"

class TranscriptionResponse(BaseModel):
    transcription_id: str
    status: str
    text: Optional[str] = None
    segments: Optional[List[dict]] = None
    session_id: Optional[str] = None

@router.post("/", response_model=TranscriptionResponse)
async def create_transcription(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    request: TranscriptionRequest = None
):
    """
    Create a new transcription from an audio file
    """
    if not file.filename.endswith(('.mp3', '.wav', '.m4a', '.ogg')):
        raise HTTPException(status_code=400, detail="Unsupported file format")
    
    if request is None:
        request = TranscriptionRequest()
    
    # Generate unique ID for this transcription
    transcription_id = str(uuid.uuid4())
    
    try:
        # Process in background to avoid blocking
        background_tasks.add_task(
            transcribe_audio,
            transcription_id=transcription_id,
            file=file,
            language=request.language,
            model=request.model,
            session_id=request.session_id
        )
        
        return TranscriptionResponse(
            transcription_id=transcription_id,
            status="processing",
            session_id=request.session_id
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{transcription_id}", response_model=TranscriptionResponse)
async def get_transcription(transcription_id: str):
    """
    Get the status or result of a transcription
    """
    try:
        result = get_transcription_status(transcription_id)
        if result is None:
            raise HTTPException(status_code=404, detail="Transcription not found")
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))