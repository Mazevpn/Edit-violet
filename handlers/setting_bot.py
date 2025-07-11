import logging
from telethon import events, Button
from models.user import User
from models.setting_bot import SettingBot
from keyboards.admin_keyboards import admin_start_menu

logger = logging.getLogger(__name__)

async def register_setting_bot_handlers(client):
    """Mendaftarkan semua handler untuk pengaturan bot"""

    @client.on(events.CallbackQuery(data=b'setting_bot'))
    async def handle_setting_bot(event):
        """Handler untuk menu pengaturan bot"""
        user_id = event.sender_id
        user = User.get_by_id(user_id)  # Remove await since method is not async
        
        if not user or user.role != 'admin':
            await event.answer("⛔ Anda tidak memiliki akses ke menu ini", alert=True)
            return
        
        try:
            settings = SettingBot.get_settings()
            public_status = "🌐 Public" if settings.public else "🔒 Private"
            current_status = settings.status.capitalize()
            
            await event.edit(
                "🤖 **Pengaturan Bot**\n\n"
                f"**Mode Saat Ini:** {public_status}\n"
                f"**Status:** {current_status}\n\n"
                "Silakan pilih pengaturan yang ingin diubah:",
                buttons=[
                    [Button.inline("🔄 Ubah Mode Public/Private", b'toggle_public')],
                    [Button.inline("⚙️ Ubah Status Bot", b'change_status')],
                    [Button.inline("🔙 Kembali", b'back_to_admin')]
                ]
            )
        except Exception as e:
            logger.error(f"Error in handle_setting_bot: {e}")
            await event.respond("Terjadi kesalahan saat memproses permintaan.")

    @client.on(events.CallbackQuery(data=b'toggle_public'))
    async def handle_toggle_public(event):
        user_id = event.sender_id
        user = User.get_by_id(user_id)  # Remove await
        
        if not user or user.role != 'admin':
            await event.answer("⛔ Anda tidak memiliki akses ke menu ini", alert=True)
            return
        
        try:
            settings = SettingBot.get_settings()
            new_public_status = not settings.public
            
            if SettingBot.set_bot_public(new_public_status):
                status_text = "Public" if new_public_status else "Private"
                await event.edit(
                    f"✅ **Mode Bot Berhasil Diubah**\n\n"
                    f"Bot sekarang dalam mode **{status_text}**",
                    buttons=[[Button.inline("🔙 Kembali", b'setting_bot')]]
                )
                logger.info(f"Admin {user_id} changed bot public status to {status_text}")
            else:
                await event.answer("❌ Gagal mengubah mode bot", alert=True)
        except Exception as e:
            logger.error(f"Error in handle_toggle_public: {e}")
            await event.respond("Terjadi kesalahan saat memproses permintaan.")

    @client.on(events.CallbackQuery(data=b'change_status'))
    async def handle_change_status(event):
        user_id = event.sender_id
        user = User.get_by_id(user_id)  # Remove await
        
        if not user or user.role != 'admin':
            await event.answer("⛔ Anda tidak memiliki akses ke menu ini", alert=True)
            return
        
        try:
            settings = SettingBot.get_settings()
            await event.edit(
                f"⚙️ **Ubah Status Bot**\n\n"
                f"Status saat ini: **{settings.status.capitalize()}**\n\n"
                f"Pilih status baru:",
                buttons=[
                    [Button.inline("✅ Buka", b'set_status_buka')],
                    [Button.inline("❌ Tutup", b'set_status_tutup')],
                    [Button.inline("🔧 Maintenance", b'set_status_maintenance')],
                    [Button.inline("🔙 Kembali", b'setting_bot')]
                ]
            )
        except Exception as e:
            logger.error(f"Error in handle_change_status: {e}")
            await event.respond("Terjadi kesalahan saat memproses permintaan.")

    @client.on(events.CallbackQuery(pattern=r'^set_status_(\w+)$'))
    async def handle_set_status(event):
        user_id = event.sender_id
        user = User.get_by_id(user_id)  # Remove await
        
        if not user or user.role != 'admin':
            await event.answer("⛔ Anda tidak memiliki akses ke menu ini", alert=True)
            return
        
        try:
            status = event.data_match.group(1).decode()
            if SettingBot.set_bot_status(status):
                status_text = status.capitalize()
                await event.edit(
                    f"✅ **Status Bot Berhasil Diubah**\n\n"
                    f"Status bot sekarang: **{status_text}**",
                    buttons=[[Button.inline("🔙 Kembali", b'setting_bot')]]
                )
                logger.info(f"Admin {user_id} changed bot status to {status}")
            else:
                await event.answer("❌ Gagal mengubah status bot", alert=True)
        except Exception as e:
            logger.error(f"Error in handle_set_status: {e}")
            await event.respond("Terjadi kesalahan saat memproses permintaan.")

    return True