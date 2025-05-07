"""Database models and schema for the train bot."""

import aiosqlite
from datetime import datetime
import json

# Database setup
DB_PATH = "train_bot.db"

async def setup_database():
    """Create the database tables if they don't exist."""
    async with aiosqlite.connect(DB_PATH) as conn:
        # Create users table
        await conn.execute('''
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        telegram_id INTEGER UNIQUE,
        username TEXT,
        first_name TEXT,
        last_name TEXT,
        language_code TEXT,
        notification_before_departure INTEGER DEFAULT 15,
        notification_delay_threshold INTEGER DEFAULT 5,
        notifications_paused BOOLEAN DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')

        # Create favorite stations table
        await conn.execute('''
    CREATE TABLE IF NOT EXISTS favorite_stations (
        id INTEGER PRIMARY KEY,
        user_id INTEGER,
        station_id TEXT,
        FOREIGN KEY (user_id) REFERENCES users(user_id),
        UNIQUE(user_id, station_id)
    )
    ''')

        # Create subscriptions table
        await conn.execute('''
    CREATE TABLE IF NOT EXISTS subscriptions (
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
    )
    ''')

        # Create notifications table
        await conn.execute('''
    CREATE TABLE IF NOT EXISTS notifications (
        notification_id INTEGER PRIMARY KEY,
        subscription_id INTEGER,
        notification_type TEXT,
        message TEXT,
        sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (subscription_id) REFERENCES subscriptions(subscription_id)
    )
    ''')

        await conn.commit()
