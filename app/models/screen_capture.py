from sqlalchemy import Column, String, Text, DateTime, Boolean, Integer, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime

from app.models.database import Base


class ScreenCapture(Base):
    """Model for storing screen captures and OCR results"""
    __tablename__ = "screen_captures"

    id = Column(String(36), primary_key=True)
    filename = Column(String(255), nullable=False)
    file_path = Column(String(512), nullable=False)
    thumbnail_path = Column(String(512), nullable=True)
    status = Column(String(20), nullable=False, default="pending")  # pending, processing, completed, failed
    ocr_enabled = Column(Boolean, default=True)
    ocr_text = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    session_id = Column(String(36), nullable=True, index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    
    # For periodic captures
    is_periodic = Column(Boolean, default=False)
    capture_interval = Column(Integer, nullable=True)  # In seconds
    
    def __repr__(self):
        return f"<ScreenCapture(id='{self.id}', status='{self.status}', ocr_enabled={self.ocr_enabled})>"