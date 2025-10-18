import os
import json
import uuid
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List, Union
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.database import get_db
from app.models.storage import StorageItem

# Configure logging
logger = logging.getLogger(__name__)

# Configure storage paths
STORAGE_DIR = Path("storage/notes")
STORAGE_DIR.mkdir(parents=True, exist_ok=True)

class StorageService:
    """Service for managing local file storage"""
    
    @staticmethod
    def save_content(
        content: Dict[str, Any],
        format: str = "markdown",
        filename: Optional[str] = None,
        session_id: Optional[str] = None,
        content_type: Optional[str] = "notes"
    ) -> Dict[str, Any]:
        """
        Save content to local storage in specified format
        
        Args:
            content: Dictionary containing the content to save
            format: Format to save in (markdown or json)
            filename: Optional filename (without extension)
            session_id: Optional session identifier
            content_type: Type of content (notes, summary, etc.)
            
        Returns:
            Dictionary with storage details
        """
        db = next(get_db())
        
        try:
            # Generate storage ID
            storage_id = str(uuid.uuid4())
            
            # Generate filename if not provided
            if not filename:
                filename = f"whispa_{content_type}_{storage_id[:8]}"
            
            # Add appropriate extension
            if format == "markdown":
                file_extension = ".md"
                formatted_content = StorageService._format_as_markdown(content)
            elif format == "json":
                file_extension = ".json"
                formatted_content = json.dumps(content, indent=2)
            else:
                raise ValueError(f"Unsupported format: {format}")
            
            # Ensure filename has correct extension
            if not filename.endswith(file_extension):
                filename = f"{filename}{file_extension}"
            
            # Create file path
            file_path = STORAGE_DIR / filename
            
            # Write content to file
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(formatted_content)
            
            # Generate preview (first 200 chars)
            preview = formatted_content[:200] + "..." if len(formatted_content) > 200 else formatted_content
            
            # Create database record
            storage_item = StorageItem(
                id=storage_id,
                filename=filename,
                file_path=str(file_path),
                format=format,
                content_type=content_type,
                content_preview=preview,
                session_id=session_id,
                metadata={"size": len(formatted_content)}
            )
            
            db.add(storage_item)
            db.commit()
            
            return storage_item.to_dict()
        
        except Exception as e:
            logger.error(f"Error saving content: {str(e)}")
            db.rollback()
            raise
        finally:
            db.close()
    
    @staticmethod
    def _format_as_markdown(content: Dict[str, Any]) -> str:
        """
        Format content dictionary as markdown
        
        Args:
            content: Dictionary containing the content
            
        Returns:
            Formatted markdown string
        """
        md = []
        
        # Add title if present
        if "title" in content:
            md.append(f"# {content['title']}\n")
        
        # Add timestamp
        md.append(f"*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n")
        
        # Add summary if present
        if "summary" in content:
            md.append(f"## Summary\n\n{content['summary']}\n")
        
        # Add observations if present
        if "observations" in content and isinstance(content["observations"], list):
            md.append("## Observations\n")
            
            for obs in content["observations"]:
                if isinstance(obs, dict):
                    obs_type = obs.get("type", "note")
                    desc = obs.get("description", "")
                    severity = obs.get("severity", "")
                    
                    md.append(f"### {obs_type.upper()}{' - ' + severity.upper() if severity else ''}\n")
                    md.append(f"{desc}\n")
                else:
                    md.append(f"- {obs}\n")
        
        # Add any other sections
        for key, value in content.items():
            if key not in ["title", "summary", "observations"]:
                md.append(f"## {key.capitalize()}\n")
                
                if isinstance(value, list):
                    for item in value:
                        if isinstance(item, dict):
                            for k, v in item.items():
                                md.append(f"- **{k}**: {v}\n")
                        else:
                            md.append(f"- {item}\n")
                elif isinstance(value, dict):
                    for k, v in value.items():
                        md.append(f"- **{k}**: {v}\n")
                else:
                    md.append(f"{value}\n")
        
        return "\n".join(md)
    
    @staticmethod
    def get_content(storage_id: str) -> Dict[str, Any]:
        """
        Retrieve saved content by ID
        
        Args:
            storage_id: ID of the storage item
            
        Returns:
            Dictionary with content and metadata
        """
        db = next(get_db())
        
        try:
            # Get storage item from database
            storage_item = db.query(StorageItem).filter(StorageItem.id == storage_id).first()
            
            if not storage_item:
                raise ValueError(f"Storage item not found: {storage_id}")
            
            # Read file content
            with open(storage_item.file_path, "r", encoding="utf-8") as f:
                file_content = f.read()
            
            # Parse content based on format
            if storage_item.format == "json":
                content = json.loads(file_content)
            else:
                # For markdown, return raw content
                content = {"raw_content": file_content}
            
            # Return with metadata
            result = storage_item.to_dict()
            result["content"] = content
            
            return result
        
        except Exception as e:
            logger.error(f"Error retrieving content: {str(e)}")
            raise
        finally:
            db.close()
    
    @staticmethod
    def list_content(session_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        List all saved content, optionally filtered by session_id
        
        Args:
            session_id: Optional session ID to filter by
            
        Returns:
            List of storage items
        """
        db = next(get_db())
        
        try:
            # Query storage items
            query = db.query(StorageItem)
            
            if session_id:
                query = query.filter(StorageItem.session_id == session_id)
            
            # Order by creation date, newest first
            query = query.order_by(StorageItem.created_at.desc())
            
            # Convert to dictionaries
            return [item.to_dict() for item in query.all()]
        
        except Exception as e:
            logger.error(f"Error listing content: {str(e)}")
            raise
        finally:
            db.close()
    
    @staticmethod
    def delete_content(storage_id: str) -> Dict[str, Any]:
        """
        Delete saved content by ID
        
        Args:
            storage_id: ID of the storage item
            
        Returns:
            Dictionary with status message
        """
        db = next(get_db())
        
        try:
            # Get storage item from database
            storage_item = db.query(StorageItem).filter(StorageItem.id == storage_id).first()
            
            if not storage_item:
                raise ValueError(f"Storage item not found: {storage_id}")
            
            # Delete file if it exists
            file_path = Path(storage_item.file_path)
            if file_path.exists():
                file_path.unlink()
            
            # Delete database record
            db.delete(storage_item)
            db.commit()
            
            return {
                "message": f"Content {storage_id} deleted successfully",
                "storage_id": storage_id
            }
        
        except Exception as e:
            logger.error(f"Error deleting content: {str(e)}")
            db.rollback()
            raise
        finally:
            db.close()


# Functions to be called from API endpoints
def save_content(
    content: Dict[str, Any],
    format: str = "markdown",
    filename: Optional[str] = None,
    session_id: Optional[str] = None,
    content_type: Optional[str] = "notes"
) -> Dict[str, Any]:
    """
    Save content to local storage in specified format
    
    Args:
        content: Dictionary containing the content to save
        format: Format to save in (markdown or json)
        filename: Optional filename (without extension)
        session_id: Optional session identifier
        content_type: Type of content (notes, summary, etc.)
        
    Returns:
        Dictionary with storage details
    """
    return StorageService.save_content(
        content=content,
        format=format,
        filename=filename,
        session_id=session_id,
        content_type=content_type
    )


def get_content(storage_id: str) -> Dict[str, Any]:
    """
    Retrieve saved content by ID
    
    Args:
        storage_id: ID of the storage item
        
    Returns:
        Dictionary with content and metadata
    """
    return StorageService.get_content(storage_id)


def list_content(session_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    List all saved content, optionally filtered by session_id
    
    Args:
        session_id: Optional session ID to filter by
        
    Returns:
        List of storage items
    """
    return StorageService.list_content(session_id)


def delete_content(storage_id: str) -> Dict[str, Any]:
    """
    Delete saved content by ID
    
    Args:
        storage_id: ID of the storage item
        
    Returns:
        Dictionary with status message
    """
    return StorageService.delete_content(storage_id)