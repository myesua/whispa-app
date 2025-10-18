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

class TicketResponse(BaseModel):
    ticket_id: str
    external_id: str
    integration_type: str
    url: str
    status: str

@router.post("/config", response_model=Dict[str, Any])
async def set_integration_config(config: IntegrationConfig):
    """
    Configure integration settings for external services
    """
    try:
        # This would store the configuration securely
        return {
            "message": f"{config.type} integration configured successfully",
            "status": "success"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to configure integration: {str(e)}")

@router.get("/config/{integration_type}")
async def get_integration_config(integration_type: str):
    """
    Get integration configuration for a specific service
    """
    try:
        # This would retrieve the stored configuration
        # Return minimal info without sensitive data
        return {
            "type": integration_type,
            "configured": True,
            "workspace_id": "sample-workspace-id",
            "project_id": "sample-project-id"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve configuration: {str(e)}")

@router.post("/linear/ticket", response_model=TicketResponse)
async def create_linear_ticket(request: TicketRequest):
    """
    Create a ticket in Linear from QA notes
    """
    if request.integration_type != "linear":
        raise HTTPException(status_code=400, detail="Invalid integration type for this endpoint")
    
    try:
        # This would call a service to create a Linear ticket
        ticket_id = str(uuid.uuid4())
        external_id = f"LIN-{uuid.uuid4().hex[:6].upper()}"
        
        return TicketResponse(
            ticket_id=ticket_id,
            external_id=external_id,
            integration_type="linear",
            url=f"https://linear.app/whispa/issue/{external_id}",
            status="created"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create Linear ticket: {str(e)}")

@router.post("/notion/page", response_model=Dict[str, Any])
async def create_notion_page(request: TicketRequest):
    """
    Create a page in Notion from QA notes
    """
    if request.integration_type != "notion":
        raise HTTPException(status_code=400, detail="Invalid integration type for this endpoint")
    
    try:
        # This would call a service to create a Notion page
        page_id = str(uuid.uuid4())
        
        return {
            "page_id": page_id,
            "url": f"https://notion.so/{page_id.replace('-', '')}",
            "status": "created"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create Notion page: {str(e)}")

@router.get("/status/{ticket_id}")
async def get_ticket_status(ticket_id: str):
    """
    Get the status of a ticket in an external system
    """
    try:
        # This would call a service to check the ticket status
        return {
            "ticket_id": ticket_id,
            "external_id": "LIN-123ABC",
            "status": "open",
            "assignee": "John Doe",
            "last_updated": "2025-10-18T14:30:00Z"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get ticket status: {str(e)}")