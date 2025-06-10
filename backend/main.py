from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List, Optional
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
import models
import schemas
from database import SessionLocal, engine
from routers import auth as auth_router
from routers import security as security_router
from routers import oauth as oauth_router
from auth import get_current_user, get_current_active_user, check_user_role
from config import CORS_ORIGINS
from security import (
    SecurityMiddleware, limiter, rate_limit_api, rate_limit_public,
    security_logger
)

models.Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Todo API", 
    version="1.0.0",
    docs_url="/docs",  # Swagger UI
    redoc_url="/redoc"  # ReDoc
)

# Add security middleware
app.add_middleware(SecurityMiddleware)
app.add_middleware(SlowAPIMiddleware)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
    allow_headers=["*"],
    expose_headers=["X-Total-Count", "X-RateLimit-Limit", "X-RateLimit-Remaining"],
)

# Add rate limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Include routers
app.include_router(auth_router.router)
app.include_router(security_router.router)
app.include_router(oauth_router.router)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/")
@rate_limit_public()
def read_root(request: Request):
    return {"message": "Todo API is running"}

@app.get("/api/health")
@rate_limit_public()
def health_check(request: Request):
    return {"status": "healthy", "timestamp": "2024-12-10T22:30:00Z"}

@app.get("/api/tasks", response_model=List[schemas.Task])
@rate_limit_api()
def get_tasks(
    request: Request,
    skip: int = 0,
    limit: int = 100,
    completed: Optional[bool] = None,
    priority: Optional[str] = None,
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    query = db.query(models.Task)
    
    # Filter by user unless admin
    if current_user.role != "admin":
        query = query.filter(models.Task.user_id == current_user.id)
    
    if completed is not None:
        query = query.filter(models.Task.completed == completed)
    
    if priority:
        query = query.filter(models.Task.priority == priority)
    
    tasks = query.offset(skip).limit(limit).all()
    return tasks

@app.post("/api/tasks", response_model=schemas.Task)
@rate_limit_api()
def create_task(
    request: Request,
    task: schemas.TaskCreate,
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    db_task = models.Task(**task.dict(), user_id=current_user.id)
    db.add(db_task)
    db.commit()
    db.refresh(db_task)
    return db_task

@app.get("/api/tasks/{task_id}", response_model=schemas.Task)
@rate_limit_api()
def get_task(
    request: Request,
    task_id: int,
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Check permissions
    if current_user.role != "admin" and task.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to view this task")
    
    return task

@app.put("/api/tasks/{task_id}", response_model=schemas.Task)
@rate_limit_api()
def update_task(
    request: Request,
    task_id: int,
    task: schemas.TaskUpdate,
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    db_task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if db_task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Check permissions
    if current_user.role != "admin" and db_task.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to update this task")
    
    for key, value in task.dict(exclude_unset=True).items():
        setattr(db_task, key, value)
    
    db.commit()
    db.refresh(db_task)
    return db_task

@app.patch("/api/tasks/{task_id}", response_model=schemas.Task)
@rate_limit_api()
def patch_task(
    request: Request,
    task_id: int,
    task: schemas.TaskUpdate,
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    return update_task(task_id, task, current_user, db)

@app.delete("/api/tasks/{task_id}")
@rate_limit_api()
def delete_task(
    request: Request,
    task_id: int,
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    db_task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if db_task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Check permissions
    if current_user.role != "admin" and db_task.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to delete this task")
    
    db.delete(db_task)
    db.commit()
    return {"message": "Task deleted successfully"}

@app.get("/api/stats")
@rate_limit_api()
def get_stats(
    request: Request,
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    query = db.query(models.Task)
    
    # Filter by user unless admin
    if current_user.role != "admin":
        query = query.filter(models.Task.user_id == current_user.id)
    
    total_tasks = query.count()
    completed_tasks = query.filter(models.Task.completed == True).count()
    active_tasks = total_tasks - completed_tasks
    
    return {
        "total_tasks": total_tasks,
        "completed_tasks": completed_tasks,
        "active_tasks": active_tasks,
        "user": current_user.username
    }