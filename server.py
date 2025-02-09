from telethon import TelegramClient, events
from telethon.tl.types import MessageEntitySpoiler, MessageEntityBold
import asyncio
import re

# Replace with your own Telegram API credentials
API_ID = 28298985  # <-- Replace with your actual API ID
API_HASH = "39f421942304070739872145d0eb6f2e"  # <-- Replace with your actual API hash

# Create a Telegram client session
client = TelegramClient("message_logger_session", API_ID, API_HASH)

# Dictionary to track awaiting platforms
awaiting_platform = {}  # {chat_id: platform}

def extract_bold_text(entities, text):
    """Extract bold text from a message."""
    if not entities:
        return None
    for entity in entities:
        if isinstance(entity, MessageEntityBold):
            return text[entity.offset : entity.offset + entity.length]
    return None

async def main():
    print("Starting Telegram client...")
    await client.start()
    print("Client started successfully! Listening for messages...\n")

    @client.on(events.NewMessage)
    async def handler(event):
        global awaiting_platform

        sender = await event.get_sender()
        chat = await event.get_chat()
        chat_id = chat.id

        chat_name = chat.title if hasattr(chat, "title") else f"User({chat.id})"
        sender_name = sender.username if sender.username else f"User({sender.id})"
        message_text = event.text.strip()

        # Check for platform triggers
        if "Next message is the coin name" in message_text:
            print(f"[{chat_name}] ({sender_name}): {message_text} [AWAITING POLONIEX]")
            awaiting_platform[chat_id] = "Poloniex"
            return
        elif "Next name is money name" in message_text:
            print(f"[{chat_name}] ({sender_name}): {message_text} [AWAITING XT]")
            awaiting_platform[chat_id] = "XT"
            return

        # Process awaited messages
        if chat_id in awaiting_platform:
            platform = awaiting_platform[chat_id]

            if platform == "Poloniex":
                # Coin name must be a spoiler and in **CoinName** format
                if event.message.entities:
                    spoiler_detected = any(isinstance(e, MessageEntitySpoiler) for e in event.message.entities)
                    bold_text = extract_bold_text(event.message.entities, message_text)
                    
                    if spoiler_detected and bold_text and re.fullmatch(r"\*\*[A-Z]{2,6}\*\*", message_text):
                        coin_name = message_text.strip("*")
                        print(f"[POLONIEX] Detected Coin: {coin_name}")
                        del awaiting_platform[chat_id]  # Stop awaiting
                        return
            
            elif platform == "XT":
                # Coin name must be **CoinName** format, under 10 characters
                if re.fullmatch(r"\*\*[A-Z]{2,6}\*\*", message_text) and len(message_text) <= 10:
                    coin_name = message_text.strip("*")
                    print(f"[XT] Detected Coin: {coin_name}")
                    del awaiting_platform[chat_id]  # Stop awaiting
                    return

            print(f"[IGNORE] Misleading message received: {message_text}")
            return  # Continue waiting

        print(f"[{chat_name}] ({sender_name}): {message_text}")  # Log all messages normally

    await client.run_until_disconnected()

if __name__ == "__main__":
    with client:
        client.loop.run_until_complete(main())
