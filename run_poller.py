#!/usr/bin/env python
"""
Run Poller Script for Telegram Train Bot

This script demonstrates how to run the subscription poller in different modes:
1. As a continuous daemon process with a sleep interval
2. As a one-time check (suitable for cron jobs)
3. To send a test notification for a specific subscription

Usage:
    # Run as a daemon with 5-minute intervals
    python run_poller.py --daemon --interval 300
    
    # Run once and exit (for cron)
    python run_poller.py --once
    
    # Send test notification for subscription ID 123
    python run_poller.py --test-notification 123
    # Or using the short form
    python run_poller.py -t 123
"""

import argparse
import logging
import asyncio
import sys
import os
import json
import aiosqlite
from datetime import datetime

import train_bot.subscription_poller as subscription_poller
from load_env import init_env

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger("poller")
logger.setLevel(logging.DEBUG)



async def run_daemon(interval):
    """Run the poller as a daemon process with the specified interval."""
    logger.info(f"Starting poller daemon with {interval} second interval")
    
    try:
        while True:
            start_time = datetime.now()
            logger.info(f"Running poll at {start_time}")
            
            # Run the poller
            await subscription_poller.main()
            
            # Calculate how long to sleep
            elapsed = (datetime.now() - start_time).total_seconds()
            sleep_time = max(0, interval - elapsed)
            
            logger.info(f"Poll completed in {elapsed:.2f} seconds. Sleeping for {sleep_time:.2f} seconds.")
            await asyncio.sleep(sleep_time)
            
    except KeyboardInterrupt:
        logger.info("Poller daemon stopped by user")
    except Exception as e:
        logger.error(f"Error in poller daemon: {e}")
        sys.exit(1)


async def run_once():
    """Run the poller once and exit."""
    logger.info("Running poller once")
    
    try:
        await subscription_poller.main()
        logger.info("Poll completed successfully")
    except Exception as e:
        logger.error(f"Error in poller: {e}")
        sys.exit(1)


async def run_test_notification(subscription_id):
    """Run a test notification for a specific subscription."""
    logger.info(f"Running test notification for subscription ID {subscription_id}")
    
    try:
        # Connect to database
        async with aiosqlite.connect(subscription_poller.DB_PATH) as conn:
            # Get the subscription with user info
            async with conn.execute("""
            SELECT 
                s.subscription_id, s.user_id, u.telegram_id, 
                s.departure_station, s.arrival_station, 
                s.day_of_week, s.departure_time, s.last_status,
                u.notification_before_departure, u.notification_delay_threshold,
                u.notifications_paused
            FROM subscriptions s
            JOIN users u ON s.user_id = u.user_id
            WHERE s.subscription_id = ?
            """, (subscription_id,)) as cursor:
                subscription = await cursor.fetchone()
                
                if not subscription:
                    logger.error(f"Subscription ID {subscription_id} not found")
                    sys.exit(1)
                
                (
                    subscription_id, user_id, telegram_id, 
                    departure_station, arrival_station, 
                    day_of_week, departure_time, last_status,
                    notification_before_departure, notification_delay_threshold,
                    notifications_paused
                ) = subscription
                
                # Log detailed subscription information
                from src.train_bot.utils.date_utils import WEEKDAYS
                
                # Get station names for logging
                def get_station_name(station_id):
                    for station in subscription_poller.TRAIN_STATIONS:
                        if station["id"] == station_id:
                            return station["english"]
                    return "Unknown Station"
                
                logger.debug(f"Subscription {subscription_id} details:")
                logger.debug(f"  User ID: {user_id}, Telegram ID: {telegram_id}")
                logger.debug(f"  Route: {get_station_name(departure_station)} → {get_station_name(arrival_station)}")
                logger.debug(f"  Day of week: {day_of_week} ({WEEKDAYS(day_of_week).name})")
                logger.debug(f"  Departure time: {departure_time}")
                logger.debug(f"  Notification settings: {notification_before_departure} min before, {notification_delay_threshold} min threshold")
                logger.debug(f"  Notifications paused: {notifications_paused}")
                
                # Check for paused notifications
                if notifications_paused:
                    logger.warning(f"Notifications are paused for subscription ID {subscription_id}. Test notification will not be sent.")
                    logger.info("To test notifications, unpause notifications for this user first.")
                    return
                
                # Force notification by setting last_status to trigger a status change
                forced_status = json.dumps({"status": "unknown", "delay_minutes": 0})
                logger.debug("TEST MODE: Setting forced_status to trigger notification")
                
                # Set a large hours_before_departure value to bypass time check
                hours_before_departure = 48
                logger.debug(f"TEST MODE: Using hours_before_departure={hours_before_departure} to bypass time check")
                
                # Call check_subscription but don't update the database
                _, notifications_sent = await subscription_poller.check_subscription(
                    subscription_id, user_id, telegram_id, 
                    departure_station, arrival_station, 
                    day_of_week, departure_time, forced_status,
                    notification_before_departure, notification_delay_threshold,
                    hours_before_departure=hours_before_departure
                )
                
                if notifications_sent > 0:
                    logger.info(f"Test notification sent successfully for subscription ID {subscription_id}")
                else:
                    logger.warning(f"No notification sent for subscription ID {subscription_id}")
                    logger.debug(f"TEST MODE: No notification sent - see logs above for detailed reasons")
    
    except Exception as e:
        logger.exception(f"Error in test notification: {e}")
        sys.exit(1)


async def main():
    """Parse arguments and run the poller."""
    parser = argparse.ArgumentParser(description="Run the train subscription poller")
    
    # Create a mutually exclusive group for run mode
    mode_group = parser.add_mutually_exclusive_group(required=True)
    mode_group.add_argument(
        "--daemon", 
        action="store_true", 
        help="Run as a daemon process"
    )
    mode_group.add_argument(
        "--once", 
        action="store_true", 
        help="Run once and exit (suitable for cron jobs)"
    )
    mode_group.add_argument(
        "--test-notification", "-t",
        type=int,
        metavar="SUBSCRIPTION_ID",
        help="Send a test notification for the specified subscription ID"
    )
    
    # Add interval argument for daemon mode
    parser.add_argument(
        "--interval", 
        type=int, 
        default=30,  # 30 seconds default
        help="Polling interval in seconds (for daemon mode)"
    )
    
    # Parse arguments
    args = parser.parse_args()
    
    # Load environment variables
    if not init_env():
        logger.error("Failed to load required environment variables")
        logger.error("Please set TELEGRAM_BOT_TOKEN and RAIL_TOKEN environment variables")
        logger.error("You can create a .env file based on .env.template")
        sys.exit(1)
    
    # Run in the appropriate mode
    if args.daemon:
        logger.info("Running daemon")
        await run_daemon(args.interval)
    elif args.test_notification is not None:
        logger.info(f"Testing notification for subscription {args.test_notification}")
        await run_test_notification(args.test_notification)
    else:  # args.once
        logger.info("Running once")
        await run_once()


if __name__ == "__main__":
    logger.info("Starting")
    asyncio.run(main())
