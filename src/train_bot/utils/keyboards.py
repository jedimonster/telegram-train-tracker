"""Keyboard creation utilities for the train bot."""

from typing import List, Optional
from datetime import datetime, timedelta

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from .constants import CallbackPrefix, STATIONS_PER_PAGE, StatusEmoji
from train_stations import TRAIN_STATIONS

def create_status_action_keyboard() -> InlineKeyboardMarkup:
    """Create keyboard for status action selection."""
    keyboard = [
        [
            InlineKeyboardButton("Check Future Train", callback_data=f"{CallbackPrefix.STATUS}_future"),
            InlineKeyboardButton("Check Current Train", callback_data=f"{CallbackPrefix.STATUS}_current"),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def create_station_keyboard(stations: List[dict], prefix: str, 
                          exclude_station_id: Optional[str] = None) -> InlineKeyboardMarkup:
    """Create keyboard with station buttons."""
    keyboard = []
    for station in stations:
        if station["id"] != exclude_station_id:
            keyboard.append(
                [InlineKeyboardButton(
                    station["english"], 
                    callback_data=f"{prefix}_{station['id']}"
                )]
            )
    
    # Add a button to show all stations
    keyboard.append([InlineKeyboardButton("Show All Stations", callback_data=f"show_all_{prefix}")])
    
    # Add a button to manage favorites
    keyboard.append([InlineKeyboardButton("Manage Favorites", callback_data=f"{prefix}_manage_favorites")])
    
    return InlineKeyboardMarkup(keyboard)

def create_paginated_stations_keyboard(page: int, prefix: str, 
                                     exclude_station_id: Optional[str] = None) -> InlineKeyboardMarkup:
    """Create paginated keyboard with all stations."""
    # Sort stations alphabetically by English name
    sorted_stations = sorted(TRAIN_STATIONS, key=lambda x: x["english"])
    if exclude_station_id:
        sorted_stations = [s for s in sorted_stations if s["id"] != exclude_station_id]
    
    # Calculate pagination
    start_idx = page * STATIONS_PER_PAGE
    end_idx = start_idx + STATIONS_PER_PAGE
    total_pages = (len(sorted_stations) + STATIONS_PER_PAGE - 1) // STATIONS_PER_PAGE
    
    # Create station buttons
    keyboard = []
    for station in sorted_stations[start_idx:end_idx]:
        keyboard.append(
            [InlineKeyboardButton(
                station["english"], 
                callback_data=f"{prefix}_{station['id']}"
            )]
        )
    
    # Add navigation buttons
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("◀️ Previous", callback_data=f"{CallbackPrefix.PAGE}_{prefix}_{page-1}"))
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton("Next ▶️", callback_data=f"{CallbackPrefix.PAGE}_{prefix}_{page+1}"))
    
    if nav_buttons:
        keyboard.append(nav_buttons)
    
    # Add a back button
    keyboard.append([InlineKeyboardButton("Back to Favorites", callback_data=f"{CallbackPrefix.BACK}_to_favorites_{prefix}")])
    
    return InlineKeyboardMarkup(keyboard)

def create_date_selection_keyboard() -> InlineKeyboardMarkup:
    """Create keyboard for date selection."""
    keyboard = []
    today = datetime.now().date()
    
    for i in range(8):  # Today + 7 days
        date = today + timedelta(days=i)
        date_str = date.strftime("%Y-%m-%d")
        display_date = date.strftime("%a, %b %d")  # e.g., "Mon, Jan 01"
        
        if i == 0:
            display_date = f"Today ({display_date})"
        elif i == 1:
            display_date = f"Tomorrow ({display_date})"
        
        keyboard.append([InlineKeyboardButton(display_date, callback_data=f"{CallbackPrefix.STATUS}_date_{date_str}")])
    
    return InlineKeyboardMarkup(keyboard)

def create_train_times_keyboard(train_times: List[tuple], current_time: Optional[datetime] = None) -> InlineKeyboardMarkup:
    """Create keyboard with train times."""
    keyboard = []
    current_row = []
    
    for i, (departure_time, arrival_time, switches) in enumerate(train_times):
        # Format times
        departure_dt = datetime.fromisoformat(departure_time)
        arrival_dt = datetime.fromisoformat(arrival_time)
        formatted_departure = departure_dt.strftime("%H:%M")
        
        # Calculate duration
        duration = arrival_dt - departure_dt
        hours, remainder = divmod(duration.seconds, 3600)
        minutes, _ = divmod(remainder, 60)
        duration_str = f"{hours}h {minutes}m" if hours > 0 else f"{minutes}m"
        
        # Add status indicator for current trains
        status_indicator = ""
        if current_time:
            is_running = departure_dt.time() <= current_time.time() <= arrival_dt.time()
            status_indicator = f"{StatusEmoji.RUNNING if is_running else StatusEmoji.SCHEDULED} "
        
        # Create button label
        label = f"{status_indicator}{formatted_departure} ({duration_str})"
        if switches > 0:
            label += f" - {switches + 1} trains"
        
        # Add button to current row
        current_row.append(InlineKeyboardButton(label, callback_data=f"{CallbackPrefix.STATUS}_time_{i}"))
        
        # If row has 3 buttons or this is the last item, add row to keyboard
        if len(current_row) == 3 or i == len(train_times) - 1:
            keyboard.append(current_row)
            current_row = []
    
    return InlineKeyboardMarkup(keyboard)

def create_train_details_keyboard(train_index: int, show_subscribe: bool = True, show_refresh: bool = True) -> InlineKeyboardMarkup:
    """Create keyboard for train details view."""
    keyboard = []
    
    if show_subscribe:
        keyboard.append([InlineKeyboardButton("🔔 Subscribe", callback_data=f"subscribe_train_{train_index}")])
    
    if show_refresh:
        keyboard.append([InlineKeyboardButton("🔄 Refresh", callback_data=f"refresh_status_{train_index}")])
    
    keyboard.append([InlineKeyboardButton("Back to Train List", callback_data=f"{CallbackPrefix.STATUS}_back_to_times")])
    
    return InlineKeyboardMarkup(keyboard)

def create_main_menu_keyboard() -> InlineKeyboardMarkup:
    """Create main menu keyboard with command options."""
    keyboard = [
        [InlineKeyboardButton("Check Train Status", callback_data=f"{CallbackPrefix.MENU}_status")],
        [InlineKeyboardButton("Manage Favorites", callback_data=f"{CallbackPrefix.MENU}_favorites")],
        [InlineKeyboardButton("My Subscriptions", callback_data=f"{CallbackPrefix.MENU}_subs")],
        [InlineKeyboardButton("Unsubscribe", callback_data=f"{CallbackPrefix.MENU}_unsub")]
    ]
    return InlineKeyboardMarkup(keyboard)

def add_back_to_menu_button(keyboard_buttons: List[List[InlineKeyboardButton]]) -> List[List[InlineKeyboardButton]]:
    """Add a back to menu button to an existing keyboard."""
    keyboard_buttons.append([InlineKeyboardButton("« Main Menu", callback_data=f"{CallbackPrefix.MENU}_main")])
    return keyboard_buttons

def create_cancel_keyboard() -> InlineKeyboardMarkup:
    """Create a keyboard with cancel button."""
    keyboard = [[InlineKeyboardButton("Cancel", callback_data="cancel")]]
    return InlineKeyboardMarkup(keyboard)

def create_favorites_keyboard() -> InlineKeyboardMarkup:
    """Create keyboard for favorites management."""
    keyboard = [
        [InlineKeyboardButton("Add Favorite", callback_data=f"{CallbackPrefix.FAVORITE}_add")],
        [InlineKeyboardButton("Remove Favorite", callback_data=f"{CallbackPrefix.FAVORITE}_remove")],
        [InlineKeyboardButton("Done", callback_data=f"{CallbackPrefix.FAVORITE}_done")]
    ]
    # Add back to menu button
    keyboard = add_back_to_menu_button(keyboard)
    return InlineKeyboardMarkup(keyboard)

def create_subscription_confirmation_keyboard() -> InlineKeyboardMarkup:
    """Create keyboard for subscription confirmation."""
    keyboard = [
        [
            InlineKeyboardButton("Confirm", callback_data="confirm_yes"),
            InlineKeyboardButton("Cancel", callback_data="confirm_no"),
        ]
    ]
    # Add back to menu button
    keyboard = add_back_to_menu_button(keyboard)
    return InlineKeyboardMarkup(keyboard)
