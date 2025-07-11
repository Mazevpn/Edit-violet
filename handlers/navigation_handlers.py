from telethon import events, Button
from keyboards.member_keyboards import member_start_menu
from models.data_produk import XLProduct
import logging

logger = logging.getLogger(__name__)

# Dictionary untuk menyimpan state browsing produk
product_states = {}

async def setup_navigation_handlers(client):
    @client.on(events.CallbackQuery(data=b'back_to_menu'))
    async def back_to_menu_handler(event):
        """Handler untuk tombol kembali ke menu"""
        user_id = event.sender_id
        
        # Hapus state login jika ada
        from handlers.login_handlers import login_states
        if user_id in login_states:
            del login_states[user_id]
        
        # Hapus state produk jika ada
        if user_id in product_states:
            del product_states[user_id]
        
        # Hapus state pembayaran jika ada
        from handlers.payment_handlers import payment_states
        if user_id in payment_states:
            del payment_states[user_id]
        
        # Dapatkan informasi user
        sender = await event.get_sender()
        first_name = sender.first_name
        
        await event.edit(
            f"**👋 Selamat datang {first_name}!**",
            buttons=member_start_menu()
        )
    
    # Hapus handler back_to_products dari sini karena sudah ada di product_item_handlers.py
    # Jangan mendefinisikan handler yang sama di dua tempat berbeda
