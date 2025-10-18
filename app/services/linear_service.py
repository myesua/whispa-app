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

# Linear API endpoint
LINEAR_API_URL = "https://api.linear.app/graphql"

class LinearService:
    """Service for interacting with Linear API"""
    
    @staticmethod
    def get_integration(db: Session = None) -> Optional[Integration]:
        """
        Get Linear integration configuration
        
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
                Integration.type == "linear",
                Integration.is_active == True
            ).first()
            
            return integration
        except Exception as e:
            logger.error(f"Error retrieving Linear integration: {str(e)}")
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
        Save Linear integration configuration
        
        Args:
            api_key: Linear API key
            workspace_id: Optional workspace ID
            project_id: Optional project ID
            additional_config: Optional additional configuration
            
        Returns:
            Dictionary with integration details
        """
        db = next(get_db())
        
        try:
            # Check if integration exists
            integration = db.query(Integration).filter(
                Integration.type == "linear"
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
                    type="linear",
                    api_key=api_key,
                    workspace_id=workspace_id,
                    project_id=project_id,
                    additional_config=additional_config,
                    is_active=True
                )
                db.add(integration)
            
            db.commit()
            
            # Verify API key by making a test request
            is_valid = LinearService._verify_api_key(api_key)
            
            if not is_valid:
                integration.is_active = False
                db.commit()
                raise ValueError("Invalid Linear API key")
            
            return integration.to_dict()
        
        except Exception as e:
            logger.error(f"Error saving Linear integration: {str(e)}")
            db.rollback()
            raise
        finally:
            db.close()
    
    @staticmethod
    def _verify_api_key(api_key: str) -> bool:
        """
        Verify Linear API key by making a test request
        
        Args:
            api_key: Linear API key
            
        Returns:
            True if API key is valid, False otherwise
        """
        try:
            # Simple query to verify API key
            query = """
            query {
                viewer {
                    id
                    name
                }
            }
            """
            
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            
            response = requests.post(
                LINEAR_API_URL,
                json={"query": query},
                headers=headers
            )
            
            if response.status_code == 200 and "data" in response.json():
                return True
            
            return False
        
        except Exception as e:
            logger.error(f"Error verifying Linear API key: {str(e)}")
            return False
    
    @staticmethod
    def create_ticket(
        summary_id: str,
        title: str,
        description: Optional[str] = None,
        priority: Optional[str] = None,
        labels: Optional[List[str]] = None,
        assignee: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a ticket in Linear
        
        Args:
            summary_id: ID of the summary to link to the ticket
            title: Ticket title
            description: Optional ticket description
            priority: Optional priority (high, medium, low)
            labels: Optional list of labels
            assignee: Optional assignee email or ID
            
        Returns:
            Dictionary with ticket details
        """
        db = next(get_db())
        
        try:
            # Get Linear integration
            integration = LinearService.get_integration(db)
            
            if not integration:
                raise ValueError("Linear integration not configured")
            
            # Map priority to Linear priority
            priority_map = {
                "high": 1,
                "medium": 2,
                "low": 3,
                None: None
            }
            
            linear_priority = priority_map.get(priority.lower() if priority else None)
            
            # Create ticket in Linear
            ticket_data = LinearService._create_linear_issue(
                api_key=integration.api_key,
                title=title,
                description=description,
                priority=linear_priority,
                labels=labels,
                assignee=assignee,
                team_id=integration.project_id
            )
            
            # Create ticket record in database
            ticket = Ticket(
                id=str(uuid.uuid4()),
                integration_id=integration.id,
                integration_type="linear",
                external_id=ticket_data["id"],
                summary_id=summary_id,
                title=title,
                description=description,
                url=ticket_data["url"],
                status=ticket_data["state"],
                priority=priority,
                assignee=assignee,
                metadata={
                    "linear_id": ticket_data["id"],
                    "team_id": integration.project_id,
                    "labels": labels
                }
            )
            
            db.add(ticket)
            db.commit()
            
            return ticket.to_dict()
        
        except Exception as e:
            logger.error(f"Error creating Linear ticket: {str(e)}")
            db.rollback()
            raise
        finally:
            db.close()
    
    @staticmethod
    def _create_linear_issue(
        api_key: str,
        title: str,
        description: Optional[str] = None,
        priority: Optional[int] = None,
        labels: Optional[List[str]] = None,
        assignee: Optional[str] = None,
        team_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create an issue in Linear via API
        
        Args:
            api_key: Linear API key
            title: Issue title
            description: Optional issue description
            priority: Optional priority (1=high, 2=medium, 3=low)
            labels: Optional list of labels
            assignee: Optional assignee email or ID
            team_id: Optional team ID
            
        Returns:
            Dictionary with issue details from Linear API
        """
        try:
            # Prepare mutation
            mutation = """
            mutation CreateIssue($title: String!, $description: String, $teamId: String, $priority: Int, $labelIds: [String!]) {
                issueCreate(
                    input: {
                        title: $title,
                        description: $description,
                        teamId: $teamId,
                        priority: $priority,
                        labelIds: $labelIds
                    }
                ) {
                    success
                    issue {
                        id
                        identifier
                        title
                        url
                        state {
                            name
                        }
                    }
                }
            }
            """
            
            # Prepare variables
            variables = {
                "title": title,
                "description": description,
                "priority": priority
            }
            
            if team_id:
                variables["teamId"] = team_id
            
            # TODO: Handle labels and assignee
            # This would require additional queries to get label IDs and user IDs
            
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            
            response = requests.post(
                LINEAR_API_URL,
                json={"query": mutation, "variables": variables},
                headers=headers
            )
            
            if response.status_code != 200:
                raise ValueError(f"Linear API error: {response.text}")
            
            result = response.json()
            
            if "errors" in result:
                raise ValueError(f"Linear API error: {result['errors']}")
            
            issue_data = result["data"]["issueCreate"]["issue"]
            
            return {
                "id": issue_data["identifier"],
                "title": issue_data["title"],
                "url": issue_data["url"],
                "state": issue_data["state"]["name"]
            }
        
        except Exception as e:
            logger.error(f"Error creating Linear issue: {str(e)}")
            raise
    
    @staticmethod
    def get_ticket_status(ticket_id: str) -> Dict[str, Any]:
        """
        Get the status of a ticket in Linear
        
        Args:
            ticket_id: ID of the ticket
            
        Returns:
            Dictionary with ticket details
        """
        db = next(get_db())
        
        try:
            # Get ticket from database
            ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
            
            if not ticket:
                raise ValueError(f"Ticket not found: {ticket_id}")
            
            # Get Linear integration
            integration = LinearService.get_integration(db)
            
            if not integration:
                raise ValueError("Linear integration not configured")
            
            # Get ticket status from Linear
            ticket_data = LinearService._get_linear_issue(
                api_key=integration.api_key,
                issue_id=ticket.external_id
            )
            
            # Update ticket in database
            ticket.status = ticket_data["state"]
            ticket.assignee = ticket_data.get("assignee")
            ticket.updated_at = datetime.utcnow()
            
            db.commit()
            
            return ticket.to_dict()
        
        except Exception as e:
            logger.error(f"Error getting Linear ticket status: {str(e)}")
            raise
        finally:
            db.close()
    
    @staticmethod
    def _get_linear_issue(api_key: str, issue_id: str) -> Dict[str, Any]:
        """
        Get issue details from Linear API
        
        Args:
            api_key: Linear API key
            issue_id: Issue identifier (e.g., ABC-123)
            
        Returns:
            Dictionary with issue details from Linear API
        """
        try:
            # Prepare query
            query = """
            query GetIssue($id: String!) {
                issue(id: $id) {
                    id
                    identifier
                    title
                    description
                    url
                    state {
                        name
                    }
                    assignee {
                        name
                        email
                    }
                    priority
                    updatedAt
                }
            }
            """
            
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            
            response = requests.post(
                LINEAR_API_URL,
                json={"query": query, "variables": {"id": issue_id}},
                headers=headers
            )
            
            if response.status_code != 200:
                raise ValueError(f"Linear API error: {response.text}")
            
            result = response.json()
            
            if "errors" in result:
                raise ValueError(f"Linear API error: {result['errors']}")
            
            issue_data = result["data"]["issue"]
            
            return {
                "id": issue_data["identifier"],
                "title": issue_data["title"],
                "description": issue_data["description"],
                "url": issue_data["url"],
                "state": issue_data["state"]["name"],
                "assignee": issue_data["assignee"]["name"] if issue_data["assignee"] else None,
                "priority": issue_data["priority"],
                "updated_at": issue_data["updatedAt"]
            }
        
        except Exception as e:
            logger.error(f"Error getting Linear issue: {str(e)}")
            raise


# Functions to be called from API endpoints
def save_integration(
    api_key: str,
    workspace_id: Optional[str] = None,
    project_id: Optional[str] = None,
    additional_config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Save Linear integration configuration
    
    Args:
        api_key: Linear API key
        workspace_id: Optional workspace ID
        project_id: Optional project ID
        additional_config: Optional additional configuration
        
    Returns:
        Dictionary with integration details
    """
    return LinearService.save_integration(
        api_key=api_key,
        workspace_id=workspace_id,
        project_id=project_id,
        additional_config=additional_config
    )


def get_integration() -> Optional[Dict[str, Any]]:
    """
    Get Linear integration configuration
    
    Returns:
        Dictionary with integration details if found, None otherwise
    """
    integration = LinearService.get_integration()
    return integration.to_dict() if integration else None


def create_ticket(
    summary_id: str,
    title: str,
    description: Optional[str] = None,
    priority: Optional[str] = None,
    labels: Optional[List[str]] = None,
    assignee: Optional[str] = None
) -> Dict[str, Any]:
    """
    Create a ticket in Linear
    
    Args:
        summary_id: ID of the summary to link to the ticket
        title: Ticket title
        description: Optional ticket description
        priority: Optional priority (high, medium, low)
        labels: Optional list of labels
        assignee: Optional assignee email or ID
        
    Returns:
        Dictionary with ticket details
    """
    return LinearService.create_ticket(
        summary_id=summary_id,
        title=title,
        description=description,
        priority=priority,
        labels=labels,
        assignee=assignee
    )


def get_ticket_status(ticket_id: str) -> Dict[str, Any]:
    """
    Get the status of a ticket in Linear
    
    Args:
        ticket_id: ID of the ticket
        
    Returns:
        Dictionary with ticket details
    """
    return LinearService.get_ticket_status(ticket_id)