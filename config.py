# config.py

# Telegram Bot Token
TOKEN = "<Bot-Token>"

# MySQL Database Configuration
DB_CONFIG = {
    'user': 'your-database-username',
    'password': 'your-database-password',
    'host': 'localhost',
    'database': 'your-database-name'
}

# Default
CHANNELS = ['IOTDrop']
ADMIN_USER_IDS = [6747459876]  # Replace with real admin user IDs

STATUS_FILE = 'status.txt'
CHECK_INTERVAL = 1  # Check every second

DELETE_TIME = 10
DELETE_TEXT = f"⚠️ This message will self-destruct in {DELETE_TIME} seconds! 💥\nPlease make sure to save it somewhere! 📥"

# Default log file
error_log_file = 'error.log'

# Webhook URL for the bot
WEBHOOK_URL = "https://yourdomain.com/webhook"
