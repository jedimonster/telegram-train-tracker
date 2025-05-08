"""Message formatting utilities for the train bot."""

from datetime import datetime
from typing import Dict, Any, List, Optional

from .constants import StatusEmoji, TIME_FORMAT, DATETIME_FORMAT

def format_train_details(
    departure_station: Dict[str, str],
    arrival_station: Dict[str, str],
    departure_time: datetime,
    arrival_time: datetime,
    switches: int,
    delay_minutes: Optional[int] = None,
    switch_stations: Optional[List[str]] = None,
    date: Optional[datetime] = None,
    last_updated: Optional[datetime] = None
) -> str:
    """Format train details message."""
    # Format times
    formatted_departure = departure_time.strftime(TIME_FORMAT)
    formatted_arrival = arrival_time.strftime(TIME_FORMAT)
    
    # Calculate duration
    duration = arrival_time - departure_time
    hours, remainder = divmod(duration.seconds, 3600)
    minutes, _ = divmod(remainder, 60)
    duration_str = f"{hours}h {minutes}m" if hours > 0 else f"{minutes}m"
    
    # Build the message
    message = [f"{StatusEmoji.TRAIN} Train Details\n"]
    
    # Add route
    message.append(f"\nRoute: {departure_station['name']} → {arrival_station['name']}")
    
    # Add date if provided
    if date:
        message.append(f"Date: {date.strftime('%A, %B %d, %Y')}")
    
    message.append("")  # Empty line
    
    # Add status and times
    if delay_minutes is not None:
        if delay_minutes > 0:
            message.append(f"Status: {StatusEmoji.DELAYED} Delayed by {delay_minutes} minutes")
            message.append(f"Updated departure: {formatted_departure}")
            message.append(f"Updated arrival: {formatted_arrival}")
        else:
            message.append(f"Status: {StatusEmoji.ON_TIME} On time")
            message.append(f"Departure: {formatted_departure}")
            message.append(f"Arrival: {formatted_arrival}")
    else:
        message.append(f"Status: {StatusEmoji.UNKNOWN} Status unknown")
        message.append(f"Departure: {formatted_departure}")
        message.append(f"Arrival: {formatted_arrival}")
    
    # Add duration
    message.append(f"Duration: {duration_str}")
    
    # Add train changes info
    if switches > 0:
        message.append(f"Changes: {switches + 1} trains")
    
    # Add switch stations if available
    if switch_stations:
        message.append(f"Change at: {', '.join(switch_stations)}")
    
    # Add last updated timestamp if provided
    if last_updated:
        message.append(f"\nLast updated: {last_updated.strftime(TIME_FORMAT)}")
    
    return "\n".join(message)

def format_subscription_details(subscription: Dict[str, Any]) -> str:
    """Format subscription details message."""
    message = [
        "Please confirm your subscription:\n",
        f"Route: {subscription['departure_station']['name']} → {subscription['arrival_station']['name']}\n"
    ]
    
    # Handle day_of_week which might be None
    if subscription['day_of_week'] is not None:
        message.append(f"Day: {subscription['day_of_week']['name']}\n")
    else:
        message.append("Day: Today (current day)\n")
    
    # Handle departure_time format which might be a string or a dict
    if isinstance(subscription['departure_time'], dict) and 'formatted' in subscription['departure_time']:
        time_str = subscription['departure_time']['formatted']
    else:
        # Assume it's an ISO string and extract time portion
        time_str = subscription['departure_time'].split('T')[1][:5]  # Get HH:MM from ISO format
    
    message.append(f"Time: {time_str}\n\n")
    message.append("You will receive notifications about this train's status every week.")
    
    return "".join(message)

def format_subscriptions_list(subscriptions: List[Dict[str, Any]]) -> str:
    """Format list of subscriptions."""
    if not subscriptions:
        return "You don't have any active subscriptions."
    
    # Day of week mapping (0 = Sunday, 6 = Saturday)
    day_names = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
    
    message = ["Your active subscriptions:\n"]
    
    for sub in subscriptions:
        # Get day name from numeric day_of_week
        day_name = day_names[sub['day_of_week']]
        
        message.extend([
            f"\n{StatusEmoji.TRAIN} {sub['departure_station']} → {sub['arrival_station']}",
            f"   Every {day_name} at {sub['departure_time']}",
            f"   (ID: {sub['id']})"
        ])
    
    message.append("\nTo unsubscribe, use /unsubscribe")
    
    return "\n".join(message)

def format_favorites_list(favorites: List[Dict[str, str]]) -> str:
    """Format list of favorite stations."""
    message = ["Your favorite stations:\n"]
    
    if favorites:
        for station in favorites:
            message.append(f"• {station['english']} (ID: {station['id']})")
    else:
        message.append("You don't have any favorite stations yet.")
    
    message.append("\nWhat would you like to do?")
    
    return "\n".join(message)

def format_train_times_header(
    departure_station: Dict[str, str],
    arrival_station: Dict[str, str],
    date: Optional[datetime] = None,
    current_time: Optional[datetime] = None
) -> str:
    """Format header for train times list."""
    message = [f"{StatusEmoji.TRAIN} Train Schedule\n"]
    
    message.append(f"\nRoute: {departure_station['name']} → {arrival_station['name']}")
    
    if date:
        message.append(f"Date: {date.strftime('%A, %B %d, %Y')}")
    
    if current_time:
        message.append(f"Current time: {current_time.strftime(TIME_FORMAT)}")
        message.extend([
            "\nPlease select a train time:",
            f"{StatusEmoji.RUNNING} = Currently running",
            f"{StatusEmoji.SCHEDULED} = Departing soon"
        ])
    else:
        message.append("\nPlease select a train time:")
    
    return "\n".join(message)
