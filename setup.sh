#!/bin/bash
# Setup script for Telegram Train Bot
# This script helps set up the environment for running the Telegram Train Bot

echo "Setting up Telegram Train Bot..."

# Check if Python 3 is installed
if command -v python3 &>/dev/null; then
    echo "Python 3 is installed."
else
    echo "Error: Python 3 is not installed. Please install Python 3 and try again."
    exit 1
fi

# Check if pip is installed
if command -v pip3 &>/dev/null; then
    echo "pip is installed."
else
    echo "Error: pip is not installed. Please install pip and try again."
    exit 1
fi

# Create virtual environment
echo "Creating virtual environment..."
python3 -m venv venv
if [ ! -d "venv" ]; then
    echo "Error: Failed to create virtual environment."
    exit 1
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
pip install python-telegram-bot requests python-dateutil

# Check if environment variables are set
echo "Checking environment variables..."
if [ -z "$TELEGRAM_BOT_TOKEN" ]; then
    echo "Warning: TELEGRAM_BOT_TOKEN environment variable is not set."
    echo "Please set it using: export TELEGRAM_BOT_TOKEN=your_telegram_bot_token"
fi

if [ -z "$RAIL_TOKEN" ]; then
    echo "Warning: RAIL_TOKEN environment variable is not set."
    echo "Please set it using: export RAIL_TOKEN=your_rail_api_key"
fi

# Create .env file template
echo "Creating .env file template..."
cat > .env.template << EOL
# Environment variables for Telegram Train Bot
# Copy this file to .env and fill in your values

# Telegram Bot Token (obtained from BotFather)
TELEGRAM_BOT_TOKEN=your_telegram_bot_token

# Israeli Rail API Key
RAIL_TOKEN=your_rail_api_key
EOL

echo "Setup complete!"
echo ""
echo "To run the bot:"
echo "1. Activate the virtual environment: source venv/bin/activate"
echo "2. Set your environment variables:"
echo "   export TELEGRAM_BOT_TOKEN=your_telegram_bot_token"
echo "   export RAIL_TOKEN=your_rail_api_key"
echo "3. Run the bot: python train_bot.py"
echo ""
echo "To run the subscription poller:"
echo "1. As a daemon: python run_poller.py --daemon --interval 300"
echo "2. As a one-time check: python run_poller.py --once"
echo ""
echo "For more information, see README.md"
