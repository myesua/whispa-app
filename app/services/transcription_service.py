import os
import tempfile
import asyncio
import json
from typing import Dict, Optional, List, Any
import logging
from fastapi import UploadFile, Depends
from sqlalchemy.orm import Session
from datetime import datetime
import uuid
import whisper
import numpy as np
import torch
from pathlib import Path

from app.models.database import get_db
from app.models.transcription import Transcription, TranscriptionSegment
from app.services.event_bus import EventType, publish, publish_async

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create storage directory for audio files
AUDIO_STORAGE_PATH = Path("./storage/audio")
AUDIO_STORAGE_PATH.mkdir(parents=True, exist_ok=True)

# Load Whisper model (cached for reuse)
_whisper_model = None

def get_whisper_model(model_size="base"):
    """
    Get or initialize the Whisper model
    """
    global _whisper_model
    if _whisper_model is None:
        logger.info(f"Loading Whisper model: {model_size}")
        _whisper_model = whisper.load_model(model_size)
    return _whisper_model

async def transcribe_audio(
    transcription_id: str,
    file: UploadFile,
    language: str = "en",
    model: str = "whisper",
    session_id: Optional[str] = None,
    db: Session = Depends(get_db)
) -> None:
    """
    Process audio file and generate transcription using specified model
    """
    # Create database record
    db_transcription = Transcription(
        transcription_id=transcription_id,
        session_id=session_id,
        status="processing",
        language=language,
        model=model
    )
    db.add(db_transcription)
    db.commit()
    
    # Publish transcription started event
    await publish_async(
        EventType.TRANSCRIPTION_STARTED,
        {
            "transcription_id": transcription_id,
            "session_id": session_id,
            "model": model,
            "language": language
        }
    )
    
    try:
        # Save uploaded file to permanent storage
        audio_filename = f"{transcription_id}{os.path.splitext(file.filename)[1]}"
        audio_path = AUDIO_STORAGE_PATH / audio_filename
        
        # Save the file
        content = await file.read()
        with open(audio_path, "wb") as f:
            f.write(content)
        
        # Update database with file path
        db_transcription.audio_file_path = str(audio_path)
        db.commit()
        
        logger.info(f"Processing audio file: {file.filename} (ID: {transcription_id})")
        
        if model == "whisper":
            await process_with_whisper(db_transcription, audio_path, language, db)
        elif model == "web_speech":
            # Web Speech API is browser-based, not available in backend
            db_transcription.status = "error"
            db_transcription.error = "Web Speech API not available in backend"
            await publish_async(
                EventType.TRANSCRIPTION_FAILED,
                {
                    "transcription_id": transcription_id,
                    "session_id": session_id,
                    "error": "Web Speech API not available in backend"
                }
            )
        else:
            db_transcription.status = "error"
            db_transcription.error = f"Unsupported transcription model: {model}"
            await publish_async(
                EventType.TRANSCRIPTION_FAILED,
                {
                    "transcription_id": transcription_id,
                    "session_id": session_id,
                    "error": f"Unsupported transcription model: {model}"
                }
            )
        
    except Exception as e:
        logger.error(f"Transcription error: {str(e)}")
        db_transcription.status = "error"
        db_transcription.error = str(e)
        
        # Publish transcription failed event
        await publish_async(
            EventType.TRANSCRIPTION_FAILED,
            {
                "transcription_id": transcription_id,
                "session_id": session_id,
                "error": str(e)
            }
        )
    
    finally:
        # Update completion time if not already set
        if db_transcription.completed_at is None:
            db_transcription.completed_at = datetime.now()
        
        # Commit final status
        db.commit()

async def process_with_whisper(
    db_transcription: Transcription, 
    file_path: Path, 
    language: str,
    db: Session
) -> None:
    """
    Process audio using Whisper model
    """
    try:
        # Get Whisper model
        model = get_whisper_model()
        
        # Run in a thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: model.transcribe(
                str(file_path),
                language=language if language != "auto" else None,
                verbose=False
            )
        )
        
        # Update transcription with results
        db_transcription.status = "completed"
        db_transcription.text = result["text"]
        db_transcription.segments = result["segments"]
        db_transcription.completed_at = datetime.now()
        
        # Store segments in separate table
        for segment in result["segments"]:
            db_segment = TranscriptionSegment(
                transcription_id=db_transcription.transcription_id,
                start_time=segment["start"],
                end_time=segment["end"],
                text=segment["text"],
                confidence=segment.get("confidence", None)
            )
            db.add(db_segment)
        
        # Commit changes
        db.commit()
        
        logger.info(f"Transcription completed for ID: {db_transcription.transcription_id}")
        
        # Publish transcription completed event
        await publish_async(
            EventType.TRANSCRIPTION_COMPLETED,
            {
                "transcription_id": db_transcription.transcription_id,
                "session_id": db_transcription.session_id,
                "text": result["text"],
                "segments_count": len(result["segments"])
            }
        )
        
    except Exception as e:
        logger.error(f"Whisper processing error: {str(e)}")
        db_transcription.status = "error"
        db_transcription.error = f"Whisper processing error: {str(e)}"
        db.commit()
        
        # Publish transcription failed event
        await publish_async(
            EventType.TRANSCRIPTION_FAILED,
            {
                "transcription_id": db_transcription.transcription_id,
                "session_id": db_transcription.session_id,
                "error": f"Whisper processing error: {str(e)}"
            }
        )

def get_transcription_status(transcription_id: str, db: Session = Depends(get_db)) -> Optional[Dict[str, Any]]:
    """
    Get the current status or result of a transcription
    """
    db_transcription = db.query(Transcription).filter(
        Transcription.transcription_id == transcription_id
    ).first()
    
    if not db_transcription:
        return None
    
    return db_transcription.to_dict()

def get_transcriptions_by_session(session_id: str, db: Session = Depends(get_db)) -> List[Dict[str, Any]]:
    """
    Get all transcriptions for a specific session
    """
    db_transcriptions = db.query(Transcription).filter(
        Transcription.session_id == session_id
    ).all()
    
    return [t.to_dict() for t in db_transcriptions]

def cleanup_old_transcriptions(max_age_days: int = 30, db: Session = Depends(get_db)) -> None:
    """
    Remove transcriptions older than the specified age
    """
    from datetime import timedelta
    
    cutoff_date = datetime.now() - timedelta(days=max_age_days)
    
    # Get transcriptions to delete
    old_transcriptions = db.query(Transcription).filter(
        Transcription.created_at < cutoff_date
    ).all()
    
    # Delete associated audio files
    for transcription in old_transcriptions:
        if transcription.audio_file_path and os.path.exists(transcription.audio_file_path):
            try:
                os.remove(transcription.audio_file_path)
            except Exception as e:
                logger.error(f"Error deleting audio file: {str(e)}")
    
    # Delete from database
    count = db.query(Transcription).filter(
        Transcription.created_at < cutoff_date
    ).delete()
    
    db.commit()
    
    logger.info(f"Cleaned up {count} old transcriptions")