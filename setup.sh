#!/bin/bash

echo "🔧 setting up todo app with uv..."

# Install UV if not present
if ! command -v uv &> /dev/null; then
    echo "📦 Installing UV..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    # Add UV to PATH for this session
    export PATH="$HOME/.local/bin:$PATH"
    
    # Verify UV is now available
    if ! command -v uv &> /dev/null; then
        echo "❌ UV installation failed"
        exit 1
    fi
    echo "✅ UV installed successfully"
fi

# Setup backend
echo "🐍 Setting up backend with UV..."
cd backend

# Remove existing .venv if it exists
if [ -d ".venv" ]; then
    rm -rf .venv
fi

# Create project and install dependencies with UV
uv venv
uv pip install -r requirements.txt

# Initialize the database
echo "🗄️  Initializing database..."
source .venv/bin/activate
python init_db.py

echo "✅ Backend setup complete"
cd ..

# Setup frontend
echo "⚛️ Setting up frontend..."
cd frontend
npm install
echo "✅ Frontend setup complete"
cd ..

echo "🎉 Setup complete! You can now run: ./start-dev.sh"
