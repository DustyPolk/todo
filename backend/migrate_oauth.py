#!/usr/bin/env python3
"""
Database migration script to add OAuth2 tables and update User table.
"""
from sqlalchemy import create_engine, text
from database import Base, engine
import models

def migrate_oauth_tables():
    """Add OAuth2 tables and update User table for OAuth support."""
    print("Starting OAuth2 database migration...")
    
    # Create all new tables (won't affect existing ones)
    Base.metadata.create_all(bind=engine)
    
    with engine.connect() as conn:
        # Check if OAuth columns exist in users table
        result = conn.execute(text("""
            SELECT COUNT(*) 
            FROM pragma_table_info('users') 
            WHERE name='oauth_provider'
        """))
        
        if result.scalar() == 0:
            print("Adding OAuth columns to users table...")
            
            # Add OAuth columns to users table
            try:
                conn.execute(text("ALTER TABLE users ADD COLUMN oauth_provider VARCHAR(50)"))
                conn.execute(text("ALTER TABLE users ADD COLUMN oauth_id VARCHAR(255)"))
                conn.execute(text("ALTER TABLE users ADD COLUMN avatar_url VARCHAR(500)"))
                conn.execute(text("ALTER TABLE users ADD COLUMN provider_data JSON"))
                
                # Make hashed_password nullable for OAuth users
                # Note: SQLite doesn't support ALTER COLUMN, so we'll handle this differently
                # For SQLite, we'll just document that hashed_password can be NULL
                
                conn.commit()
                print("OAuth columns added successfully")
            except Exception as e:
                print(f"Error adding OAuth columns: {e}")
                conn.rollback()
                raise
        else:
            print("OAuth columns already exist")
    
    print("OAuth2 database migration completed successfully!")

if __name__ == "__main__":
    migrate_oauth_tables()