import uuid
import logging
import requests
from typing import Optional, Dict, Any, List
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.database import get_db
from app.models.integration import Integration, IntegrationTicket

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
    def create_qa_ticket(
        summary_id: str,
        title: str,
        description: str,
        priority: Optional[str] = "medium",
        labels: Optional[List[str]] = None,
        assignee: Optional[str] = None,
        additional_fields: Optional[Dict[str, Any]] = None,
        db: Session = None
    ) -> Dict[str, Any]:
        """
        Create a QA ticket in Linear from summarized notes
        
        Args:
            summary_id: ID of the summary to link
            title: Ticket title
            description: Ticket description in markdown format
            priority: Ticket priority (low, medium, high, urgent)
            labels: List of labels to apply
            assignee: User ID to assign the ticket to
            additional_fields: Additional fields to include
            db: Database session
            
        Returns:
            Dictionary with ticket details including Linear URL
        """
        close_db = False
        if db is None:
            db = next(get_db())
            close_db = True
            
        try:
            # Get Linear integration
            integration = LinearService.get_integration(db)
            if not integration:
                raise ValueError("Linear integration not configured")
            
            # Map priority to Linear priority values
            priority_map = {
                "low": "3",
                "medium": "2", 
                "high": "1",
                "urgent": "0"
            }
            linear_priority = priority_map.get(priority.lower(), "2")
            
            # Prepare GraphQL mutation
            mutation = """
            mutation CreateIssue($title: String!, $description: String, $teamId: String!, $priority: Int, $labelIds: [String!]) {
                issueCreate(input: {
                    title: $title,
                    description: $description,
                    teamId: $teamId,
                    priority: $priority,
                    labelIds: $labelIds
                }) {
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
            
            # Set variables for the mutation
            variables = {
                "title": title,
                "description": description,
                "teamId": integration.project_id or integration.workspace_id,
                "priority": int(linear_priority)
            }
            
            if labels and len(labels) > 0:
                # In a real implementation, we would need to fetch label IDs first
                # For now, we'll assume labelIds are provided directly
                variables["labelIds"] = labels
                
            # Make API request to Linear
            headers = {
                "Authorization": f"Bearer {integration.api_key}",
                "Content-Type": "application/json"
            }
            
            response = requests.post(
                LINEAR_API_URL,
                json={"query": mutation, "variables": variables},
                headers=headers
            )
            
            if response.status_code != 200:
                raise Exception(f"Linear API error: {response.text}")
                
            result = response.json()
            
            if "errors" in result:
                raise Exception(f"Linear GraphQL error: {result['errors']}")
                
            issue_data = result.get("data", {}).get("issueCreate", {}).get("issue", {})
            
            # Create ticket record in database
            ticket = Ticket(
                id=str(uuid.uuid4()),
                summary_id=summary_id,
                integration_type="linear",
                external_id=issue_data.get("identifier"),
                title=title,
                url=issue_data.get("url"),
                status=issue_data.get("state", {}).get("name", "created"),
                metadata={
                    "linear_id": issue_data.get("id"),
                    "created_at": datetime.utcnow().isoformat()
                }
            )
            
            db.add(ticket)
            db.commit()
            
            return {
                "ticket_id": ticket.id,
                "external_id": ticket.external_id,
                "integration_type": "linear",
                "url": ticket.url,
                "status": ticket.status,
                "metadata": ticket.metadata
            }
            
        except Exception as e:
            logger.error(f"Error creating Linear ticket: {str(e)}")
            if db and db.is_active:
                db.rollback()
            raise
        finally:
            if close_db and db:
                db.close()
            
    @staticmethod
    def _verify_api_key(api_key: str) -> bool:
        """
        Verify Linear API key by making a test request
        
        Args:
            api_key: Linear API key to verify
            
        Returns:
            True if API key is valid, False otherwise
        """
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
        
        try:
            response = requests.post(
                LINEAR_API_URL,
                json={"query": query},
                headers=headers
            )
            
            if response.status_code != 200:
                return False
                
            result = response.json()
            
            if "errors" in result:
                return False
                
            return "data" in result and "viewer" in result["data"]
        except Exception:
            return False
    
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
            ticket = IntegrationTicket(
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
            ticket = db.query(IntegrationTicket).filter(IntegrationTicket.id == ticket_id).first()
            
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
                "status": issue_data["state"]["name"],
                "priority": issue_data["priority"],
                "assignee": issue_data["assignee"]["name"] if issue_data["assignee"] else None,
                "updated_at": issue_data["updatedAt"]
            }
        except Exception as e:
            raise ValueError(f"Error fetching Linear ticket: {str(e)}")
    
    @staticmethod
    def create_qa_ticket(
        summary_id: str,
        title: str,
        description: str,
        priority: str = None,
        labels: list = None,
        assignee: str = None,
        additional_fields: dict = None,
        db: Session = None
    ):
        """
        Create a QA ticket in Linear from summarized notes
        
        Args:
            summary_id: ID of the summary to link to the ticket
            title: Title of the ticket
            description: Description/content of the ticket
            priority: Priority level (high, medium, low)
            labels: List of labels to apply
            assignee: Email of the assignee
            additional_fields: Any additional fields to include
            db: Database session
            
        Returns:
            Dictionary with ticket details
        """
        try:
            # Get active Linear integration
            integration = LinearService.get_integration(db)
            if not integration:
                raise ValueError("No active Linear integration found")
            
            api_key = integration.api_key
            team_id = integration.workspace_id  # In Linear, workspace_id is the team ID
            
            # Map priority to Linear priority values (1-4)
            priority_map = {
                "urgent": 1,
                "high": 2,
                "medium": 3,
                "low": 4,
                None: 3  # Default to medium
            }
            
            linear_priority = priority_map.get(priority.lower() if priority else None, 3)
            
            # Prepare the GraphQL mutation
            mutation = """
            mutation CreateIssue($title: String!, $description: String, $teamId: String!, $priority: Int, $labelIds: [String!], $assigneeId: String) {
                issueCreate(
                    input: {
                        title: $title,
                        description: $description,
                        teamId: $teamId,
                        priority: $priority,
                        labelIds: $labelIds,
                        assigneeId: $assigneeId
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
            
            # Prepare variables for the mutation
            variables = {
                "title": title,
                "description": description,
                "teamId": team_id,
                "priority": linear_priority
            }
            
            # Add labels if provided
            if labels and integration.additional_config and "label_ids" in integration.additional_config:
                label_map = integration.additional_config["label_ids"]
                label_ids = [label_map.get(label) for label in labels if label in label_map]
                if label_ids:
                    variables["labelIds"] = label_ids
            
            # Add assignee if provided
            if assignee and integration.additional_config and "team_members" in integration.additional_config:
                team_members = integration.additional_config["team_members"]
                if assignee in team_members:
                    variables["assigneeId"] = team_members[assignee]
            
            # Make the API request
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
            
            if not result["data"]["issueCreate"]["success"]:
                raise ValueError("Failed to create Linear issue")
            
            issue = result["data"]["issueCreate"]["issue"]
            
            # Create a record in the database
            from app.models.tickets import Ticket
            
            ticket = Ticket(
                id=str(uuid.uuid4()),
                summary_id=summary_id,
                integration_type="linear",
                external_id=issue["identifier"],
                title=title,
                url=issue["url"],
                status=issue["state"]["name"],
                metadata={
                    "linear_id": issue["id"],
                    "created_at": datetime.utcnow().isoformat()
                }
            )
            
            db.add(ticket)
            db.commit()
            
            # Return the ticket details
            return {
                "ticket_id": ticket.id,
                "external_id": ticket.external_id,
                "integration_type": "linear",
                "url": ticket.url,
                "status": ticket.status,
                "metadata": ticket.metadata
            }
            
        except Exception as e:
            if db:
                db.rollback()
            raise ValueError(f"Error creating Linear ticket: {str(e)}")
        
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