"""Constants used throughout the train bot."""

from enum import IntEnum

# Conversation states
class ConversationState(IntEnum):
    SELECT_ACTION = 0
    SELECT_DEPARTURE = 1
    SELECT_ARRIVAL = 2
    SELECT_DATE = 3
    SELECT_TIME = 4
    CONFIRM_SUBSCRIPTION = 5
    SELECT_SUBSCRIPTION = 6
    MANAGE_FAVORITES = 7
    SELECT_FAVORITE_ACTION = 8
    ADD_FAVORITE = 9
    REMOVE_FAVORITE = 10
    MAIN_MENU = 11  # New state for main menu interactions

# Message templates
HELP_MESSAGE = (
    "I can help you check train status and subscribe to train updates.\n\n"
    "Available commands:\n"
    "/start - Start the bot\n"
    "/help - Show this help message\n"
    "/status - Check current or future train status\n"
    "/subscribe - Subscribe to train updates\n"
    "/mysubscriptions - View your subscriptions\n"
    "/unsubscribe - Cancel a subscription\n"
    "/favorites - Manage your favorite stations\n"
    "/settings - Configure notification preferences\n"
    "/pause - Pause all notifications\n"
    "/resume - Resume notifications\n\n"
    "To get started, try /status to check train times or /favorites to set up your favorite stations."
)

WELCOME_MESSAGE = (
    "Hello {first_name}! I'm the Train Information Bot.\n\n"
    "I can help you check train status and subscribe to train updates.\n\n"
    "Available commands:\n"
    "/status - Check current or future train status\n"
    "/subscribe - Subscribe to train updates\n"
    "/mysubscriptions - View your subscriptions\n"
    "/unsubscribe - Cancel a subscription\n"
    "/favorites - Manage your favorite stations\n"
    "/settings - Configure notification preferences\n"
    "/pause - Pause all notifications\n"
    "/resume - Resume notifications\n"
    "/help - Show this help message\n\n"
    "To get started, try /status to check train times or /favorites to set up your favorite stations."
)

# Button labels and callback data prefixes
class CallbackPrefix:
    STATUS = "status"
    SUBSCRIPTION = "subscription"
    FAVORITE = "favorite"
    PAGE = "page"
    BACK = "back"
    MENU = "menu"  # New prefix for menu actions

# Pagination settings
STATIONS_PER_PAGE = 8

# Time formats
TIME_FORMAT = "%H:%M"
DATE_FORMAT = "%Y-%m-%d"
DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"

# Status indicators
class StatusEmoji:
    ON_TIME = "🟢"
    DELAYED = "🔴"
    UNKNOWN = "⚪"
    RUNNING = "🚂"
    SCHEDULED = "🕒"
    TRAIN = "🚆"
