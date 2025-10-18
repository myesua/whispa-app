from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
import uuid
import os
import json

router = APIRouter()

class StorageRequest(BaseModel):
    content: Dict[str, Any]
    format: str = "markdown"  # Options: "markdown", "json"
    filename: Optional[str] = None
    session_id: Optional[str] = None

class StorageResponse(BaseModel):
    storage_id: str
    filepath: str
    format: str
    session_id: Optional[str] = None

@router.post("/", response_model=StorageResponse)
async def save_content(request: StorageRequest):
    """
    Save content to local storage in specified format
    """
    storage_id = str(uuid.uuid4())
    
    try:
        # Determine filename
        filename = request.filename or f"whispa_notes_{storage_id[:8]}"
        
        # Add appropriate extension based on format
        if request.format == "markdown":
            filename = f"{filename}.md"
        elif request.format == "json":
            filename = f"{filename}.json"
        else:
            raise HTTPException(status_code=400, detail="Unsupported format")
        
        # This would call a service to save the content
        # For now, we'll return a placeholder
        filepath = f"/storage/notes/{filename}"
        
        return StorageResponse(
            storage_id=storage_id,
            filepath=filepath,
            format=request.format,
            session_id=request.session_id
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Storage operation failed: {str(e)}")

@router.get("/list", response_model=List[StorageResponse])
async def list_saved_content(session_id: Optional[str] = None):
    """
    List all saved content, optionally filtered by session_id
    """
    try:
        # This would call a service to list saved content
        # For now, we'll return placeholder data
        return [
            StorageResponse(
                storage_id=str(uuid.uuid4()),
                filepath="/storage/notes/sample_notes_1.md",
                format="markdown",
                session_id=session_id
            ),
            StorageResponse(
                storage_id=str(uuid.uuid4()),
                filepath="/storage/notes/sample_notes_2.json",
                format="json",
                session_id=session_id
            )
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing saved content: {str(e)}")

@router.get("/{storage_id}")
async def get_saved_content(storage_id: str):
    """
    Retrieve saved content by ID
    """
    try:
        # This would call a service to retrieve the content
        # For now, we'll return placeholder data
        return {
            "storage_id": storage_id,
            "content": {
                "title": "Sample QA Notes",
                "observations": [
                    {"type": "bug", "description": "Button not responding on click", "severity": "high"},
                    {"type": "ux", "description": "Navigation flow is confusing", "severity": "medium"}
                ],
                "summary": "Several issues were identified during testing..."
            },
            "format": "markdown",
            "filepath": f"/storage/notes/whispa_notes_{storage_id[:8]}.md"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving content: {str(e)}")

@router.delete("/{storage_id}")
async def delete_saved_content(storage_id: str):
    """
    Delete saved content by ID
    """
    try:
        # This would call a service to delete the content
        return {"message": f"Content {storage_id} deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting content: {str(e)}")