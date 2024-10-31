import mysql.connector
import requests
from config import TOKEN, DB_CONFIG, WEBHOOK_URL


def init_db():
    try:
        db = mysql.connector.connect(**DB_CONFIG)
        cursor = db.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS files (
                id INT AUTO_INCREMENT PRIMARY KEY,
                file_id VARCHAR(255) NOT NULL,
                random_id VARCHAR(255) NOT NULL UNIQUE,
                file_type VARCHAR(50) NOT NULL,
                user_id INT NOT NULL,
                caption TEXT
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                id INT AUTO_INCREMENT PRIMARY KEY,
                chat_id VARCHAR(255) NOT NULL,
                message_id VARCHAR(255) NOT NULL,
                delete_time DATETIME NOT NULL
            )
        ''')

        db.commit()
        print("Database initialized successfully!")
    
    except mysql.connector.Error as err:
        print(f"Error: {err}")
    finally:
        cursor.close()
        db.close()


def set_webhook():
    url = f"https://api.telegram.org/bot{TOKEN}/setWebhook"
    response = requests.post(url, json={"url": WEBHOOK_URL})

    if response.status_code == 200:
        print("Webhook set successfully!")
    else:
        print(f"Failed to set webhook: {response.text}")


if __name__ == "__main__":
    init_db()
    set_webhook()
