"""Main bot module that sets up and runs the Telegram bot."""

import logging
import os
import sys

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ConversationHandler,
)

from .database.models import setup_database
from .utils.constants import ConversationState, CallbackPrefix
from .handlers.common import (
    start_command,
    help_command,
    error_handler,
    cancel,
    back_to_favorites,
    back_to_train_list,
    subscribe_from_status
)
from .handlers.menu import (
    main_menu_command,
    handle_menu_selection,
    cancel_callback
)
from .handlers.status import (
    status_command,
    check_train_status,
    select_status_departure_station,
    select_status_arrival_station,
    show_status_all_stations,
    handle_status_pagination,
)
from .handlers.status_handlers_2 import (
    select_status_date,
    get_future_train_status,
    get_current_train_status,
    show_train_details,
    refresh_train_status
)
from .handlers.favorites import (
    favorites_command,
    handle_favorite_action,
    add_favorite_station_handler,
    remove_favorite_station_handler
)
from .handlers.notifications import (
    pause_notifications_command,
    resume_notifications_command,
    settings_command,
    refresh_notification_status
)
from .handlers.subscriptions import (
    subscriptions_command,
    unsubscribe_command,
    handle_subscription_selection,
    handle_subscription_confirmation
)
from load_env import init_env

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

async def create_application() -> Application:
    """Create and configure the Application instance."""
    # Load environment variables
    if not init_env():
        logger.error("Failed to load required environment variables")
        logger.error("Please set TELEGRAM_BOT_TOKEN and RAIL_TOKEN environment variables")
        logger.error("You can create a .env file based on .env.template")
        sys.exit(1)
    
    # Create the database if it doesn't exist
    await setup_database()
    
    # Create the Application
    application = Application.builder().token(os.environ["TELEGRAM_BOT_TOKEN"]).build()
    
    # Register the error handler
    application.add_error_handler(error_handler)
    
    # Add conversation handlers with CallbackQueryHandler entry points
    # Status conversation - starts when a user clicks a status action button
    status_conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(check_train_status, pattern=f"^{CallbackPrefix.STATUS}_(future|current)$")],
        allow_reentry=True,  # Allow multiple concurrent conversations
        per_message=True,  # Track callback queries for every message
        states={
            ConversationState.SELECT_ACTION: [
                CallbackQueryHandler(check_train_status, pattern=f"^{CallbackPrefix.STATUS}_(future|current)$"),
            ],
            ConversationState.SELECT_DEPARTURE: [
                CallbackQueryHandler(select_status_arrival_station, pattern=f"^{CallbackPrefix.STATUS}_dep_"),
                CallbackQueryHandler(lambda u, c: show_status_all_stations(u, c, f"{CallbackPrefix.STATUS}_dep"), 
                                   pattern=f"^show_all_{CallbackPrefix.STATUS}_dep$"),
                CallbackQueryHandler(favorites_command, pattern=f"^{CallbackPrefix.STATUS}_manage_favorites$"),
                CallbackQueryHandler(handle_status_pagination, pattern=f"^{CallbackPrefix.STATUS}_page_"),
                CallbackQueryHandler(lambda u, c: back_to_favorites(u, c, f"{CallbackPrefix.STATUS}_dep"), 
                                   pattern=f"^{CallbackPrefix.BACK}_to_favorites_{CallbackPrefix.STATUS}_dep$"),
            ],
            ConversationState.SELECT_ARRIVAL: [
                CallbackQueryHandler(select_status_date, pattern=f"^{CallbackPrefix.STATUS}_arr_"),
                CallbackQueryHandler(lambda u, c: show_status_all_stations(u, c, f"{CallbackPrefix.STATUS}_arr"), 
                                   pattern=f"^show_all_{CallbackPrefix.STATUS}_arr$"),
                CallbackQueryHandler(favorites_command, pattern=f"^{CallbackPrefix.STATUS}_manage_favorites$"),
                CallbackQueryHandler(handle_status_pagination, pattern=f"^{CallbackPrefix.STATUS}_page_"),
                CallbackQueryHandler(lambda u, c: back_to_favorites(u, c, f"{CallbackPrefix.STATUS}_arr"), 
                                   pattern=f"^{CallbackPrefix.BACK}_to_favorites_{CallbackPrefix.STATUS}_arr$"),
            ],
            ConversationState.SELECT_DATE: [
                CallbackQueryHandler(get_future_train_status, pattern=f"^{CallbackPrefix.STATUS}_date_"),
            ],
            ConversationState.SELECT_TIME: [
                CallbackQueryHandler(show_train_details, pattern=f"^{CallbackPrefix.STATUS}_time_"),
                CallbackQueryHandler(lambda u, c: back_to_train_list(u, c), 
                                   pattern=f"^{CallbackPrefix.STATUS}_back_to_times$"),
                CallbackQueryHandler(refresh_train_status, pattern="^refresh_status_"),
                CallbackQueryHandler(subscribe_from_status, pattern="^subscribe_train_"),
            ],
            ConversationState.CONFIRM_SUBSCRIPTION: [
                CallbackQueryHandler(handle_subscription_confirmation, pattern="^confirm_(yes|no)$"),
            ],
        },
        fallbacks=[
            CallbackQueryHandler(cancel_callback, pattern="^cancel$"),
            CallbackQueryHandler(handle_menu_selection, pattern=f"^{CallbackPrefix.MENU}_main$"),
        ],
    )
    
    # Add conversation handler for favorites - starts when user interacts with favorites buttons
    favorites_conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(handle_favorite_action, pattern=f"^{CallbackPrefix.FAVORITE}_(add|remove|done)$")],
        allow_reentry=True,
        per_message=True,  # Track callback queries for every message
        states={
            ConversationState.MANAGE_FAVORITES: [
                CallbackQueryHandler(handle_favorite_action, 
                                   pattern=f"^{CallbackPrefix.FAVORITE}_(add|remove|done)$"),
            ],
            ConversationState.ADD_FAVORITE: [
                CallbackQueryHandler(add_favorite_station_handler, pattern=f"^{CallbackPrefix.FAVORITE}_add_"),
                CallbackQueryHandler(handle_status_pagination, pattern=f"^{CallbackPrefix.PAGE}_"),
                CallbackQueryHandler(lambda u, c: back_to_favorites(u, c), 
                                   pattern=f"^{CallbackPrefix.BACK}_to_favorites_"),
            ],
            ConversationState.REMOVE_FAVORITE: [
                CallbackQueryHandler(remove_favorite_station_handler, pattern=f"^{CallbackPrefix.FAVORITE}_remove_"),
                CallbackQueryHandler(remove_favorite_station_handler, pattern=f"^{CallbackPrefix.FAVORITE}_done$"),
            ],
        },
        fallbacks=[
            CallbackQueryHandler(cancel_callback, pattern="^cancel$"),
            CallbackQueryHandler(handle_menu_selection, pattern=f"^{CallbackPrefix.MENU}_main$"),
        ],
    )
    
    # Add conversation handler for unsubscribe - starts when user selects a subscription
    unsubscribe_conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(handle_subscription_selection, pattern="^subscription_")],
        allow_reentry=True,
        per_message=True,  # Track callback queries for every message
        states={
            ConversationState.SELECT_SUBSCRIPTION: [
                CallbackQueryHandler(handle_subscription_selection, pattern="^subscription_"),
            ],
        },
        fallbacks=[
            CallbackQueryHandler(cancel_callback, pattern="^cancel$"),
            CallbackQueryHandler(handle_menu_selection, pattern=f"^{CallbackPrefix.MENU}_main$"),
        ],
    )
    
    # Add menu-related handlers first
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("menu", main_menu_command))
    application.add_handler(CallbackQueryHandler(handle_menu_selection, pattern=f"^{CallbackPrefix.MENU}_"))
    
    # Add command handlers that display initial menus
    application.add_handler(CommandHandler("status", status_command))  # Shows status options menu 
    application.add_handler(CommandHandler("favorites", favorites_command))  # Shows favorites management menu
    application.add_handler(CommandHandler("mysubscriptions", subscriptions_command))  # Shows subscriptions list
    application.add_handler(CommandHandler("unsubscribe", unsubscribe_command))  # Shows subscriptions to unsubscribe
    
    # Add conversation handlers that handle the actual interactions via callbacks
    application.add_handler(status_conv_handler)
    application.add_handler(favorites_conv_handler)
    application.add_handler(unsubscribe_conv_handler)
    
    # Add simple one-shot command handlers
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("settings", settings_command))
    application.add_handler(CommandHandler("pause", pause_notifications_command))
    application.add_handler(CommandHandler("resume", resume_notifications_command))
    
    # Add notification refresh handler
    application.add_handler(
        CallbackQueryHandler(refresh_notification_status, pattern="^refresh_notif_")
    )
    
    return application

async def main() -> None:
    """Start the bot."""
    # Create the application
    application = await create_application()
    
    # Add debug logging
    logger.info("Bot initialized, starting polling...")
    
    # Start the bot and let it run until we press Ctrl-C
    logger.info("Bot starting...")
    await application.initialize()
    await application.start()
    await application.updater.start_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True
    )
    
    # Return the application so the caller can manage the event loop and shutdown
    return application

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
