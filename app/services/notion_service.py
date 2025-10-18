import uuid
import logging
import requests
from typing import Optional, Dict, Any, List
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.database import get_db
from app.models.integration import Integration, Ticket

# Configure logging
logger = logging.getLogger(__name__)

# Notion API endpoint
NOTION_API_URL = "https://api.notion.com/v1"

class NotionService:
    """Service for interacting with Notion API"""
    
    @staticmethod
    def get_integration(db: Session = None) -> Optional[Integration]:
        """
        Get Notion integration configuration
        
        Args:
            db: Database session
            
        Returns:
            Integration object if found, None otherwise
        """
        close_db = False
        if db is None:
            db = next(get_db())
            close_db = True
            
        try:
            integration = db.query(Integration).filter(
                Integration.type == "notion",
                Integration.is_active == True
            ).first()
            
            return integration
        except Exception as e:
            logger.error(f"Error retrieving Notion integration: {str(e)}")
            raise
        finally:
            if close_db:
                db.close()
    
    @staticmethod
    def save_integration(
        api_key: str,
        workspace_id: Optional[str] = None,
        project_id: Optional[str] = None,
        additional_config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Save Notion integration configuration
        
        Args:
            api_key: Notion API key (integration token)
            workspace_id: Optional workspace ID
            project_id: Optional database/page ID for default location
            additional_config: Optional additional configuration
            
        Returns:
            Dictionary with integration details
        """
        db = next(get_db())
        
        try:
            # Check if integration exists
            integration = db.query(Integration).filter(
                Integration.type == "notion"
            ).first()
            
            if integration:
                # Update existing integration
                integration.api_key = api_key
                integration.workspace_id = workspace_id
                integration.project_id = project_id
                integration.additional_config = additional_config
                integration.is_active = True
                integration.updated_at = datetime.utcnow()
            else:
                # Create new integration
                integration = Integration(
                    id=str(uuid.uuid4()),
                    type="notion",
                    api_key=api_key,
                    workspace_id=workspace_id,
                    project_id=project_id,
                    additional_config=additional_config,
                    is_active=True
                )
                db.add(integration)
            
            db.commit()
            
            # Verify API key by making a test request
            is_valid = NotionService._verify_api_key(api_key)
            
            if not is_valid:
                integration.is_active = False
                db.commit()
                raise ValueError("Invalid Notion API key")
            
            return integration.to_dict()
        
        except Exception as e:
            logger.error(f"Error saving Notion integration: {str(e)}")
            db.rollback()
            raise
        finally:
            db.close()
    
    @staticmethod
    def _verify_api_key(api_key: str) -> bool:
        """
        Verify Notion API key by making a test request
        
        Args:
            api_key: Notion API key
            
        Returns:
            True if API key is valid, False otherwise
        """
        try:
            # Simple query to verify API key - list users
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Notion-Version": "2022-06-28",
                "Content-Type": "application/json"
            }
            
            response = requests.get(
                f"{NOTION_API_URL}/users",
                headers=headers
            )
            
            if response.status_code == 200:
                return True
            
            return False
        
        except Exception as e:
            logger.error(f"Error verifying Notion API key: {str(e)}")
            return False
    
    @staticmethod
    def create_page(
        summary_id: str,
        title: str,
        content: str,
        parent_id: Optional[str] = None,
        tags: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Create a page in Notion
        
        Args:
            summary_id: ID of the summary to link to the page
            title: Page title
            content: Page content in markdown format
            parent_id: Optional parent page/database ID
            tags: Optional list of tags
            
        Returns:
            Dictionary with page details
        """
        db = next(get_db())
        
        try:
            # Get Notion integration
            integration = NotionService.get_integration(db)
            
            if not integration:
                raise ValueError("Notion integration not configured")
            
            # Use project_id as default parent if not provided
            parent_id = parent_id or integration.project_id
            
            if not parent_id:
                raise ValueError("Parent page/database ID is required")
            
            # Create page in Notion
            page_data = NotionService._create_notion_page(
                api_key=integration.api_key,
                title=title,
                content=content,
                parent_id=parent_id,
                tags=tags
            )
            
            # Create ticket record in database (reusing Ticket model for Notion pages)
            ticket = Ticket(
                id=str(uuid.uuid4()),
                integration_id=integration.id,
                integration_type="notion",
                external_id=page_data["id"],
                summary_id=summary_id,
                title=title,
                description=content[:500] if content else None,  # Store preview of content
                url=page_data["url"],
                status="created",
                metadata={
                    "notion_id": page_data["id"],
                    "parent_id": parent_id,
                    "tags": tags
                }
            )
            
            db.add(ticket)
            db.commit()
            
            return ticket.to_dict()
        
        except Exception as e:
            logger.error(f"Error creating Notion page: {str(e)}")
            db.rollback()
            raise
        finally:
            db.close()
    
    @staticmethod
    def _create_notion_page(
        api_key: str,
        title: str,
        content: str,
        parent_id: str,
        tags: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Create a page in Notion via API
        
        Args:
            api_key: Notion API key
            title: Page title
            content: Page content in markdown format
            parent_id: Parent page/database ID
            tags: Optional list of tags
            
        Returns:
            Dictionary with page details from Notion API
        """
        try:
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Notion-Version": "2022-06-28",
                "Content-Type": "application/json"
            }
            
            # Check if parent_id is a database or page
            is_database = NotionService._is_database(api_key, parent_id)
            
            if is_database:
                # Create page in database
                page_data = {
                    "parent": {"database_id": parent_id},
                    "properties": {
                        "Name": {
                            "title": [
                                {
                                    "text": {
                                        "content": title
                                    }
                                }
                            ]
                        }
                    },
                    "children": NotionService._convert_markdown_to_blocks(content)
                }
                
                # Add tags if database has a multi-select property for tags
                if tags:
                    page_data["properties"]["Tags"] = {
                        "multi_select": [{"name": tag} for tag in tags]
                    }
            else:
                # Create subpage under a page
                page_data = {
                    "parent": {"page_id": parent_id},
                    "properties": {
                        "title": [
                            {
                                "text": {
                                    "content": title
                                }
                            }
                        ]
                    },
                    "children": NotionService._convert_markdown_to_blocks(content)
                }
            
            response = requests.post(
                f"{NOTION_API_URL}/pages",
                json=page_data,
                headers=headers
            )
            
            if response.status_code != 200:
                raise ValueError(f"Notion API error: {response.text}")
            
            result = response.json()
            
            return {
                "id": result["id"],
                "url": result["url"]
            }
        
        except Exception as e:
            logger.error(f"Error creating Notion page: {str(e)}")
            raise
    
    @staticmethod
    def _is_database(api_key: str, id: str) -> bool:
        """
        Check if the given ID is a database or page
        
        Args:
            api_key: Notion API key
            id: ID to check
            
        Returns:
            True if ID is a database, False if it's a page
        """
        try:
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Notion-Version": "2022-06-28"
            }
            
            # Try to retrieve as database
            response = requests.get(
                f"{NOTION_API_URL}/databases/{id}",
                headers=headers
            )
            
            return response.status_code == 200
        
        except Exception:
            return False
    
    @staticmethod
    def _convert_markdown_to_blocks(markdown: str) -> List[Dict[str, Any]]:
        """
        Convert markdown content to Notion blocks
        
        Args:
            markdown: Markdown content
            
        Returns:
            List of Notion blocks
        """
        # This is a simplified implementation
        # A full implementation would parse markdown and convert to appropriate block types
        
        blocks = []
        paragraphs = markdown.split("\n\n")
        
        for paragraph in paragraphs:
            if paragraph.strip():
                # Check if paragraph is a heading
                if paragraph.startswith("# "):
                    blocks.append({
                        "object": "block",
                        "type": "heading_1",
                        "heading_1": {
                            "rich_text": [{"type": "text", "text": {"content": paragraph[2:]}}]
                        }
                    })
                elif paragraph.startswith("## "):
                    blocks.append({
                        "object": "block",
                        "type": "heading_2",
                        "heading_2": {
                            "rich_text": [{"type": "text", "text": {"content": paragraph[3:]}}]
                        }
                    })
                elif paragraph.startswith("### "):
                    blocks.append({
                        "object": "block",
                        "type": "heading_3",
                        "heading_3": {
                            "rich_text": [{"type": "text", "text": {"content": paragraph[4:]}}]
                        }
                    })
                else:
                    blocks.append({
                        "object": "block",
                        "type": "paragraph",
                        "paragraph": {
                            "rich_text": [{"type": "text", "text": {"content": paragraph}}]
                        }
                    })
        
        return blocks
    
    @staticmethod
    def get_page_status(page_id: str) -> Dict[str, Any]:
        """
        Get the status of a page in Notion
        
        Args:
            page_id: ID of the page in our database
            
        Returns:
            Dictionary with page details
        """
        db = next(get_db())
        
        try:
            # Get page from database
            page = db.query(Ticket).filter(Ticket.id == page_id).first()
            
            if not page:
                raise ValueError(f"Page not found: {page_id}")
            
            # Get Notion integration
            integration = NotionService.get_integration(db)
            
            if not integration:
                raise ValueError("Notion integration not configured")
            
            # Check if page exists in Notion
            page_exists = NotionService._check_notion_page(
                api_key=integration.api_key,
                page_id=page.external_id
            )
            
            # Update page status in database
            page.status = "active" if page_exists else "deleted"
            page.updated_at = datetime.utcnow()
            
            db.commit()
            
            return page.to_dict()
        
        except Exception as e:
            logger.error(f"Error getting Notion page status: {str(e)}")
            raise
        finally:
            db.close()
    
    @staticmethod
    def _check_notion_page(api_key: str, page_id: str) -> bool:
        """
        Check if a page exists in Notion
        
        Args:
            api_key: Notion API key
            page_id: Page ID in Notion
            
        Returns:
            True if page exists, False otherwise
        """
        try:
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Notion-Version": "2022-06-28"
            }
            
            response = requests.get(
                f"{NOTION_API_URL}/pages/{page_id}",
                headers=headers
            )
            
            return response.status_code == 200
        
        except Exception as e:
            logger.error(f"Error checking Notion page: {str(e)}")
            return False


# Functions to be called from API endpoints
def save_integration(
    api_key: str,
    workspace_id: Optional[str] = None,
    project_id: Optional[str] = None,
    additional_config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Save Notion integration configuration
    
    Args:
        api_key: Notion API key
        workspace_id: Optional workspace ID
        project_id: Optional database/page ID for default location
        additional_config: Optional additional configuration
        
    Returns:
        Dictionary with integration details
    """
    return NotionService.save_integration(
        api_key=api_key,
        workspace_id=workspace_id,
        project_id=project_id,
        additional_config=additional_config
    )


def get_integration() -> Optional[Dict[str, Any]]:
    """
    Get Notion integration configuration
    
    Returns:
        Dictionary with integration details if found, None otherwise
    """
    integration = NotionService.get_integration()
    return integration.to_dict() if integration else None


def create_page(
    summary_id: str,
    title: str,
    content: str,
    parent_id: Optional[str] = None,
    tags: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Create a page in Notion
    
    Args:
        summary_id: ID of the summary to link to the page
        title: Page title
        content: Page content in markdown format
        parent_id: Optional parent page/database ID
        tags: Optional list of tags
        
    Returns:
        Dictionary with page details
    """
    return NotionService.create_page(
        summary_id=summary_id,
        title=title,
        content=content,
        parent_id=parent_id,
        tags=tags
    )


def get_page_status(page_id: str) -> Dict[str, Any]:
    """
    Get the status of a page in Notion
    
    Args:
        page_id: ID of the page in our database
        
    Returns:
        Dictionary with page details
    """
    return NotionService.get_page_status(page_id)