from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
import uuid

from app.services.storage_service import (
    save_content as service_save_content,
    get_content as service_get_content,
    list_content as service_list_content,
    delete_content as service_delete_content
)

router = APIRouter()

class StorageRequest(BaseModel):
    content: Dict[str, Any]
    format: str = "markdown"  # Options: "markdown", "json"
    filename: Optional[str] = None
    session_id: Optional[str] = None
    content_type: Optional[str] = "notes"

class StorageResponse(BaseModel):
    storage_id: str
    filepath: str
    format: str
    filename: str
    content_type: Optional[str] = None
    content_preview: Optional[str] = None
    session_id: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

@router.post("/", response_model=StorageResponse)
async def save_content(request: StorageRequest):
    """
    Save content to local storage in specified format
    """
    try:
        result = service_save_content(
            content=request.content,
            format=request.format,
            filename=request.filename,
            session_id=request.session_id,
            content_type=request.content_type
        )
        
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Storage operation failed: {str(e)}")

@router.get("/list", response_model=List[StorageResponse])
async def list_saved_content(session_id: Optional[str] = None):
    """
    List all saved content, optionally filtered by session_id
    """
    try:
        return service_list_content(session_id=session_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing saved content: {str(e)}")

@router.get("/{storage_id}")
async def get_saved_content(storage_id: str):
    """
    Retrieve saved content by ID
    """
    try:
        return service_get_content(storage_id=storage_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving content: {str(e)}")

@router.delete("/{storage_id}")
async def delete_saved_content(storage_id: str):
    """
    Delete saved content by ID
    """
    try:
        return service_delete_content(storage_id=storage_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting content: {str(e)}")