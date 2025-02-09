from telethon import TelegramClient, events
from telethon.tl.types import MessageEntitySpoiler, MessageEntityBold
import asyncio
import re

# Replace with your own Telegram API credentials
API_ID = 28298985  # <-- Replace with your actual API ID
API_HASH = "39f421942304070739872145d0eb6f2e"  # <-- Replace with your actual API hash

# Create a Telegram client session
client = TelegramClient("message_logger_session", API_ID, API_HASH)

# Flag to track awaiting coin name
awaiting_coin_name = False

def extract_bold_text(entities, text):
    """Extract bold text from a message."""
    if not entities:
        return None
    for entity in entities:
        if isinstance(entity, MessageEntityBold):
            return text[entity.offset : entity.offset + entity.length]
    return None

async def main():
    global awaiting_coin_name
    print("Starting Telegram client...")
    await client.start()
    print("Client started successfully! Listening for messages...\n")

    @client.on(events.NewMessage)
    async def handler(event):
        global awaiting_coin_name

        sender = await event.get_sender()
        chat = await event.get_chat()

        chat_name = chat.title if hasattr(chat, "title") else f"User({chat.id})"
        sender_name = sender.username if sender.username else f"User({sender.id})"
        message_text = event.text.strip()

        # Check for hidden/spoiler messages
        if event.message.entities:
            for entity in event.message.entities:
                if isinstance(entity, MessageEntitySpoiler):
                    print(f"[SPOILER] Hidden message revealed but ignored: {message_text}")
                    return  # Ignore this message and wait for the next one

        # Handle expected messages
        if awaiting_coin_name:
            if re.fullmatch(r"\*\*[A-Z]{2,6}\*\*", message_text):
                coin_name = message_text.strip("*")  # Extract coin name
                print(f"[BUY] Detected valid coin: {coin_name}")
                awaiting_coin_name = False  # Reset flag after receiving valid coin name
                # Call buy function here if needed
            else:
                print(f"[IGNORE] Misleading message received: {message_text}")
                return  # Continue waiting for the correct message

        # Check for trigger messages
        elif "Next message is the coin name" in message_text:
            print(f"[{chat_name}] ({sender_name}): {message_text}")
            awaiting_coin_name = True
        else:
            print(f"[{chat_name}] ({sender_name}): {message_text}")  # Log all messages normally

    @client.on(events.CallbackQuery)
    async def callback_handler(event):
        print(f"[BUTTON CLICKED] Data: {event.data}")
        await event.answer("Button clicked!")  # Reply to button click

    await client.run_until_disconnected()

if __name__ == "__main__":
    with client:
        client.loop.run_until_complete(main())
