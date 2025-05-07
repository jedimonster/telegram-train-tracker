"""Favorites command handlers for the train bot."""

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

from train_stations import TRAIN_STATIONS
from ..database.operations import (
    get_or_create_user,
    get_user_favorite_stations,
    add_favorite_station,
    remove_favorite_station
)
from ..utils.constants import ConversationState, CallbackPrefix
from ..utils.keyboards import (
    create_favorites_keyboard,
    create_paginated_stations_keyboard
)
from ..utils.formatting import format_favorites_list
from .common import (
    get_message_context,
    clear_message_context,
    get_page_number,
    set_page_number,
    log_command,
    log_callback,
    get_station_objects_by_ids
)

async def start_favorites_flow(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start the favorites flow from a callback query."""
    query = update.callback_query
    
    # Get user's favorite stations
    user = update.effective_user
    user_id = await get_or_create_user(
        user.id, user.username, user.first_name, user.last_name, user.language_code
    )
    favorite_station_ids = await get_user_favorite_stations(user_id)
    
    # Convert station IDs to station objects
    favorite_stations = get_station_objects_by_ids(favorite_station_ids)
    
    # Format message and create keyboard
    message = format_favorites_list(favorite_stations)
    keyboard = create_favorites_keyboard()
    
    # Edit message
    await query.edit_message_text(message, reply_markup=keyboard)
    
    return ConversationState.MANAGE_FAVORITES

async def favorites_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle the /favorites command to manage favorite stations."""
    log_command(update, "favorites")
    
    # Get user's favorite stations
    user = update.effective_user
    user_id = await get_or_create_user(
        user.id, user.username, user.first_name, user.last_name, user.language_code
    )
    favorite_station_ids = await get_user_favorite_stations(user_id)
    
    # Convert station IDs to station objects
    favorite_stations = get_station_objects_by_ids(favorite_station_ids)
    
    # Format message and create keyboard
    message = format_favorites_list(favorite_stations)
    keyboard = create_favorites_keyboard()
    
    # Send or edit message
    if update.message:
        await update.message.reply_text(message, reply_markup=keyboard)
    else:
        await update.callback_query.edit_message_text(message, reply_markup=keyboard)
    
    return ConversationState.MANAGE_FAVORITES

async def handle_favorite_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle the favorite action selection."""
    query = update.callback_query
    log_callback(update, query.data)
    await query.answer()
    
    if query.data == f"{CallbackPrefix.FAVORITE}_add":
        # Reset page number and show all stations
        set_page_number(update, context, 0)
        return await show_add_favorites(update, context)
    
    elif query.data == f"{CallbackPrefix.FAVORITE}_remove":
        return await show_remove_favorites(update, context)
    
    elif query.data == f"{CallbackPrefix.FAVORITE}_done":
        await query.edit_message_text("Favorites management completed.")
        return ConversationHandler.END

async def show_add_favorites(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Show all stations for adding to favorites."""
    query = update.callback_query
    
    # Get current page
    page = get_page_number(update, context)
    
    # Create keyboard
    keyboard = create_paginated_stations_keyboard(
        page,
        f"{CallbackPrefix.FAVORITE}_add"
    )
    
    # Update message
    await query.edit_message_text(
        f"Select a station to add to favorites (Page {page + 1}):", 
        reply_markup=keyboard
    )
    
    return ConversationState.ADD_FAVORITE

async def show_remove_favorites(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Show favorite stations for removal."""
    query = update.callback_query
    
    # Get user's favorite stations
    user = update.effective_user
    user_id = await get_or_create_user(
        user.id, user.username, user.first_name, user.last_name, user.language_code
    )
    favorite_station_ids = await get_user_favorite_stations(user_id)
    
    if not favorite_station_ids:
        await query.edit_message_text(
            "You don't have any favorite stations to remove.\n\n"
            "Use /favorites to manage your favorites."
        )
        return ConversationHandler.END
    
    # Convert station IDs to station objects
    favorite_stations = get_station_objects_by_ids(favorite_station_ids)
    
    # Create keyboard
    keyboard = create_paginated_stations_keyboard(
        0,  # No pagination for favorites
        f"{CallbackPrefix.FAVORITE}_remove",
        stations=favorite_stations
    )
    
    await query.edit_message_text(
        "Select a station to remove from favorites:", 
        reply_markup=keyboard
    )
    
    return ConversationState.REMOVE_FAVORITE

async def add_favorite_station_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Add a station to favorites."""
    query = update.callback_query
    await query.answer()
    
    # Handle pagination
    if query.data.startswith(f"{CallbackPrefix.PAGE}_"):
        parts = query.data.split("_")
        page = int(parts[-1])
        set_page_number(update, context, page)
        return await show_add_favorites(update, context)
    
    # Handle back to favorites
    if query.data.startswith(f"{CallbackPrefix.BACK}_"):
        return await favorites_command(update, context)
    
    # Extract station ID and add to favorites
    station_id = query.data.split("_")[-1]
    user = update.effective_user
    user_id = await get_or_create_user(
        user.id, user.username, user.first_name, user.last_name, user.language_code
    )
    
    # Find station name
    station_name = next(
        (station["english"] for station in TRAIN_STATIONS if station["id"] == station_id),
        "Unknown"
    )
    
    if await add_favorite_station(user_id, station_id):
        await query.edit_message_text(
            f"✅ Added {station_name} to your favorites.\n\n"
            "Use /favorites to manage your favorites."
        )
    else:
        await query.edit_message_text(
            "❌ Sorry, there was an error adding the station to your favorites."
        )
    
    return ConversationHandler.END

async def remove_favorite_station_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Remove a station from favorites."""
    query = update.callback_query
    await query.answer()
    
    # Handle done request
    if query.data == f"{CallbackPrefix.FAVORITE}_done":
        await query.edit_message_text("Favorites management completed.")
        return ConversationHandler.END
    
    # Extract station ID and remove from favorites
    station_id = query.data.split("_")[-1]
    user = update.effective_user
    user_id = await get_or_create_user(
        user.id, user.username, user.first_name, user.last_name, user.language_code
    )
    
    # Find station name
    station_name = next(
        (station["english"] for station in TRAIN_STATIONS if station["id"] == station_id),
        "Unknown"
    )
    
    if await remove_favorite_station(user_id, station_id):
        await query.edit_message_text(
            f"✅ Removed {station_name} from your favorites."
        )
        # Return to favorites management
        return await favorites_command(update, context)
    else:
        await query.edit_message_text(
            "❌ Sorry, there was an error removing the station from your favorites."
        )
        return ConversationHandler.END
