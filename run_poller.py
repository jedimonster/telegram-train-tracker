#!/usr/bin/env python
"""
Run Poller Script for Telegram Train Bot

This script demonstrates how to run the subscription poller either:
1. As a continuous daemon process with a sleep interval
2. As a one-time check (suitable for cron jobs)

Usage:
    # Run as a daemon with 5-minute intervals
    python run_poller.py --daemon --interval 300
    
    # Run once and exit (for cron)
    python run_poller.py --once
"""

import argparse
import logging
import asyncio
import sys
import os
from datetime import datetime

import subscription_poller
from load_env import init_env

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger("poller")
logger.setLevel(logging.DEBUG)



async def run_daemon(interval):
    """Run the poller as a daemon process with the specified interval."""
    logger.info(f"Starting poller daemon with {interval} second interval")
    
    try:
        while True:
            start_time = datetime.now()
            logger.info(f"Running poll at {start_time}")
            
            # Run the poller
            await subscription_poller.main()
            
            # Calculate how long to sleep
            elapsed = (datetime.now() - start_time).total_seconds()
            sleep_time = max(0, interval - elapsed)
            
            logger.info(f"Poll completed in {elapsed:.2f} seconds. Sleeping for {sleep_time:.2f} seconds.")
            await asyncio.sleep(sleep_time)
            
    except KeyboardInterrupt:
        logger.info("Poller daemon stopped by user")
    except Exception as e:
        logger.error(f"Error in poller daemon: {e}")
        sys.exit(1)


async def run_once():
    """Run the poller once and exit."""
    logger.info("Running poller once")
    
    try:
        await subscription_poller.main()
        logger.info("Poll completed successfully")
    except Exception as e:
        logger.error(f"Error in poller: {e}")
        sys.exit(1)


async def main():
    """Parse arguments and run the poller."""
    parser = argparse.ArgumentParser(description="Run the train subscription poller")
    
    # Create a mutually exclusive group for run mode
    mode_group = parser.add_mutually_exclusive_group(required=True)
    mode_group.add_argument(
        "--daemon", 
        action="store_true", 
        help="Run as a daemon process"
    )
    mode_group.add_argument(
        "--once", 
        action="store_true", 
        help="Run once and exit (suitable for cron jobs)"
    )
    
    # Add interval argument for daemon mode
    parser.add_argument(
        "--interval", 
        type=int, 
        default=30,  # 30 seconds default
        help="Polling interval in seconds (for daemon mode)"
    )
    
    # Parse arguments
    args = parser.parse_args()
    
    # Load environment variables
    if not init_env():
        logger.error("Failed to load required environment variables")
        logger.error("Please set TELEGRAM_BOT_TOKEN and RAIL_TOKEN environment variables")
        logger.error("You can create a .env file based on .env.template")
        sys.exit(1)
    
    # Run in the appropriate mode
    if args.daemon:
        logger.info("Running daemon")
        await run_daemon(args.interval)
    else:  # args.once
        logger.info("Running once")
        await run_once()


if __name__ == "__main__":
    logger.info("Starting")
    asyncio.run(main())
