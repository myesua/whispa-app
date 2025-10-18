from sqlalchemy import Column, String, Text, DateTime, JSON, Boolean
from sqlalchemy.sql import func
from datetime import datetime

from app.models.database import Base


class Integration(Base):
    """Model for storing integration configurations"""
    __tablename__ = "integrations"

    id = Column(String(36), primary_key=True)
    type = Column(String(50), nullable=False, index=True)  # linear, notion
    api_key = Column(String(255), nullable=False)
    workspace_id = Column(String(255), nullable=True)
    project_id = Column(String(255), nullable=True)
    additional_config = Column(JSON, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"<Integration(id='{self.id}', type='{self.type}')>"
    
    def to_dict(self, include_sensitive=False):
        """Convert model to dictionary for API responses"""
        result = {
            "integration_id": self.id,
            "type": self.type,
            "workspace_id": self.workspace_id,
            "project_id": self.project_id,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }
        
        # Only include sensitive data if explicitly requested
        if include_sensitive:
            result["api_key"] = self.api_key
            result["additional_config"] = self.additional_config
            
        return result


class Ticket(Base):
    """Model for storing tickets created in external systems"""
    __tablename__ = "tickets"

    id = Column(String(36), primary_key=True)
    integration_id = Column(String(36), nullable=False, index=True)
    integration_type = Column(String(50), nullable=False)  # linear, notion
    external_id = Column(String(255), nullable=False)  # ID in external system
    summary_id = Column(String(36), nullable=True, index=True)  # Reference to summary that created this ticket
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    url = Column(String(512), nullable=True)  # URL to the ticket in external system
    status = Column(String(50), nullable=True)  # open, closed, etc.
    priority = Column(String(50), nullable=True)  # high, medium, low
    assignee = Column(String(255), nullable=True)
    metadata = Column(JSON, nullable=True)  # Additional metadata
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"<Ticket(id='{self.id}', external_id='{self.external_id}', integration_type='{self.integration_type}')>"
    
    def to_dict(self):
        """Convert model to dictionary for API responses"""
        return {
            "ticket_id": self.id,
            "integration_id": self.integration_id,
            "integration_type": self.integration_type,
            "external_id": self.external_id,
            "summary_id": self.summary_id,
            "title": self.title,
            "description": self.description,
            "url": self.url,
            "status": self.status,
            "priority": self.priority,
            "assignee": self.assignee,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }