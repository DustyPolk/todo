# Claude Code Project Documentation

This document contains important information for Claude Code about this Todo Application project.

## Project Overview

This is a full-stack todo application built with:
- **Backend**: FastAPI + SQLite
- **Frontend**: React + TypeScript + shadcn/ui + Tailwind CSS
- **Package Manager**: UV (Python) + npm (Node.js)
- **Development**: Vite dev server with proxy setup

## Project Structure

```
todo_app/
├── backend/                 # FastAPI backend
│   ├── main.py             # Main FastAPI application
│   ├── models.py           # SQLAlchemy database models
│   ├── schemas.py          # Pydantic validation schemas
│   ├── database.py         # Database configuration
│   ├── init_db.py          # Database initialization script
│   ├── test_main.py        # Backend tests
│   ├── requirements.txt    # Python dependencies
│   ├── .venv/             # Python virtual environment (ignored)
│   └── todos.db           # SQLite database (ignored)
├── frontend/               # React frontend
│   ├── src/
│   │   ├── components/    # React components
│   │   │   ├── ui/        # shadcn/ui components
│   │   │   ├── TaskList.tsx
│   │   │   ├── TaskItem.tsx
│   │   │   └── TaskForm.tsx
│   │   ├── hooks/         # Custom React hooks
│   │   ├── services/      # API service layer
│   │   ├── types/         # TypeScript type definitions
│   │   └── lib/           # Utility functions
│   ├── public/            # Static assets
│   ├── package.json       # Node.js dependencies
│   ├── tailwind.config.js # Tailwind CSS configuration
│   ├── vite.config.ts     # Vite configuration with proxy
│   └── node_modules/      # Node dependencies (ignored)
├── setup.sh               # Initial setup script
├── start-dev.sh           # Development server startup script
├── README.md              # User documentation
├── .gitignore             # Git ignore rules
└── CLAUDE.md              # This file
```

## Development Commands

### Setup (One-time)
```bash
./setup.sh
```
This script:
- Installs UV package manager if not present
- Creates Python virtual environment with UV
- Installs Python dependencies
- Initializes SQLite database
- Installs Node.js dependencies

### Start Development Server
```bash
./start-dev.sh
```
This script:
- Starts FastAPI backend on port 8000
- Starts Vite frontend dev server on port 80
- Sets up proxy for API calls (/api -> localhost:8000)
- Handles graceful shutdown with Ctrl+C

### Manual Commands
```bash
# Backend only
cd backend
source .venv/bin/activate
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Frontend only
cd frontend
npm run dev

# Database reset
cd backend
source .venv/bin/activate
python init_db.py
```

## Architecture Details

### Backend (FastAPI)
- **Port**: 8000
- **Database**: SQLite (`todos.db`)
- **ORM**: SQLAlchemy
- **Validation**: Pydantic
- **CORS**: Configured for frontend on port 80
- **API Base**: `/api`

### Frontend (React)
- **Port**: 80 (requires root/sudo)
- **Build Tool**: Vite
- **Styling**: Tailwind CSS v3
- **UI Components**: shadcn/ui
- **State Management**: React Query + Zustand
- **API Proxy**: `/api` -> `http://localhost:8000/api`

### Database Schema
```sql
CREATE TABLE tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    completed BOOLEAN DEFAULT FALSE,
    priority VARCHAR(10) DEFAULT 'medium',
    due_date DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

## API Endpoints

### Task Management
- `GET /api/tasks` - Get all tasks (with optional filters)
- `POST /api/tasks` - Create new task
- `GET /api/tasks/{id}` - Get specific task
- `PUT /api/tasks/{id}` - Update task
- `DELETE /api/tasks/{id}` - Delete task
- `PATCH /api/tasks/{id}` - Partial update (e.g., toggle completion)

### Utility
- `GET /api/health` - Health check
- `GET /api/stats` - Task statistics

### Query Parameters
- `completed` - Filter by completion status (true/false)
- `priority` - Filter by priority (low/medium/high)
- `skip` - Pagination offset
- `limit` - Number of results

## Key Features

### Implemented ✅
- Complete CRUD operations for tasks
- Task priorities (Low, Medium, High)
- Due dates
- Filter by status and priority
- Dark/light theme toggle
- Responsive design
- Real-time updates with optimistic UI
- Form validation
- Error handling
- Database initialization
- Graceful server shutdown

### UI Components
- `TaskList` - Main task display with filters
- `TaskItem` - Individual task with actions
- `TaskForm` - Create/edit task modal
- `ThemeToggle` - Dark/light mode switcher
- shadcn/ui components (Button, Input, Card, Checkbox, etc.)

## Development Notes

### Package Management
- **Python**: Uses UV for fast dependency management
- **Node.js**: Uses npm for frontend dependencies
- **Virtual Environment**: `.venv` directory (auto-created)

### Port Configuration
- **Frontend**: Port 80 (with Vite proxy for API)
- **Backend**: Port 8000 (internal only)
- **API Access**: Through frontend proxy at `/api`

### Styling
- **Framework**: Tailwind CSS v3
- **Theme**: CSS variables for dark/light mode
- **Components**: shadcn/ui with custom styling
- **Responsive**: Mobile-first design

### Database
- **File**: `backend/todos.db` (auto-created)
- **Initialization**: Automatic on setup
- **Reset**: Run `python init_db.py` in backend directory

## Common Issues & Solutions

### Port 80 Access
- Requires root privileges
- If port busy, Vite will use port 81
- Check with `sudo lsof -i :80`

### Database Issues
- Run `python init_db.py` to reset database
- Check `.venv` activation if SQLAlchemy errors

### Styling Not Loading
- Ensure Tailwind CSS v3 is installed
- Check PostCSS configuration
- Verify `@tailwind` directives in `index.css`

### API Connection Issues
- Check if backend is running on port 8000
- Verify CORS configuration in `main.py`
- Test direct API access: `curl http://localhost:8000/api/health`

## Testing

### Backend Tests
```bash
cd backend
source .venv/bin/activate
pytest
```

### Frontend Tests
```bash
cd frontend
npm test
```

## Deployment Notes

### Environment Variables
- No environment variables currently required
- Database path is relative (`./todos.db`)

### Production Considerations
- Use production ASGI server (Gunicorn + Uvicorn)
- Build frontend: `npm run build`
- Serve static files through reverse proxy
- Use proper database (PostgreSQL) for production
- Set up proper CORS origins

## Performance

### Backend
- SQLite suitable for single-user/development
- API response time < 200ms
- Supports 1000+ tasks efficiently

### Frontend
- Vite dev server with HMR
- Optimistic updates for better UX
- React Query for caching and state management

## Security

### Current Implementation
- Input validation via Pydantic
- SQL injection prevention via SQLAlchemy ORM
- XSS protection in React
- CORS configured for development

### Production Security
- Add rate limiting
- Implement authentication/authorization
- Use HTTPS
- Sanitize all inputs
- Add request/response logging

---

**Last Updated**: Current development version
**Claude Code**: Use this documentation to understand project structure and development workflows.