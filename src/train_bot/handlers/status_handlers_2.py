"""Additional status command handlers for the train bot."""

from datetime import datetime, timedelta
import logging

# Configure logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
import telegram.error

import train_facade
from train_stations import TRAIN_STATIONS
from ..utils.constants import ConversationState, CallbackPrefix
from ..utils.keyboards import (
    create_date_selection_keyboard,
    create_train_times_keyboard,
    create_train_details_keyboard
)
from ..utils.formatting import format_train_details, format_train_times_header
from .common import (
    get_message_context,
    clear_message_context,
    log_callback
)
from .status import show_status_all_stations

async def select_status_date(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Show date selection for future train status."""
    query = update.callback_query
    await query.answer()
    
    status_context = get_message_context(update, context, "status")
    
    # Handle show all stations request
    if query.data == f"show_all_{CallbackPrefix.STATUS}_arr":
        return await show_status_all_stations(update, context, f"{CallbackPrefix.STATUS}_arr")
    
    # Extract the station ID and store arrival station
    if query.data.startswith(f"{CallbackPrefix.STATUS}_arr_"):
        station_id = query.data.split("_")[-1]
        for station in TRAIN_STATIONS:
            if station["id"] == station_id:
                status_context["arrival_station"] = {
                    "id": station["id"],
                    "name": station["english"]
                }
                break
    
    # If this is a current train status check, get the times now
    if status_context["type"] == "current":
        return await get_current_train_status(update, context)
    
    # For future train status, show date selection
    keyboard = create_date_selection_keyboard()
    
    await query.edit_message_text(
        f"Selected route: {status_context['departure_station']['name']} → "
        f"{status_context['arrival_station']['name']}\n"
        f"Please select the date:",
        reply_markup=keyboard
    )
    
    return ConversationState.SELECT_DATE

async def get_future_train_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Show available train times for the selected date."""
    query = update.callback_query
    await query.answer()
    
    status_context = get_message_context(update, context, "status")
    
    # Extract the date from the callback data
    if query.data.startswith(f"{CallbackPrefix.STATUS}_date_"):
        date_str = query.data.split("_")[-1]
        date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
        
        # Store the selected date
        status_context["date"] = {
            "raw": date_str,
            "formatted": date_obj.strftime("%A, %B %d, %Y")
        }
    
    # Get the day of week (0=Sunday, 6=Saturday)
    day_of_week = date_obj.weekday()
    # Adjust for Sunday=0 in our system vs Monday=0 in Python's
    day_of_week = (day_of_week + 1) % 7
    
    # Add day of week to the context with a human-readable name
    day_names = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
    status_context["date"]["day_of_week"] = {
        "value": day_of_week,
        "name": day_names[day_of_week]
    }
    
    try:
        # Get train times
        train_times = train_facade.get_train_times(
            status_context["departure_station"]["id"],
            status_context["arrival_station"]["id"],
            day_of_week
        )
        
        if not train_times:
            await query.edit_message_text(
                f"No trains found for this route on {status_context['date']['formatted']}.\n"
                f"Please try a different date or route."
            )
            return ConversationHandler.END
        
        # Store train times
        status_context["train_times"] = train_times
        
        # Create keyboard
        keyboard = create_train_times_keyboard(train_times)
        
        # Create header
        header = format_train_times_header(
            status_context["departure_station"],
            status_context["arrival_station"],
            date=date_obj
        )
        
        await query.edit_message_text(header, reply_markup=keyboard)
        return ConversationState.SELECT_TIME
        
    except Exception as e:
        await query.edit_message_text(
            f"Sorry, there was an error getting train times. Please try again later."
        )
        return ConversationHandler.END

async def get_current_train_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Show available current train times for the selected route."""
    query = update.callback_query
    await query.answer()
    
    status_context = get_message_context(update, context, "status")
    
    # Get current time
    now = datetime.now()
    
    # Get the day of week
    day_of_week = (now.weekday() + 1) % 7  # Adjust for Sunday=0
    
    # Add day of week to the context with a human-readable name
    day_names = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
    # Make sure the date object exists
    if "date" not in status_context:
        status_context["date"] = {
            "raw": now.strftime("%Y-%m-%d"),
            "formatted": now.strftime("%A, %B %d, %Y")
        }
    
    # Add day of week information
    status_context["date"]["day_of_week"] = {
        "value": day_of_week,
        "name": day_names[day_of_week]
    }
    
    try:
        # Get train times
        train_times = train_facade.get_train_times(
            status_context["departure_station"]["id"],
            status_context["arrival_station"]["id"],
            day_of_week
        )
        
        if not train_times:
            await query.edit_message_text(
                f"No trains found for this route today.\n"
                f"Please try a different route."
            )
            return ConversationHandler.END
        
        # Filter for current and upcoming trains
        current_time = now.time()
        relevant_trains = []
        
        for departure_time, arrival_time, switches in train_times:
            departure_dt = datetime.fromisoformat(departure_time)
            arrival_dt = datetime.fromisoformat(arrival_time)
            
            # Include if currently running or departing within 2 hours
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
        
        # Store train times
        status_context["train_times"] = relevant_trains
        
        # Create keyboard
        keyboard = create_train_times_keyboard(relevant_trains, current_time=now)
        
        # Create header
        header = format_train_times_header(
            status_context["departure_station"],
            status_context["arrival_station"],
            current_time=now
        )
        
        await query.edit_message_text(header, reply_markup=keyboard)
        return ConversationState.SELECT_TIME
        
    except Exception as e:
        await query.edit_message_text(
            f"Sorry, there was an error getting train times. Please try again later."
        )
        return ConversationHandler.END

async def show_train_details(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Show details for the selected train."""
    query = update.callback_query
    await query.answer()
    
    user = update.effective_user
    logger.info(f"User {user.id} ({user.username}) requested train details with callback data: {query.data}")
    
    status_context = get_message_context(update, context, "status")
    logger.debug(f"Status context in show_train_details: {status_context}")
    
    try:
        # Handle back to train list request
        if query.data == f"{CallbackPrefix.STATUS}_back_to_times":
            logger.debug("Going back to train times list")
            if status_context["type"] == "future":
                return await get_future_train_status(update, context)
            else:
                return await get_current_train_status(update, context)
        
        # First check if there's a stored train index from refresh
        train_index = context.user_data.pop("selected_train_index", None)
        
        # If not, extract from callback data
        if train_index is None:
            train_index = int(query.data.split("_")[-1])
            
        logger.debug(f"Using train_index in show_train_details: {train_index}")
        
        # Get train details
        train_times = status_context.get("train_times", [])
        logger.debug(f"Train times available: {len(train_times)} trains")
        
        if train_index >= len(train_times):
            logger.error(f"Invalid train index: {train_index}, only {len(train_times)} trains available")
            await query.edit_message_text("Invalid train selection. Please try again.")
            return ConversationHandler.END
        
        departure_time, arrival_time, switches = train_times[train_index]
        logger.debug(f"Showing details for train: {departure_time} -> {arrival_time} with {switches} switches")
        
        # Get current time and format times
        now = datetime.now()
        departure_dt = datetime.fromisoformat(departure_time)
        arrival_dt = datetime.fromisoformat(arrival_time)
        
        try:
            # Get train status
            logger.debug(f"Fetching train status from API for departure: {departure_time}")
            logger.debug(f"Departure station: {status_context['departure_station']['id']}, Arrival station: {status_context['arrival_station']['id']}")
            
            train_status = train_facade.get_delay_from_api(
                status_context["departure_station"]["id"],
                status_context["arrival_station"]["id"],
                departure_time
            )
            logger.debug(f"API returned delay of {train_status.delay_in_minutes} minutes")
            
            # Format message
            message = format_train_details(
                status_context["departure_station"],
                status_context["arrival_station"],
                departure_dt,
                arrival_dt,
                switches,
                delay_minutes=train_status.delay_in_minutes,
                switch_stations=train_status.switch_stations,
                date=datetime.strptime(status_context["date"]["raw"], "%Y-%m-%d") if "date" in status_context else None,
                last_updated=now
            )
            
        except train_facade.TrainNotFoundError as tnf:
            logger.warning(f"Train not found in API: {str(tnf)}")
            # Format message without status
            message = format_train_details(
                status_context["departure_station"],
                status_context["arrival_station"],
                departure_dt,
                arrival_dt,
                switches,
                date=datetime.strptime(status_context["date"]["raw"], "%Y-%m-%d") if "date" in status_context else None,
                last_updated=now
            )
        except Exception as api_error:
            logger.error(f"Error getting train status from API: {str(api_error)}", exc_info=api_error)
            # Format message without status but mention the error
            message = format_train_details(
                status_context["departure_station"],
                status_context["arrival_station"],
                departure_dt,
                arrival_dt,
                switches,
                date=datetime.strptime(status_context["date"]["raw"], "%Y-%m-%d") if "date" in status_context else None,
                last_updated=now
            )
            message += f"\n\nNote: Could not retrieve current delay information due to an API error."
        
        # Add subscription note
        message += (
            "\n\nTo receive automatic updates about this train, use the /subscribe command "
            "to set up a subscription for your regular trains."
        )
        
        # Create keyboard
        keyboard = create_train_details_keyboard(
            train_index,
            show_subscribe=True,  # Always show subscribe for both current and future trains
            show_refresh=True     # Always show refresh for both current and future trains
        )
        
        logger.debug("Sending train details to user")
        try:
            await query.edit_message_text(message, reply_markup=keyboard)
        except telegram.error.BadRequest as e:
            # Handle case when content hasn't changed (common during refresh)
            if "Message is not modified" in str(e):
                logger.info("Message content unchanged, sending notification")
                await query.answer("No changes to train status", show_alert=True)
            else:
                # Re-raise if it's a different BadRequest error
                raise
        
        return ConversationState.SELECT_TIME
        
    except Exception as e:
        logger.error(f"Error showing train details: {str(e)}", exc_info=e)
        await query.edit_message_text(
            f"Sorry, there was an error showing the train details: {str(e)}. Please try again."
        )
        return ConversationHandler.END

async def refresh_train_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Refresh the train status."""
    query = update.callback_query
    await query.answer()
    
    user = update.effective_user
    logger.info(f"User {user.id} ({user.username}) clicked refresh button with callback data: {query.data}")
    
    try:
        # Extract train index
        train_index = int(query.data.split("_")[-1])
        logger.debug(f"Extracted train_index: {train_index}")
        
        status_context = get_message_context(update, context, "status")
        logger.debug(f"Status context: {status_context}")
        
        # Log train details before refreshing
        if "train_times" in status_context and train_index < len(status_context["train_times"]):
            departure_time, arrival_time, switches = status_context["train_times"][train_index]
            logger.debug(f"Refreshing train: {departure_time} -> {arrival_time} with {switches} switches")
        
        # Store train index in context instead of modifying query.data
        context.user_data["selected_train_index"] = train_index
        logger.debug(f"Stored train_index {train_index} in context.user_data")
        
        # Show updated details
        return await show_train_details(update, context)
        
    except Exception as e:
        logger.error(f"Error refreshing train status: {str(e)}", exc_info=e)
        await query.edit_message_text(
            f"Sorry, there was an error refreshing the train status: {str(e)}. Please try again."
        )
        return ConversationHandler.END
