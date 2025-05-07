"""Menu handlers for the train bot."""

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

from ..utils.constants import ConversationState, CallbackPrefix
from ..utils.keyboards import create_main_menu_keyboard
from ..database.operations import get_or_create_user
from .common import log_command, log_callback

async def main_menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Display the main menu from a command."""
    user = update.effective_user
    log_command(update, "menu")
    
    # Register user
    get_or_create_user(
        user.id, user.username, user.first_name, user.last_name, user.language_code
    )
    
    # Create keyboard
    keyboard = create_main_menu_keyboard()
    
    # Send menu
    await update.message.reply_text(
        "What would you like to do?", 
        reply_markup=keyboard
    )
    
    return ConversationState.MAIN_MENU

async def handle_menu_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle main menu selection."""
    query = update.callback_query
    log_callback(update, query.data)
    await query.answer()
    
    action = query.data.split("_")[1]
    
    if action == "status":
        # Import locally to avoid circular imports
        from .status import start_status_flow
        return await start_status_flow(update, context)
    
    elif action == "favorites":
        # Import locally to avoid circular imports
        from .favorites import start_favorites_flow
        return await start_favorites_flow(update, context)
    
    elif action == "subs":
        # Import locally to avoid circular imports
        from .subscriptions import show_subscriptions
        return await show_subscriptions(update, context)
    
    elif action == "unsub":
        # Import locally to avoid circular imports
        from .subscriptions import start_unsubscribe_flow
        return await start_unsubscribe_flow(update, context)
    
    elif action == "main":
        # Return to main menu
        keyboard = create_main_menu_keyboard()
        await query.edit_message_text(
            "What would you like to do?", 
            reply_markup=keyboard
        )
        return ConversationState.MAIN_MENU

async def cancel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel the conversation via callback."""
    query = update.callback_query
    await query.answer()
    
    # Show main menu options again
    keyboard = create_main_menu_keyboard()
    await query.edit_message_text(
        "Operation cancelled. What would you like to do?", 
        reply_markup=keyboard
    )
    
    return ConversationState.MAIN_MENU
