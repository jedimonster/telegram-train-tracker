#!/usr/bin/env python
"""Entry point for running the train bot."""

import asyncio
import signal
import sys
from src.train_bot.bot import main

# Global variable to hold the application instance
application = None
# Flag to track if shutdown is in progress to prevent multiple shutdown attempts
shutdown_in_progress = False

async def shutdown():
    """Shutdown the bot gracefully."""
    global application, shutdown_in_progress
    
    # Prevent multiple shutdown attempts
    if shutdown_in_progress:
        return
    shutdown_in_progress = True
    
    print("Shutting down bot...")
    if application:
        # First check if updater is running before stopping it
        try:
            if hasattr(application, 'updater') and application.updater.running:
                await application.updater.stop()
                print("Updater stopped")
        except Exception as e:
            print(f"Error stopping updater: {e}")
        
        # Then stop the application
        try:
            await application.stop()
            print("Application stopped")
        except Exception as e:
            print(f"Error stopping application: {e}")
        
        # Finally run shutdown
        try:
            await application.shutdown()
            print("Application shutdown complete")
        except Exception as e:
            print(f"Error during shutdown: {e}")
    
    # Signal the main task to end
    print("Bot shutdown completed")
    
async def run_bot():
    """Run the bot with proper signal handling."""
    global application
    
    # Create an event to signal when to stop
    stop_event = asyncio.Event()
    
    # Set up signal handlers for graceful shutdown
    for s in [signal.SIGINT, signal.SIGTERM]:
        asyncio.get_event_loop().add_signal_handler(
            s, lambda: asyncio.create_task(handle_signal(stop_event))
        )
    
    # Start the bot
    try:
        application = await main()
        print("Bot is running. Press Ctrl+C to stop.")
        
        # Wait until stop event is set
        await stop_event.wait()
    finally:
        # Make sure to call shutdown if we exit the try block
        await shutdown()

async def handle_signal(stop_event):
    """Handle termination signals."""
    print("Received termination signal!")
    stop_event.set()  # Signal the main task to stop

if __name__ == "__main__":
    try:
        asyncio.run(run_bot())
    except KeyboardInterrupt:
        print("Caught keyboard interrupt outside asyncio loop")
    finally:
        print("Bot script exited")
