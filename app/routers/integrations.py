from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
import uuid
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.services.linear_service import LinearService

router = APIRouter()

class IntegrationConfig(BaseModel):
    type: str  # "linear", "jira", "notion"
    api_key: str
    workspace_id: Optional[str] = None
    project_id: Optional[str] = None
    additional_config: Optional[Dict[str, Any]] = None

class TicketRequest(BaseModel):
    summary_id: str
    integration_type: str
    title: Optional[str] = None
    description: Optional[str] = None
    priority: Optional[str] = None
    labels: Optional[List[str]] = None
    assignee: Optional[str] = None
    additional_fields: Optional[Dict[str, Any]] = None

class TicketResponse(BaseModel):
    ticket_id: str
    external_id: str
    integration_type: str
    url: Optional[str] = None
    status: str
    metadata: Optional[Dict[str, Any]] = None

@router.post("/config", response_model=Dict[str, Any])
async def save_integration_config(config: IntegrationConfig, db: Session = Depends(get_db)):
    """
    Save integration configuration
    """
    try:
        if config.type == "linear":
            result = LinearService.save_integration(
                api_key=config.api_key,
                workspace_id=config.workspace_id,
                project_id=config.project_id,
                additional_config=config.additional_config,
                db=db
            )
            return result
        else:
            # Placeholder for other integration types
            return {
                "status": "success",
                "message": f"{config.type} integration configured successfully"
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/ticket", response_model=TicketResponse)
async def create_ticket(request: TicketRequest, db: Session = Depends(get_db)):
    """
    Create a ticket in the specified integration
    """
    try:
        if request.integration_type == "linear":
            # Use the Linear service to create a ticket
            result = LinearService.create_qa_ticket(
                summary_id=request.summary_id,
                title=request.title or "QA Issue",
                description=request.description or "",
                priority=request.priority,
                labels=request.labels,
                assignee=request.assignee,
                additional_fields=request.additional_fields,
                db=db
            )
            
            return TicketResponse(
                ticket_id=result["ticket_id"],
                external_id=result["external_id"],
                integration_type=result["integration_type"],
                url=result["url"],
                status=result["status"],
                metadata=result["metadata"]
            )
        else:
            # Fallback for other integration types not yet implemented
            ticket_id = str(uuid.uuid4())
            
            return TicketResponse(
                ticket_id=ticket_id,
                external_id=f"EXT-{ticket_id[:8]}",
                integration_type=request.integration_type,
                url=f"https://example.com/tickets/{ticket_id}",
                status="created"
            )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/ticket/{ticket_id}", response_model=TicketResponse)
async def get_ticket(ticket_id: str, db: Session = Depends(get_db)):
    """
    Get ticket status
    """
    try:
        # Delegate to LinearService to fetch the ticket
        result = LinearService.get_ticket(ticket_id=ticket_id, db=db)
        return TicketResponse(
            ticket_id=result["ticket_id"],
            external_id=result["external_id"],
            integration_type=result["integration_type"],
            url=result["url"],
            status=result["status"],
            metadata=result.get("metadata")
        )
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))