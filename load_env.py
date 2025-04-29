"""
Environment Variable Loader for Telegram Train Bot

This module loads environment variables from a .env file if it exists.
It's used by the bot and poller scripts to ensure the required
environment variables are available.
"""

import os
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

def load_env_file(env_file='.env'):
    """
    Load environment variables from a .env file.
    
    Args:
        env_file (str): Path to the .env file
        
    Returns:
        bool: True if the file was loaded successfully, False otherwise
    """
    try:
        if not os.path.exists(env_file):
            logger.warning(f"Environment file {env_file} not found")
            return False
            
        logger.info(f"Loading environment variables from {env_file}")
        with open(env_file, 'r') as f:
            for line in f:
                line = line.strip()
                
                # Skip empty lines and comments
                if not line or line.startswith('#'):
                    continue
                    
                # Parse key-value pairs
                if '=' in line:
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip()
                    
                    # Remove quotes if present
                    if value.startswith('"') and value.endswith('"'):
                        value = value[1:-1]
                    elif value.startswith("'") and value.endswith("'"):
                        value = value[1:-1]
                    
                    # Set environment variable if not already set
                    if key and value and key not in os.environ:
                        os.environ[key] = value
                        logger.debug(f"Set environment variable: {key}")
        
        return True
        
    except Exception as e:
        logger.error(f"Error loading environment file: {e}")
        return False

def check_required_env_vars(required_vars):
    """
    Check if required environment variables are set.
    
    Args:
        required_vars (list): List of required environment variable names
        
    Returns:
        bool: True if all required variables are set, False otherwise
    """
    missing_vars = []
    
    for var in required_vars:
        if var not in os.environ or not os.environ[var]:
            missing_vars.append(var)
    
    if missing_vars:
        logger.warning(f"Missing required environment variables: {', '.join(missing_vars)}")
        return False
    
    return True

def init_env():
    """
    Initialize environment variables by loading from .env file
    and checking required variables.
    
    Returns:
        bool: True if initialization was successful, False otherwise
    """
    # Load from .env file if it exists
    load_env_file()
    
    # Check required environment variables
    required_vars = ['TELEGRAM_BOT_TOKEN', 'RAIL_TOKEN']
    return check_required_env_vars(required_vars)

if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        level=logging.INFO
    )
    
    # Test the module
    if init_env():
        print("Environment variables loaded successfully")
        print(f"TELEGRAM_BOT_TOKEN: {'*' * 10}{os.environ['TELEGRAM_BOT_TOKEN'][-5:]}")
        print(f"RAIL_TOKEN: {'*' * 10}{os.environ['RAIL_TOKEN'][-5:]}")
    else:
        print("Failed to load all required environment variables")
        print("Please set the following environment variables:")
        print("- TELEGRAM_BOT_TOKEN")
        print("- RAIL_TOKEN")
