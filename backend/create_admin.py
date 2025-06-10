#!/usr/bin/env python3
"""
Script to create a default admin user for development.
"""
from sqlalchemy.orm import Session
from database import SessionLocal, engine
from auth import get_password_hash
import models

def create_admin_user():
    """Create a default admin user."""
    db = SessionLocal()
    
    try:
        # Check if admin already exists
        admin = db.query(models.User).filter(
            models.User.username == "admin"
        ).first()
        
        if admin:
            print("Admin user already exists")
            return
        
        # Create admin user
        admin_user = models.User(
            email="admin@example.com",
            username="admin",
            hashed_password=get_password_hash("Admin123!@#$"),
            role="admin",
            is_active=True,
            is_verified=True
        )
        
        db.add(admin_user)
        db.commit()
        
        print("Admin user created successfully!")
        print("Username: admin")
        print("Password: Admin123!@#$")
        print("Please change this password after first login!")
        
    except Exception as e:
        print(f"Error creating admin user: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    # Ensure database tables exist
    models.Base.metadata.create_all(bind=engine)
    create_admin_user()