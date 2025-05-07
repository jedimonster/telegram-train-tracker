"""Additional status command handlers for the train bot."""

from datetime import datetime, timedelta

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

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
    
    status_context = get_message_context(update, context, "status")
    
    try:
        # Handle back to train list request
        if query.data == f"{CallbackPrefix.STATUS}_back_to_times":
            if status_context["type"] == "future":
                return await get_future_train_status(update, context)
            else:
                return await get_current_train_status(update, context)
        
        # Extract train index
        train_index = int(query.data.split("_")[-1])
        
        # Get train details
        train_times = status_context["train_times"]
        if train_index >= len(train_times):
            await query.edit_message_text("Invalid train selection. Please try again.")
            return ConversationHandler.END
        
        departure_time, arrival_time, switches = train_times[train_index]
        
        # Get current time and format times
        now = datetime.now()
        departure_dt = datetime.fromisoformat(departure_time)
        arrival_dt = datetime.fromisoformat(arrival_time)
        
        try:
            # Get train status
            train_status = train_facade.get_delay_from_api(
                status_context["departure_station"]["id"],
                status_context["arrival_station"]["id"],
                departure_time
            )
            
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
            
        except train_facade.TrainNotFoundError:
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
        
        # Add subscription note
        message += (
            "\n\nTo receive automatic updates about this train, use the /subscribe command "
            "to set up a subscription for your regular trains."
        )
        
        # Create keyboard
        keyboard = create_train_details_keyboard(
            train_index,
            show_subscribe=status_context["type"] == "future"
        )
        
        await query.edit_message_text(message, reply_markup=keyboard)
        return ConversationState.SELECT_TIME
        
    except Exception as e:
        await query.edit_message_text(
            "Sorry, there was an error showing the train details. Please try again."
        )
        return ConversationHandler.END

async def refresh_train_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Refresh the train status."""
    query = update.callback_query
    await query.answer()
    
    try:
        # Extract train index and update data
        train_index = int(query.data.split("_")[-1])
        query.data = f"{CallbackPrefix.STATUS}_time_{train_index}"
        
        # Show updated details
        return await show_train_details(update, context)
        
    except Exception as e:
        await query.edit_message_text(
            "Sorry, there was an error refreshing the train status. Please try again."
        )
        return ConversationHandler.END
