# Import models in the correct order to avoid circular dependencies
from app.models.database import Base, get_db
from app.models.transcription import Transcription, TranscriptionSegment
from app.models.tickets import Ticket
from app.models.summarization import Summary, SummaryType
from app.models.screen_capture import ScreenCapture
from app.models.storage import StorageItem
from app.models.integration import Integration, IntegrationTicket

# Import any other models here

# This file ensures proper initialization order for SQLAlchemy mappers