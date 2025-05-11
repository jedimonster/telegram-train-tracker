"""Notification command handlers for the train bot."""

import logging
import json
from datetime import datetime, timedelta
import aiosqlite

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
import telegram.error

import train_facade
from ..database.operations import (
    get_or_create_user,
    update_notification_settings,
    get_subscription_by_id
)
from ..database.models import DB_PATH
from ..utils.formatting import format_train_details
from .common import log_command, log_callback
from train_stations import TRAIN_STATIONS

# Configure logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

async def pause_notifications_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Pause all notifications for the user."""
    log_command(update, "pause")
    
    # Get user ID
    user = update.effective_user
    user_id = await get_or_create_user(
        user.id, user.username, user.first_name, user.last_name, user.language_code
    )
    
    # Update notifications_paused flag
    if await update_notification_settings(user_id, paused=True):
        await update.message.reply_text(
            "✅ Notifications paused successfully. You will not receive any train updates "
            "until you resume notifications.\n\n"
            "Use /resume to resume notifications."
        )
    else:
        await update.message.reply_text(
            "❌ Sorry, there was an error pausing notifications. Please try again later."
        )

async def resume_notifications_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Resume notifications for the user."""
    log_command(update, "resume")
    
    # Get user ID
    user = update.effective_user
    user_id = await get_or_create_user(
        user.id, user.username, user.first_name, user.last_name, user.language_code
    )
    
    # Update notifications_paused flag
    if await update_notification_settings(user_id, paused=False):
        await update.message.reply_text(
            "✅ Notifications resumed successfully. You will now receive train updates as usual."
        )
    else:
        await update.message.reply_text(
            "❌ Sorry, there was an error resuming notifications. Please try again later."
        )

async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /settings command."""
    log_command(update, "settings")
    
    await update.message.reply_text(
        "Settings functionality will be implemented in a future version."
    )

async def refresh_notification_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the refresh button click from notification messages."""
    query = update.callback_query
    log_callback(update, query.data)
    
    try:
        # Extract subscription ID from callback data
        subscription_id = int(query.data.split("_")[-1])
        
        # Get subscription details
        subscription = await get_subscription_by_id(subscription_id)
        if not subscription:
            await query.answer("Subscription not found", show_alert=True)
            return
        
        # Get station names
        def get_station_name(station_id):
            for station in TRAIN_STATIONS:
                if station["id"] == station_id:
                    return station["english"]
            return "Unknown Station"
        
        departure_station_name = get_station_name(subscription["departure_station"])
        arrival_station_name = get_station_name(subscription["arrival_station"])
        
        # Create station objects for formatting
        departure_station_obj = {"name": departure_station_name, "id": subscription["departure_station"]}
        arrival_station_obj = {"name": arrival_station_name, "id": subscription["arrival_station"]}
        
        # Parse departure time (using the train on current/next day logic)
        departure_dt = datetime.fromisoformat(subscription["departure_time"])
        
        # Get the current day of week
        current_day = datetime.now().weekday()
        # Adjust for Sunday=0 in our system vs Monday=0 in Python's
        current_day = (current_day + 1) % 7
        
        # Check if this is the subscription's day or the next day
        day_of_week = subscription["day_of_week"]
        is_subscription_day = current_day == day_of_week
        
        # Get the appropriate date for the train
        if is_subscription_day:
            train_date = datetime.now().date()
        else:
            # Get the next occurrence of this day
            days_ahead = (day_of_week - current_day) % 7
            train_date = (datetime.now() + timedelta(days=days_ahead)).date()
        
        # Combine date and time
        train_datetime = datetime.combine(
            train_date,
            departure_dt.time()
        )
        
        # Format time for API
        api_time_format = train_datetime.strftime("%Y-%m-%dT%H:%M:%S")
        
        # Get updated train status from API
        train_times = None
        try:
            train_times = train_facade.get_delay_from_api(
                subscription["departure_station"],
                subscription["arrival_station"],
                api_time_format
            )
        except train_facade.TrainNotFoundError:
            await query.answer("Train schedule not found", show_alert=True)
            return
        except Exception as e:
            logger.error(f"API error: {e}")
            await query.answer("Error fetching train status", show_alert=True)
            return
        
        # Format updated message
        message = format_train_details(
            departure_station=departure_station_obj,
            arrival_station=arrival_station_obj,
            departure_time=departure_dt,
            arrival_time=train_times.get_updated_arrival(),
            switches=len(train_times.switch_stations) if train_times.switch_stations else 0,
            delay_minutes=train_times.delay_in_minutes,
            switch_stations=train_times.switch_stations,
            last_updated=datetime.now()
        )
        
        # Add notification context
        message += (
            "\n\n🔔 This is an updated status for your subscribed train.\n"
            "To manage your subscriptions, use the /subscriptions command."
        )
        
        # Create refresh keyboard
        callback_data = f"refresh_notif_{subscription_id}"
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Refresh", callback_data=callback_data)]
        ])
        
        # Update the message with new information
        try:
            await query.edit_message_text(
                message,
                reply_markup=keyboard
            )
            # Try to preserve fields from previous status
            try:
                prev_status = json.loads((await get_subscription_by_id(subscription_id))["last_status"] or "{}")
                # Keep important fields from previous status
                departure_reminder_sent = prev_status.get("departure_reminder_sent", False)
                last_notification_sent_at = prev_status.get("last_notification_sent_at")
            except (json.JSONDecodeError, TypeError):
                departure_reminder_sent = False
                last_notification_sent_at = None
                
            # Update status in database
            updated_status = {
                "status": "delayed" if train_times.delay_in_minutes > 0 else "on-time",
                "delay_minutes": train_times.delay_in_minutes,
                "updated_departure": train_times.get_updated_departure().isoformat(),
                "updated_arrival": train_times.get_updated_arrival().isoformat(),
                "switch_stations": train_times.switch_stations,
                "departure_reminder_sent": departure_reminder_sent  # Keep this flag if it was set
            }
            
            # Preserve notification tracking field if it exists
            if last_notification_sent_at:
                updated_status["last_notification_sent_at"] = last_notification_sent_at
            
            async with aiosqlite.connect(DB_PATH) as conn:
                await conn.execute(
                    "UPDATE subscriptions SET last_status = ?, last_checked = ? WHERE subscription_id = ?",
                    (json.dumps(updated_status), datetime.now().isoformat(), subscription_id)
                )
                await conn.commit()
            
        except telegram.error.BadRequest as e:
            # Handle case when content hasn't changed
            if "Message is not modified" in str(e):
                await query.answer("Train status is up to date", show_alert=True)
            else:
                # Re-raise if it's a different BadRequest error
                raise
    except Exception as e:
        logger.error(f"Error refreshing notification: {str(e)}", exc_info=e)
        await query.answer("Failed to refresh train status", show_alert=True)
