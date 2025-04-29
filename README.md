# Telegram Train Information Bot

A Telegram bot that allows users to check train information and subscribe to train updates. The bot provides information about train schedules, delays, and can send notifications for subscribed trains.

## Project Overview

This project implements a Telegram bot that interfaces with the Israeli Rail API through a facade to provide users with train information. The bot allows users to:

1. Check the status of future trains
2. Check the status of in-flight (currently running) trains
3. Subscribe to specific trains on a weekly cadence
4. Receive notifications about train delays and status changes

## Project Structure

- `requirements.md` - General requirements document for the Telegram train bot
- `architecture.md` - High-level architecture diagram and description
- `bot_requirements.md` - Detailed requirements document that takes into account the existing train facade
- `train_bot.py` - Sample implementation of the Telegram bot
- `subscription_poller.py` - Script that polls train status for subscriptions and sends notifications
- `run_poller.py` - Script to run the subscription poller as a daemon or scheduled task
- `train_facade.py` - Facade for accessing train data from the Israeli Rail API
- `train_stations.py` - Lists of train stations with IDs and names
- `date_utils.py` - Utility functions for date handling

## Setup Instructions

### Prerequisites

- Python 3.7 or higher
- A Telegram Bot Token (obtained from BotFather)
- Israeli Rail API Key

### Installation

#### Automatic Setup

Use the provided setup script to automatically set up the environment:

```bash
# Clone the repository
git clone <repository-url>
cd cline-rail-bot

# Make the setup script executable
chmod +x setup.sh

# Run the setup script
./setup.sh
```

The setup script will:
- Check if Python 3 and pip are installed
- Create a virtual environment
- Install the required dependencies
- Create a template .env file
- Provide instructions for running the bot

#### Manual Setup

If you prefer to set up manually:

1. Clone this repository:
   ```
   git clone <repository-url>
   cd cline-rail-bot
   ```

2. Create and activate a virtual environment (optional but recommended):
   ```
   python3 -m venv venv
   source venv/bin/activate
   ```

3. Install the required dependencies:
   ```
   pip install python-telegram-bot requests python-dateutil
   ```

4. Set up environment variables:
   ```
   export TELEGRAM_BOT_TOKEN=your_telegram_bot_token
   export RAIL_TOKEN=your_rail_api_key
   ```

   Alternatively, you can create a `.env` file based on the provided `.env.template`.

### Running the Bot

Run the bot using:
```
python train_bot.py
```

### Running the Subscription Poller

The subscription poller checks for train status changes and sends notifications to users. It can be run in two ways:

1. As a daemon process that runs continuously:
```
python run_poller.py --daemon --interval 300
```
This will check subscriptions every 5 minutes (300 seconds).

2. As a one-time check (suitable for cron jobs):
```
python run_poller.py --once
```

For production use, it's recommended to set up a cron job to run the poller at regular intervals:
```
# Example cron entry to run every 5 minutes
*/5 * * * * cd /path/to/cline-rail-bot && python run_poller.py --once
```

## Usage

Once the bot is running, users can interact with it through Telegram using the following commands:

- `/start` - Start the bot and get an introduction
- `/help` - Show available commands
- `/status` - Check current or future train status
- `/subscribe` - Subscribe to train updates
- `/mysubscriptions` - View current subscriptions
- `/unsubscribe` - Cancel a subscription
- `/favorites` - Manage your favorite stations
- `/settings` - Configure notification preferences

## Subscription Process

1. User initiates subscription with `/subscribe`
2. User selects departure station from favorites or full list
3. User selects arrival station from favorites or full list
4. User selects day of the week
5. User selects train time
6. User confirms subscription
7. Bot saves subscription and begins monitoring

## Checking Train Status

The bot provides two ways to check train status:

1. **Current Train Status**: Check trains that are currently running or departing soon
   - Select from a list of trains with departure times and journey durations
   - Currently running trains are marked with 🚂, while trains departing soon are marked with 🕒
   - View detailed information for a specific train including real-time delays and platform changes
   - See estimated arrival times based on current train status

2. **Future Train Status**: Check train schedules for upcoming days
   - Select a date (today through the next 7 days)
   - Choose from a list of available trains with departure times and journey durations
   - View detailed information for a specific train including departure time, arrival time, and journey duration

Users can select stations from their favorites list or browse the complete station directory.

## Managing Favorite Stations

Users can customize their list of favorite stations for quicker access:

1. Use the `/favorites` command to manage favorite stations
2. Add stations to favorites from the full station list
3. Remove stations from favorites as needed
4. Access favorite stations when selecting departure/arrival stations during status checks or subscriptions

The bot initially uses a default set of popular stations, but users can customize this list to include their most frequently used stations.

## Notification System

The bot will automatically check the status of subscribed trains and send notifications to users when:

- A train's status changes (e.g., from on-time to delayed)
- A significant delay occurs (configurable threshold)
- A train is about to depart (configurable time before departure)

## Database Structure

The bot uses SQLite to store:

- User information
- Favorite stations
- Subscriptions
- Notification history

## Future Enhancements

- Multi-language support (Hebrew/English)
- Integration with other messaging platforms
- Advanced search capabilities
- Journey planning features
- Disruption notifications for specific routes/stations

## BotFather Commands

Use the following formatted list of commands when configuring your bot with BotFather's `/setcommands` feature:

```
start - Start the bot and get an introduction
help - Show available commands and how to use the bot
status - Check current or future train status
subscribe - Subscribe to train updates for a specific route
mysubscriptions - View your active subscriptions
unsubscribe - Cancel an existing subscription
favorites - Manage your favorite stations
settings - Configure notification preferences
pause - Pause all notifications temporarily
resume - Resume notifications after pausing
```

To set these commands in BotFather:
1. Start a chat with @BotFather
2. Send the command `/setcommands`
3. Select your bot
4. Copy and paste the command list above

## License

[Specify license information here]
