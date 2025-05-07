"""Status command handlers for the train bot."""

from datetime import datetime
from typing import Dict, Any

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

import train_facade
from train_stations import TRAIN_STATIONS
from ..database.operations import get_or_create_user, get_user_favorite_stations
from ..utils.constants import ConversationState, CallbackPrefix
from ..utils.keyboards import (
    create_status_action_keyboard,
    create_station_keyboard,
    create_paginated_stations_keyboard,
    create_date_selection_keyboard,
    create_train_times_keyboard,
    create_train_details_keyboard
)
from ..utils.formatting import format_train_details, format_train_times_header
from .common import (
    get_message_context,
    clear_message_context,
    get_page_number,
    set_page_number,
    log_command,
    log_callback,
    get_station_objects_by_ids
)

async def start_status_flow(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start the status flow from a callback query."""
    query = update.callback_query
    
    # Initialize status data with message-specific context
    status_context = get_message_context(update, context, "status")
    
    # Show status options
    keyboard = create_status_action_keyboard()
    await query.edit_message_text(
        "What would you like to check?", 
        reply_markup=keyboard
    )
    
    return ConversationState.SELECT_ACTION

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle the /status command to check train status."""
    log_command(update, "status")
    
    # Initialize status data with message-specific context
    status_context = get_message_context(update, context, "status")
    
    keyboard = create_status_action_keyboard()
    await update.message.reply_text(
        "What would you like to check?", reply_markup=keyboard
    )
    return ConversationState.SELECT_ACTION

async def check_train_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle the callback for checking train status."""
    query = update.callback_query
    log_callback(update, query.data)
    await query.answer()
    
    # Store the status type
    status_context = get_message_context(update, context, "status")
    status_context["type"] = "future" if query.data == f"{CallbackPrefix.STATUS}_future" else "current"
    
    # Show departure station selection
    return await select_status_departure_station(update, context)

async def select_status_departure_station(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Show departure station selection for status check."""
    # Get user's favorite stations
    user = update.effective_user
    user_id = await get_or_create_user(
        user.id, user.username, user.first_name, user.last_name, user.language_code
    )
    favorite_station_ids = await get_user_favorite_stations(user_id)
    
    # Convert station IDs to station objects
    favorite_stations = get_station_objects_by_ids(favorite_station_ids)
    
    # Create keyboard with favorite stations
    keyboard = create_station_keyboard(
        favorite_stations, 
        f"{CallbackPrefix.STATUS}_dep"
    )
    
    # Send or edit message
    if update.callback_query:
        await update.callback_query.edit_message_text(
            "Please select your departure station:", reply_markup=keyboard
        )
    else:
        await update.message.reply_text(
            "Please select your departure station:", reply_markup=keyboard
        )
    
    return ConversationState.SELECT_DEPARTURE

async def show_status_all_stations(update: Update, context: ContextTypes.DEFAULT_TYPE, prefix: str) -> int:
    """Show all stations for status selection."""
    query = update.callback_query
    await query.answer()
    
    # Get current page
    page = get_page_number(update, context)
    
    # Create keyboard
    keyboard = create_paginated_stations_keyboard(
        page,
        prefix,
        exclude_station_id=get_message_context(update, context, "status")
        .get("departure_station", {}).get("id")
    )
    
    # Update message
    await query.edit_message_text(
        f"Select a station (Page {page + 1}):", 
        reply_markup=keyboard
    )
    
    # Return appropriate state
    return (ConversationState.SELECT_DEPARTURE if prefix == f"{CallbackPrefix.STATUS}_dep"
            else ConversationState.SELECT_ARRIVAL)

async def handle_status_pagination(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle pagination for status station lists."""
    query = update.callback_query
    await query.answer()
    
    # Extract page number and prefix from callback data
    # Format: status_page_<prefix>_<page_number>
    parts = query.data.split("_")
    page = int(parts[-1])
    prefix = "_".join(parts[2:-1])  # Skip "status" and "page", take everything until the last part
    
    # Store the new page
    set_page_number(update, context, page)
    
    # Show the stations for this page
    return await show_status_all_stations(update, context, prefix)

async def select_status_arrival_station(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Show arrival station selection for status check."""
    query = update.callback_query
    await query.answer()
    
    status_context = get_message_context(update, context, "status")
    
    # Handle show all stations request
    if query.data == f"show_all_{CallbackPrefix.STATUS}_dep":
        set_page_number(update, context, 0)
        return await show_status_all_stations(update, context, f"{CallbackPrefix.STATUS}_dep")
    
    # Extract the station ID and store departure station
    if query.data.startswith(f"{CallbackPrefix.STATUS}_dep_"):
        station_id = query.data.split("_")[-1]
        for station in TRAIN_STATIONS:
            if station["id"] == station_id:
                status_context["departure_station"] = {
                    "id": station["id"],
                    "name": station["english"]
                }
                break
    
    # Get user's favorite stations
    user = update.effective_user
    user_id = await get_or_create_user(
        user.id, user.username, user.first_name, user.last_name, user.language_code
    )
    favorite_station_ids = await get_user_favorite_stations(user_id)
    
    # Convert station IDs to station objects
    favorite_stations = get_station_objects_by_ids(favorite_station_ids)
    
    # Create keyboard
    keyboard = create_station_keyboard(
        favorite_stations,
        f"{CallbackPrefix.STATUS}_arr",
        exclude_station_id=status_context["departure_station"]["id"]
    )
    
    await query.edit_message_text(
        f"Selected departure: {status_context['departure_station']['name']}\n"
        f"Please select your arrival station:",
        reply_markup=keyboard
    )
    
    return ConversationState.SELECT_ARRIVAL

# Continue with other status-related handlers...
# The file is getting long, so I'll create a status_handlers_2.py for the remaining handlers
