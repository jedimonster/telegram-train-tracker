# Train Information Bot

A Telegram bot for checking train schedules, status updates, and receiving notifications about delays.

## Features

- Check current and future train schedules
- Get real-time status updates and delay information
- Subscribe to regular train routes for automatic updates
- Manage favorite stations for quick access
- Pause/resume notifications as needed

## Setup

1. Clone the repository:
```bash
git clone https://github.com/yourusername/train-bot.git
cd train-bot
```

2. Run the setup script:
```bash
./setup.sh
```

3. Edit the `.env` file with your tokens:
```
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
RAIL_TOKEN=your_rail_api_token
```

4. Start the services:

On Linux (using systemd):
```bash
sudo systemctl start train-bot.service
sudo systemctl start train-poller.service
```

Manually:
```bash
# Terminal 1 - Run the bot
python3 run.py

# Terminal 2 - Run the poller
python3 run_poller.py
```

## Bot Commands

- `/start` - Start the bot
- `/help` - Show help message
- `/status` - Check train status
- `/subscribe` - Subscribe to train updates
- `/mysubscriptions` - View your subscriptions
- `/unsubscribe` - Cancel a subscription
- `/favorites` - Manage your favorite stations
- `/settings` - Configure notification preferences
- `/pause` - Pause all notifications
- `/resume` - Resume notifications

## Development

The project uses a modular structure:

```
src/train_bot/
├── database/           # Database models and operations
├── handlers/           # Command handlers
├── utils/             # Utility modules
└── bot.py             # Main bot module
```

To install in development mode:
```bash
pip install -e .
```

## Requirements

- Python 3.7+
- python-telegram-bot>=20.0
- python-dotenv>=0.19.0
- requests>=2.26.0
- aiohttp>=3.8.0
- asyncio>=3.4.3
- pytz>=2021.3

## License

This project is licensed under the MIT License - see the LICENSE file for details.
