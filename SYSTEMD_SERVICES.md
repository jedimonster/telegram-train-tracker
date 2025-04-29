# Systemd Services for Telegram Train Bot

This directory contains systemd service files for running the Telegram Train Bot and its subscription poller as system services. Using systemd allows the bot and poller to:

- Start automatically on system boot
- Restart automatically if they crash
- Be managed using standard systemd commands
- Have their logs integrated with the system journal

## Service Files

Two service files are provided:

1. **train-bot.service**: Runs the main Telegram bot that handles user interactions
2. **train-poller.service**: Runs the subscription poller that checks for train updates and sends notifications

## Installation

### Automatic Installation

An installation script is provided to simplify the process:

```bash
# Make the script executable (if not already)
chmod +x install_services.sh

# Run the installation script with sudo
sudo ./install_services.sh
```

### Manual Installation

If you prefer to install the services manually:

1. Copy the service files to the systemd directory:
   ```bash
   sudo cp train-bot.service /etc/systemd/system/
   sudo cp train-poller.service /etc/systemd/system/
   ```

2. Set the correct permissions:
   ```bash
   sudo chmod 644 /etc/systemd/system/train-bot.service
   sudo chmod 644 /etc/systemd/system/train-poller.service
   ```

3. Reload systemd to recognize the new services:
   ```bash
   sudo systemctl daemon-reload
   ```

## Usage

### Enabling Services

To configure the services to start automatically on system boot:

```bash
sudo systemctl enable train-bot.service
sudo systemctl enable train-poller.service
```

### Starting Services

To start the services immediately:

```bash
sudo systemctl start train-bot.service
sudo systemctl start train-poller.service
```

### Checking Status

To check the current status of the services:

```bash
sudo systemctl status train-bot.service
sudo systemctl status train-poller.service
```

### Stopping Services

To stop the services:

```bash
sudo systemctl stop train-bot.service
sudo systemctl stop train-poller.service
```

### Restarting Services

To restart the services (for example, after updating the code):

```bash
sudo systemctl restart train-bot.service
sudo systemctl restart train-poller.service
```

### Viewing Logs

To view the service logs:

```bash
# View bot logs
sudo journalctl -u train-bot.service

# View poller logs
sudo journalctl -u train-poller.service

# Follow logs in real-time
sudo journalctl -u train-bot.service -f
sudo journalctl -u train-poller.service -f
```

## Configuration

The service files are configured to:

- Run as the root user (you may want to change this to a dedicated user for security)
- Use the .env file in the project directory for environment variables
- Restart automatically if the services crash
- Output logs to the system journal

### Customizing the Services

If you need to customize the services (for example, to change the user they run as or modify the restart policy), edit the service files and then reload systemd:

```bash
sudo systemctl daemon-reload
```

## Troubleshooting

If you encounter issues with the services:

1. Check the service status:
   ```bash
   sudo systemctl status train-bot.service
   ```

2. View the logs for error messages:
   ```bash
   sudo journalctl -u train-bot.service -e
   ```

3. Ensure the .env file exists and contains the required environment variables:
   - TELEGRAM_BOT_TOKEN
   - RAIL_TOKEN

4. Verify that the paths in the service files match your actual installation directory.

5. If you've made changes to the service files, make sure to reload systemd:
   ```bash
   sudo systemctl daemon-reload
   ```
