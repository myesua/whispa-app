import os
import logging
import asyncio
from typing import List, Dict, Any, Optional
import json
from datetime import datetime
import google.generativeai as genai
from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.models.database import get_db
from app.models.summarization import Summary, SummaryType

# Configure logging
logger = logging.getLogger(__name__)

# Initialize Gemini API
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
else:
    logger.warning("GEMINI_API_KEY not found in environment variables")

# Define Gemini model configuration
GEMINI_MODEL = "gemini-pro-latest"

class GeminiService:
    """Service for interacting with Google's Gemini API for QA note generation"""
    
    @staticmethod
    async def generate_qa_notes(
        summary_id: str,
        transcription_id: str,
        screenshot_ids: Optional[List[str]] = None,
        format: str = "markdown",
        qa_type: str = "general",
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate QA notes from transcription and optional screenshots using Gemini
        
        Args:
            summary_id: Unique identifier for this summary
            transcription_id: ID of the transcription to summarize
            screenshot_ids: Optional list of screenshot IDs to include in analysis
            format: Output format (markdown or json)
            qa_type: Type of QA notes to generate (general, bug, ux, feature)
            session_id: Optional session identifier
            
        Returns:
            Dictionary containing the generated QA notes
        """
        logger.info(f"Generating QA notes for transcription {transcription_id}")
        
        # Get database session
        db = next(get_db())
        
        try:
            # Create summary record in pending state
            db_summary = Summary(
                id=summary_id,
                transcription_id=transcription_id,
                status="pending",
                summary_type=qa_type,
                format=format,
                session_id=session_id
            )
            db.add(db_summary)
            db.commit()
            
            # Get transcription text from database
            from app.models.transcription import Transcription
            transcription = db.query(Transcription).filter(Transcription.id == transcription_id).first()
            
            if not transcription:
                logger.error(f"Transcription {transcription_id} not found")
                db_summary.status = "failed"
                db_summary.error_message = f"Transcription {transcription_id} not found"
                db.commit()
                return {"error": f"Transcription {transcription_id} not found"}
            
            # Get screenshot OCR text if provided
            screenshot_texts = []
            if screenshot_ids:
                # This would retrieve OCR text from screenshots
                # For now, we'll use placeholder data
                screenshot_texts = [f"Screenshot {i+1} OCR text would be here" for i, _ in enumerate(screenshot_ids)]
            
            # Update summary status to processing
            db_summary.status = "processing"
            db.commit()
            
            # Process with Gemini in the background
            asyncio.create_task(GeminiService._process_with_gemini(
                db=db,
                summary_id=summary_id,
                transcription_text=transcription.text,
                screenshot_texts=screenshot_texts,
                format=format,
                qa_type=qa_type
            ))
            
            return {
                "summary_id": summary_id,
                "status": "processing",
                "session_id": session_id
            }
            
        except Exception as e:
            logger.error(f"Error generating QA notes: {str(e)}")
            db_summary.status = "failed"
            db_summary.error_message = str(e)
            db.commit()
            raise HTTPException(status_code=500, detail=f"Error generating QA notes: {str(e)}")
    
    @staticmethod
    async def _process_with_gemini(
        db: Session,
        summary_id: str,
        transcription_text: str,
        screenshot_texts: List[str],
        format: str,
        qa_type: str
    ) -> None:
        """
        Process the transcription and screenshots with Gemini API
        
        Args:
            db: Database session
            summary_id: ID of the summary to update
            transcription_text: Text of the transcription
            screenshot_texts: List of OCR text from screenshots
            format: Output format (markdown or json)
            qa_type: Type of QA notes to generate
        """
        try:
            # Get the summary from database
            summary = db.query(Summary).filter(Summary.id == summary_id).first()
            if not summary:
                logger.error(f"Summary {summary_id} not found")
                return
            
            # Check if Gemini API key is configured
            if not GEMINI_API_KEY:
                logger.error("GEMINI_API_KEY not found in environment variables")
                summary.status = "failed"
                summary.error_message = "GEMINI_API_KEY not configured"
                db.commit()
                return
            
            # Prepare prompt based on QA type
            prompt = GeminiService._create_prompt(
                transcription_text=transcription_text,
                screenshot_texts=screenshot_texts,
                qa_type=qa_type,
                format=format
            )
            
            # Call Gemini API
            model = genai.GenerativeModel(GEMINI_MODEL)
            response = await asyncio.to_thread(
                model.generate_content,
                prompt
            )
            
            # Process response
            if not response or not response.text:
                logger.error("Empty response from Gemini API")
                summary.status = "failed"
                summary.error_message = "Empty response from Gemini API"
                db.commit()
                return
            
            # Parse and format the response
            content = GeminiService._format_response(response.text, format)
            
            # Update summary in database
            summary.status = "completed"
            summary.content = content
            summary.completed_at = datetime.utcnow()
            db.commit()
            
            logger.info(f"Successfully generated QA notes for summary {summary_id}")
            
        except Exception as e:
            logger.error(f"Error in _process_with_gemini: {str(e)}")
            summary = db.query(Summary).filter(Summary.id == summary_id).first()
            if summary:
                summary.status = "failed"
                summary.error_message = str(e)
                db.commit()
    
    @staticmethod
    def _create_prompt(
        transcription_text: str,
        screenshot_texts: List[str],
        qa_type: str,
        format: str
    ) -> str:
        """
        Create a prompt for Gemini based on the QA type and format
        
        Args:
            transcription_text: Text of the transcription
            screenshot_texts: List of OCR text from screenshots
            qa_type: Type of QA notes to generate
            format: Output format
            
        Returns:
            Formatted prompt string
        """
        # Base prompt
        prompt = f"""
        You are Whispa, an AI QA assistant that helps generate insightful notes from user feedback sessions.
        
        Please analyze the following transcription and generate QA notes:
        
        TRANSCRIPTION:
        {transcription_text}
        """
        
        # Add screenshot text if available
        if screenshot_texts:
            prompt += "\n\nSCREENSHOT OCR TEXT:\n"
            for i, text in enumerate(screenshot_texts):
                prompt += f"Screenshot {i+1}: {text}\n"
        
        # Add specific instructions based on QA type
        if qa_type == "bug":
            prompt += """
            Focus on identifying bugs and technical issues mentioned in the feedback.
            For each bug, extract:
            1. A clear description of the issue
            2. Steps to reproduce (if mentioned)
            3. Impact or severity
            4. Any context about when it occurs
            """
        elif qa_type == "ux":
            prompt += """
            Focus on user experience issues and feedback mentioned in the transcription.
            For each UX issue, extract:
            1. A clear description of the usability problem
            2. User sentiment or frustration level
            3. Impact on user workflow
            4. Any suggestions for improvement mentioned
            """
        elif qa_type == "feature":
            prompt += """
            Focus on feature requests and enhancement suggestions mentioned in the feedback.
            For each feature request, extract:
            1. A clear description of the requested feature
            2. The user need or problem it would solve
            3. Priority or importance (if mentioned)
            4. Any specific implementation details suggested
            """
        else:  # general
            prompt += """
            Provide a comprehensive analysis of the feedback, including:
            1. Key issues identified (bugs, UX problems, etc.)
            2. Feature requests or enhancement suggestions
            3. User sentiment and pain points
            4. Prioritized recommendations based on user impact
            """
        
        # Add format instructions
        if format == "markdown":
            prompt += """
            Format your response as a well-structured Markdown document with:
            - A clear title summarizing the feedback session
            - Sections for different types of findings
            - Bullet points for individual issues
            - Code blocks for any technical details
            - A summary section with key takeaways
            """
        else:  # json
            prompt += """
            Format your response as a valid JSON object with the following structure:
            {
              "title": "Summary title",
              "observations": [
                {
                  "type": "bug|ux|feature",
                  "description": "Clear description",
                  "severity": "high|medium|low",
                  "details": "Additional context",
                  "recommendations": "Suggested actions"
                }
              ],
              "summary": "Overall summary text"
            }
            
            Ensure the JSON is valid and properly formatted.
            """
        
        return prompt
    
    @staticmethod
    def _format_response(response_text: str, format: str) -> Dict[str, Any]:
        """
        Format the Gemini response based on the requested format
        
        Args:
            response_text: Raw text response from Gemini
            format: Desired output format (markdown or json)
            
        Returns:
            Formatted response as a dictionary
        """
        if format == "json":
            # Try to extract JSON from the response
            try:
                # Find JSON content between triple backticks if present
                if "```json" in response_text:
                    json_str = response_text.split("```json")[1].split("```")[0].strip()
                elif "```" in response_text:
                    json_str = response_text.split("```")[1].strip()
                else:
                    json_str = response_text.strip()
                
                # Parse JSON
                content = json.loads(json_str)
                return content
            except json.JSONDecodeError:
                # If JSON parsing fails, create a structured JSON from the text
                return {
                    "title": "QA Notes (JSON parsing failed)",
                    "observations": [
                        {
                            "type": "error",
                            "description": "Failed to parse JSON response",
                            "severity": "high",
                            "details": "The AI generated an invalid JSON response",
                            "recommendations": "Review the raw response"
                        }
                    ],
                    "raw_response": response_text,
                    "summary": "Error occurred while parsing the response"
                }
        else:  # markdown
            # For markdown, just return the text as is
            return {
                "markdown_content": response_text,
                "format": "markdown"
            }
    
    @staticmethod
    def get_summary_status(summary_id: str) -> Dict[str, Any]:
        """
        Get the status of a summary
        
        Args:
            summary_id: ID of the summary to check
            
        Returns:
            Dictionary with summary status and content if available
        """
        db = next(get_db())
        
        try:
            summary = db.query(Summary).filter(Summary.id == summary_id).first()
            
            if not summary:
                return None
            
            result = {
                "summary_id": summary.id,
                "status": summary.status,
                "session_id": summary.session_id
            }
            
            if summary.status == "completed":
                result["content"] = summary.content
                result["completed_at"] = summary.completed_at.isoformat() if summary.completed_at else None
            elif summary.status == "failed":
                result["error"] = summary.error_message
            
            return result
        
        except Exception as e:
            logger.error(f"Error getting summary status: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error getting summary status: {str(e)}")
    
    @staticmethod
    def get_summaries_by_session(session_id: str) -> List[Dict[str, Any]]:
        """
        Get all summaries for a session
        
        Args:
            session_id: Session ID to filter by
            
        Returns:
            List of summaries for the session
        """
        db = next(get_db())
        
        try:
            summaries = db.query(Summary).filter(Summary.session_id == session_id).all()
            
            return [
                {
                    "summary_id": summary.id,
                    "status": summary.status,
                    "summary_type": summary.summary_type,
                    "format": summary.format,
                    "created_at": summary.created_at.isoformat(),
                    "completed_at": summary.completed_at.isoformat() if summary.completed_at else None
                }
                for summary in summaries
            ]
        
        except Exception as e:
            logger.error(f"Error getting summaries by session: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error getting summaries by session: {str(e)}")


# Function to be called from API endpoints
async def generate_qa_notes(
    summary_id: str,
    transcription_id: str,
    screenshot_ids: Optional[List[str]] = None,
    format: str = "markdown",
    qa_type: str = "general",
    session_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Generate QA notes from transcription and optional screenshots
    
    Args:
        summary_id: Unique identifier for this summary
        transcription_id: ID of the transcription to summarize
        screenshot_ids: Optional list of screenshot IDs to include in analysis
        format: Output format (markdown or json)
        qa_type: Type of QA notes to generate (general, bug, ux, feature)
        session_id: Optional session identifier
        
    Returns:
        Dictionary containing the generated QA notes
    """
    return await GeminiService.generate_qa_notes(
        summary_id=summary_id,
        transcription_id=transcription_id,
        screenshot_ids=screenshot_ids,
        format=format,
        qa_type=qa_type,
        session_id=session_id
    )


def get_summary_status(summary_id: str) -> Dict[str, Any]:
    """
    Get the status of a summary
    
    Args:
        summary_id: ID of the summary to check
        
    Returns:
        Dictionary with summary status and content if available
    """
    return GeminiService.get_summary_status(summary_id)


def get_summaries_by_session(session_id: str) -> List[Dict[str, Any]]:
    """
    Get all summaries for a session
    
    Args:
        session_id: Session ID to filter by
        
    Returns:
        List of summaries for the session
    """
    return GeminiService.get_summaries_by_session(session_id)