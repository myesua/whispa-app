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
from pathlib import Path
import google.generativeai as genai

from app.models.database import get_db
from app.models.transcription import Transcription, TranscriptionSegment
from app.services.event_bus import EventType, publish, publish_async

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create storage directory for audio files
AUDIO_STORAGE_PATH = Path("./storage/audio")
AUDIO_STORAGE_PATH.mkdir(parents=True, exist_ok=True)

# Initialize Gemini API
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
else:
    logger.warning("GEMINI_API_KEY not found in environment variables")

# Define Gemini model configuration
GEMINI_MODEL = "gemini-pro-latest"

async def transcribe_audio(
    transcription_id: str,
    file: UploadFile,
    language: str = "en",
    model: str = "gemini",
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
        
        if model == "gemini":
            await process_with_gemini(db_transcription, audio_path, language, db)
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
            # Unsupported model
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

async def process_with_gemini(
    db_transcription: Transcription, 
    file_path: Path, 
    language: str,
    db: Session
) -> None:
    """
    Process audio using Gemini model
    """
    try:
        # Check if Gemini API key is available
        if not GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY not found in environment variables")
        
        # Read audio file as binary
        with open(file_path, "rb") as f:
            audio_data = f.read()
        
        # Create Gemini model instance
        model = genai.GenerativeModel(GEMINI_MODEL)
        
        # Prepare prompt for audio transcription
        prompt = f"Please transcribe this audio file accurately. The language is {language}. Include all spoken words, maintain proper punctuation, and preserve the original meaning. Format the output as plain text without any additional commentary."
        
        # Process with Gemini in a non-blocking way
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: model.generate_content(
                [
                    prompt,
                    {"mime_type": "audio/mp3", "data": audio_data}
                ]
            )
        )
        
        # Extract transcription text
        transcription_text = response.text
        
        # Log successful transcription
        logger.info(f"Successfully transcribed audio file: {file_path.name}")
        
        # Create a simple segmentation (Gemini doesn't provide segments like Whisper)
        # We'll create segments based on punctuation and length
        segments = []
        sentences = []
        
        # Simple sentence splitting based on punctuation
        current_sentence = ""
        current_start = 0
        
        for i, char in enumerate(transcription_text):
            current_sentence += char
            if char in ['.', '!', '?', '\n'] and len(current_sentence.strip()) > 0:
                sentences.append({
                    "text": current_sentence.strip(),
                    "start": current_start,
                    "end": i / len(transcription_text) * 60  # Approximate time in seconds
                })
                current_sentence = ""
                current_start = i / len(transcription_text) * 60
        
        # Add any remaining text
        if current_sentence.strip():
            sentences.append({
                "text": current_sentence.strip(),
                "start": current_start,
                "end": len(transcription_text) / len(transcription_text) * 60
            })
        
        # Update transcription with results
        db_transcription.status = "completed"
        db_transcription.text = transcription_text
        db_transcription.segments = sentences
        db_transcription.completed_at = datetime.now()
        
        # Store segments in separate table
        for segment in sentences:
            db_segment = TranscriptionSegment(
                transcription_id=db_transcription.transcription_id,
                start_time=segment["start"],
                end_time=segment["end"],
                text=segment["text"],
                confidence=1.0  # Gemini doesn't provide confidence scores
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
                "text": transcription_text,
                "segments_count": len(sentences)
            }
        )
        
    except Exception as e:
        logger.error(f"Gemini processing error: {str(e)}")
        db_transcription.status = "error"
        db_transcription.error = f"Gemini processing error: {str(e)}"
        db.commit()
        
        # Publish transcription failed event
        await publish_async(
            EventType.TRANSCRIPTION_FAILED,
            {
                "transcription_id": db_transcription.transcription_id,
                "session_id": db_transcription.session_id,
                "error": f"Gemini processing error: {str(e)}"
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

def update_transcription(
    transcription_id: str, 
    text: str = None,
    segments: List[Dict[str, Any]] = None,
    db: Session = Depends(get_db)
) -> Optional[Dict[str, Any]]:
    """
    Update a transcription with edited text and segments
    
    Args:
        transcription_id: ID of the transcription to update
        text: New transcription text
        segments: New transcription segments
        db: Database session
        
    Returns:
        Updated transcription data or None if not found
    """
    db_transcription = db.query(Transcription).filter(
        Transcription.transcription_id == transcription_id
    ).first()
    
    if not db_transcription:
        return None
    
    # Only update if transcription is completed
    if db_transcription.status != "completed":
        raise ValueError("Cannot edit transcription that is not completed")
    
    # Update text if provided
    if text is not None:
        db_transcription.text = text
    
    # Update segments if provided
    if segments is not None:
        # Delete existing segments
        db.query(TranscriptionSegment).filter(
            TranscriptionSegment.transcription_id == transcription_id
        ).delete()
        
        # Add new segments
        for segment in segments:
            db_segment = TranscriptionSegment(
                transcription_id=transcription_id,
                start_time=segment.get("start", 0),
                end_time=segment.get("end", 0),
                text=segment.get("text", ""),
                confidence=segment.get("confidence", 1.0)
            )
            db.add(db_segment)
        
        # Update segments in transcription
        db_transcription.segments = segments
    
    # Update modified timestamp
    db_transcription.updated_at = datetime.now()
    
    # Commit changes
    db.commit()
    
    # Publish event for transcription update
    publish(
        EventType.TRANSCRIPTION_UPDATED,
        {
            "transcription_id": transcription_id,
            "session_id": db_transcription.session_id,
            "text": db_transcription.text,
            "segments_count": len(segments) if segments else len(db_transcription.segments or [])
        }
    )
    
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