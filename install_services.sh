#!/bin/bash
# Script to install systemd service files for the Telegram Train Bot

# Check if running as root
if [ "$EUID" -ne 0 ]; then
  echo "Please run as root (use sudo)"
  exit 1
fi

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Copy service files to systemd directory
echo "Installing systemd service files..."
cp "${SCRIPT_DIR}/train-bot.service" /etc/systemd/system/
cp "${SCRIPT_DIR}/train-poller.service" /etc/systemd/system/

# Set permissions
chmod 644 /etc/systemd/system/train-bot.service
chmod 644 /etc/systemd/system/train-poller.service

# Reload systemd to recognize new services
echo "Reloading systemd..."
systemctl daemon-reload

echo "Services installed successfully!"
echo ""
echo "To enable and start the services, run:"
echo "  sudo systemctl enable train-bot.service"
echo "  sudo systemctl start train-bot.service"
echo "  sudo systemctl enable train-poller.service"
echo "  sudo systemctl start train-poller.service"
echo ""
echo "To check status:"
echo "  sudo systemctl status train-bot.service"
echo "  sudo systemctl status train-poller.service"
echo ""
echo "To view logs:"
echo "  sudo journalctl -u train-bot.service -f"
echo "  sudo journalctl -u train-poller.service -f"
