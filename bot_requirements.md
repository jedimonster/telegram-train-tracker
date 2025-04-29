# Telegram Train Information Bot Requirements

## Overview
A Telegram bot that allows users to query train information, check train status, and subscribe to regular train updates. The bot will be implemented in Python as a standalone script and will interface with the existing train data facade to retrieve information about Israeli trains.

## Existing Components

### Train Data Facade
The bot will utilize the existing `train_facade.py` which provides:
- Functions to get train times between stations
- Functions to check for train delays
- Access to the Israeli Rail API
- Train station information via `train_stations.py`
- Date utilities via `date_utils.py`

## Functional Requirements

### 1. Train Status Queries
- **1.1** Users must be able to check the status of a future train by providing:
  - Departure station (from the list in `train_stations.py`)
  - Arrival station (from the list in `train_stations.py`)
  - Date of travel
  - Optional: specific departure time
- **1.2** Users must be able to check the status of an in-flight (currently running) train by providing:
  - Departure station
  - Arrival station
  - Optional: specific departure time (if not provided, show all current trains on that route)
- **1.3** Status information should include:
  - Scheduled departure and arrival times
  - Current delay status (on time/delayed)
  - If delayed, the estimated delay time
  - Information about station switches if applicable (using the `extract_switch_stations` function)

### 2. Train Subscription Service
- **2.1** Users must be able to subscribe to specific trains on a weekly cadence by providing:
  - Departure station
  - Arrival station
  - Day(s) of the week (using the `WEEKDAYS` enum from `date_utils.py`)
  - Departure time
  - Optional: specific time period (start date to end date)
  - Optional: notification preferences
- **2.2** The bot should automatically poll the train status at appropriate intervals for subscribed trains
  - Use the `get_delay_from_api` function to check for delays
  - Poll more frequently as the train departure time approaches
- **2.3** The bot should send notifications to subscribed users when:
  - A train's status changes (e.g., from on-time to delayed)
  - A significant delay occurs (configurable threshold)
  - A train is about to depart (configurable time before departure)
- **2.4** Users must be able to view, modify, and cancel their subscriptions

### 3. User Interface and Commands
- **3.1** The bot should provide a clear, intuitive command structure:
  - `/start` - Introduction and help information
  - `/help` - List available commands and their usage
  - `/status` - Check status of a specific train
  - `/subscribe` - Subscribe to a train
  - `/mysubscriptions` - List current subscriptions
  - `/unsubscribe` - Cancel a subscription
  - `/settings` - Configure notification preferences
- **3.2** The bot should implement conversation flows for complex operations
  - Station selection (from the list in `train_stations.py`)
  - Date and time selection
  - Subscription configuration
- **3.3** The bot should provide inline keyboard options where appropriate to simplify user input
  - Station selection from favorites or full list
  - Day of week selection
  - Common times selection

## Non-Functional Requirements

### 4. Performance
- **4.1** The bot should respond to user queries within 3 seconds
- **4.2** The bot should handle multiple concurrent users
- **4.3** The subscription polling mechanism should be optimized to minimize API calls to the train data facade
  - Batch similar subscription checks
  - Implement caching for frequently requested routes

### 5. Reliability
- **5.1** The bot should be operational 24/7
- **5.2** The bot should implement error handling and recovery mechanisms
  - Handle API failures gracefully
  - Retry failed API calls with exponential backoff
- **5.3** The bot should log errors and important events for troubleshooting
- **5.4** The bot should gracefully handle API failures or downtime
  - Inform users when the train data service is unavailable
  - Resume normal operation automatically when service is restored

### 6. Security
- **6.1** The bot should implement user authentication for Telegram users
- **6.2** The bot should securely store user subscription data
- **6.3** The bot should not expose sensitive information about the train data facade
  - Keep the API key secure (currently stored in environment variable `RAIL_TOKEN`)

### 7. Scalability
- **7.1** The bot architecture should support scaling to handle an increasing number of users
- **7.2** The subscription database should be designed to handle a growing number of subscriptions

## Technical Specifications

### 8. Implementation
- **8.1** The bot must be written in Python
- **8.2** The bot must run as a standalone script
- **8.3** The bot must use the python-telegram-bot library
- **8.4** The bot must interface with the existing train data facade
- **8.5** The bot should implement a database for storing user subscriptions (SQLite or similar)

### 9. Train Data Facade Integration
- **9.1** The bot must use the existing facade functions:
  - `get_train_times` - For checking future train schedules
  - `get_timetable` - For retrieving detailed timetable information
  - `get_delay_from_api` - For checking current train delays
- **9.2** The bot should implement additional facade methods if needed:
  - Function to get all trains between stations for a given day
  - Function to convert between user-friendly time formats and API formats
- **9.3** The bot should implement caching mechanisms to reduce load on the facade
- **9.4** The bot should handle facade API rate limits appropriately

### 10. Deployment and Operations
- **10.1** The bot should be deployable on standard Linux/Unix environments
- **10.2** The bot should include documentation for setup and configuration
- **10.3** The bot should support configuration via environment variables or config files
  - Telegram Bot Token
  - Rail API Key (already using `RAIL_TOKEN` environment variable)
  - Polling intervals
  - Notification thresholds
- **10.4** The bot should implement logging for operational monitoring

## Data Requirements

### 11. User Data
- **11.1** Telegram user ID
- **11.2** Subscription preferences
- **11.3** Notification settings
- **11.4** Favorite stations (subset of `TRAIN_STATIONS` from `train_stations.py`)

### 12. Subscription Data
- **12.1** Train route information (departure and arrival stations)
- **12.2** Schedule information (day of week, time)
- **12.3** Subscription start/end dates
- **12.4** Notification preferences for each subscription
- **12.5** Last known status (to detect changes)

## Database Schema

### Users Table
```
CREATE TABLE users (
    user_id INTEGER PRIMARY KEY,
    telegram_id INTEGER UNIQUE,
    username TEXT,
    first_name TEXT,
    last_name TEXT,
    language_code TEXT,
    notification_before_departure INTEGER DEFAULT 15,
    notification_delay_threshold INTEGER DEFAULT 5,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Favorite Stations Table
```
CREATE TABLE favorite_stations (
    id INTEGER PRIMARY KEY,
    user_id INTEGER,
    station_id TEXT,
    FOREIGN KEY (user_id) REFERENCES users(user_id),
    UNIQUE(user_id, station_id)
);
```

### Subscriptions Table
```
CREATE TABLE subscriptions (
    subscription_id INTEGER PRIMARY KEY,
    user_id INTEGER,
    departure_station TEXT,
    arrival_station TEXT,
    day_of_week INTEGER,
    departure_time TEXT,
    active BOOLEAN DEFAULT 1,
    start_date DATE,
    end_date DATE,
    notify_before_departure BOOLEAN DEFAULT 1,
    notify_delay BOOLEAN DEFAULT 1,
    notify_arrival BOOLEAN DEFAULT 0,
    last_status TEXT,
    last_checked TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);
```

### Notifications Table
```
CREATE TABLE notifications (
    notification_id INTEGER PRIMARY KEY,
    subscription_id INTEGER,
    notification_type TEXT,
    message TEXT,
    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (subscription_id) REFERENCES subscriptions(subscription_id)
);
```

## Implementation Plan

### Phase 1: Basic Bot Setup
1. Set up Telegram bot using python-telegram-bot
2. Implement basic command handlers
3. Create database schema
4. Implement user registration

### Phase 2: Train Status Queries
1. Implement station selection interface
2. Implement date and time selection
3. Integrate with existing facade to get train times
4. Implement status display formatting

### Phase 3: Subscription System
1. Implement subscription creation flow
2. Create subscription database tables
3. Develop polling mechanism for checking train status
4. Implement notification system

### Phase 4: Testing and Refinement
1. Test with real users
2. Optimize polling frequency
3. Refine user interface
4. Add additional features based on feedback

## Future Enhancements (Optional)

### 13. Potential Extensions
- **13.1** Multi-language support (Hebrew/English)
- **13.2** Integration with other messaging platforms
- **13.3** Advanced search capabilities (e.g., finding trains between stations with specific criteria)
- **13.4** Journey planning features
- **13.5** Disruption notifications for specific routes/stations
- **13.6** Integration with ticket purchasing systems
