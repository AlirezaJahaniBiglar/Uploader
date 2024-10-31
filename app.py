from flask import Flask, request
import requests
import mysql.connector
import random
import string
import time
from datetime import datetime, timedelta, timezone
from multiprocessing import Process
import logging
from logging.handlers import RotatingFileHandler
from config import *


app = Flask(__name__)


# Connect to the database
def get_db_connection():
    return mysql.connector.connect(**DB_CONFIG)


# Generate a random string
def generate_random_id():
    return ''.join(random.choices(string.ascii_letters + string.digits, k=10))


# Check if the user is a member of the required channels
def check_user_in_channels(user_id):
    for channel in CHANNELS:
        url = f"https://api.telegram.org/bot{TOKEN}/getChatMember?chat_id=@{channel}&user_id={user_id}"
        response = requests.get(url).json()
        if response.get('result', {}).get('status') not in ['member', 'administrator', 'creator']:
            return False, channel
    return True, None


# Check if the user is an admin
def is_admin(user_id):
    return user_id in ADMIN_USER_IDS


# Send a message to the user
def send_message(chat_id, text, parse_mode='HTML'):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    requests.post(url, json={'chat_id': chat_id, 'text': text, 'parse_mode': parse_mode})


# Send a file to the user
def send_file(chat_id, file_id, file_type, caption=None):
    url = f"https://api.telegram.org/bot{TOKEN}/send{file_type.capitalize()}"
    data = {
        'chat_id': chat_id, 
        file_type: file_id, 
        'caption': caption, 
        'parse_mode': 'HTML'
    } if caption else {
        'chat_id': chat_id, 
        file_type: file_id
    }
    response = requests.post(url, json=data)
    return response.json()


# Send a welcome message to the user
def send_welcome_message(chat_id, first_name, start_time):
    text = f"👋 <b>Hello <a href='tg://user?id={chat_id}'>{first_name}</a>!</b>\n\n" \
           f"🤖 <i>You started the bot on <b>{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(start_time))}</b>.</i>\n"
    send_message(chat_id, text)


# Send a message asking the user to join the channel
def send_join_channel_message(chat_id, channel, random_id):
    keyboard = {
        'inline_keyboard': [[{'text': '📢 Join Channel', 'url': f'https://t.me/{channel}'}],
                            [{'text': '🔄 Check Again', 'callback_data': f'check_{random_id}'}]]
    }
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    requests.post(url, json={'chat_id': chat_id, 'text': 'Please join the channel first 🙏', 'reply_markup': keyboard, 'parse_mode': 'HTML'})


# Delete a message
def delete_message(chat_id, message_id):
    url = f"https://api.telegram.org/bot{TOKEN}/deleteMessage"
    requests.post(url, json={'chat_id': chat_id, 'message_id': message_id})


# Delete a message from the database
def delete_message_from_db(message_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM messages WHERE message_id = %s', (message_id,))
    conn.commit()
    conn.close()


# Check the status file
def read_status():
    try:
        with open(STATUS_FILE, 'r') as file:
            status = file.read().strip()
            return status.lower() == 'true'
    except FileNotFoundError:
        return False


def cleanup_messages():
    with open(STATUS_FILE, 'w') as file:
        file.write('False')

    while True:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Retrieve all messages from the database
        cursor.execute('SELECT chat_id, message_id, delete_time FROM messages')
        messages = cursor.fetchall()
        
        now = datetime.now()  # Current UTC time
        
        # Process each message
        for chat_id, message_id, delete_time in messages:
            # Convert delete_time from database to datetime object
            
            if now >= delete_time:
                print(f"Deleting message {message_id} in chat {chat_id}")
                url = f"https://api.telegram.org/bot{TOKEN}/deleteMessage"
                requests.post(url, json={'chat_id': chat_id, 'message_id': message_id})
        
        # If no messages to delete, update the status file and terminate the thread
        if not messages:
            # Update the status file
            with open(STATUS_FILE, 'w') as file:
                file.write('True')
            break
        
        conn.close()
        time.sleep(CHECK_INTERVAL)


# Start a new thread for cleanup if the status is True
def start_cleanup_thread():
    if read_status():
        process = Process(target=cleanup_messages)
        process.start()


# Handle incoming requests on a single route
@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.json
    if 'message' in data:
        message = data['message']
        user_id = message['from']['id']
        chat_id = message['chat']['id']
        first_name = message['from'].get('first_name', '')
        username = message['from'].get('username', '')
        start_time = message['date']

        if message['chat']['type'] != "private":
            return ""

        if 'text' in message:
            text = message['text']
            if text.startswith('/start'):
                if len(text.split()) > 1:
                    random_id = text.split()[1]
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    cursor.execute('SELECT file_id, file_type, caption FROM files WHERE random_id = %s', (random_id,))
                    result = cursor.fetchone()
                    conn.close()

                    if result:
                        is_member, channel = check_user_in_channels(user_id)
                        if is_member:
                            file_id, file_type, caption = result
                            response = send_file(chat_id, file_id, file_type, caption)
                            send_message(chat_id, "⚠️ This message will self-destruct in 10 seconds! 💥\nPlease make sure to save it somewhere! 📥")
                            if 'result' in response and 'message_id' in response['result']:
                                message_id = response['result']['message_id']
                                delete_time = datetime.now() + timedelta(seconds=DELETE_TIME)
                                # Insert the message into the database for scheduled deletion
                                conn = get_db_connection()
                                cursor = conn.cursor()
                                cursor.execute('INSERT INTO messages (chat_id, message_id, delete_time) VALUES (%s, %s, %s)',
                                               (chat_id, message_id, delete_time))
                                conn.commit()
                                conn.close()
                                # Start cleanup thread if necessary
                                start_cleanup_thread()
                        else:
                            send_join_channel_message(chat_id, channel, random_id)
                    else:
                        send_welcome_message(chat_id, first_name, start_time)
                else:
                    send_welcome_message(chat_id, first_name, start_time)

        elif any(key in message for key in ['photo', 'document', 'video', 'voice', 'audio']):
            if is_admin(user_id):
                file_type = next(key for key in ['photo', 'document', 'video', 'voice', 'audio'] if key in message)
                file_id = message[file_type][-1]['file_id'] if file_type == 'photo' else message[file_type]['file_id']
                caption = message.get('caption', None)
                random_id = generate_random_id()

                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute('INSERT INTO files (file_id, random_id, file_type, user_id, caption) VALUES (%s, %s, %s, %s, %s)', (file_id, random_id, file_type, user_id, caption))
                conn.commit()
                conn.close()

                download_link = f"https://t.me/IOTUploaderBot?start={random_id}"
                send_message(chat_id, f"🎉 Your download link: \n\n{download_link}")


    elif 'callback_query' in data:
        query = data['callback_query']
        user_id = query['from']['id']
        chat_id = query['message']['chat']['id']
        message_id = query['message']['message_id']
        
        if query['data'].startswith('check_'):
            random_id = query['data'].split("_")[1]
            is_member, channel = check_user_in_channels(user_id)
            if is_member:
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute('SELECT file_id, file_type, caption FROM files WHERE random_id = %s', (random_id,))
                result = cursor.fetchone()
                conn.close()

                if result:
                    file_id, file_type, caption = result
                    delete_message(chat_id, message_id)
                    response = send_file(chat_id, file_id, file_type, caption)
                    send_message(chat_id, DELETE_TEXT)
                    if 'result' in response and 'message_id' in response['result']:
                        message_id = response['result']['message_id']
                        delete_time = datetime.now() + timedelta(seconds=DELETE_TIME)
                        # Insert the message into the database for scheduled deletion
                        conn = get_db_connection()
                        cursor = conn.cursor()
                        cursor.execute('INSERT INTO messages (chat_id, message_id, delete_time) VALUES (%s, %s, %s)',
                                       (chat_id, message_id, delete_time))
                        conn.commit()
                        conn.close()
                        # Start cleanup thread if necessary
                        start_cleanup_thread()
            else:
                # Send an alert if the user is not a member
                url = f"https://api.telegram.org/bot{TOKEN}/answerCallbackQuery"
                requests.post(url, json={
                    'callback_query_id': query['id'],
                    'text': '❗️ You are still not a member of the required channels.',
                    'show_alert': True
                })
    
    return 'ok'


error_log = logging.getLogger('error_logger')
error_log.setLevel(logging.DEBUG)

error_handler = RotatingFileHandler(error_log_file, maxBytes=10485760, backupCount=5, encoding='utf-8')
error_formatter = logging.Formatter('%(asctime)s:%(levelname)s:%(message)s')
error_handler.setFormatter(error_formatter)
error_log.addHandler(error_handler)
