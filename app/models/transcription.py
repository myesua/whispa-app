from sqlalchemy import Column, Integer, String, Float, Text, JSON, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
from datetime import datetime

from app.models.database import Base

class Transcription(Base):
    __tablename__ = "transcriptions"
    
    id = Column(Integer, primary_key=True, index=True)
    transcription_id = Column(String, unique=True, index=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String, index=True, nullable=True)
    status = Column(String, default="processing")  # processing, completed, error
    text = Column(Text, nullable=True)
    segments = Column(JSON, nullable=True)
    error = Column(Text, nullable=True)
    language = Column(String, default="en")
    model = Column(String, default="whisper")
    audio_file_path = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)
    
    def to_dict(self):
        return {
            "transcription_id": self.transcription_id,
            "session_id": self.session_id,
            "status": self.status,
            "text": self.text,
            "segments": self.segments,
            "error": self.error,
            "language": self.language,
            "model": self.model,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None
        }

class TranscriptionSegment(Base):
    __tablename__ = "transcription_segments"
    
    id = Column(Integer, primary_key=True, index=True)
    transcription_id = Column(String, ForeignKey("transcriptions.transcription_id"), index=True)
    start_time = Column(Float)
    end_time = Column(Float)
    text = Column(Text)
    confidence = Column(Float, nullable=True)
    
    transcription = relationship("Transcription", backref="segments_rel")