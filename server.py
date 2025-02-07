from telethon import TelegramClient, events
import asyncio

# Replace with your own Telegram API credentials
API_ID = 28298985  # <-- Replace with your actual API ID
API_HASH = "39f421942304070739872145d0eb6f2e"  # <-- Replace with your actual API hash

# Create a Telegram client session
client = TelegramClient("message_logger_session", API_ID, API_HASH)

# Flags to track next message
awaiting_xt = False
awaiting_poloniex = False

async def main():
    print("Starting Telegram client...")
    await client.start()
    print("Client started successfully! Listening for messages...\n")

    @client.on(events.NewMessage)
    async def handler(event):
        global awaiting_xt, awaiting_poloniex

        sender = await event.get_sender()
        chat = await event.get_chat()

        chat_name = chat.title if hasattr(chat, "title") else f"User({chat.id})"
        sender_name = sender.username if sender.username else f"User({sender.id})"
        message_text = event.text.strip()

        # Handle expected messages
        if awaiting_xt:
            print(f"XT: {message_text}")  # Log in XT format
            awaiting_xt = False  # Reset flag
        elif awaiting_poloniex:
            print(f"Poloniex: {message_text}")  # Log in Poloniex format
            awaiting_poloniex = False  # Reset flag

        # Check for trigger messages
        elif "Next name is money name" in message_text:
            print(f"[{chat_name}] ({sender_name}): {message_text}")
            awaiting_xt = True  # Set flag to log next message as XT
        elif "Next message is the coin name" in message_text:
            print(f"[{chat_name}] ({sender_name}): {message_text}")
            awaiting_poloniex = True  # Set flag to log next message as Poloniex
        else:
            print(f"[{chat_name}] ({sender_name}): {message_text}")  # Log all messages normally

    await client.run_until_disconnected()

if __name__ == "__main__":
    with client:
        client.loop.run_until_complete(main())
