from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
import uuid

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
async def save_integration_config(config: IntegrationConfig):
    """
    Save integration configuration
    """
    try:
        # This would need to be implemented in a service
        # For now, return a placeholder
        return {
            "status": "success",
            "message": f"{config.type} integration configured successfully"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/ticket", response_model=TicketResponse)
async def create_ticket(request: TicketRequest):
    """
    Create a ticket in the specified integration
    """
    try:
        # This would need to be implemented in a service
        # For now, return a placeholder
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
async def get_ticket(ticket_id: str):
    """
    Get ticket status
    """
    try:
        # This would need to be implemented in a service
        # For now, return a placeholder
        return TicketResponse(
            ticket_id=ticket_id,
            external_id=f"EXT-{ticket_id[:8]}",
            integration_type="linear",
            url=f"https://example.com/tickets/{ticket_id}",
            status="open"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))