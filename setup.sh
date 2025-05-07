#!/bin/bash

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install requirements
echo "Installing requirements..."
pip install -r requirements.txt

# Install the package in development mode
echo "Installing package in development mode..."
pip install -e .

# Create .env file if it doesn't exist
if [ ! -f ".env" ]; then
    echo "Creating .env file from template..."
    cp .env.template .env
    echo "Please edit .env file with your tokens"
fi

# Create database directory if it doesn't exist
if [ ! -d "data" ]; then
    echo "Creating data directory..."
    mkdir data
fi

# Set up systemd services if on Linux
if [ "$(uname)" == "Linux" ]; then
    echo "Setting up systemd services..."
    sudo ./install_services.sh
fi

echo "Setup complete!"
echo "Don't forget to:"
echo "1. Edit .env file with your tokens"
echo "2. Start the services:"
echo "   - systemctl start train-bot.service"
echo "   - systemctl start train-poller.service"
