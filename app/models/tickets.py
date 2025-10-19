import uuid
from datetime import datetime
from typing import Dict, Any, Optional

from sqlalchemy import Column, String, DateTime, Boolean, JSON, ForeignKey
from sqlalchemy.orm import relationship

from app.models.database import Base

class Ticket(Base):
    """
    Model for storing ticket information from integrations like Linear, Jira, etc.
    """
    __tablename__ = "tickets"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    summary_id = Column(String, ForeignKey("summaries.id"), nullable=True)
    integration_type = Column(String, nullable=False)  # linear, jira, notion
    external_id = Column(String, nullable=False)  # ID in the external system
    title = Column(String, nullable=False)
    url = Column(String, nullable=True)
    status = Column(String, nullable=True)
    metadata = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    summary = relationship("Summary", back_populates="tickets")
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert ticket to dictionary
        """
        return {
            "id": self.id,
            "summary_id": self.summary_id,
            "integration_type": self.integration_type,
            "external_id": self.external_id,
            "title": self.title,
            "url": self.url,
            "status": self.status,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }