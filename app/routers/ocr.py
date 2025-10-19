from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Optional
import base64
import io
import os
import uuid
from PIL import Image
import pytesseract

router = APIRouter()

# Define storage directory
CAPTURES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "storage", "captures")
os.makedirs(CAPTURES_DIR, exist_ok=True)

class OCRRequest(BaseModel):
    image: str
    session_id: Optional[str] = None

@router.post("/ocr")
async def process_ocr(request: Request):
    """Process an image with OCR and Gemini Vision."""
    try:
        # Get request data
        request_data = await request.json()
        
        # Extract image data from base64 string
        image_data = request_data.get("image")
        if image_data.startswith('data:image'):
            # Remove the data URL prefix if present
            image_data = image_data.split(',')[1]
        
        # Decode base64 image
        image_bytes = base64.b64decode(image_data)
        image = Image.open(io.BytesIO(image_bytes))
        
        # Save the image to storage
        filename = f"{uuid.uuid4()}.png"
        filepath = os.path.join(CAPTURES_DIR, filename)
        image.save(filepath)
        
        # Process with pytesseract
        text = pytesseract.image_to_string(image)
        
        # Prepare image for Gemini Vision
        buffered = io.BytesIO()
        image.save(buffered, format="PNG")
        img_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')
        
        # Return the extracted text and image data
        return {
            'success': True,
            'text': text,
            'filename': filename,
            'image_data': img_base64  # Send back to client for later use with Gemini
        }
    
    except Exception as e:
        print(f"Error in OCR processing: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))