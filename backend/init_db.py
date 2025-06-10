#!/usr/bin/env python3
"""
Database initialization script for the Todo application.
Creates the SQLite database and tables if they don't exist.
"""

from database import engine, Base
from models import Task
import os

def init_database():
    """Initialize the database by creating all tables."""
    print("🗄️  Initializing database...")
    
    # Remove existing database file to start fresh
    db_file = "todos.db"
    if os.path.exists(db_file):
        print(f"Removing existing database: {db_file}")
        os.remove(db_file)
    
    # Create all tables
    Base.metadata.create_all(bind=engine)
    print("✅ Database tables created successfully!")
    
    # Verify tables were created
    from sqlalchemy import inspect
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    print(f"📋 Created tables: {tables}")

if __name__ == "__main__":
    init_database()