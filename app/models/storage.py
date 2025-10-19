from sqlalchemy import Column, String, Text, DateTime, JSON
from sqlalchemy.sql import func
from datetime import datetime

from app.models.database import Base


class StorageItem(Base):
    """Model for storing saved content items"""
    __tablename__ = "storage_items"

    id = Column(String(36), primary_key=True)
    filename = Column(String(255), nullable=False)
    file_path = Column(String(512), nullable=False)
    format = Column(String(20), nullable=False)  # markdown, json
    content_type = Column(String(50), nullable=True)  # notes, summary, etc.
    content_preview = Column(Text, nullable=True)  # First few lines for preview
    item_metadata = Column(JSON, nullable=True)  # Additional metadata
    session_id = Column(String(36), nullable=True, index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"<StorageItem(id='{self.id}', filename='{self.filename}', format='{self.format}')>"
    
    def to_dict(self):
        """Convert model to dictionary for API responses"""
        return {
            "storage_id": self.id,
            "filename": self.filename,
            "filepath": self.file_path,
            "format": self.format,
            "content_type": self.content_type,
            "content_preview": self.content_preview,
            "session_id": self.session_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "metadata": self.item_metadata
        }