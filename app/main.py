from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="Whispa API",
    description="AI-powered QA assistant API for capturing and processing feedback",
    version="0.1.0"
)

# Configure CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict this to specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Import routers
from app.routers.transcription import router as transcription_router
from app.routers.summarization import router as summarization_router
from app.routers.screen_capture import router as screen_capture_router
from app.routers.storage import router as storage_router
from app.routers.integrations import router as integrations_router

# Include routers
app.include_router(transcription_router, prefix="/routers/transcription", tags=["Transcription"])
app.include_router(summarization_router, prefix="/routers/summarization", tags=["Summarization"])
app.include_router(screen_capture_router, prefix="/routers/screen-capture", tags=["Screen Capture"])
app.include_router(storage_router, prefix="/routers/storage", tags=["Storage"])
app.include_router(integrations_router, prefix="/routers/integrations", tags=["Integrations"])

@app.get("/")
async def root():
    return {
        "message": "Welcome to Whispa API",
        "version": app.version,
        "docs_url": "/docs"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)