"""Subscription command handlers for the train bot."""

from datetime import datetime

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, ConversationHandler

from ..database.operations import (
    get_or_create_user,
    create_subscription,
    cancel_subscription,
    get_user_subscriptions
)
from ..utils.constants import ConversationState, CallbackPrefix
from ..utils.keyboards import (
    create_station_keyboard,
    create_paginated_stations_keyboard,
    create_subscription_confirmation_keyboard,
    create_main_menu_keyboard,
    add_back_to_menu_button
)
from ..utils.formatting import format_subscriptions_list, format_subscription_details
from .common import (
    get_message_context,
    clear_message_context,
    get_page_number,
    set_page_number,
    log_command,
    log_callback
)

async def show_subscriptions(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Show user subscriptions with options."""
    query = update.callback_query
    
    # Get user's subscriptions
    user = update.effective_user
    user_id = await get_or_create_user(
        user.id, user.username, user.first_name, user.last_name, user.language_code
    )
    subscriptions = await get_user_subscriptions(user_id)
    
    # Format message
    message = format_subscriptions_list(subscriptions)
    
    # Create keyboard with return to menu
    keyboard_buttons = []
    if subscriptions:
        keyboard_buttons.append([InlineKeyboardButton("Cancel Subscription", callback_data=f"{CallbackPrefix.MENU}_unsub")])
    keyboard_buttons = add_back_to_menu_button(keyboard_buttons)
    keyboard = InlineKeyboardMarkup(keyboard_buttons)
    
    await query.edit_message_text(message, reply_markup=keyboard)
    return ConversationState.MAIN_MENU

async def subscriptions_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle the /mysubscriptions command."""
    log_command(update, "mysubscriptions")
    
    # Get user's subscriptions
    user = update.effective_user
    user_id = await get_or_create_user(
        user.id, user.username, user.first_name, user.last_name, user.language_code
    )
    subscriptions = await get_user_subscriptions(user_id)
    
    # Format message
    message = format_subscriptions_list(subscriptions)
    
    # Create keyboard with return to menu
    keyboard_buttons = []
    if subscriptions:
        keyboard_buttons.append([InlineKeyboardButton("Cancel Subscription", callback_data=f"{CallbackPrefix.MENU}_unsub")])
    keyboard_buttons.append([InlineKeyboardButton("Main Menu", callback_data=f"{CallbackPrefix.MENU}_main")])
    keyboard = InlineKeyboardMarkup(keyboard_buttons)
    
    await update.message.reply_text(message, reply_markup=keyboard)
    return ConversationState.MAIN_MENU

async def start_unsubscribe_flow(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start unsubscribe flow from callback."""
    query = update.callback_query
    
    # Get user's subscriptions
    user = update.effective_user
    user_id = await get_or_create_user(
        user.id, user.username, user.first_name, user.last_name, user.language_code
    )
    subscriptions = await get_user_subscriptions(user_id)
    
    if not subscriptions:
        # No subscriptions, show message with return to menu
        keyboard_buttons = []
        keyboard_buttons = add_back_to_menu_button(keyboard_buttons)
        keyboard = InlineKeyboardMarkup(keyboard_buttons)
        
        await query.edit_message_text(
            "You don't have any active subscriptions.\n\n"
            "Use /subscribe to set up a new subscription.",
            reply_markup=keyboard
        )
        return ConversationState.MAIN_MENU
    
    # Create subscription selection keyboard
    keyboard = create_subscription_confirmation_keyboard()
    
    # Show subscription list with cancel options
    message = format_subscriptions_list(subscriptions) + "\n\nPlease select a subscription to cancel:"
    await query.edit_message_text(message, reply_markup=keyboard)
    return ConversationState.SELECT_SUBSCRIPTION

async def unsubscribe_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle the /unsubscribe command."""
    log_command(update, "unsubscribe")
    
    # Get user's subscriptions
    user = update.effective_user
    user_id = await get_or_create_user(
        user.id, user.username, user.first_name, user.last_name, user.language_code
    )
    subscriptions = await get_user_subscriptions(user_id)
    
    if not subscriptions:
        # No subscriptions, show message with return to menu
        keyboard_buttons = []
        keyboard_buttons.append([InlineKeyboardButton("Main Menu", callback_data=f"{CallbackPrefix.MENU}_main")])
        keyboard = InlineKeyboardMarkup(keyboard_buttons)
        
        await update.message.reply_text(
            "You don't have any active subscriptions.\n\n"
            "Use /subscribe to set up a new subscription.",
            reply_markup=keyboard
        )
        return ConversationState.MAIN_MENU
    
    # Format message and create keyboard
    message = format_subscriptions_list(subscriptions)
    keyboard = create_subscription_confirmation_keyboard()
    
    # Show subscription list with cancel options
    await update.message.reply_text(
        f"{message}\n\nPlease select a subscription to cancel:",
        reply_markup=keyboard
    )
    
    return ConversationState.SELECT_SUBSCRIPTION

async def handle_subscription_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle subscription selection for cancellation."""
    query = update.callback_query
    await query.answer()
    
    # Extract subscription ID
    subscription_id = int(query.data.split("_")[-1])
    
    # Cancel subscription
    if await cancel_subscription(subscription_id):
        await query.edit_message_text(
            "✅ Subscription cancelled successfully.\n\n"
            "Use /subscribe to set up a new subscription."
        )
    else:
        await query.edit_message_text(
            "❌ Sorry, there was an error cancelling your subscription. Please try again."
        )
    
    return ConversationHandler.END

async def handle_subscription_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle subscription confirmation."""
    query = update.callback_query
    await query.answer()
    
    if query.data == "confirm_yes":
        # Get subscription details
        subscription_context = get_message_context(update, context, "subscription")
        user = update.effective_user
        user_id = await get_or_create_user(
            user.id, user.username, user.first_name, user.last_name, user.language_code
        )
        
        # Create subscription
        # Extract day_of_week value if it's a dictionary
        day_of_week = subscription_context["day_of_week"]
        if isinstance(day_of_week, dict) and "value" in day_of_week:
            day_of_week = day_of_week["value"]
        
        subscription_id = await create_subscription(
            user_id,
            subscription_context["departure_station"]["id"],
            subscription_context["arrival_station"]["id"],
            day_of_week,
            subscription_context["departure_time"]
        )
        
        if subscription_id:
            await query.edit_message_text(
                "✅ Subscription created successfully!\n\n"
                "You will receive notifications about this train's status.\n"
                "Use /mysubscriptions to view your subscriptions."
            )
        else:
            await query.edit_message_text(
                "❌ Sorry, there was an error creating your subscription. Please try again."
            )
    else:
        await query.edit_message_text(
            "Subscription cancelled.\n\n"
            "Use /subscribe to set up a different subscription."
        )
    
    # Clear subscription context
    clear_message_context(update, context, "subscription")
    return ConversationHandler.END
