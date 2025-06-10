#!/usr/bin/env python3
"""
Database migration script to add authentication tables to existing database.
"""
from sqlalchemy import create_engine, text
from database import Base, engine
import models

def migrate_database():
    """Add new authentication tables to existing database."""
    print("Starting database migration...")
    
    # Create all new tables (won't affect existing ones)
    Base.metadata.create_all(bind=engine)
    
    # Check if we need to add user_id column to tasks table
    with engine.connect() as conn:
        # Check if user_id column exists
        result = conn.execute(text("""
            SELECT COUNT(*) 
            FROM pragma_table_info('tasks') 
            WHERE name='user_id'
        """))
        
        if result.scalar() == 0:
            print("Adding user_id column to tasks table...")
            # Add user_id column to existing tasks table
            conn.execute(text("""
                ALTER TABLE tasks 
                ADD COLUMN user_id INTEGER 
                REFERENCES users(id)
            """))
            conn.commit()
            print("user_id column added successfully")
        else:
            print("user_id column already exists")
    
    print("Database migration completed successfully!")

if __name__ == "__main__":
    migrate_database()