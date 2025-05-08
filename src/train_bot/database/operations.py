"""Database operations for the train bot."""

import aiosqlite
from datetime import datetime
import json
from typing import List, Dict, Optional, Tuple, Any

from .models import DB_PATH

async def get_or_create_user(telegram_id: int, username: str = None, first_name: str = None, 
                           last_name: str = None, language_code: str = None) -> int:
    """Get a user from the database or create if not exists."""
    async with aiosqlite.connect(DB_PATH) as conn:
        async with conn.execute(
            "SELECT user_id FROM users WHERE telegram_id = ?", (telegram_id,)
        ) as cursor:
            result = await cursor.fetchone()

        if result:
            user_id = result[0]
        else:
            async with conn.execute(
                "INSERT INTO users (telegram_id, username, first_name, last_name, language_code) VALUES (?, ?, ?, ?, ?)",
                (telegram_id, username, first_name, last_name, language_code),
            ) as cursor:
                await conn.commit()
                user_id = cursor.lastrowid

        return user_id

async def get_user_favorite_stations(user_id: int) -> List[str]:
    """Get a user's favorite station IDs from the database."""
    async with aiosqlite.connect(DB_PATH) as conn:
        async with conn.execute(
            """
            SELECT station_id FROM favorite_stations
            WHERE user_id = ?
            """,
            (user_id,)
        ) as cursor:
            rows = await cursor.fetchall()
            return [row[0] for row in rows]

async def add_favorite_station(user_id: int, station_id: str) -> bool:
    """Add a station to user's favorites."""
    success = False
    
    try:
        async with aiosqlite.connect(DB_PATH) as conn:
            await conn.execute(
                "INSERT OR IGNORE INTO favorite_stations (user_id, station_id) VALUES (?, ?)",
                (user_id, station_id)
            )
            await conn.commit()
            success = True
    except Exception as e:
        print(f"Error adding favorite station: {e}")
    
    return success

async def get_subscription_by_id(subscription_id: int) -> Optional[Dict[str, Any]]:
    """Get subscription details by ID."""
    try:
        async with aiosqlite.connect(DB_PATH) as conn:
            async with conn.execute(
                """
                SELECT s.subscription_id, s.user_id, u.telegram_id,
                       s.departure_station, s.arrival_station, s.day_of_week, 
                       s.departure_time, s.last_status
                FROM subscriptions s
                JOIN users u ON s.user_id = u.user_id
                WHERE subscription_id = ?
                """,
                (subscription_id,)
            ) as cursor:
                row = await cursor.fetchone()
                
                if not row:
                    return None
                
                return {
                    "id": row[0],
                    "user_id": row[1],
                    "telegram_id": row[2],
                    "departure_station": row[3],
                    "arrival_station": row[4],
                    "day_of_week": row[5],
                    "departure_time": row[6],
                    "last_status": row[7]
                }
    except Exception as e:
        print(f"Error getting subscription by ID: {e}")
        return None

async def remove_favorite_station(user_id: int, station_id: str) -> bool:
    """Remove a station from user's favorites."""
    success = False
    
    try:
        async with aiosqlite.connect(DB_PATH) as conn:
            await conn.execute(
                "DELETE FROM favorite_stations WHERE user_id = ? AND station_id = ?",
                (user_id, station_id)
            )
            await conn.commit()
            success = True
    except Exception as e:
        print(f"Error removing favorite station: {e}")
    
    return success

async def get_user_subscriptions(user_id: int, active_only: bool = True) -> List[Dict[str, Any]]:
    """Get user's subscriptions."""
    query = """
        SELECT subscription_id, departure_station, arrival_station, day_of_week, departure_time
        FROM subscriptions
        WHERE user_id = ?
    """
    if active_only:
        query += " AND active = 1"
    
    async with aiosqlite.connect(DB_PATH) as conn:
        async with conn.execute(query, (user_id,)) as cursor:
            rows = await cursor.fetchall()
            return [
                {
                    "id": sub[0],
                    "departure_station": sub[1],
                    "arrival_station": sub[2],
                    "day_of_week": sub[3],
                    "departure_time": sub[4]
                }
                for sub in rows
            ]

async def create_subscription(user_id: int, departure_station: str, arrival_station: str,
                            day_of_week: int, departure_time: str) -> Optional[int]:
    """Create a new subscription."""
    subscription_id = None
    
    try:
        async with aiosqlite.connect(DB_PATH) as conn:
            async with conn.execute(
                """
                INSERT INTO subscriptions 
                (user_id, departure_station, arrival_station, day_of_week, departure_time, 
                start_date, active, last_status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    departure_station,
                    arrival_station,
                    day_of_week,
                    departure_time,
                    datetime.now().date().isoformat(),
                    1,
                    json.dumps({"status": "unknown"})
                )
            ) as cursor:
                await conn.commit()
                subscription_id = cursor.lastrowid
    except Exception as e:
        print(f"Error creating subscription: {e}")
    
    return subscription_id

async def cancel_subscription(subscription_id: int) -> bool:
    """Cancel (deactivate) a subscription."""
    success = False
    
    try:
        async with aiosqlite.connect(DB_PATH) as conn:
            await conn.execute(
                "UPDATE subscriptions SET active = 0 WHERE subscription_id = ?",
                (subscription_id,)
            )
            await conn.commit()
            success = True
    except Exception as e:
        print(f"Error cancelling subscription: {e}")
    
    return success

async def update_notification_settings(user_id: int, paused: bool) -> bool:
    """Update user's notification settings."""
    success = False
    
    try:
        async with aiosqlite.connect(DB_PATH) as conn:
            await conn.execute(
                "UPDATE users SET notifications_paused = ? WHERE user_id = ?",
                (paused, user_id)
            )
            await conn.commit()
            success = True
    except Exception as e:
        print(f"Error updating notification settings: {e}")
    
    return success
