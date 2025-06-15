#!/bin/bash

echo "🚀 Setting up Gita TTS..."

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

echo "✅ Setup complete!"
echo "Run: source venv/bin/activate && python src/main.py"
