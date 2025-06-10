#!/bin/bash

echo "🚀 Starting Todo App Development Server..."

# Ensure UV is in PATH if it exists
if [ -f "$HOME/.local/bin/uv" ]; then
    export PATH="$HOME/.local/bin:$PATH"
fi

# Function to cleanup on exit
cleanup() {
    echo
    echo "🛑 Shutting down Todo App servers..."
    
    # Kill backend process group
    if [ ! -z "$BACKEND_PID" ]; then
        echo "Stopping backend (PID: $BACKEND_PID)..."
        # Kill the entire process group to catch child processes
        kill -TERM -$BACKEND_PID 2>/dev/null || kill -TERM $BACKEND_PID 2>/dev/null
        
        # Wait a moment for graceful shutdown
        sleep 2
        
        # Force kill if still running
        if kill -0 $BACKEND_PID 2>/dev/null; then
            echo "Force stopping backend..."
            kill -KILL -$BACKEND_PID 2>/dev/null || kill -KILL $BACKEND_PID 2>/dev/null
        fi
        echo "✅ Backend stopped."
    fi
    
    # Kill frontend process group
    if [ ! -z "$FRONTEND_PID" ]; then
        echo "Stopping frontend (PID: $FRONTEND_PID)..."
        # Kill the entire process group to catch child processes
        kill -TERM -$FRONTEND_PID 2>/dev/null || kill -TERM $FRONTEND_PID 2>/dev/null
        
        # Wait a moment for graceful shutdown
        sleep 2
        
        # Force kill if still running
        if kill -0 $FRONTEND_PID 2>/dev/null; then
            echo "Force stopping frontend..."
            kill -KILL -$FRONTEND_PID 2>/dev/null || kill -KILL $FRONTEND_PID 2>/dev/null
        fi
        echo "✅ Frontend stopped."
    fi
    
    # Also kill any remaining uvicorn or vite processes
    echo "Cleaning up any remaining processes..."
    pkill -f "uvicorn.*main:app" 2>/dev/null
    pkill -f "vite.*--port.*80" 2>/dev/null
    
    echo "🎉 Todo App shutdown complete!"
    exit 0
}

# Set up trap to cleanup on script exit (handle multiple signals)
trap cleanup SIGINT SIGTERM SIGQUIT EXIT

# Check if setup was completed
if [ ! -d "backend/.venv" ] || [ ! -d "frontend/node_modules" ]; then
    echo "❌ Setup not complete. Please run: ./setup.sh first"
    exit 1
fi

# Start backend in a new process group
echo "🐍 Starting Backend..."
cd backend
source .venv/bin/activate
# Start in background with new process group
setsid uvicorn main:app --reload --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!
echo "Backend PID: $BACKEND_PID"
cd ..

# Wait a moment for backend to start
sleep 3

# Start frontend in a new process group
echo "⚛️ Starting Frontend..."
cd frontend
# Start in background with new process group
setsid npm run dev &
FRONTEND_PID=$!
echo "Frontend PID: $FRONTEND_PID"
cd ..

echo
echo "✅ Todo App is running!"
echo "📱 Frontend: http://localhost"
echo "🔗 Backend API: http://localhost/api (proxied)"
echo "📚 API Docs: http://localhost:8000/docs (direct - may not be accessible)"
echo
echo "Press Ctrl+C to stop all services..."

# Wait for background processes
wait