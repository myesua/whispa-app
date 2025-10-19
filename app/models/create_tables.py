"""
Script to create all database tables
"""
from app.models import Base
from app.models.database import engine

def create_all_tables():
    """Create all tables in the database"""
    Base.metadata.create_all(bind=engine)

if __name__ == "__main__":
    create_all_tables()
    print("All tables created successfully!")