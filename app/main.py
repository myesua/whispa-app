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
from app.api.transcription import router as transcription_router
from app.api.summarization import router as summarization_router
from app.api.screen_capture import router as screen_capture_router
from app.api.storage import router as storage_router
from app.api.integrations import router as integrations_router

# Include routers
app.include_router(transcription_router, prefix="/api/transcription", tags=["Transcription"])
app.include_router(summarization_router, prefix="/api/summarization", tags=["Summarization"])
app.include_router(screen_capture_router, prefix="/api/screen-capture", tags=["Screen Capture"])
app.include_router(storage_router, prefix="/api/storage", tags=["Storage"])
app.include_router(integrations_router, prefix="/api/integrations", tags=["Integrations"])

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