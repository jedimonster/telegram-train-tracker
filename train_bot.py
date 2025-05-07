#!/usr/bin/env python
"""
Telegram Train Information Bot

This bot allows users to check train information and subscribe to train updates.
It uses the existing train_facade.py to interact with the Israeli Rail API.
"""

import logging
import os
import sqlite3
from datetime import datetime, timedelta
import json
import sys

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

import train_facade
from train_stations import TRAIN_STATIONS, FAVORITE_TRAIN_STATIONS
from src.train_bot.utils.date_utils import WEEKDAYS, next_weekday
from load_env import init_env

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
# Set our loggers to DEBUG level, but keep library loggers at INFO
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Conversation states
(
    SELECT_ACTION,
    SELECT_DEPARTURE,
    SELECT_ARRIVAL,
    SELECT_DATE,
    SELECT_TIME,
    CONFIRM_SUBSCRIPTION,
    SELECT_SUBSCRIPTION,
    MANAGE_FAVORITES,
    SELECT_FAVORITE_ACTION,
    ADD_FAVORITE,
    REMOVE_FAVORITE,
) = range(11)

# Database setup
DB_PATH = "train_bot.db"


def setup_database():
    """Create the database tables if they don't exist."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Create users table
    cursor.execute('''
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
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS favorite_stations (
        id INTEGER PRIMARY KEY,
        user_id INTEGER,
        station_id TEXT,
        FOREIGN KEY (user_id) REFERENCES users(user_id),
        UNIQUE(user_id, station_id)
    )
    ''')

    # Create subscriptions table
    cursor.execute('''
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
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS notifications (
        notification_id INTEGER PRIMARY KEY,
        subscription_id INTEGER,
        notification_type TEXT,
        message TEXT,
        sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (subscription_id) REFERENCES subscriptions(subscription_id)
    )
    ''')

    conn.commit()
    conn.close()


def get_or_create_user(telegram_id, username=None, first_name=None, last_name=None, language_code=None):
    """Get a user from the database or create if not exists."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute(
        "SELECT user_id FROM users WHERE telegram_id = ?", (telegram_id,)
    )
    result = cursor.fetchone()

    if result:
        user_id = result[0]
    else:
        cursor.execute(
            "INSERT INTO users (telegram_id, username, first_name, last_name, language_code) VALUES (?, ?, ?, ?, ?)",
            (telegram_id, username, first_name, last_name, language_code),
        )
        conn.commit()
        user_id = cursor.lastrowid

    conn.close()
    return user_id


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    user = update.effective_user
    logger.debug(f"Command /start executed by user {user.id} ({user.username})")
    get_or_create_user(
        user.id, user.username, user.first_name, user.last_name, user.language_code
    )

    await update.message.reply_text(
        f"Hello {user.first_name}! I'm the Train Information Bot.\n\n"
        "I can help you check train status and subscribe to train updates.\n\n"
        "Available commands:\n"
        "/status - Check current or future train status\n"
        "/subscribe - Subscribe to train updates\n"
        "/mysubscriptions - View your subscriptions\n"
        "/unsubscribe - Cancel a subscription\n"
        "/favorites - Manage your favorite stations\n"
        "/settings - Configure notification preferences\n"
        "/pause - Pause all notifications\n"
        "/resume - Resume notifications\n"
        "/help - Show this help message\n\n"
        "To get started, try /status to check train times or /favorites to set up your favorite stations."
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /help is issued."""
    user = update.effective_user
    logger.debug(f"Command /help executed by user {user.id} ({user.username})")
    help_text = (
        "I can help you check train status and subscribe to train updates.\n\n"
        "Available commands:\n"
        "/start - Start the bot\n"
        "/help - Show this help message\n"
        "/status - Check current or future train status\n"
        "/subscribe - Subscribe to train updates\n"
        "/mysubscriptions - View your subscriptions\n"
        "/unsubscribe - Cancel a subscription\n"
        "/favorites - Manage your favorite stations\n"
        "/settings - Configure notification preferences\n"
        "/pause - Pause all notifications\n"
        "/resume - Resume notifications\n\n"
        "To get started, try /status to check train times or /favorites to set up your favorite stations."
    )
    await update.message.reply_text(help_text)


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle the /status command to check train status."""
    user = update.effective_user
    message_id = update.message.message_id
    logger.debug(f"Command /status executed by user {user.id} ({user.username})")
    
    # Initialize status data with message-specific key
    context.user_data[f"status_{message_id}"] = {}
    
    keyboard = [
        [
            InlineKeyboardButton("Check Future Train", callback_data="status_future"),
            InlineKeyboardButton("Check Current Train", callback_data="status_current"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "What would you like to check?", reply_markup=reply_markup
    )
    return SELECT_ACTION


async def subscribe_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle the /subscribe command to subscribe to train updates."""
    user = update.effective_user
    message_id = update.message.message_id
    logger.debug(f"Command /subscribe executed by user {user.id} ({user.username})")
    
    # Store an empty context for building the subscription with message-specific key
    context.user_data[f"subscription_{message_id}"] = {}
    
    # Show departure station selection
    return await select_departure_station(update, context)


async def get_user_favorite_stations(user_id):
    """Get a user's favorite stations from the database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute(
        """
        SELECT station_id FROM favorite_stations
        WHERE user_id = ?
        """,
        (user_id,)
    )
    
    favorite_station_ids = [row[0] for row in cursor.fetchall()]
    conn.close()
    
    # If the user has no favorites, use the default favorites
    if not favorite_station_ids:
        logger.info("No favorites found for user %s, falling back to default", user_id)
        # Sort default favorites alphabetically
        return sorted(FAVORITE_TRAIN_STATIONS, key=lambda x: x["english"])
    
    # Get the full station details for the favorite IDs
    favorite_stations = []
    for station in TRAIN_STATIONS:
        if station["id"] in favorite_station_ids:
            favorite_stations.append(station)
    
    # Sort favorite stations alphabetically by English name
    return sorted(favorite_stations, key=lambda x: x["english"])

async def select_departure_station(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Show departure station selection."""
    # Get user ID
    user = update.effective_user
    user_id = get_or_create_user(
        user.id, user.username, user.first_name, user.last_name, user.language_code
    )
    
    # Get user's favorite stations
    favorite_stations = await get_user_favorite_stations(user_id)
    
    # Create a keyboard with favorite stations
    keyboard = []
    for station in favorite_stations:
        keyboard.append(
            [InlineKeyboardButton(
                station["english"], 
                callback_data=f"dep_{station['id']}"
            )]
        )
    
    # Add a button to show all stations
    keyboard.append([InlineKeyboardButton("Show All Stations", callback_data="show_all_dep")])
    
    # Add a button to manage favorites
    keyboard.append([InlineKeyboardButton("Manage Favorites", callback_data="manage_favorites")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Determine if this is a new message or an edit
    if update.message:
        await update.message.reply_text(
            "Please select your departure station:", reply_markup=reply_markup
        )
    else:
        await update.callback_query.edit_message_text(
            "Please select your departure station:", reply_markup=reply_markup
        )
    
    return SELECT_DEPARTURE


async def show_all_stations(update: Update, context: ContextTypes.DEFAULT_TYPE, prefix="dep") -> int:
    """Show all stations for selection."""
    query = update.callback_query
    message_id = query.message.message_id
    await query.answer()
    
    # Get the current page from context or default to 0
    page = context.user_data.get(f"station_page_{message_id}", 0)
    
    # Sort stations alphabetically by English name
    sorted_stations = sorted(TRAIN_STATIONS, key=lambda x: x["english"])
    
    # Calculate pagination
    stations_per_page = 8
    start_idx = page * stations_per_page
    end_idx = start_idx + stations_per_page
    total_pages = (len(sorted_stations) + stations_per_page - 1) // stations_per_page
    
    # Create a keyboard with stations for this page
    keyboard = []
    for station in sorted_stations[start_idx:end_idx]:
        keyboard.append(
            [InlineKeyboardButton(
                station["english"], 
                callback_data=f"{prefix}_{station['id']}"
            )]
        )
    
    # Add navigation buttons
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("◀️ Previous", callback_data=f"page_{prefix}_{page-1}"))
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton("Next ▶️", callback_data=f"page_{prefix}_{page+1}"))
    
    if nav_buttons:
        keyboard.append(nav_buttons)
    
    # Add a back button
    keyboard.append([InlineKeyboardButton("Back to Favorites", callback_data=f"back_to_favorites_{prefix}")])
    
    # Update the message with the new keyboard
    await query.edit_message_text(
        f"Select a station (Page {page+1}/{total_pages}):", 
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    
    # Return the appropriate state based on the prefix
    if prefix == "dep":
        return SELECT_DEPARTURE
    elif prefix == "arr":
        return SELECT_ARRIVAL
    elif prefix == "add_fav":
        return ADD_FAVORITE
    elif prefix == "rem_fav":
        return REMOVE_FAVORITE

async def handle_pagination(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle pagination for station lists."""
    query = update.callback_query
    message_id = query.message.message_id
    await query.answer()
    
    # Extract page number and prefix from callback data
    # Format: page_<prefix>_<page_number> or page_<prefix1>_<prefix2>_<page_number>
    parts = query.data.split("_")
    
    # The first part is "page", the last part is the page number
    # Everything in between is the prefix
    page = int(parts[-1])
    prefix = "_".join(parts[1:-1])
    
    # Store the new page in context
    context.user_data[f"station_page_{message_id}"] = page
    
    # Show the stations for this page
    return await show_all_stations(update, context, prefix)

async def back_to_favorites(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Go back to the favorites selection."""
    query = update.callback_query
    message_id = query.message.message_id
    await query.answer()
    
    try:
        # Extract the prefix from callback data
        # Format: back_to_favorites_<prefix> or back_to_favorites_<prefix1>_<prefix2>
        parts = query.data.split("_")
        
        # The first three parts are "back_to_favorites", everything after is the prefix
        prefix = "_".join(parts[3:])
        
        # Reset the page
        context.user_data[f"station_page_{message_id}"] = 0
        
        # Return to the appropriate state
        if prefix == "dep":
            return await select_departure_station(update, context)
        elif prefix == "arr":
            return await select_arrival_station(update, context)
        elif prefix == "add_fav" or prefix == "rem_fav" or prefix.startswith("add_fav") or prefix.startswith("rem_fav"):
            return await favorites_command(update, context)
        else:
            # Default fallback
            logger.warning(f"Unknown prefix in back_to_favorites: {prefix}")
            return await favorites_command(update, context)
    except Exception as e:
        logger.error(f"Error in back_to_favorites: {e}")
        await query.edit_message_text(
            "Sorry, there was an error. Please try again using the main commands."
        )
        return ConversationHandler.END

async def select_arrival_station(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Show arrival station selection."""
    query = update.callback_query
    message_id = query.message.message_id
    await query.answer()
    
    # Check if this is a show all stations request
    if query.data == "show_all_dep":
        context.user_data[f"station_page_{message_id}"] = 0
        return await show_all_stations(update, context, "dep")
    
    # Check if this is a manage favorites request
    if query.data == "manage_favorites":
        return await favorites_command(update, context)
    
    # Extract the station ID from the callback data
    if query.data.startswith("dep_"):
        station_id = query.data[4:]  # Remove "dep_" prefix
        
        # Find the station in the list
        for station in TRAIN_STATIONS:
            if station["id"] == station_id:
                # Store the selected departure station
                context.user_data[f"subscription_{message_id}"]["departure_station"] = {
                    "id": station["id"],
                    "name": station["english"]
                }
                break
    
    # Get user ID
    user = update.effective_user
    user_id = get_or_create_user(
        user.id, user.username, user.first_name, user.last_name, user.language_code
    )
    
    # Get user's favorite stations
    favorite_stations = await get_user_favorite_stations(user_id)
    
    # Create a keyboard with favorite stations (excluding the departure station)
    keyboard = []
    for station in favorite_stations:
        if station["id"] != context.user_data[f"subscription_{message_id}"].get("departure_station", {}).get("id"):
            keyboard.append(
                [InlineKeyboardButton(
                    station["english"], 
                    callback_data=f"arr_{station['id']}"
                )]
            )
    
    # Add a button to show all stations
    keyboard.append([InlineKeyboardButton("Show All Stations", callback_data="show_all_arr")])
    
    # Add a button to manage favorites
    keyboard.append([InlineKeyboardButton("Manage Favorites", callback_data="manage_favorites")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        f"Selected departure: {context.user_data[f'subscription_{message_id}']['departure_station']['name']}\n"
        f"Please select your arrival station:", 
        reply_markup=reply_markup
    )
    
    return SELECT_ARRIVAL


async def select_day_of_week(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Show day of week selection."""
    query = update.callback_query
    message_id = query.message.message_id
    await query.answer()
    
    # Extract the station ID from the callback data
    if query.data.startswith("arr_"):
        station_id = query.data[4:]  # Remove "arr_" prefix
        
        # Find the station in the list
        for station in TRAIN_STATIONS:
            if station["id"] == station_id:
                # Store the selected arrival station
                context.user_data[f"subscription_{message_id}"]["arrival_station"] = {
                    "id": station["id"],
                    "name": station["english"]
                }
                break
    
    # Create a keyboard with days of the week
    keyboard = []
    for day_num, day_name in enumerate(WEEKDAYS._member_names_):
        keyboard.append([InlineKeyboardButton(day_name, callback_data=f"day_{day_num}")])
    
    # Add an "All Weekdays" button (Sunday to Thursday)
    keyboard.append([InlineKeyboardButton("All Weekdays (Sun-Thu)", callback_data="day_all_weekdays")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        f"Selected route: {context.user_data[f'subscription_{message_id}']['departure_station']['name']} → "
        f"{context.user_data[f'subscription_{message_id}']['arrival_station']['name']}\n"
        f"Please select the day of the week:", 
        reply_markup=reply_markup
    )
    
    return SELECT_DATE


async def select_time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Show time selection."""
    query = update.callback_query
    message_id = query.message.message_id
    await query.answer()
    
    # Extract the day from the callback data
    if query.data.startswith("day_"):
        if query.data == "day_all_weekdays":
            # Store that we're subscribing to all weekdays
            context.user_data[f"subscription_{message_id}"]["all_weekdays"] = True
            context.user_data[f"subscription_{message_id}"]["day_of_week"] = {
                "num": 0,  # Start with Sunday
                "name": "All Weekdays (Sun-Thu)"
            }
        else:
            day_num = int(query.data[4:])  # Remove "day_" prefix
            day_name = WEEKDAYS._member_names_[day_num]
            
            # Store the selected day
            context.user_data[f"subscription_{message_id}"]["day_of_week"] = {
                "num": day_num,
                "name": day_name
            }
            context.user_data[f"subscription_{message_id}"]["all_weekdays"] = False
    
    # Get available train times for this route on this day
    departure_id = context.user_data[f"subscription_{message_id}"]["departure_station"]["id"]
    arrival_id = context.user_data[f"subscription_{message_id}"]["arrival_station"]["id"]
    day_num = context.user_data[f"subscription_{message_id}"]["day_of_week"]["num"]
    
    try:
        train_times = train_facade.get_train_times(departure_id, arrival_id, day_num)
        
        # Create a keyboard with available times
        keyboard = []
        for departure_time, arrival_time, switches in train_times:
            # Format the time for display (assuming ISO format from API)
            departure_dt = datetime.fromisoformat(departure_time)
            formatted_time = departure_dt.strftime("%H:%M")
            
            keyboard.append([
                InlineKeyboardButton(
                    formatted_time, 
                    callback_data=f"time_{departure_time}"
                )
            ])
        
        if not keyboard:
            # No trains available
            await query.edit_message_text(
                f"No trains found for this route on {day_name}. "
                f"Please try a different day or route."
            )
            # Go back to day selection
            return SELECT_DATE
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            f"Selected route: {context.user_data[f'subscription_{message_id}']['departure_station']['name']} → "
            f"{context.user_data[f'subscription_{message_id}']['arrival_station']['name']}\n"
            f"Selected day: {context.user_data[f'subscription_{message_id}']['day_of_week']['name']}\n"
            f"Please select the departure time:", 
            reply_markup=reply_markup
        )
        
        return SELECT_TIME
        
    except Exception as e:
        logger.error(f"Error getting train times: {e}")
        await query.edit_message_text(
            f"Sorry, there was an error getting train times. Please try again later."
        )
        return ConversationHandler.END


async def confirm_subscription(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Confirm subscription details."""
    query = update.callback_query
    message_id = query.message.message_id
    await query.answer()
    
    # Extract the time from the callback data
    if query.data.startswith("time_"):
        time_str = query.data[5:]  # Remove "time_" prefix
        
        # Parse the time
        departure_dt = datetime.fromisoformat(time_str)
        formatted_time = departure_dt.strftime("%H:%M")
        
        # Store the selected time
        context.user_data[f"subscription_{message_id}"]["departure_time"] = {
            "raw": time_str,
            "formatted": formatted_time
        }
    
    # Create confirmation keyboard
    keyboard = [
        [
            InlineKeyboardButton("Confirm", callback_data="confirm_yes"),
            InlineKeyboardButton("Cancel", callback_data="confirm_no"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Format the subscription details
    subscription = context.user_data[f"subscription_{message_id}"]
    details = (
        f"Please confirm your subscription:\n\n"
        f"Route: {subscription['departure_station']['name']} → {subscription['arrival_station']['name']}\n"
        f"Day: {subscription['day_of_week']['name']}\n"
        f"Time: {subscription['departure_time']['formatted']}\n\n"
        f"You will receive notifications about this train's status every week."
    )
    
    await query.edit_message_text(details, reply_markup=reply_markup)
    
    return CONFIRM_SUBSCRIPTION


async def save_subscription(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Save the subscription to the database."""
    query = update.callback_query
    message_id = query.message.message_id
    await query.answer()
    
    if query.data == "confirm_yes":
        # Get user ID
        user = update.effective_user
        user_id = get_or_create_user(
            user.id, user.username, user.first_name, user.last_name, user.language_code
        )
        
        # Get subscription details
        subscription = context.user_data[f"subscription_{message_id}"]
        
        # Connect to database
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        try:
            # Check if this is an "All Weekdays" subscription
            if subscription.get("all_weekdays", False):
                # Create subscriptions for Sunday through Thursday (days 0-4)
                for day_num in range(5):  # 0=Sunday, 1=Monday, ..., 4=Thursday
                    day_name = WEEKDAYS._member_names_[day_num]
                    
                    # Insert subscription for this day
                    cursor.execute(
                        """
                        INSERT INTO subscriptions 
                        (user_id, departure_station, arrival_station, day_of_week, departure_time, 
                        start_date, active, last_status)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            user_id,
                            subscription["departure_station"]["id"],
                            subscription["arrival_station"]["id"],
                            day_num,
                            subscription["departure_time"]["raw"],
                            datetime.now().date().isoformat(),
                            1,
                            json.dumps({"status": "unknown"})
                        )
                    )
                
                conn.commit()
                
                await query.edit_message_text(
                    "✅ Subscriptions saved successfully!\n\n"
                    "You will now receive weekly updates about this train for all weekdays (Sunday-Thursday).\n"
                    "Use /mysubscriptions to view or manage your subscriptions."
                )
            else:
                # Insert a single subscription
                cursor.execute(
                    """
                    INSERT INTO subscriptions 
                    (user_id, departure_station, arrival_station, day_of_week, departure_time, 
                    start_date, active, last_status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        user_id,
                        subscription["departure_station"]["id"],
                        subscription["arrival_station"]["id"],
                        subscription["day_of_week"]["num"],
                        subscription["departure_time"]["raw"],
                        datetime.now().date().isoformat(),
                        1,
                        json.dumps({"status": "unknown"})
                    )
                )
                conn.commit()
                
                await query.edit_message_text(
                    "✅ Subscription saved successfully!\n\n"
                    "You will now receive weekly updates about this train.\n"
                    "Use /mysubscriptions to view or manage your subscriptions."
                )
            
        except Exception as e:
            logger.error(f"Error saving subscription: {e}")
            await query.edit_message_text(
                "❌ Sorry, there was an error saving your subscription. Please try again later."
            )
        finally:
            conn.close()
    else:
        await query.edit_message_text("Subscription cancelled.")
    
    # Clear the subscription data
    subscription_key = f"subscription_{message_id}"
    if subscription_key in context.user_data:
        del context.user_data[subscription_key]
    
    return ConversationHandler.END


async def my_subscriptions_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show user's subscriptions."""
    user = update.effective_user
    logger.debug(f"Command /mysubscriptions executed by user {user.id} ({user.username})")
    
    # Get user ID from database
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute(
        "SELECT user_id FROM users WHERE telegram_id = ?", (user.id,)
    )
    result = cursor.fetchone()
    
    if not result:
        await update.message.reply_text("You don't have any subscriptions yet.")
        conn.close()
        return
    
    user_id = result[0]
    
    # Get user's subscriptions
    cursor.execute(
        """
        SELECT subscription_id, departure_station, arrival_station, day_of_week, departure_time
        FROM subscriptions
        WHERE user_id = ? AND active = 1
        """,
        (user_id,)
    )
    subscriptions = cursor.fetchall()
    
    if not subscriptions:
        await update.message.reply_text("You don't have any active subscriptions.")
        conn.close()
        return
    
    # Format subscriptions
    response = "Your active subscriptions:\n\n"
    
    for sub_id, dep_station, arr_station, day_num, dep_time in subscriptions:
        # Get station names
        dep_name = "Unknown"
        arr_name = "Unknown"
        
        for station in TRAIN_STATIONS:
            if station["id"] == dep_station:
                dep_name = station["english"]
            if station["id"] == arr_station:
                arr_name = station["english"]
        
        # Get day name
        day_name = WEEKDAYS._member_names_[day_num]
        
        # Format time
        try:
            time_dt = datetime.fromisoformat(dep_time)
            formatted_time = time_dt.strftime("%H:%M")
        except:
            formatted_time = dep_time
        
        response += f"🚆 {dep_name} → {arr_name}\n"
        response += f"   Every {day_name} at {formatted_time}\n"
        response += f"   (ID: {sub_id})\n\n"
    
    response += "To unsubscribe, use /unsubscribe"
    
    await update.message.reply_text(response)
    conn.close()


async def unsubscribe_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle the /unsubscribe command."""
    user = update.effective_user
    logger.debug(f"Command /unsubscribe executed by user {user.id} ({user.username})")
    
    # Get user ID from database
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute(
        "SELECT user_id FROM users WHERE telegram_id = ?", (user.id,)
    )
    result = cursor.fetchone()
    
    if not result:
        await update.message.reply_text("You don't have any subscriptions to cancel.")
        conn.close()
        return ConversationHandler.END
    
    user_id = result[0]
    
    # Get user's subscriptions
    cursor.execute(
        """
        SELECT subscription_id, departure_station, arrival_station, day_of_week, departure_time
        FROM subscriptions
        WHERE user_id = ? AND active = 1
        """,
        (user_id,)
    )
    subscriptions = cursor.fetchall()
    conn.close()
    
    if not subscriptions:
        await update.message.reply_text("You don't have any active subscriptions to cancel.")
        return ConversationHandler.END
    
    # Create keyboard with subscriptions
    keyboard = []
    
    for sub_id, dep_station, arr_station, day_num, dep_time in subscriptions:
        # Get station names
        dep_name = "Unknown"
        arr_name = "Unknown"
        
        for station in TRAIN_STATIONS:
            if station["id"] == dep_station:
                dep_name = station["english"]
            if station["id"] == arr_station:
                arr_name = station["english"]
        
        # Get day name
        day_name = WEEKDAYS._member_names_[day_num]
        
        # Format time
        try:
            time_dt = datetime.fromisoformat(dep_time)
            formatted_time = time_dt.strftime("%H:%M")
        except:
            formatted_time = dep_time
        
        label = f"{dep_name} → {arr_name}, {day_name} {formatted_time}"
        keyboard.append([InlineKeyboardButton(label, callback_data=f"unsub_{sub_id}")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "Select a subscription to cancel:", reply_markup=reply_markup
    )
    
    return SELECT_SUBSCRIPTION


async def cancel_subscription(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel the selected subscription."""
    query = update.callback_query
    await query.answer()
    
    if query.data.startswith("unsub_"):
        subscription_id = int(query.data[6:])  # Remove "unsub_" prefix
        
        # Connect to database
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        try:
            # Update subscription to inactive
            cursor.execute(
                "UPDATE subscriptions SET active = 0 WHERE subscription_id = ?",
                (subscription_id,)
            )
            conn.commit()
            
            await query.edit_message_text("✅ Subscription cancelled successfully.")
            
        except Exception as e:
            logger.error(f"Error cancelling subscription: {e}")
            await query.edit_message_text(
                "❌ Sorry, there was an error cancelling your subscription. Please try again later."
            )
        finally:
            conn.close()
    
    return ConversationHandler.END


async def favorites_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle the /favorites command to manage favorite stations."""
    user = update.effective_user
    logger.debug(f"Command /favorites executed by user {user.id} ({user.username})")
    
    # Determine if this is a new command or a callback
    if update.message:
        message = update.message
    else:
        message = update.callback_query.message
        await update.callback_query.answer()
    
    # Get user ID
    user = update.effective_user
    user_id = get_or_create_user(
        user.id, user.username, user.first_name, user.last_name, user.language_code
    )
    
    # Get user's favorite stations
    favorite_stations = await get_user_favorite_stations(user_id)
    
    # Create a message with the current favorites
    favorites_text = "Your favorite stations:\n\n"
    if favorite_stations:
        for station in favorite_stations:
            favorites_text += f"• {station['english']} (ID: {station['id']})\n"
    else:
        favorites_text += "You don't have any favorite stations yet.\n"
    
    favorites_text += "\nWhat would you like to do?"
    
    # Create a keyboard with options
    keyboard = [
        [InlineKeyboardButton("Add Favorite", callback_data="add_favorite")],
        [InlineKeyboardButton("Remove Favorite", callback_data="remove_favorite")],
        [InlineKeyboardButton("Done", callback_data="favorites_done")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Send or edit the message
    if update.message:
        await message.reply_text(favorites_text, reply_markup=reply_markup)
    else:
        await message.edit_text(favorites_text, reply_markup=reply_markup)
    
    return MANAGE_FAVORITES

async def handle_favorite_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle the favorite action selection."""
    query = update.callback_query
    message_id = query.message.message_id
    await query.answer()
    
    if query.data == "add_favorite":
        # Reset the page
        context.user_data[f"station_page_{message_id}"] = 0
        
        # Show all stations for adding to favorites
        return await show_all_stations(update, context, "add_fav")
    
    elif query.data == "remove_favorite":
        # Get user ID
        user = update.effective_user
        user_id = get_or_create_user(
            user.id, user.username, user.first_name, user.last_name, user.language_code
        )
        
        # Get user's favorite stations
        favorite_stations = await get_user_favorite_stations(user_id)
        
        if not favorite_stations:
            await query.edit_message_text(
                "You don't have any favorite stations to remove.\n\n"
                "Use /favorites to manage your favorites."
            )
            return ConversationHandler.END
        
        # Create a keyboard with favorite stations to remove
        keyboard = []
        for station in favorite_stations:
            keyboard.append(
                [InlineKeyboardButton(
                    station["english"], 
                    callback_data=f"rem_fav_{station['id']}"
                )]
            )
        
        # Add a cancel button
        keyboard.append([InlineKeyboardButton("Cancel", callback_data="favorites_done")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "Select a station to remove from favorites:", 
            reply_markup=reply_markup
        )
        
        return REMOVE_FAVORITE
    
    elif query.data == "favorites_done":
        await query.edit_message_text("Favorites management completed.")
        return ConversationHandler.END

async def add_favorite_station(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Add a station to favorites."""
    query = update.callback_query
    await query.answer()
    
    # Check if this is a pagination request
    if query.data.startswith("page_"):
        return await handle_pagination(update, context)
    
    # Check if this is a back to favorites request
    if query.data.startswith("back_to_favorites_"):
        return await back_to_favorites(update, context)
    
    # Extract the station ID from the callback data
    if query.data.startswith("add_fav_"):
        station_id = query.data[8:]  # Remove "add_fav_" prefix
        
        # Get user ID
        user = update.effective_user
        user_id = get_or_create_user(
            user.id, user.username, user.first_name, user.last_name, user.language_code
        )
        
        # Add the station to favorites
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        try:
            cursor.execute(
                "INSERT OR IGNORE INTO favorite_stations (user_id, station_id) VALUES (?, ?)",
                (user_id, station_id)
            )
            conn.commit()
            
            # Find the station name
            station_name = "Unknown"
            for station in TRAIN_STATIONS:
                if station["id"] == station_id:
                    station_name = station["english"]
                    break
            
            await query.edit_message_text(
                f"✅ Added {station_name} to your favorites.\n\n"
                "Use /favorites to manage your favorites."
            )
            
        except Exception as e:
            logger.error(f"Error adding favorite station: {e}")
            await query.edit_message_text(
                "❌ Sorry, there was an error adding the station to your favorites."
            )
        finally:
            conn.close()
        
        return ConversationHandler.END

async def remove_favorite_station(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Remove a station from favorites."""
    query = update.callback_query
    await query.answer()
    
    # Check if this is a done request
    if query.data == "favorites_done":
        await query.edit_message_text("Favorites management completed.")
        return ConversationHandler.END
    
    # Extract the station ID from the callback data
    if query.data.startswith("rem_fav_"):
        station_id = query.data[8:]  # Remove "rem_fav_" prefix
        
        # Get user ID
        user = update.effective_user
        user_id = get_or_create_user(
            user.id, user.username, user.first_name, user.last_name, user.language_code
        )
        
        # Remove the station from favorites
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        try:
            cursor.execute(
                "DELETE FROM favorite_stations WHERE user_id = ? AND station_id = ?",
                (user_id, station_id)
            )
            conn.commit()
            
            # Find the station name
            station_name = "Unknown"
            for station in TRAIN_STATIONS:
                if station["id"] == station_id:
                    station_name = station["english"]
                    break
            
            # Show the updated favorites list
            await query.edit_message_text(
                f"✅ Removed {station_name} from your favorites."
            )
            
            # Return to the favorites management screen
            return await favorites_command(update, context)
            
        except Exception as e:
            logger.error(f"Error removing favorite station: {e}")
            await query.edit_message_text(
                "❌ Sorry, there was an error removing the station from your favorites."
            )
        finally:
            conn.close()
        
        return ConversationHandler.END

async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /settings command."""
    user = update.effective_user
    logger.debug(f"Command /settings executed by user {user.id} ({user.username})")
    
    await update.message.reply_text(
        "Settings functionality will be implemented in a future version."
    )
    logger.debug(f"Settings command completed for user {user.id}")

async def pause_notifications_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Pause all notifications for the user."""
    user = update.effective_user
    logger.debug(f"Command /pause executed by user {user.id} ({user.username})")
    
    # Get user ID from database
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Get user ID
        cursor.execute(
            "SELECT user_id FROM users WHERE telegram_id = ?", (user.id,)
        )
        result = cursor.fetchone()
        
        if not result:
            # Create user if not exists
            user_id = get_or_create_user(
                user.id, user.username, user.first_name, user.last_name, user.language_code
            )
        else:
            user_id = result[0]
        
        # Update notifications_paused flag
        cursor.execute(
            "UPDATE users SET notifications_paused = 1 WHERE user_id = ?",
            (user_id,)
        )
        conn.commit()
        
        await update.message.reply_text(
            "✅ Notifications paused successfully. You will not receive any train updates until you resume notifications.\n\n"
            "Use /resume to resume notifications."
        )
    except Exception as e:
        logger.error(f"Error pausing notifications: {e}")
        await update.message.reply_text(
            "❌ Sorry, there was an error pausing notifications. Please try again later."
        )
    finally:
        conn.close()

async def resume_notifications_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Resume notifications for the user."""
    user = update.effective_user
    logger.debug(f"Command /resume executed by user {user.id} ({user.username})")
    
    # Get user ID from database
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Get user ID
        cursor.execute(
            "SELECT user_id FROM users WHERE telegram_id = ?", (user.id,)
        )
        result = cursor.fetchone()
        
        if not result:
            # Create user if not exists
            user_id = get_or_create_user(
                user.id, user.username, user.first_name, user.last_name, user.language_code
            )
        else:
            user_id = result[0]
        
        # Update notifications_paused flag
        cursor.execute(
            "UPDATE users SET notifications_paused = 0 WHERE user_id = ?",
            (user_id,)
        )
        conn.commit()
        
        await update.message.reply_text(
            "✅ Notifications resumed successfully. You will now receive train updates as usual."
        )
    except Exception as e:
        logger.error(f"Error resuming notifications: {e}")
        await update.message.reply_text(
            "❌ Sorry, there was an error resuming notifications. Please try again later."
        )
    finally:
        conn.close()


async def check_train_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle the callback for checking train status."""
    query = update.callback_query
    message_id = query.message.message_id
    logger.debug(f"Callback check_train_status executed with data: {query.data}")
    await query.answer()
    
    # Store the status type
    if query.data == "status_future":
        context.user_data[f"status_{message_id}"]["type"] = "future"
    elif query.data == "status_current":
        context.user_data[f"status_{message_id}"]["type"] = "current"
    
    # Show departure station selection
    return await select_status_departure_station(update, context)

async def select_status_departure_station(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Show departure station selection for status check."""
    # Get user ID
    user = update.effective_user
    logger.debug(f"Callback select_status_departure_station executed for user {user.id}")
    user_id = get_or_create_user(
        user.id, user.username, user.first_name, user.last_name, user.language_code
    )
    
    # Get user's favorite stations
    favorite_stations = await get_user_favorite_stations(user_id)
    
    # Create a keyboard with favorite stations
    keyboard = []
    for station in favorite_stations:
        keyboard.append(
            [InlineKeyboardButton(
                station["english"], 
                callback_data=f"status_dep_{station['id']}"
            )]
        )
    
    # Add a button to show all stations
    keyboard.append([InlineKeyboardButton("Show All Stations", callback_data="status_show_all_dep")])
    
    # Add a button to manage favorites
    keyboard.append([InlineKeyboardButton("Manage Favorites", callback_data="status_manage_favorites")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Determine if this is a new message or an edit
    if update.callback_query:
        await update.callback_query.edit_message_text(
            "Please select your departure station:", reply_markup=reply_markup
        )
    else:
        await update.message.reply_text(
            "Please select your departure station:", reply_markup=reply_markup
        )
    
    return SELECT_DEPARTURE

async def show_status_all_stations(update: Update, context: ContextTypes.DEFAULT_TYPE, prefix="status_dep") -> int:
    """Show all stations for status selection."""
    query = update.callback_query
    logger.debug(f"Callback show_status_all_stations executed with prefix: {prefix}")
    await query.answer()
    
    # Get the current page from context or default to 0
    message_id = query.message.message_id
    page = context.user_data.get(f"station_page_{message_id}", 0)
    
    # Sort stations alphabetically by English name
    sorted_stations = sorted(TRAIN_STATIONS, key=lambda x: x["english"])
    
    # Calculate pagination
    stations_per_page = 8
    start_idx = page * stations_per_page
    end_idx = start_idx + stations_per_page
    total_pages = (len(sorted_stations) + stations_per_page - 1) // stations_per_page
    
    # Create a keyboard with stations for this page
    keyboard = []
    for station in sorted_stations[start_idx:end_idx]:
        keyboard.append(
            [InlineKeyboardButton(
                station["english"], 
                callback_data=f"{prefix}_{station['id']}"
            )]
        )
    
    # Add navigation buttons
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("◀️ Previous", callback_data=f"status_page_{prefix}_{page-1}"))
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton("Next ▶️", callback_data=f"status_page_{prefix}_{page+1}"))
    
    if nav_buttons:
        keyboard.append(nav_buttons)
    
    # Add a back button
    keyboard.append([InlineKeyboardButton("Back to Favorites", callback_data=f"status_back_to_favorites_{prefix}")])
    
    # Update the message with the new keyboard
    await query.edit_message_text(
        f"Select a station (Page {page+1}/{total_pages}):", 
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    
    # Return the appropriate state based on the prefix
    if prefix == "status_dep":
        return SELECT_DEPARTURE
    elif prefix == "status_arr":
        return SELECT_ARRIVAL

async def handle_status_pagination(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle pagination for status station lists."""
    query = update.callback_query
    message_id = query.message.message_id
    logger.debug(f"Callback handle_status_pagination executed with data: {query.data}")
    await query.answer()
    
    # Extract page number and prefix from callback data
    # Format: status_page_<prefix>_<page_number>
    _, _, prefix, page = query.data.split("_")
    page = int(page)
    
    # Store the new page in context
    context.user_data[f"station_page_{message_id}"] = page
    
    # Show the stations for this page
    return await show_status_all_stations(update, context, prefix)

async def back_to_status_favorites(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Go back to the favorites selection for status."""
    query = update.callback_query
    message_id = query.message.message_id
    logger.debug(f"Callback back_to_status_favorites executed with data: {query.data}")
    await query.answer()
    
    try:
        # Extract the prefix from callback data
        # Format: status_back_to_favorites_<prefix> or status_back_to_favorites_<prefix1>_<prefix2>
        parts = query.data.split("_")
        
        # The first four parts are "status_back_to_favorites", everything after is the prefix
        prefix = "_".join(parts[4:])
        
        # Reset the page
        context.user_data[f"station_page_{message_id}"] = 0
        
        # Return to the appropriate state
        if prefix == "status_dep":
            return await select_status_departure_station(update, context)
        elif prefix == "status_arr":
            return await select_status_arrival_station(update, context)
        else:
            # Default fallback
            logger.warning(f"Unknown prefix in back_to_status_favorites: {prefix}")
            return await select_status_departure_station(update, context)
    except Exception as e:
        logger.error(f"Error in back_to_status_favorites: {e}")
        await query.edit_message_text(
            "Sorry, there was an error. Please try again using the main commands."
        )
        return ConversationHandler.END

async def select_status_arrival_station(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Show arrival station selection for status check."""
    query = update.callback_query
    message_id = query.message.message_id
    logger.debug(f"Callback select_status_arrival_station executed with data: {query.data}")
    await query.answer()
    
    # Check if this is a show all stations request
    if query.data == "status_show_all_dep":
        context.user_data[f"station_page_{message_id}"] = 0
        return await show_status_all_stations(update, context, "status_dep")
    
    # Check if this is a manage favorites request
    if query.data == "status_manage_favorites":
        return await favorites_command(update, context)
    
    # Extract the station ID from the callback data
    if query.data.startswith("status_dep_"):
        station_id = query.data[11:]  # Remove "status_dep_" prefix
        
        # Find the station in the list
        for station in TRAIN_STATIONS:
            if station["id"] == station_id:
                # Store the selected departure station
                context.user_data[f"status_{message_id}"]["departure_station"] = {
                    "id": station["id"],
                    "name": station["english"]
                }
                break
    
    # Get user ID
    user = update.effective_user
    user_id = get_or_create_user(
        user.id, user.username, user.first_name, user.last_name, user.language_code
    )
    
    # Get user's favorite stations
    favorite_stations = await get_user_favorite_stations(user_id)
    
    # Create a keyboard with favorite stations (excluding the departure station)
    keyboard = []
    for station in favorite_stations:
        if station["id"] != context.user_data[f"status_{message_id}"].get("departure_station", {}).get("id"):
            keyboard.append(
                [InlineKeyboardButton(
                    station["english"], 
                    callback_data=f"status_arr_{station['id']}"
                )]
            )
    
    # Add a button to show all stations
    keyboard.append([InlineKeyboardButton("Show All Stations", callback_data="status_show_all_arr")])
    
    # Add a button to manage favorites
    keyboard.append([InlineKeyboardButton("Manage Favorites", callback_data="status_manage_favorites")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        f"Selected departure: {context.user_data[f'status_{message_id}']['departure_station']['name']}\n"
        f"Please select your arrival station:", 
        reply_markup=reply_markup
    )
    
    return SELECT_ARRIVAL

async def select_status_date(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Show date selection for future train status."""
    query = update.callback_query
    message_id = query.message.message_id
    logger.debug(f"Callback select_status_date executed with data: {query.data}")
    await query.answer()
    
    # Check if this is a show all stations request
    if query.data == "status_show_all_arr":
        context.user_data[f"station_page_{message_id}"] = 0
        return await show_status_all_stations(update, context, "status_arr")
    
    # Check if this is a manage favorites request
    if query.data == "status_manage_favorites":
        return await favorites_command(update, context)
    
    # Extract the station ID from the callback data
    if query.data.startswith("status_arr_"):
        station_id = query.data[11:]  # Remove "status_arr_" prefix
        
        # Find the station in the list
        for station in TRAIN_STATIONS:
            if station["id"] == station_id:
                # Store the selected arrival station
                context.user_data[f"status_{message_id}"]["arrival_station"] = {
                    "id": station["id"],
                    "name": station["english"]
                }
                break
    
    # If this is a current train status check, get the times now
    if context.user_data[f"status_{message_id}"]["type"] == "current":
        return await get_current_train_status(update, context)
    
    # For future train status, show date selection
    # Create a keyboard with dates (today and next 7 days)
    keyboard = []
    today = datetime.now().date()
    
    for i in range(8):  # Today + 7 days
        date = today + timedelta(days=i)
        date_str = date.strftime("%Y-%m-%d")
        display_date = date.strftime("%a, %b %d")  # e.g., "Mon, Jan 01"
        
        if i == 0:
            display_date = f"Today ({display_date})"
        elif i == 1:
            display_date = f"Tomorrow ({display_date})"
        
        keyboard.append([InlineKeyboardButton(display_date, callback_data=f"status_date_{date_str}")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        f"Selected route: {context.user_data[f'status_{message_id}']['departure_station']['name']} → "
        f"{context.user_data[f'status_{message_id}']['arrival_station']['name']}\n"
        f"Please select the date:", 
        reply_markup=reply_markup
    )
    
    return SELECT_DATE

async def get_future_train_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Show available train times for the selected date."""
    query = update.callback_query
    message_id = query.message.message_id
    logger.debug(f"Callback get_future_train_status executed with data: {query.data}")
    await query.answer()
    
    # Extract the date from the callback data
    if query.data.startswith("status_date_"):
        date_str = query.data[12:]  # Remove "status_date_" prefix
        date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
        
        # Store the selected date
        context.user_data[f"status_{message_id}"]["date"] = {
            "raw": date_str,
            "formatted": date_obj.strftime("%A, %B %d, %Y")
        }
    
    # Get the day of week (0=Sunday, 6=Saturday)
    day_of_week = date_obj.weekday()
    # Adjust for Sunday=0 in our system vs Monday=0 in Python's
    day_of_week = (day_of_week + 1) % 7
    
    # Get train times for the selected route and date
    departure_id = context.user_data[f"status_{message_id}"]["departure_station"]["id"]
    arrival_id = context.user_data[f"status_{message_id}"]["arrival_station"]["id"]
    
    try:
        train_times = train_facade.get_train_times(departure_id, arrival_id, day_of_week)
        
        if not train_times:
            await query.edit_message_text(
                f"No trains found for this route on {context.user_data[f'status_{message_id}']['date']['formatted']}.\n"
                f"Please try a different date or route."
            )
            return ConversationHandler.END
        
        # Store train times in context for later use
        context.user_data[f"status_{message_id}"]["train_times"] = train_times
        
        # Create a keyboard with available times (3 buttons per row)
        keyboard = []
        current_row = []
        
        for i, (departure_time, arrival_time, switches) in enumerate(train_times):
            # Format times
            departure_dt = datetime.fromisoformat(departure_time)
            arrival_dt = datetime.fromisoformat(arrival_time)
            formatted_departure = departure_dt.strftime("%H:%M")
            
            # Calculate duration
            duration = arrival_dt - departure_dt
            hours, remainder = divmod(duration.seconds, 3600)
            minutes, _ = divmod(remainder, 60)
            duration_str = f"{hours}h {minutes}m" if hours > 0 else f"{minutes}m"
            
            # Create button label with time and duration
            label = f"{formatted_departure} ({duration_str})"
            if switches > 0:
                label += f" - {switches + 1} trains"
            
            # Add button to current row
            current_row.append(InlineKeyboardButton(label, callback_data=f"status_time_{i}"))
            
            # If row has 3 buttons or this is the last item, add row to keyboard
            if len(current_row) == 3 or i == len(train_times) - 1:
                keyboard.append(current_row)
                current_row = []
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            f"🚆 Train Schedule\n\n"
            f"Route: {context.user_data[f'status_{message_id}']['departure_station']['name']} → "
            f"{context.user_data[f'status_{message_id}']['arrival_station']['name']}\n"
            f"Date: {context.user_data[f'status_{message_id}']['date']['formatted']}\n\n"
            f"Please select a train time:",
            reply_markup=reply_markup
        )
        
        return SELECT_TIME
        
    except Exception as e:
        logger.error(f"Error getting train times: {e}")
        await query.edit_message_text(
            f"Sorry, there was an error getting train times. Please try again later."
        )
        return ConversationHandler.END

async def show_future_train_details(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Show details for the selected future train."""
    query = update.callback_query
    message_id = query.message.message_id
    logger.debug(f"Callback show_future_train_details executed with data: {query.data}")
    await query.answer()
    
    try:
        # Check if this is a back to train list request
        if query.data == "status_back_to_times":
            return await back_to_train_list(update, context)
        
        # Extract the train index from the callback data
        if query.data.startswith("status_time_"):
            train_index = int(query.data[12:])  # Remove "status_time_" prefix
            
            # Get the selected train details
            train_times = context.user_data[f"status_{message_id}"]["train_times"]
            if train_index >= len(train_times):
                await query.edit_message_text("Invalid train selection. Please try again.")
                return ConversationHandler.END
            
            departure_time, arrival_time, switches = train_times[train_index]
            
            # Format times
            now = datetime.now()
            departure_dt = datetime.fromisoformat(departure_time)
            arrival_dt = datetime.fromisoformat(arrival_time)
            formatted_departure = departure_dt.strftime("%H:%M")
            formatted_arrival = arrival_dt.strftime("%H:%M")
            
            # Calculate duration
            duration = arrival_dt - departure_dt
            hours, remainder = divmod(duration.seconds, 3600)
            minutes, _ = divmod(remainder, 60)
            duration_str = f"{hours}h {minutes}m" if hours > 0 else f"{minutes}m"
            
            # Check if date is available in context, if not add today's date
            if "date" not in context.user_data[f"status_{message_id}"]:
                today = datetime.now().date()
                context.user_data[f"status_{message_id}"]["date"] = {
                    "raw": today.strftime("%Y-%m-%d"),
                    "formatted": today.strftime("%A, %B %d, %Y")
                }
            
            # Get train status information
            departure_id = context.user_data[f"status_{message_id}"]["departure_station"]["id"]
            arrival_id = context.user_data[f"status_{message_id}"]["arrival_station"]["id"]
            
            try:
                train_status = train_facade.get_delay_from_api(
                    departure_id, arrival_id, departure_time
                )
                
                delay_minutes = train_status.delay_in_minutes
                updated_departure = train_status.get_updated_departure().strftime("%H:%M")
                updated_arrival = train_status.get_updated_arrival().strftime("%H:%M")
                
                if delay_minutes > 0:
                    status_str = f"🔴 Delayed by {delay_minutes} minutes"
                    time_str = f"Updated departure: {updated_departure}\nUpdated arrival: {updated_arrival}"
                else:
                    status_str = "🟢 On time"
                    time_str = f"Departure: {formatted_departure}\nArrival: {formatted_arrival}"
                
                # Add information about station switches if applicable
                switches_str = ""
                if train_status.switch_stations:
                    switches_str = f"Changes: {', '.join(train_status.switch_stations)}\n"
                
            except train_facade.TrainNotFoundError:
                status_str = "⚪ Status unknown"
                time_str = f"Departure: {formatted_departure}\nArrival: {formatted_arrival}"
                switches_str = ""
            except Exception as e:
                logger.error(f"Error getting train status: {e}")
                status_str = "⚪ Status unknown"
                time_str = f"Departure: {formatted_departure}\nArrival: {formatted_arrival}"
                switches_str = ""
            
            # Store the current time as last updated
            last_updated = now.strftime("%H:%M:%S")
            context.user_data[f"status_{message_id}"]["last_updated"] = last_updated
            
            # Format the train details
            response = (
                f"🚆 Train Details\n\n"
                f"Route: {context.user_data[f'status_{message_id}']['departure_station']['name']} → "
                f"{context.user_data[f'status_{message_id}']['arrival_station']['name']}\n"
                f"Date: {context.user_data[f'status_{message_id}']['date']['formatted']}\n\n"
                f"Status: {status_str}\n"
                f"{time_str}\n"
                f"Duration: {duration_str}\n"
            )
            
            if switches > 0:
                response += f"Changes: {switches + 1} trains\n"
            
            if switches_str:
                response += f"{switches_str}"
            
            # Add last updated timestamp
            response += f"\nLast updated: {last_updated}"
            
            # Add a note about checking specific train status
            response += (
                "\n\nTo receive automatic updates about this train, use the /subscribe command "
                "to set up a subscription for your regular trains."
            )
            
            # Add subscribe, refresh, and back buttons
            keyboard = [
                [InlineKeyboardButton("🔔 Subscribe", callback_data=f"subscribe_train_{train_index}")],
                [InlineKeyboardButton("🔄 Refresh", callback_data=f"refresh_status_{train_index}")],
                [InlineKeyboardButton("Back to Train List", callback_data="status_back_to_times")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(response, reply_markup=reply_markup)
            return SELECT_TIME
    except Exception as e:
        logger.error(f"Error showing train details: {e}")
        await query.edit_message_text(
            "Sorry, there was an error showing the train details. Please try again."
        )
        return ConversationHandler.END

async def get_current_train_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Show available current train times for the selected route."""
    query = update.callback_query
    message_id = query.message.message_id
    logger.debug(f"Callback get_current_train_status executed with data: {query.data}")
    await query.answer()
    
    # Get the current date and time
    now = datetime.now()
    current_hour = now.strftime("%H:%M")
    
    # Get the day of week (0=Sunday, 6=Saturday)
    day_of_week = now.weekday()
    # Adjust for Sunday=0 in our system vs Monday=0 in Python's
    day_of_week = (day_of_week + 1) % 7
    
    # Get train times for the selected route and today
    departure_id = context.user_data[f"status_{message_id}"]["departure_station"]["id"]
    arrival_id = context.user_data[f"status_{message_id}"]["arrival_station"]["id"]
    
    try:
        train_times = train_facade.get_train_times(departure_id, arrival_id, day_of_week)
        
        if not train_times:
            await query.edit_message_text(
                f"No trains found for this route today.\n"
                f"Please try a different route."
            )
            return ConversationHandler.END
        
        # Filter for trains that are currently running or departing soon
        current_time = now.time()
        relevant_trains = []
        
        for departure_time, arrival_time, switches in train_times:
            departure_dt = datetime.fromisoformat(departure_time)
            arrival_dt = datetime.fromisoformat(arrival_time)
            
            # Check if the train is currently running or departing within the next 2 hours
            if (departure_dt.time() <= current_time <= arrival_dt.time() or
                (departure_dt.time() > current_time and 
                 (datetime.combine(now.date(), departure_dt.time()) - 
                  datetime.combine(now.date(), current_time)).seconds / 3600 <= 2)):
                relevant_trains.append((departure_time, arrival_time, switches))
        
        if not relevant_trains:
            await query.edit_message_text(
                f"No trains currently running or departing soon for this route.\n"
                f"Please try checking future trains instead."
            )
            return ConversationHandler.END
        
        # Store relevant trains in context for later use
        context.user_data[f"status_{message_id}"]["train_times"] = relevant_trains
        
        # Create a keyboard with available times (3 buttons per row)
        keyboard = []
        current_row = []
        
        for i, (departure_time, arrival_time, switches) in enumerate(relevant_trains):
            # Format times
            departure_dt = datetime.fromisoformat(departure_time)
            arrival_dt = datetime.fromisoformat(arrival_time)
            formatted_departure = departure_dt.strftime("%H:%M")
            
            # Calculate duration
            duration = arrival_dt - departure_dt
            hours, remainder = divmod(duration.seconds, 3600)
            minutes, _ = divmod(remainder, 60)
            duration_str = f"{hours}h {minutes}m" if hours > 0 else f"{minutes}m"
            
            # Check if the train is currently running
            is_running = departure_dt.time() <= current_time <= arrival_dt.time()
            status_indicator = "🚂" if is_running else "🕒"
            
            # Create button label with time and duration
            label = f"{status_indicator} {formatted_departure} ({duration_str})"
            if switches > 0:
                label += f" - {switches + 1} trains"
            
            # Add button to current row
            current_row.append(InlineKeyboardButton(label, callback_data=f"status_time_{i}"))
            
            # If row has 3 buttons or this is the last item, add row to keyboard
            if len(current_row) == 3 or i == len(relevant_trains) - 1:
                keyboard.append(current_row)
                current_row = []
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            f"🚆 Current Train Status\n\n"
            f"Route: {context.user_data[f'status_{message_id}']['departure_station']['name']} → "
            f"{context.user_data[f'status_{message_id}']['arrival_station']['name']}\n"
            f"Current time: {current_hour}\n\n"
            f"Please select a train time:\n"
            f"🚂 = Currently running\n"
            f"🕒 = Departing soon",
            reply_markup=reply_markup
        )
        
        return SELECT_TIME
        
    except Exception as e:
        logger.error(f"Error getting train times: {e}")
        await query.edit_message_text(
            f"Sorry, there was an error getting train times. Please try again later."
        )
        return ConversationHandler.END

async def back_to_train_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Go back to the train list."""
    query = update.callback_query
    message_id = query.message.message_id
    logger.debug(f"Callback back_to_train_list executed with data: {query.data}")
    await query.answer()
    
    # Check if this is a future or current train status
    if context.user_data[f"status_{message_id}"]["type"] == "future":
        return await get_future_train_status(update, context)
    else:
        return await get_current_train_status(update, context)

async def show_current_train_details(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Show details for the selected current train."""
    query = update.callback_query
    message_id = query.message.message_id
    logger.debug(f"Callback show_current_train_details executed with data: {query.data}")
    await query.answer()
    
    try:
        # Check if this is a back to train list request
        if query.data == "status_back_to_times":
            return await back_to_train_list(update, context)
        
        # Extract the train index from the callback data
        if query.data.startswith("status_time_"):
            train_index = int(query.data[12:])  # Remove "status_time_" prefix
            
            # Get the selected train details
            train_times = context.user_data[f"status_{message_id}"]["train_times"]
            if train_index >= len(train_times):
                await query.edit_message_text("Invalid train selection. Please try again.")
                return ConversationHandler.END
            
            departure_time, arrival_time, switches = train_times[train_index]
            
            # Get the current date and time
            now = datetime.now()
            current_time = now.time()
            
            # Format times
            departure_dt = datetime.fromisoformat(departure_time)
            arrival_dt = datetime.fromisoformat(arrival_time)
            formatted_departure = departure_dt.strftime("%H:%M")
            formatted_arrival = arrival_dt.strftime("%H:%M")
            
            # Check if the train is currently running
            is_running = departure_dt.time() <= current_time <= arrival_dt.time()
            
            # Get train status information
            departure_id = context.user_data[f"status_{message_id}"]["departure_station"]["id"]
            arrival_id = context.user_data[f"status_{message_id}"]["arrival_station"]["id"]
            
            try:
                train_status = train_facade.get_delay_from_api(
                    departure_id, arrival_id, departure_time
                )
                
                delay_minutes = train_status.delay_in_minutes
                updated_departure = train_status.get_updated_departure().strftime("%H:%M")
                updated_arrival = train_status.get_updated_arrival().strftime("%H:%M")
                
                if delay_minutes > 0:
                    status_str = f"🔴 Delayed by {delay_minutes} minutes"
                    time_str = f"Updated departure: {updated_departure}\nUpdated arrival: {updated_arrival}"
                else:
                    status_str = "🟢 On time"
                    time_str = f"Departure: {formatted_departure}\nArrival: {formatted_arrival}"
                
                # Add information about station switches if applicable
                switches_str = ""
                if train_status.switch_stations:
                    switches_str = f"Changes: {', '.join(train_status.switch_stations)}\n"
                
            except train_facade.TrainNotFoundError:
                status_str = "⚪ Status unknown"
                time_str = f"Departure: {formatted_departure}\nArrival: {formatted_arrival}"
                switches_str = ""
            except Exception as e:
                logger.error(f"Error getting train status: {e}")
                status_str = "⚪ Status unknown"
                time_str = f"Departure: {formatted_departure}\nArrival: {formatted_arrival}"
                switches_str = ""
            
            # Calculate duration
            duration = arrival_dt - departure_dt
            hours, remainder = divmod(duration.seconds, 3600)
            minutes, _ = divmod(remainder, 60)
            duration_str = f"{hours}h {minutes}m" if hours > 0 else f"{minutes}m"
            
            # Format the train details
            response = (
                f"🚆 Train Details\n\n"
                f"Route: {context.user_data[f'status_{message_id}']['departure_station']['name']} → "
                f"{context.user_data[f'status_{message_id}']['arrival_station']['name']}\n\n"
                f"Status: {status_str}\n"
                f"{time_str}\n"
                f"Duration: {duration_str}\n"
            )
            
            if switches > 0:
                response += f"Trains: {switches + 1}\n"
            
            if switches_str:
                response += f"{switches_str}"
            
            # Add a note about subscribing
            response += (
                "\nTo receive automatic updates about this train, use the /subscribe command "
                "to set up a subscription for your regular trains."
            )
            
            # Add a back button to return to the train list
            keyboard = [[InlineKeyboardButton("Back to Train List", callback_data="status_back_to_times")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(response, reply_markup=reply_markup)
            return SELECT_TIME
    except Exception as e:
        logger.error(f"Error showing train details: {e}")
        await query.edit_message_text(
            "Sorry, there was an error showing the train details. Please try again."
        )
        return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel and end the conversation."""
    # Get message ID from either message or callback query
    message_id = update.message.message_id if update.message else update.callback_query.message.message_id
    
    # Clear conversation-specific data
    status_key = f"status_{message_id}"
    subscription_key = f"subscription_{message_id}"
    if status_key in context.user_data:
        del context.user_data[status_key]
    if subscription_key in context.user_data:
        del context.user_data[subscription_key]
    
    if update.message:
        await update.message.reply_text("Operation cancelled.")
    else:
        await update.callback_query.edit_message_text("Operation cancelled.")
    
    return ConversationHandler.END


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle errors by ending the conversation and notifying the user."""
    logger.error("Exception while handling an update:", exc_info=context.error)
    
    # Get the exception info
    error_message = str(context.error)
    
    # Send a message to the user
    if update and isinstance(update, Update) and update.effective_message:
        text = (
            "Sorry, an error occurred while processing your request.\n"
            "The conversation has been reset. Please try again using one of the main commands:\n"
            "/status - Check train status\n"
            "/subscribe - Subscribe to train updates\n"
            "/favorites - Manage your favorite stations"
        )
        
        # If this is a callback query, edit the message
        if update.callback_query:
            await update.callback_query.edit_message_text(text)
        # Otherwise, send a new message
        else:
            await update.effective_message.reply_text(text)
    
    # End the conversation if it's active
    return ConversationHandler.END

def main() -> None:
    """Start the bot."""
    # Load environment variables
    if not init_env():
        logger.error("Failed to load required environment variables")
        logger.error("Please set TELEGRAM_BOT_TOKEN and RAIL_TOKEN environment variables")
        logger.error("You can create a .env file based on .env.template")
        sys.exit(1)

    
    # Create the database if it doesn't exist
    setup_database()
    
    # Create the Application
    application = Application.builder().token(os.environ["TELEGRAM_BOT_TOKEN"]).build()
    
    # Register the error handler
    application.add_error_handler(error_handler)

       # Add conversation handler for status command
    status_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("status", status_command)],
        allow_reentry=True,  # Allow multiple concurrent conversations
        states={
            SELECT_ACTION: [
                CallbackQueryHandler(check_train_status, pattern="^status_(future|current)$"),
            ],
            SELECT_DEPARTURE: [
                CallbackQueryHandler(select_status_arrival_station, pattern="^status_dep_"),
                CallbackQueryHandler(show_status_all_stations, pattern="^status_show_all_dep$"),
                CallbackQueryHandler(favorites_command, pattern="^status_manage_favorites$"),
                CallbackQueryHandler(handle_status_pagination, pattern="^status_page_"),
                CallbackQueryHandler(back_to_status_favorites, pattern="^status_back_to_favorites_"),
            ],
            SELECT_ARRIVAL: [
                CallbackQueryHandler(select_status_date, pattern="^status_arr_"),
                CallbackQueryHandler(lambda u, c: show_status_all_stations(u, c, "status_arr"), pattern="^status_show_all_arr$"),
                CallbackQueryHandler(favorites_command, pattern="^status_manage_favorites$"),
                CallbackQueryHandler(handle_status_pagination, pattern="^status_page_"),
                CallbackQueryHandler(back_to_status_favorites, pattern="^status_back_to_favorites_"),
            ],
            SELECT_DATE: [
                CallbackQueryHandler(get_future_train_status, pattern="^status_date_"),
            ],
            SELECT_TIME: [
                CallbackQueryHandler(show_future_train_details, pattern="^status_time_"),
                CallbackQueryHandler(show_current_train_details, pattern="^status_time_"),
                CallbackQueryHandler(back_to_train_list, pattern="^status_back_to_times$"),
                CallbackQueryHandler(refresh_train_status, pattern="^refresh_status_"),
                CallbackQueryHandler(subscribe_from_status, pattern="^subscribe_train_"),
            ],
            # Add MANAGE_FAVORITES state to handle favorites management from status flow
            MANAGE_FAVORITES: [
                CallbackQueryHandler(handle_favorite_action, pattern="^(add_favorite|remove_favorite|favorites_done)$"),
            ],
            ADD_FAVORITE: [
                CallbackQueryHandler(add_favorite_station, pattern="^add_fav_"),
                CallbackQueryHandler(handle_pagination, pattern="^page_"),
                CallbackQueryHandler(back_to_favorites, pattern="^back_to_favorites_"),
            ],
            REMOVE_FAVORITE: [
                CallbackQueryHandler(remove_favorite_station, pattern="^rem_fav_"),
                CallbackQueryHandler(remove_favorite_station, pattern="^favorites_done$"),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    
    # Add conversation handler for subscribe command
    subscribe_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("subscribe", subscribe_command)],
        allow_reentry=True,  # Allow multiple concurrent conversations
        states={
            SELECT_DEPARTURE: [
                CallbackQueryHandler(select_arrival_station, pattern="^dep_"),
                CallbackQueryHandler(show_all_stations, pattern="^show_all_dep$"),
                CallbackQueryHandler(favorites_command, pattern="^manage_favorites$"),
                CallbackQueryHandler(handle_pagination, pattern="^page_"),
                CallbackQueryHandler(back_to_favorites, pattern="^back_to_favorites_"),
            ],
            SELECT_ARRIVAL: [
                CallbackQueryHandler(select_day_of_week, pattern="^arr_"),
                CallbackQueryHandler(lambda u, c: show_all_stations(u, c, "arr"), pattern="^show_all_arr$"),
                CallbackQueryHandler(favorites_command, pattern="^manage_favorites$"),
                CallbackQueryHandler(handle_pagination, pattern="^page_"),
                CallbackQueryHandler(back_to_favorites, pattern="^back_to_favorites_"),
            ],
            SELECT_DATE: [
                CallbackQueryHandler(select_time, pattern="^day_"),
            ],
            SELECT_TIME: [
                CallbackQueryHandler(confirm_subscription, pattern="^time_"),
            ],
            CONFIRM_SUBSCRIPTION: [
                CallbackQueryHandler(save_subscription, pattern="^confirm_"),
            ],
            # Add MANAGE_FAVORITES state to handle favorites management from subscribe flow
            MANAGE_FAVORITES: [
                CallbackQueryHandler(handle_favorite_action, pattern="^(add_favorite|remove_favorite|favorites_done)$"),
            ],
            ADD_FAVORITE: [
                CallbackQueryHandler(add_favorite_station, pattern="^add_fav_"),
                CallbackQueryHandler(handle_pagination, pattern="^page_"),
                CallbackQueryHandler(back_to_favorites, pattern="^back_to_favorites_"),
            ],
            REMOVE_FAVORITE: [
                CallbackQueryHandler(remove_favorite_station, pattern="^rem_fav_"),
                CallbackQueryHandler(remove_favorite_station, pattern="^favorites_done$"),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    
    # Add conversation handler for unsubscribe command
    unsubscribe_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("unsubscribe", unsubscribe_command)],
        allow_reentry=True,  # Allow multiple concurrent conversations
        states={
            SELECT_SUBSCRIPTION: [
                CallbackQueryHandler(cancel_subscription, pattern="^unsub_"),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    # Add conversation handler for favorites command
    favorites_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("favorites", favorites_command)],
        allow_reentry=True,  # Allow multiple concurrent conversations
        states={
            MANAGE_FAVORITES: [
                CallbackQueryHandler(handle_favorite_action, pattern="^(add_favorite|remove_favorite|favorites_done)$"),
            ],
            ADD_FAVORITE: [
                CallbackQueryHandler(add_favorite_station, pattern="^add_fav_"),
                CallbackQueryHandler(handle_pagination, pattern="^page_"),
                CallbackQueryHandler(back_to_favorites, pattern="^back_to_favorites_"),
            ],
            REMOVE_FAVORITE: [
                CallbackQueryHandler(remove_favorite_station, pattern="^rem_fav_"),
                CallbackQueryHandler(remove_favorite_station, pattern="^favorites_done$"),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    
    # Add command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("mysubscriptions", my_subscriptions_command))
    application.add_handler(CommandHandler("settings", settings_command))
    application.add_handler(CommandHandler("pause", pause_notifications_command))
    application.add_handler(CommandHandler("resume", resume_notifications_command))
    
    # Add conversation handlers
    application.add_handler(status_conv_handler)
    application.add_handler(subscribe_conv_handler)
    application.add_handler(unsubscribe_conv_handler)
    application.add_handler(favorites_conv_handler)

    # Start the Bot
    application.run_polling()


async def refresh_train_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Refresh the train status."""
    query = update.callback_query
    message_id = query.message.message_id
    logger.debug(f"Callback refresh_train_status executed with data: {query.data}")
    await query.answer()
    
    try:
        # Extract the train index from the callback data
        if query.data.startswith("refresh_status_"):
            train_index = int(query.data[15:])  # Remove "refresh_status_" prefix
            
            # Simply call the show_future_train_details function with the same train index
            # We'll create a new callback query data with the train index
            context.user_data[f"callback_data_{message_id}"] = f"status_time_{train_index}"
            query.data = f"status_time_{train_index}"
            
            return await show_future_train_details(update, context)
    except Exception as e:
        logger.error(f"Error refreshing train status: {e}")
        await query.edit_message_text(
            "Sorry, there was an error refreshing the train status. Please try again."
        )
        return ConversationHandler.END

async def subscribe_from_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Subscribe to a train from the status view."""
    query = update.callback_query
    message_id = query.message.message_id
    logger.debug(f"Callback subscribe_from_status executed with data: {query.data}")
    await query.answer()
    
    try:
        # Extract the train index from the callback data
        if query.data.startswith("subscribe_train_"):
            train_index = int(query.data[15:])  # Remove "subscribe_train_" prefix
            
            # Get the selected train details
            train_times = context.user_data[f"status_{message_id}"]["train_times"]
            if train_index >= len(train_times):
                await query.edit_message_text("Invalid train selection. Please try again.")
                return ConversationHandler.END
            
            departure_time, arrival_time, switches = train_times[train_index]
            
            # Initialize subscription data with message-specific key
            context.user_data[f"subscription_{message_id}"] = {
                "departure_station": context.user_data[f"status_{message_id}"]["departure_station"],
                "arrival_station": context.user_data[f"status_{message_id}"]["arrival_station"],
                "departure_time": {
                    "raw": departure_time,
                    "formatted": datetime.fromisoformat(departure_time).strftime("%H:%M")
                }
            }
            
            # Show day of week selection
            return await select_day_of_week(update, context)
            
    except Exception as e:
        logger.error(f"Error subscribing from status: {e}")
        await query.edit_message_text(
            "Sorry, there was an error setting up your subscription. Please try again using the /subscribe command."
        )
        return ConversationHandler.END

 


if __name__ == "__main__":
    main()
