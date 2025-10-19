import os
import logging
import asyncio
import uuid
import shutil
from typing import Optional, Dict, Any, List
from datetime import datetime
from pathlib import Path
from fastapi import UploadFile, HTTPException
import pytesseract
from PIL import Image
import numpy as np
import cv2
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.models.screen_capture import ScreenCapture

# Configure logging
logger = logging.getLogger(__name__)

# Configure paths
STORAGE_DIR = Path("storage/captures")
THUMBNAIL_DIR = Path("storage/thumbnails")

# Ensure directories exist
STORAGE_DIR.mkdir(parents=True, exist_ok=True)
THUMBNAIL_DIR.mkdir(parents=True, exist_ok=True)

# Configure OCR
TESSERACT_CMD = os.getenv("TESSERACT_CMD", "tesseract")
if os.path.exists(TESSERACT_CMD) or shutil.which(TESSERACT_CMD):
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD
else:
    logger.warning(f"Tesseract not found at {TESSERACT_CMD}. OCR functionality may be limited.")

# Dictionary to track active periodic capture sessions
active_sessions = {}


class ScreenCaptureService:
    """Service for processing screen captures and performing OCR"""
    
    @staticmethod
    async def process_screen_capture(
        capture_id: str,
        file: UploadFile,
        ocr_enabled: bool = True,
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Process a screen capture image with optional OCR
        
        Args:
            capture_id: Unique identifier for this capture
            file: Uploaded image file
            ocr_enabled: Whether to perform OCR on the image
            session_id: Optional session identifier
            
        Returns:
            Dictionary with capture details
        """
        logger.info(f"Processing screen capture {capture_id}")
        
        # Get database session
        db = next(get_db())
        
        try:
            # Generate filename with original extension
            filename = f"{capture_id}{os.path.splitext(file.filename)[1]}"
            file_path = STORAGE_DIR / filename
            thumbnail_path = THUMBNAIL_DIR / f"thumb_{filename}"
            
            # Create capture record in pending state
            db_capture = ScreenCapture(
                id=capture_id,
                filename=filename,
                file_path=str(file_path),
                thumbnail_path=str(thumbnail_path),
                status="pending",
                ocr_enabled=ocr_enabled,
                session_id=session_id
            )
            db.add(db_capture)
            db.commit()
            
            # Save the file
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            
            # Update status to processing
            db_capture.status = "processing"
            db.commit()
            
            # Process in background
            asyncio.create_task(ScreenCaptureService._process_image(
                db=db,
                capture_id=capture_id,
                file_path=file_path,
                thumbnail_path=thumbnail_path,
                ocr_enabled=ocr_enabled
            ))
            
            return {
                "capture_id": capture_id,
                "status": "processing",
                "session_id": session_id
            }
            
        except Exception as e:
            logger.error(f"Error processing screen capture: {str(e)}")
            db_capture = db.query(ScreenCapture).filter(ScreenCapture.id == capture_id).first()
            if db_capture:
                db_capture.status = "failed"
                db_capture.error_message = str(e)
                db.commit()
            raise HTTPException(status_code=500, detail=f"Screen capture processing failed: {str(e)}")
    
    @staticmethod
    async def _process_image(
        db: Session,
        capture_id: str,
        file_path: Path,
        thumbnail_path: Path,
        ocr_enabled: bool
    ) -> None:
        """
        Process the image file and perform OCR if enabled
        
        Args:
            db: Database session
            capture_id: ID of the capture to update
            file_path: Path to the image file
            thumbnail_path: Path to save the thumbnail
            ocr_enabled: Whether to perform OCR
        """
        try:
            # Get the capture from database
            capture = db.query(ScreenCapture).filter(ScreenCapture.id == capture_id).first()
            if not capture:
                logger.error(f"Capture {capture_id} not found")
                return
            
            # Generate thumbnail
            ScreenCaptureService._create_thumbnail(file_path, thumbnail_path)
            
            # Perform OCR if enabled
            ocr_text = None
            if ocr_enabled:
                ocr_text = await ScreenCaptureService._perform_ocr(file_path)
            
            # Update capture in database
            capture.status = "completed"
            capture.ocr_text = ocr_text
            capture.completed_at = datetime.utcnow()
            db.commit()
            
            logger.info(f"Successfully processed screen capture {capture_id}")
            
        except Exception as e:
            logger.error(f"Error in _process_image: {str(e)}")
            capture = db.query(ScreenCapture).filter(ScreenCapture.id == capture_id).first()
            if capture:
                capture.status = "failed"
                capture.error_message = str(e)
                db.commit()
    
    @staticmethod
    def _create_thumbnail(file_path: Path, thumbnail_path: Path, size=(200, 200)) -> None:
        """
        Create a thumbnail of the image
        
        Args:
            file_path: Path to the original image
            thumbnail_path: Path to save the thumbnail
            size: Thumbnail dimensions (width, height)
        """
        try:
            with Image.open(file_path) as img:
                img.thumbnail(size)
                img.save(thumbnail_path)
        except Exception as e:
            logger.error(f"Error creating thumbnail: {str(e)}")
            # Continue without thumbnail if it fails
    
    @staticmethod
    async def _perform_ocr(file_path: Path) -> str:
        """
        Perform OCR on the image with enhanced preprocessing
        
        Args:
            file_path: Path to the image file
            
        Returns:
            Extracted text from the image
        """
        try:
            # First enhance the image for better OCR results
            enhanced_image = await ScreenCaptureService._enhance_image_for_ocr(file_path)
            
            # Convert numpy array back to PIL Image for pytesseract
            pil_image = Image.fromarray(enhanced_image)
            
            # Use pytesseract with improved configuration
            ocr_config = '--oem 3 --psm 6'  # Use LSTM OCR Engine with page segmentation mode
            
            # Extract text with improved configuration
            text = await asyncio.to_thread(
                pytesseract.image_to_string,
                pil_image,
                config=ocr_config
            )
            
            # Post-process text to clean up results
            text = text.strip()
            
            return text
        except Exception as e:
            logger.error(f"OCR failed: {str(e)}")
            return f"OCR failed: {str(e)}"
    
    @staticmethod
    async def _enhance_image_for_ocr(file_path: Path) -> np.ndarray:
        """
        Enhance image for better OCR results
        
        Args:
            file_path: Path to the image file
            
        Returns:
            Enhanced image as numpy array
        """
        try:
            # Read image
            img = cv2.imread(str(file_path))
            
            # Convert to grayscale
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            
            # Apply thresholding
            _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            
            # Apply noise reduction
            denoised = cv2.fastNlMeansDenoising(thresh, None, 10, 7, 21)
            
            return denoised
        except Exception as e:
            logger.error(f"Image enhancement failed: {str(e)}")
            # Return original image if enhancement fails
            return cv2.imread(str(file_path))
    
    @staticmethod
    def get_capture_status(capture_id: str) -> Dict[str, Any]:
        """
        Get the status of a screen capture
        
        Args:
            capture_id: ID of the capture to check
            
        Returns:
            Dictionary with capture status and details
        """
        db = next(get_db())
        
        try:
            capture = db.query(ScreenCapture).filter(ScreenCapture.id == capture_id).first()
            
            if not capture:
                return None
            
            result = {
                "capture_id": capture.id,
                "status": capture.status,
                "session_id": capture.session_id,
                "created_at": capture.created_at.isoformat()
            }
            
            if capture.status == "completed":
                result["ocr_text"] = capture.ocr_text if capture.ocr_enabled else None
                result["image_url"] = f"/storage/captures/{capture.filename}"
                result["thumbnail_url"] = f"/storage/thumbnails/thumb_{capture.filename}"
                result["completed_at"] = capture.completed_at.isoformat() if capture.completed_at else None
            elif capture.status == "failed":
                result["error"] = capture.error_message
            
            return result
        
        except Exception as e:
            logger.error(f"Error getting capture status: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error getting capture status: {str(e)}")
    
    @staticmethod
    def get_captures_by_session(session_id: str) -> List[Dict[str, Any]]:
        """
        Get all captures for a session
        
        Args:
            session_id: Session ID to filter by
            
        Returns:
            List of captures for the session
        """
        db = next(get_db())
        
        try:
            captures = db.query(ScreenCapture).filter(ScreenCapture.session_id == session_id).all()
            
            return [
                {
                    "capture_id": capture.id,
                    "status": capture.status,
                    "ocr_enabled": capture.ocr_enabled,
                    "image_url": f"/storage/captures/{capture.filename}" if capture.status == "completed" else None,
                    "thumbnail_url": f"/storage/thumbnails/thumb_{capture.filename}" if capture.status == "completed" else None,
                    "created_at": capture.created_at.isoformat()
                }
                for capture in captures
            ]
        
        except Exception as e:
            logger.error(f"Error getting captures by session: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error getting captures by session: {str(e)}")
    
    @staticmethod
    async def start_periodic_capture(
        session_id: str,
        capture_interval: int,
        ocr_enabled: bool = True
    ) -> Dict[str, Any]:
        """
        Start periodic screen capture at specified intervals
        
        Args:
            session_id: Session identifier
            capture_interval: Interval in seconds between captures
            ocr_enabled: Whether to perform OCR on captured images
            
        Returns:
            Dictionary with session details
        """
        if session_id in active_sessions:
            # Stop existing session if it exists
            await ScreenCaptureService.stop_periodic_capture(session_id)
        
        # Create task for periodic capture
        task = asyncio.create_task(
            ScreenCaptureService._run_periodic_capture(
                session_id=session_id,
                capture_interval=capture_interval,
                ocr_enabled=ocr_enabled
            )
        )
        
        # Store task reference
        active_sessions[session_id] = {
            "task": task,
            "interval": capture_interval,
            "ocr_enabled": ocr_enabled,
            "started_at": datetime.utcnow()
        }
        
        return {
            "session_id": session_id,
            "status": "active",
            "capture_interval": capture_interval,
            "ocr_enabled": ocr_enabled
        }
    
    @staticmethod
    async def _run_periodic_capture(
        session_id: str,
        capture_interval: int,
        ocr_enabled: bool
    ) -> None:
        """
        Run periodic screen capture task
        
        Args:
            session_id: Session identifier
            capture_interval: Interval in seconds between captures
            ocr_enabled: Whether to perform OCR on captured images
        """
        db = next(get_db())
        
        try:
            while session_id in active_sessions:
                # This would capture the screen
                # For now, we'll create a placeholder image
                capture_id = str(uuid.uuid4())
                
                # Create capture record
                db_capture = ScreenCapture(
                    id=capture_id,
                    filename=f"{capture_id}.png",
                    file_path=str(STORAGE_DIR / f"{capture_id}.png"),
                    thumbnail_path=str(THUMBNAIL_DIR / f"thumb_{capture_id}.png"),
                    status="pending",
                    ocr_enabled=ocr_enabled,
                    session_id=session_id,
                    is_periodic=True,
                    capture_interval=capture_interval
                )
                db.add(db_capture)
                db.commit()
                
                # In a real implementation, this would capture the screen
                # For now, we'll just update the status
                db_capture.status = "completed"
                db_capture.ocr_text = "Periodic capture placeholder text"
                db_capture.completed_at = datetime.utcnow()
                db.commit()
                
                # Wait for next capture
                await asyncio.sleep(capture_interval)
        
        except asyncio.CancelledError:
            logger.info(f"Periodic capture for session {session_id} cancelled")
        except Exception as e:
            logger.error(f"Error in periodic capture: {str(e)}")
        finally:
            # Remove session if it still exists
            if session_id in active_sessions:
                del active_sessions[session_id]
    
    @staticmethod
    async def stop_periodic_capture(session_id: str) -> Dict[str, Any]:
        """
        Stop periodic screen capture for a session
        
        Args:
            session_id: Session identifier
            
        Returns:
            Dictionary with status message
        """
        if session_id in active_sessions:
            # Cancel the task
            active_sessions[session_id]["task"].cancel()
            
            # Remove from active sessions
            del active_sessions[session_id]
            
            return {
                "message": f"Periodic capture stopped for session {session_id}",
                "status": "stopped"
            }
        else:
            return {
                "message": f"No active periodic capture for session {session_id}",
                "status": "not_found"
            }


# Functions to be called from API endpoints
async def process_screen_capture(
    capture_id: str,
    file: UploadFile,
    ocr_enabled: bool = True,
    session_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Process a screen capture image with optional OCR
    
    Args:
        capture_id: Unique identifier for this capture
        file: Uploaded image file
        ocr_enabled: Whether to perform OCR on the image
        session_id: Optional session identifier
        
    Returns:
        Dictionary with capture details
    """
    return await ScreenCaptureService.process_screen_capture(
        capture_id=capture_id,
        file=file,
        ocr_enabled=ocr_enabled,
        session_id=session_id
    )


def get_capture_status(capture_id: str) -> Dict[str, Any]:
    """
    Get the status of a screen capture
    
    Args:
        capture_id: ID of the capture to check
        
    Returns:
        Dictionary with capture status and details
    """
    return ScreenCaptureService.get_capture_status(capture_id)


def get_captures_by_session(session_id: str) -> List[Dict[str, Any]]:
    """
    Get all captures for a session
    
    Args:
        session_id: Session ID to filter by
        
    Returns:
        List of captures for the session
    """
    return ScreenCaptureService.get_captures_by_session(session_id)


async def start_periodic_capture(
    session_id: str,
    capture_interval: int,
    ocr_enabled: bool = True
) -> Dict[str, Any]:
    """
    Start periodic screen capture at specified intervals
    
    Args:
        session_id: Session identifier
        capture_interval: Interval in seconds between captures
        ocr_enabled: Whether to perform OCR on captured images
        
    Returns:
        Dictionary with session details
    """
    return await ScreenCaptureService.start_periodic_capture(
        session_id=session_id,
        capture_interval=capture_interval,
        ocr_enabled=ocr_enabled
    )


async def stop_periodic_capture(session_id: str) -> Dict[str, Any]:
    """
    Stop periodic screen capture for a session
    
    Args:
        session_id: Session identifier
        
    Returns:
        Dictionary with status message
    """
    return await ScreenCaptureService.stop_periodic_capture(session_id)