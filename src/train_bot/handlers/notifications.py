"""Notification command handlers for the train bot."""

from telegram import Update
from telegram.ext import ContextTypes

from ..database.operations import (
    get_or_create_user,
    update_notification_settings
)
from .common import log_command

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
