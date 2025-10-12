#!/bin/bash

# Startup script for Satellite Analysis Backend

echo "🛰️  Starting Satellite Analysis Backend..."

# Check if .env exists
if [ ! -f .env ]; then
    echo "⚠️  Warning: .env file not found"
    echo "📝 Creating .env from example..."
    cat > .env << EOF
# Backend Configuration
ANALYZER_TYPE=replicate
REPLICATE_API_TOKEN=your_token_here
EOF
    echo "✅ Created .env file. Please update REPLICATE_API_TOKEN before continuing."
    exit 1
fi

# Load environment variables
export $(cat .env | grep -v '^#' | xargs)

# Validate Replicate token if using replicate analyzer
if [ "$ANALYZER_TYPE" = "replicate" ] && [ "$REPLICATE_API_TOKEN" = "your_token_here" ]; then
    echo "❌ Error: Please set REPLICATE_API_TOKEN in .env file"
    echo "📖 Get your token at: https://replicate.com/account/api-tokens"
    exit 1
fi

# Check if dependencies are installed
if ! python -c "import fastapi" &> /dev/null; then
    echo "📦 Installing dependencies..."
    pip install -r requirements.txt
fi

# Create data directories
mkdir -p "$DATA_DIR"
mkdir -p "$PROCESSED_DATA_DIR"

# Start the server
echo "🚀 Starting FastAPI server..."
echo "📍 Analyzer type: $ANALYZER_TYPE"
echo "🌐 Server will be available at: http://localhost:8000"
echo ""

uvicorn api:app --host 0.0.0.0 --port 8000 --reload 