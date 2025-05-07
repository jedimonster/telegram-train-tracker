"""Common utilities for command handlers."""

import logging
from typing import Dict, Any, Optional, List

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, ConversationHandler
from train_stations import TRAIN_STATIONS

from ..database.operations import get_or_create_user
from ..utils.constants import ConversationState, CallbackPrefix, HELP_MESSAGE, WELCOME_MESSAGE
from ..utils.formatting import format_subscription_details
from ..utils.keyboards import create_subscription_confirmation_keyboard

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

def get_message_context(update: Update, context: ContextTypes.DEFAULT_TYPE, prefix: str) -> Dict[str, Any]:
    """Get or create message-specific context data."""
    message_id = update.message.message_id if update.message else update.callback_query.message.message_id
    context_key = f"{prefix}_{message_id}"
    
    if context_key not in context.user_data:
        context.user_data[context_key] = {}
    
    return context.user_data[context_key]

def clear_message_context(update: Update, context: ContextTypes.DEFAULT_TYPE, prefix: str) -> None:
    """Clear message-specific context data."""
    message_id = update.message.message_id if update.message else update.callback_query.message.message_id
    context_key = f"{prefix}_{message_id}"
    
    if context_key in context.user_data:
        del context.user_data[context_key]

def get_page_number(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Get the current page number for pagination."""
    message_id = update.message.message_id if update.message else update.callback_query.message.message_id
    return context.user_data.get(f"station_page_{message_id}", 0)

def set_page_number(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int) -> None:
    """Set the current page number for pagination."""
    message_id = update.message.message_id if update.message else update.callback_query.message.message_id
    context.user_data[f"station_page_{message_id}"] = page

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Send a message when the command /start is issued."""
    user = update.effective_user
    logger.debug(f"Command /start executed by user {user.id} ({user.username})")
    
    await get_or_create_user(
        user.id, user.username, user.first_name, user.last_name, user.language_code
    )
    
    # Create keyboard with main menu options
    from ..utils.keyboards import create_main_menu_keyboard
    keyboard = create_main_menu_keyboard()
    
    await update.message.reply_text(
        WELCOME_MESSAGE.format(first_name=user.first_name),
        reply_markup=keyboard
    )
    
    return ConversationState.MAIN_MENU

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Send help message with menu button."""
    user = update.effective_user
    logger.debug(f"Command /help executed by user {user.id} ({user.username})")
    
    # Create keyboard with return to menu
    keyboard_buttons = []
    keyboard_buttons.append([InlineKeyboardButton("Main Menu", callback_data=f"{CallbackPrefix.MENU}_main")])
    keyboard = InlineKeyboardMarkup(keyboard_buttons)
    
    await update.message.reply_text(HELP_MESSAGE, reply_markup=keyboard)
    return ConversationState.MAIN_MENU

async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle the /settings command."""
    user = update.effective_user
    logger.debug(f"Command /settings executed by user {user.id} ({user.username})")
    
    # Create keyboard with return to menu
    keyboard_buttons = []
    keyboard_buttons.append([InlineKeyboardButton("Main Menu", callback_data=f"{CallbackPrefix.MENU}_main")])
    keyboard = InlineKeyboardMarkup(keyboard_buttons)
    
    await update.message.reply_text(
        "Settings functionality will be implemented in a future version.",
        reply_markup=keyboard
    )
    logger.debug(f"Settings command completed for user {user.id}")
    return ConversationState.MAIN_MENU

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle errors by ending the conversation and notifying the user."""
    logger.error("Exception while handling an update:", exc_info=context.error)
    
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

def get_user_info(update: Update) -> Dict[str, Any]:
    """Get user information from update."""
    user = update.effective_user
    return {
        "id": user.id,
        "username": user.username,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "language_code": user.language_code
    }

def log_command(update: Update, command: str) -> None:
    """Log command execution."""
    user = update.effective_user
    logger.debug(f"Command /{command} executed by user {user.id} ({user.username})")

def log_callback(update: Update, callback_data: str) -> None:
    """Log callback query execution."""
    user = update.effective_user
    logger.debug(f"Callback executed by user {user.id} ({user.username}) with data: {callback_data}")

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel the current conversation."""
    if update.message:
        # Create keyboard with main menu options
        from ..utils.keyboards import create_main_menu_keyboard
        keyboard = create_main_menu_keyboard()
        
        await update.message.reply_text(
            "Operation cancelled. What would you like to do?",
            reply_markup=keyboard
        )
        return ConversationState.MAIN_MENU
    else:
        return ConversationHandler.END

async def back_to_favorites(update: Update, context: ContextTypes.DEFAULT_TYPE, prefix: str = None) -> int:
    """Return to favorites management."""
    query = update.callback_query
    await query.answer()
    # Import here to avoid circular imports
    from .favorites import favorites_command
    return await favorites_command(update, context)

async def back_to_train_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Return to train list."""
    query = update.callback_query
    await query.answer()
    
    status_context = get_message_context(update, context, "status")
    # Import here to avoid circular imports
    from .status_handlers_2 import get_future_train_status, get_current_train_status
    if status_context["type"] == "future":
        return await get_future_train_status(update, context)
    else:
        return await get_current_train_status(update, context)

def get_station_objects_by_ids(station_ids: List[str]) -> List[Dict[str, Any]]:
    """Convert a list of station IDs to a list of station objects."""
    return [station for station in TRAIN_STATIONS if station["id"] in station_ids]

async def subscribe_from_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start subscription process from status view."""
    query = update.callback_query
    await query.answer()
    
    # Extract train index
    train_index = int(query.data.split("_")[-1])
    
    # Get train details from status context
    status_context = get_message_context(update, context, "status")
    train_times = status_context["train_times"]
    if train_index >= len(train_times):
        await query.edit_message_text("Invalid train selection. Please try again.")
        return ConversationHandler.END
    
    departure_time, arrival_time, switches = train_times[train_index]
    
    # Store subscription details
    subscription_context = get_message_context(update, context, "subscription")
    subscription_context.update({
        "departure_station": status_context["departure_station"],
        "arrival_station": status_context["arrival_station"],
        "departure_time": departure_time,
        "day_of_week": status_context["date"]["day_of_week"] if "date" in status_context else None
    })
    
    # Show subscription confirmation
    message = format_subscription_details(subscription_context)
    keyboard = create_subscription_confirmation_keyboard()
    
    await query.edit_message_text(message, reply_markup=keyboard)
    return ConversationState.CONFIRM_SUBSCRIPTION
