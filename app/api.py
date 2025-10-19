from fastapi import FastAPI, HTTPException, Request, File, UploadFile, Form, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import pytesseract
from PIL import Image
import base64
import io
import os
import uuid
import time
import re
from collections import Counter
from pydantic import BaseModel
import uvicorn
import google.generativeai as genai
import json
from dotenv import load_dotenv
from typing import Optional
from sqlalchemy.orm import Session
from app.models.database import get_db
from app.models.transcription import Transcription
from app.services.transcription_service import transcribe_audio

# Load environment variables
load_dotenv()

# Configure Gemini API
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
else:
    print("WARNING: GEMINI_API_KEY not found in environment variables")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure storage paths
STORAGE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'storage')
CAPTURES_DIR = os.path.join(STORAGE_DIR, 'captures')
AUDIO_DIR = os.path.join(STORAGE_DIR, 'audio')
NOTES_DIR = os.path.join(STORAGE_DIR, 'notes')

# Ensure directories exist
for directory in [CAPTURES_DIR, AUDIO_DIR, NOTES_DIR]:
    os.makedirs(directory, exist_ok=True)

# Configure Gemini models
gemini_pro = genai.GenerativeModel('gemini-pro-latest')
gemini_vision = genai.GenerativeModel('gemini-pro-latest')

# AI-powered note generation using Gemini
async def generate_ai_notes(image_data, transcription):
    """Generate AI-powered notes using Gemini models for both image and text analysis."""
    try:
        result = {
            'notes': '',
            'image_analysis': '',
            'transcription_analysis': ''
        }
        
        # Process image with Gemini Vision if image data is available
        if image_data:
            try:
                vision_model = genai.GenerativeModel('gemini-pro-latest')
                image_prompt = """
                Analyze this screenshot and describe what you see.
                Focus on:
                1. The main content and purpose of the screen
                2. Any key information, data, or text visible
                3. The context of what this screen might be used for
                
                Provide a concise but comprehensive analysis.
                """
                
                # Create image part from base64 data
                image_part = {"mime_type": "image/png", "data": base64.b64decode(image_data)}
                vision_response = await vision_model.generate_content_async([image_prompt, image_part])
                result['image_analysis'] = vision_response.text
            except Exception as e:
                print(f"Error in image analysis: {str(e)}")
                result['image_analysis'] = "Image analysis failed."
        
        # Process transcription with Gemini Pro
        if transcription:
            try:
                text_model = genai.GenerativeModel('gemini-pro-latest')
                transcription_prompt = f"""
                Analyze this transcription from a voice recording:
                
                "{transcription}"
                
                Extract key points, main ideas, and any action items mentioned.
                """
                
                text_response = await text_model.generate_content_async(transcription_prompt)
                result['transcription_analysis'] = text_response.text
            except Exception as e:
                print(f"Error in transcription analysis: {str(e)}")
                result['transcription_analysis'] = "Transcription analysis failed."
        
        # Generate comprehensive notes combining both analyses
        try:
            notes_model = genai.GenerativeModel('gemini-pro-latest')
            
            # Prepare the prompt with available information
            notes_prompt = f"""
            Create comprehensive, well-structured notes based on the following information:
            
            """
            
            if result['image_analysis']:
                notes_prompt += f"""
                SCREEN ANALYSIS:
                {result['image_analysis']}
                """
            
            if result['transcription_analysis']:
                notes_prompt += f"""
                AUDIO ANALYSIS:
                {result['transcription_analysis']}
                """
            
            if not result['image_analysis'] and not result['transcription_analysis']:
                notes_prompt += f"""
                RAW TRANSCRIPTION:
                {transcription}
                """
            
            notes_prompt += """
            Format the notes in a clear, organized manner with:
            - A concise title
            - Key points and insights
            - Any action items or follow-ups
            - Use markdown formatting for better readability
            """
            
            notes_response = await notes_model.generate_content_async(notes_prompt)
            result['notes'] = notes_response.text
        except Exception as e:
            print(f"Error in notes generation: {str(e)}")
            result['notes'] = "AI note generation failed. Please try again."
        
        return result
    
    except Exception as e:
        print(f"Error in generate_ai_notes: {str(e)}")
        return {
            'notes': f"Error generating AI notes: {str(e)}",
            'image_analysis': '',
            'transcription_analysis': ''
        }

# Define request models
class OCRRequest(BaseModel):
    image: str

class OCRRequest(BaseModel):
    image: str
    session_id: Optional[str] = None

class NotesRequest(BaseModel):
    ocrText: str
    transcription: str
    imageData: str = None

@app.post("/api/ocr")
async def process_ocr(request: OCRRequest):
    """Process an image with OCR and Gemini Vision."""
    try:
        # Extract image data from base64 string
        image_data = request.image
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

@app.post("/api/transcribe")
async def transcribe_audio_endpoint(
    file: UploadFile = File(...),
    language: str = Form("en"),
    session_id: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    """
    Endpoint to transcribe audio files
    """
    try:
        # Generate a unique ID for this transcription
        transcription_id = str(uuid.uuid4())
        
        # Process the audio file asynchronously
        await transcribe_audio(
            transcription_id=transcription_id,
            file=file,
            language=language,
            model="gemini",
            session_id=session_id,
            db=db
        )
        
        # Get the transcription from the database
        db_transcription = db.query(Transcription).filter(
            Transcription.transcription_id == transcription_id
        ).first()
        
        if not db_transcription:
            raise HTTPException(status_code=404, detail="Transcription not found")
        
        # Return the transcription text
        return {
            "success": True,
            "transcription_id": transcription_id,
            "text": db_transcription.text,
            "status": db_transcription.status
        }
    
    except Exception as e:
        print(f"Error in transcribe_audio_endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/notes/generate")
async def generate_notes(request: NotesRequest):
    """Generate AI-powered notes from OCR text and audio transcription using Gemini."""
    try:
        ocr_text = request.ocrText
        transcription = request.transcription
        image_data = request.imageData
        
        # Generate AI-powered notes using Gemini
        ai_result = await generate_ai_notes(image_data, transcription)
        
        # Format the notes with the AI analysis
        notes = f"""
# AI-Generated Notes

## Summary
{ai_result['notes']}

## Original Content
OCR Text from Screen:
{ocr_text}

Audio Transcription:
{transcription if transcription else "No audio transcription available."}
        """.strip()
        
        # Save notes to a file
        filename = f"notes_{int(time.time())}.txt"
        filepath = os.path.join(NOTES_DIR, filename)
        with open(filepath, 'w') as f:
            f.write(notes)
        
        return {
            'success': True,
            'notes': notes,
            'filename': filename,
            'ai_analysis': {
                'transcription_analysis': ai_result.get('transcription_analysis', ''),
                'image_analysis': ai_result.get('image_analysis', '')
            }
        }
    
    except Exception as e:
        print(f"Error in generate_notes: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == '__main__':
    uvicorn.run(app, host="0.0.0.0", port=5000)