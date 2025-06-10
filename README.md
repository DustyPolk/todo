# Todo Application

A modern, full-stack todo application built with FastAPI (backend) and React with shadcn/ui (frontend).

## Features

- ✅ Create, read, update, and delete tasks
- ✅ Mark tasks as complete/incomplete
- ✅ Set task priorities (Low, Medium, High)
- ✅ Add due dates to tasks
- ✅ Filter tasks by status and priority
- ✅ Modern, responsive UI with dark/light theme support
- ✅ Real-time updates with optimistic UI
- ✅ SQLite database for reliable data persistence

## Tech Stack

### Backend
- **FastAPI** - Modern, fast web framework for building APIs
- **SQLAlchemy** - SQL toolkit and ORM
- **SQLite** - Lightweight database
- **Pydantic** - Data validation using Python type annotations

### Frontend
- **React 18** - Frontend framework
- **TypeScript** - Type-safe JavaScript
- **shadcn/ui** - Modern UI components
- **Tailwind CSS** - Utility-first CSS framework
- **React Query** - Data fetching and caching
- **Vite** - Fast build tool

## Getting Started

### Prerequisites

- Python 3.9+
- Node.js 18+
- npm or yarn

### Backend Setup

#### Option 1: Using UV (Recommended - Faster)
1. Navigate to the backend directory:
   ```bash
   cd backend
   ```

2. Install dependencies with UV:
   ```bash
   uv venv
   uv pip install -r requirements.txt
   ```

3. Start the development server:
   ```bash
   source .venv/bin/activate
   uvicorn main:app --reload --host 0.0.0.0 --port 8000
   ```

#### Option 2: Traditional Python/Pip
1. Navigate to the backend directory:
   ```bash
   cd backend
   ```

2. Create a virtual environment:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Start the development server:
   ```bash
   uvicorn main:app --reload --host 0.0.0.0 --port 8000
   ```

The API will be available at `http://localhost:8000`

### Frontend Setup

1. Navigate to the frontend directory:
   ```bash
   cd frontend
   ```

2. Install dependencies:
   ```bash
   npm install
   ```

3. Start the development server:
   ```bash
   npm run dev
   ```

The application will be available at `http://localhost` (port 80)

## API Endpoints

### Task Management
- `GET /api/tasks` - Get all tasks (with optional filters)
- `POST /api/tasks` - Create a new task
- `GET /api/tasks/{id}` - Get a specific task
- `PUT /api/tasks/{id}` - Update a specific task
- `DELETE /api/tasks/{id}` - Delete a specific task
- `PATCH /api/tasks/{id}` - Partially update a task

### Utility
- `GET /api/health` - Health check
- `GET /api/stats` - Get task statistics

### Query Parameters
- `completed` - Filter by completion status (true/false)
- `priority` - Filter by priority (low/medium/high)
- `skip` - Number of tasks to skip (pagination)
- `limit` - Maximum number of tasks to return

## Development

### Running Tests

Backend tests:
```bash
cd backend
pytest
```

Frontend tests:
```bash
cd frontend
npm test
```

### Project Structure

```
todo_app/
├── backend/                 # FastAPI backend
│   ├── main.py             # Main application file
│   ├── models.py           # Database models
│   ├── schemas.py          # Pydantic schemas
│   ├── database.py         # Database configuration
│   └── requirements.txt    # Python dependencies
├── frontend/               # React frontend
│   ├── src/
│   │   ├── components/     # React components
│   │   ├── hooks/         # Custom React hooks
│   │   ├── services/      # API services
│   │   ├── types/         # TypeScript type definitions
│   │   └── lib/           # Utility functions
│   ├── public/            # Static assets
│   └── package.json       # Node.js dependencies
└── README.md              # Project documentation
```

## Database Schema

### Tasks Table
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

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.