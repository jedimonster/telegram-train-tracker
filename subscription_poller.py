#!/usr/bin/env python
"""
Subscription Poller for Telegram Train Bot

This script polls the train status for all active subscriptions and sends
notifications to users when there are changes or upcoming departures.
It is designed to be run as a scheduled task (e.g., via cron) or as a
daemon process.
"""

import logging
import os
import aiosqlite
import json
from datetime import datetime, timedelta
import time
import sys
import asyncio

import telegram
from telegram.error import TelegramError
from telegram.ext import ApplicationBuilder

import train_facade
from train_stations import TRAIN_STATIONS
from src.train_bot.utils.date_utils import WEEKDAYS, next_weekday
from load_env import init_env

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
# Set our loggers to DEBUG level, but keep library loggers at INFO
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Database path
DB_PATH = "train_bot.db"

# Initialize environment variables
init_env()

# Telegram bot token
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")

# Global bot instance
_bot = None

# Initialize bot in async context
async def get_bot():
    """Get a shared instance of the Telegram bot."""
    global _bot
    if _bot is None:
        # Initialize with default connection pool settings for v20+
        # which has better defaults than the previous versions
        _bot = telegram.Bot(token=TELEGRAM_TOKEN)
    return _bot

logger.info("Starting bot")

def get_station_name(station_id):
    """Get the English name of a station by its ID."""
    for station in TRAIN_STATIONS:
        if station["id"] == station_id:
            return station["english"]
    return "Unknown Station"


async def check_subscription(subscription_id, user_id, telegram_id, departure_station, 
                           arrival_station, day_of_week, departure_time, 
                           last_status_json, notification_before_departure, 
                           notification_delay_threshold, notifications_paused=False):
    """
    Check a single subscription for status changes and send notifications if needed.
    
    Args:
        subscription_id: The ID of the subscription
        user_id: The database user ID
        telegram_id: The Telegram user ID
        departure_station: The departure station ID
        arrival_station: The arrival station ID
        day_of_week: The day of the week (0-6, where 0 is Sunday)
        departure_time: The departure time string
        last_status_json: JSON string of the last known status
        notification_before_departure: Minutes before departure to notify
        notification_delay_threshold: Minimum delay minutes to trigger notification
    
    Returns:
        tuple: (updated_status_json, notifications_sent)
    """
    try:
        # Parse the departure time
        departure_dt = datetime.fromisoformat(departure_time)
        
        # Get the current day of week
        current_day = datetime.now().weekday()
        # Adjust for Sunday=0 in our system vs Monday=0 in Python's
        current_day = (current_day + 1) % 7
        
        # Check if this is the subscription's day or the day before
        is_subscription_day = current_day == day_of_week
        is_day_before = (current_day + 1) % 7 == day_of_week
        
        # If it's not the subscription day or the day before, no need to check
        if not (is_subscription_day or is_day_before):
            return last_status_json, 0
        
        # Get the next occurrence of this train
        if is_subscription_day:
            train_date = datetime.now().date()
        else:  # is_day_before
            train_date = (datetime.now() + timedelta(days=1)).date()
        
        # Combine date and time
        train_datetime = datetime.combine(
            train_date,
            departure_dt.time()
        )
        
        # If the train has already departed today, no need to check
        if is_subscription_day and train_datetime < datetime.now():
            return last_status_json, 0
        
        # Time until departure
        time_until_departure = train_datetime - datetime.now()
        hours_until_departure = time_until_departure.total_seconds() / 3600
        
        # Parse the last status
        try:
            last_status = json.loads(last_status_json)
        except (json.JSONDecodeError, TypeError):
            last_status = {"status": "unknown", "delay_minutes": 0}
        
        # Check current status
        notifications_sent = 0
        current_status = {"status": "unknown", "delay_minutes": 0}
        
        # Only check status if within 1 hours of departure
        if hours_until_departure <= 1:
            try:
                # Format time for API
                api_time_format = train_datetime.strftime("%Y-%m-%dT%H:%M:%S")
                
                logger.info("Checking updates for subscription %s for train on %s", subscription_id, train_datetime)
                # Get train status from facade
                train_times = train_facade.get_delay_from_api(
                    departure_station, arrival_station, api_time_format
                )
                
                # Update current status
                current_status = {
                    "status": "delayed" if train_times.delay_in_minutes > 0 else "on-time",
                    "delay_minutes": train_times.delay_in_minutes,
                    "updated_departure": train_times.get_updated_departure().isoformat(),
                    "updated_arrival": train_times.get_updated_arrival().isoformat(),
                    "switch_stations": train_times.switch_stations
                }
                
                # Check for status changes that require notification
                status_changed = (
                    last_status.get("status") != current_status["status"] or
                    abs(last_status.get("delay_minutes", 0) - current_status["delay_minutes"]) >= notification_delay_threshold
                )

                logger.info("Subscription %s prevStatus: %s currStatus: %s", subscription_id, last_status["status"], current_status["status"])
                
                # Send notification if status changed significantly and notifications are not paused
                if status_changed and not notifications_paused:
                    dep_name = get_station_name(departure_station)
                    arr_name = get_station_name(arrival_station)
                    
                    if current_status["status"] == "delayed":
                        message = (
                            f"🚨 Train Update: {dep_name} → {arr_name}\n"
                            f"Scheduled: {departure_dt.strftime('%H:%M')}\n"
                            f"Status: Delayed by {current_status['delay_minutes']} minutes\n"
                            f"New departure: {datetime.fromisoformat(current_status['updated_departure']).strftime('%H:%M')}"
                        )
                    else:
                        message = (
                            f"✅ Train Update: {dep_name} → {arr_name}\n"
                            f"Scheduled: {departure_dt.strftime('%H:%M')}\n"
                            f"Status: On time"
                        )
                    
                    # Add information about station switches if applicable
                    if current_status.get("switch_stations"):
                        switches = current_status["switch_stations"]
                        message += f"\n\n⚠️ Note: This journey requires changing trains at: {', '.join(switches)}"
                    
                    # Send the message
                    bot = await get_bot()
                    await bot.send_message(chat_id=telegram_id, text=message)
                    notifications_sent += 1
                    
                    # Log the notification
                    async with aiosqlite.connect(DB_PATH) as conn:
                        await conn.execute(
                            "INSERT INTO notifications (subscription_id, notification_type, message) VALUES (?, ?, ?)",
                            (subscription_id, "status_change", message)
                        )
                        await conn.commit()
                elif status_changed and notifications_paused:
                    logger.info(f"Status change for subscription {subscription_id} not sent - notifications paused")
                
                # Check if we need to send a departure reminder
                minutes_until_departure = time_until_departure.total_seconds() / 60
                should_send_reminder = (
                    notification_before_departure <= minutes_until_departure <= notification_before_departure + 5 and
                    "departure_reminder_sent" not in last_status and
                    not notifications_paused
                )
                
                if should_send_reminder:
                    dep_name = get_station_name(departure_station)
                    arr_name = get_station_name(arrival_station)
                    
                    message = (
                        f"🔔 Departure Reminder: {dep_name} → {arr_name}\n"
                        f"Scheduled departure: {departure_dt.strftime('%H:%M')}\n"
                    )
                    
                    if current_status["status"] == "delayed":
                        message += (
                            f"Status: Delayed by {current_status['delay_minutes']} minutes\n"
                            f"New departure: {datetime.fromisoformat(current_status['updated_departure']).strftime('%H:%M')}"
                        )
                    else:
                        message += "Status: On time"
                    
                    # Send the message
                    bot = await get_bot()
                    await bot.send_message(chat_id=telegram_id, text=message)
                    notifications_sent += 1
                    
                    # Mark that we've sent the departure reminder
                    current_status["departure_reminder_sent"] = True
                    
                    # Log the notification
                    async with aiosqlite.connect(DB_PATH) as conn:
                        await conn.execute(
                            "INSERT INTO notifications (subscription_id, notification_type, message) VALUES (?, ?, ?)",
                            (subscription_id, "departure_reminder", message)
                        )
                        await conn.commit()
                elif (notification_before_departure <= minutes_until_departure <= notification_before_departure + 5 and
                      "departure_reminder_sent" not in last_status and notifications_paused):
                    logger.info(f"Departure reminder for subscription {subscription_id} not sent - notifications paused")
                    # Still mark as sent so we don't keep checking
                    current_status["departure_reminder_sent"] = True
                
            except train_facade.TrainNotFoundError:
                logger.warning(f"Train not found for subscription {subscription_id}")
                current_status = {"status": "not_found", "delay_minutes": 0}
            except Exception as e:
                logger.error(f"Error checking train status for subscription {subscription_id}: {e}")
                # Keep the last status in case of error
                current_status = last_status
        
        # Return the updated status
        return json.dumps(current_status), notifications_sent
        
    except Exception as e:
        logger.error(f"Error in check_subscription for {subscription_id}: {e}")
        return last_status_json, 0


async def poll_subscriptions():
    """Poll all active subscriptions and send notifications if needed."""
    try:
        # Connect to database
        async with aiosqlite.connect(DB_PATH) as conn:
            # Get all active subscriptions with user info
            async with conn.execute("""
            SELECT 
                s.subscription_id, s.user_id, u.telegram_id, 
                s.departure_station, s.arrival_station, 
                s.day_of_week, s.departure_time, s.last_status,
                u.notification_before_departure, u.notification_delay_threshold
            FROM subscriptions s
            JOIN users u ON s.user_id = u.user_id
            WHERE s.active = 1
        """) as cursor:
                subscriptions = await cursor.fetchall()
                logger.info(f"Checking {len(subscriptions)} active subscriptions")
                
                total_notifications = 0
                
                # Check each subscription
                for subscription in subscriptions:
                    (
                        subscription_id, user_id, telegram_id, 
                        departure_station, arrival_station, 
                        day_of_week, departure_time, last_status,
                        notification_before_departure, notification_delay_threshold
                    ) = subscription
                    
                    # Check this subscription
                    updated_status, notifications_sent = await check_subscription(
                        subscription_id, user_id, telegram_id, 
                        departure_station, arrival_station, 
                        day_of_week, departure_time, last_status,
                        notification_before_departure, notification_delay_threshold,
                        False  # Default to notifications not paused
                    )
                    
                    total_notifications += notifications_sent
                    
                    # Update the last status and check time
                    await conn.execute(
                        """
                        UPDATE subscriptions 
                        SET last_status = ?, last_checked = ? 
                        WHERE subscription_id = ?
                        """,
                        (updated_status, datetime.now().isoformat(), subscription_id)
                    )
                    await conn.commit()
                logger.info(f"Polling complete. Sent {total_notifications} notifications.")
        
    except Exception as e:
        logger.error(f"Error in poll_subscriptions: {e}")
    finally:
        if 'conn' in locals():
            await conn.close()


async def main():
    """Main function to run the poller."""
    logger.info("Starting subscription poller")
    
    try:
        # Load environment variables
        if not init_env():
            logger.error("Failed to load required environment variables")
            logger.error("Please set TELEGRAM_BOT_TOKEN and RAIL_TOKEN environment variables")
            logger.error("You can create a .env file based on .env.template")
            sys.exit(1)
        
        # Check if the database exists
        if not os.path.exists(DB_PATH):
            logger.error(f"Database file {DB_PATH} not found")
            return
        
        # Check if the bot token is set
        if not TELEGRAM_TOKEN:
            logger.error("TELEGRAM_BOT_TOKEN environment variable not set")
            return
        
        # Poll subscriptions
        await poll_subscriptions()
        
    except Exception as e:
        logger.error(f"Error in main: {e}")


if __name__ == "__main__":
    asyncio.run(main())
