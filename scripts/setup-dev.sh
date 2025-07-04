#!/bin/bash
# Development environment setup script for Discord IP Monitor Bot

set -e  # Exit on any error

echo "🚀 Setting up Discord IP Monitor Bot development environment..."

# Check if Python 3.11+ is available
python_version=$(python3 --version 2>/dev/null | cut -d' ' -f2 | cut -d'.' -f1,2 || echo "0.0")
required_version="3.11"

if [[ $(echo -e "$python_version\n$required_version" | sort -V | head -n1) != "$required_version" ]]; then
    echo "❌ Python 3.11+ is required. Found: $python_version"
    echo "Please install Python 3.11 or higher"
    exit 1
fi

echo "✅ Python version check passed: $python_version"

# Create virtual environment if it doesn't exist
if [ ! -d ".venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv .venv
    echo "✅ Virtual environment created"
else
    echo "✅ Virtual environment already exists"
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source .venv/bin/activate

# Upgrade pip
echo "⬆️  Upgrading pip..."
pip install --upgrade pip

# Install production dependencies
echo "📦 Installing production dependencies..."
pip install -r requirements.txt

# Install development dependencies
echo "🛠️  Installing development dependencies..."
pip install -r requirements-dev.txt

# Install pre-commit hooks
echo "🪝 Installing pre-commit hooks..."
pre-commit install

# Run pre-commit on all files to ensure everything is set up correctly
echo "🔍 Running initial pre-commit check..."
pre-commit run --all-files || {
    echo "⚠️  Pre-commit found some issues that were automatically fixed"
    echo "   Please review the changes and commit them"
}

# Create .env.example if it doesn't exist
if [ ! -f ".env.example" ]; then
    echo "📝 Creating .env.example file..."
    cat > .env.example << 'EOF'
# Discord Bot Configuration
DISCORD_BOT_TOKEN=your_bot_token_here
CHANNEL_ID=your_channel_id_here

# Database Configuration
DB_FILE=ip_monitor.db

# Monitoring Configuration
CHECK_INTERVAL=300
MAX_RETRIES=3
RETRY_DELAY=30

# Feature Flags
CIRCUIT_BREAKER_ENABLED=true
MESSAGE_QUEUE_ENABLED=true
CACHE_ENABLED=true
STARTUP_MESSAGE_ENABLED=true
CUSTOM_APIS_ENABLED=true

# Rate Limiting
RATE_LIMIT_PERIOD=300
MAX_CHECKS_PER_PERIOD=10

# Logging
LOG_LEVEL=INFO

# Development/Testing
TESTING_MODE=false
EOF
    echo "✅ Created .env.example file"
fi

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo "⚠️  No .env file found. Copying from .env.example..."
    cp .env.example .env
    echo "📝 Please edit .env file with your actual configuration values"
fi

# Run a quick test to make sure everything works
echo "🧪 Running a quick test to verify setup..."
python -c "
import sys
try:
    from ip_monitor.config import AppConfig
    print('✅ Package imports successfully')
except ImportError as e:
    print(f'❌ Import error: {e}')
    sys.exit(1)
"

# Run tests to make sure everything is working
echo "🧪 Running test suite..."
pytest --version
if pytest -x -q tests/unit/commands/admin_commands/test_base_handler.py::TestBaseHandler::test_init; then
    echo "✅ Basic tests are passing"
else
    echo "⚠️  Some tests may need attention"
fi

echo ""
echo "🎉 Development environment setup complete!"
echo ""
echo "Next steps:"
echo "1. Activate the virtual environment: source .venv/bin/activate"
echo "2. Edit .env file with your Discord bot token and channel ID"
echo "3. Run the bot: python main.py"
echo "4. Run tests: pytest"
echo "5. Run code quality checks: pre-commit run --all-files"
echo ""
echo "Useful commands:"
echo "- pytest                     # Run all tests"
echo "- pytest -v                  # Run tests with verbose output"
echo "- pytest --cov               # Run tests with coverage"
echo "- ruff check .               # Lint code"
echo "- ruff format .              # Format code"
echo "- pre-commit run --all-files # Run all quality checks"
echo ""
echo "Happy coding! 🚀"