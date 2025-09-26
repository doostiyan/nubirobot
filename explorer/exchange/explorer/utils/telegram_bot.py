import os
import requests
from exchange.settings.secret import decrypt_string


def send_telegram_alert(message):
    encrypt_bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    encrypt_chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not encrypt_bot_token or not encrypt_chat_id:
        print("Error: Encrypted Telegram bot token or chat ID is missing!")
        return
    bot_token = decrypt_string(encrypt_bot_token)
    chat_id = decrypt_string(encrypt_chat_id)
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"

    payload = {
        "chat_id": chat_id,
        "text": message
    }

    try:
        response = requests.post(url, json=payload)
        if response.status_code == 200:
            print("Alert sent successfully!")
        else:
            print(f"Failed to send alert: {response.text}")
    except Exception as e:
        print(f"Error sending alert: {e}")
