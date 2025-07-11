from telethon import TelegramClient, events
from core.config import DB_CONFIG, TG_CONFIG
import logging
import asyncio

# Configure logging
logging.basicConfig(
    format='[%(levelname)s] %(asctime)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Initialize client
client = TelegramClient(
    'bot_session',
    TG_CONFIG['api_id'],
    TG_CONFIG['api_hash']
)

async def register_handlers():
    """Register all bot handlers"""
    # Import handlers
    from handlers.start_handler import setup_start_handler
    from handlers.product_handlers import setup_product_handlers
    from handlers.login_handlers import setup_login_handlers
    from handlers.navigation_handlers import setup_navigation_handlers
    from handlers.product_item_handlers import setup_product_item_handlers
    from handlers.payment_handlers import setup_payment_handlers
    from handlers.setting_user import setup_setting_user_handlers
    from handlers.sidompul_handlers import setup_sidompul_handlers
    from handlers.deposit import setup_deposit_handlers
    from tasks.deposit_tasks import start_deposit_tasks
    from tasks.auto_backup_database import mulai_backup_scheduler
    from handlers.setting_bot import register_setting_bot_handlers
    from handlers.member_chat import register_handlers as register_member_chat_handlers
    from handlers.admin_chat import register_handlers as register_admin_chat_handlers
    from handlers.member_chat import load_chats_from_file, chat_messages
    from handlers.multi_trx import register_handlers

    # Register handlers
    await setup_start_handler(client)
    await setup_product_handlers(client)
    await setup_navigation_handlers(client)
    await setup_login_handlers(client)
    await setup_product_item_handlers(client)
    await setup_payment_handlers(client)
    await setup_setting_user_handlers(client)
    await setup_sidompul_handlers(client)
    await setup_deposit_handlers(client)
    await start_deposit_tasks()
    await mulai_backup_scheduler()
    await register_setting_bot_handlers(client)
    await register_member_chat_handlers(client)
    await register_admin_chat_handlers(client)
    await register_handlers(client)

    # Add more handlers here as needed

async def main():
    try:
        # Register all handlers
        await register_handlers()
        
        # Start the bot
        await client.start(bot_token=TG_CONFIG['bot_token'])
        logger.info("Bot started successfully!")
        
        await client.run_until_disconnected()
    except Exception as e:
        logger.error(f"Bot failed to start: {str(e)}")
        raise

if __name__ == '__main__':
    try:
        client.loop.run_until_complete(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {str(e)}")
