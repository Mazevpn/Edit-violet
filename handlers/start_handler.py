from telethon import events, Button, types
from telethon import errors, functions
from keyboards.admin_keyboards import admin_start_menu
from keyboards.member_keyboards import member_start_menu
from models.user import User
from models.setting_bot import SettingBot
import logging
from core.config import CHANNEL_TELEGRAM, BOT_NOTIFICATION
import aiohttp
from scripts.cek_saldo import get_panel_balance  # Import the new function

logger = logging.getLogger(__name__)

async def setup_start_handler(client):
    @client.on(events.NewMessage(pattern='/start'))
    async def start_handler(event):
        try:
            # Get user information
            user_id = event.sender_id
            sender = await event.get_sender()
            username = sender.username
            first_name = sender.first_name
            
            # Check if user exists in database
            existing_user = User.get_by_id(user_id)
            
            # Check if user is admin
            is_admin = existing_user and existing_user.role == 'admin'
            
            # Get bot settings
            settings = SettingBot.get_settings()
            if not settings and not is_admin:
                await event.respond("⚠️ Bot sedang dalam pemeliharaan.")
                return
                
            # Check bot status - skip for admin
            if not is_admin and settings.status != "buka":
                status_message = {
                    "tutup": "❌ Bot sedang tutup.",
                    "maintenance": "🔧 Bot sedang dalam pemeliharaan."
                }.get(settings.status, "⚠️ Bot tidak tersedia.")
                await event.respond(status_message)
                return
                
            # Check private mode - skip for admin
            if not is_admin and not settings.public and not existing_user:
                await event.respond("🔒 **Bot ini dalam mode private**\n\n"
                                   "Hanya pengguna terdaftar yang dapat menggunakan bot ini.")
                return
                
            # Check if user is active - only for existing non-admin users
            if existing_user and not is_admin and not existing_user.is_active:
                await event.respond("❌ **Akun Anda Nonaktif**\n\n"
                                   "Akun Anda telah dinonaktifkan. Silakan hubungi admin untuk mengaktifkan kembali.")
                return
                
            # Check channel membership - skip for admin
            if not is_admin and not await check_user_joined_channels(client, user_id):
                channels_buttons = []
                for channel_id, channel_info in CHANNEL_TELEGRAM.items():
                    channel_name = channel_info.get('name', 'Channel')
                    channel_url = channel_info.get('url', '')
                    if channel_url:
                        channels_buttons.append([Button.url(f"Join {channel_name}", channel_url)])
                channels_buttons.append([Button.inline("✅ Saya sudah bergabung", b"check_membership")])
                await event.respond("**⚠️ Anda harus bergabung ke channel kami terlebih dahulu.**\n\n"
                                   "Silakan klik tombol di bawah untuk bergabung, lalu klik 'Saya sudah bergabung'.",
                                   buttons=channels_buttons)
                return
                
            # Create or update user
            is_new_user = existing_user is None
            user = User.create_or_update(user_id, username, first_name)
            if not user:
                logger.error(f"Failed to create/update user: {user_id}")
                await event.respond("Terjadi kesalahan, silakan coba lagi.")
                return
                
            # Send notification for new users (except admins)
            if is_new_user and not is_admin:
                await send_new_user_notification(client, user)
                
            # Format user information
            status = "✅ Aktif" if user.is_active else "❌ Nonaktif"
            username_display = f"@{username}" if username else "Tidak ada username"
            user_info = (f"===================================\n"
                        f"**👤 Informasi Akun Anda**\n"
                        f"===================================\n"
                        f"**ID:** `{user_id}`\n"
                        f"**Username:** {username_display}\n"
                        f"**Nama:** {first_name}\n"
                        f"**Saldo:** Rp {user.balance:,.0f}\n")
            
            # Add panel balance information for admins
            if user.role == 'admin':
                # Get panel balance
                panel_balance = await get_panel_balance()
                if panel_balance['success']:
                    user_info += (f"**Saldo Panel:** Rp {panel_balance['saldo']:,.0f}\n"
                                 f"**Points Panel:** {panel_balance['points']}\n")
                else:
                    user_info += f"**Saldo Panel:** Gagal memuat\n"
            
            # Complete the user info
            user_info += (f"**Status:** {status}\n"
                         f"**Role:** {user.role.capitalize()}\n"
                         f"====================================\n")
            
            # Show appropriate menu based on role
            if user.role == 'admin':
                await event.respond(f"**👋 Selamat datang Admin {first_name}!**\n\n{user_info}",
                                   buttons=admin_start_menu())
            else:
                await event.respond(f"**👋 Selamat datang {first_name}!**\n\n{user_info}",
                                   buttons=member_start_menu())
                
            logger.info(f"User started bot: {user_id} ({username or 'No username'}) - {user.role}")
        except Exception as e:
            logger.error(f"Error in start handler: {e}")
            await event.respond("Terjadi kesalahan, silakan coba lagi.")

    @client.on(events.CallbackQuery(data=b'check_membership'))
    async def check_membership_callback(event):
        user_id = event.sender_id
        try:
            # Periksa kembali keanggotaan channel
            if await check_user_joined_channels(client, user_id):
                # Jika sudah bergabung, lanjutkan proses
                sender = await event.get_sender()
                username = sender.username
                first_name = sender.first_name
                
                # Cek apakah user sudah ada di database
                existing_user = User.get_by_id(user_id)
                is_new_user = existing_user is None
                
                # Cek jika user sudah ada tapi nonaktif
                if existing_user and not existing_user.is_active and existing_user.role != 'admin':
                    await event.edit(
                        "❌ **Akun Anda Nonaktif**\n\n"
                        "Akun Anda telah dinonaktifkan. Silakan hubungi admin untuk mengaktifkan kembali."
                    )
                    return
                
                # Simpan atau perbarui user di database
                user = User.create_or_update(user_id, username, first_name)
                if not user:
                    logger.error(f"Failed to create/update user: {user_id}")
                    await event.answer("Terjadi kesalahan. Silakan coba lagi dengan mengetik /start", alert=True)
                    return
                
                # Jika user baru, kirim notifikasi ke admin
                if is_new_user:
                    await send_new_user_notification(client, user)
                
                # Format status user
                status = "✅ Aktif" if user.is_active else "❌ Nonaktif"
                username_display = f"@{username}" if username else "Tidak ada username"
                
                # Buat pesan dengan informasi user
                user_info = (
                    f"===================================\n"
                    f"**👤 Informasi Akun Anda**\n"
                    f"===================================\n"
                    f"**ID:** `{user_id}`\n"
                    f"**Username:** {username_display}\n"
                    f"**Nama:** {first_name}\n"
                    f"**Saldo:** Rp {user.balance:,.0f}\n"
                    f"**Status:** {status}\n"
                    f"**Role:** {user.role.capitalize()}\n"
                    f"====================================\n"
                )
                
                # Cek role user
                message = None
                if user.role == 'admin':
                    message = f"**👋 Selamat datang Admin {first_name}!**\n\n{user_info}"
                    buttons = admin_start_menu()
                else:
                    # Tampilkan saldo untuk member
                    message = f"**👋 Selamat datang {first_name}!**\n\n{user_info}"
                    buttons = member_start_menu()
                
                try:
                    await event.edit(message, buttons=buttons)
                except Exception as e:
                    # Jika gagal edit (misalnya MessageNotModifiedError), kirim pesan baru
                    if "MessageNotModifiedError" in str(e):
                        await event.answer("Verifikasi berhasil! Silakan gunakan bot.", alert=True)
                        await client.send_message(user_id, message, buttons=buttons)
                    else:
                        raise e
                
                logger.info(f"User verified membership and started bot: {user_id} ({username or 'No username'}) - {user.role}")
            else:
                # Jika belum bergabung, tampilkan pesan lagi
                channels_buttons = []
                for channel_id, channel_info in CHANNEL_TELEGRAM.items():
                    channel_name = channel_info.get('name', 'Channel')
                    channel_url = channel_info.get('url', '')
                    if channel_url:
                        channels_buttons.append([Button.url(f"Join {channel_name}", channel_url)])
                channels_buttons.append([Button.inline("✅ Saya sudah bergabung", b"check_membership")])
                
                try:
                    await event.edit(
                        "**⚠️ Anda belum bergabung ke semua channel yang diperlukan.**\n\n"
                        "Silakan klik tombol di bawah untuk bergabung, lalu klik 'Saya sudah bergabung' untuk melanjutkan.",
                        buttons=channels_buttons
                    )
                except Exception as e:
                    # Jika gagal edit, tampilkan alert
                    if "MessageNotModifiedError" in str(e):
                        await event.answer("Anda belum bergabung ke semua channel yang diperlukan.", alert=True)
                    else:
                        raise e
        except Exception as e:
            logger.error(f"Error in check_membership_callback: {e}")
            await event.answer("Terjadi kesalahan. Silakan coba lagi dengan mengetik /start", alert=True)

async def check_user_joined_channels(client, user_id):
    """
    Memeriksa apakah user sudah bergabung ke semua channel yang diperlukan
    
    Args:
        client: Telethon client
        user_id: ID pengguna Telegram
        
    Returns:
        bool: True jika sudah bergabung ke semua channel, False jika belum
    """
    try:
        # Jika tidak ada channel yang dikonfigurasi, anggap sudah bergabung
        if not CHANNEL_TELEGRAM:
            return True
            
        for channel_id, channel_info in CHANNEL_TELEGRAM.items():
            try:
                # Gunakan entity dari konfigurasi (bisa berupa link atau ID numerik)
                entity = channel_info.get('entity')
                if not entity:
                    logger.error(f"Missing entity for channel {channel_id}")
                    return False
                
                # Dapatkan entity channel
                channel_entity = await client.get_entity(entity)
                
                # Cek apakah user adalah anggota channel
                participant = await client(functions.channels.GetParticipantRequest(
                    channel=channel_entity,
                    participant=user_id
                ))
                
                # Jika sampai di sini tanpa exception, berarti user adalah anggota
                logger.info(f"User {user_id} is a member of channel {channel_id}")
            except errors.UserNotParticipantError:
                # User bukan anggota channel
                logger.info(f"User {user_id} is NOT a member of channel {channel_id}")
                return False
            except Exception as e:
                logger.error(f"Error checking channel membership for {channel_id}: {e}")
                # Untuk channel private, kita mungkin tidak bisa memeriksa keanggotaan
                # Jadi kita anggap user belum bergabung
                return False
                
        # Jika sudah memeriksa semua channel dan user ada di semua channel
        return True
    except Exception as e:
        logger.error(f"Error in check_user_joined_channels: {e}")
        # Jika terjadi error, anggap belum bergabung
        return False

async def send_new_user_notification(client, user):
    """
    Mengirim notifikasi ke admin saat ada user baru menggunakan API Telegram
    
    Args:
        client: Telethon client
        user: Objek User yang baru terdaftar
    """
    try:
        # Dapatkan semua admin dari database
        admin_users = User.get_all_users(role='admin')
        if not admin_users:
            logger.warning("No admin users found in database for notifications")
            return
            
        # Format pesan notifikasi
        username_display = f"@{user.username}" if user.username else "Tidak ada username"
        notification_message = (
            f"🔔 **Pengguna Baru Terdaftar**\n\n"
            f"**ID:** `{user.user_id}`\n"
            f"**Username:** {username_display}\n"
            f"**Nama:** {user.first_name}\n"
            f"**Waktu Daftar:** {user.created_at.strftime('%Y-%m-%d %H:%M:%S')}\n"
        )
        
        # Gunakan bot token dari konfigurasi
        bot_token = BOT_NOTIFICATION.get('bot_token')
        if not bot_token:
            logger.error("Bot token not found in configuration")
            return
            
        # Kirim notifikasi ke semua admin menggunakan API Telegram
        for admin in admin_users:
            try:
                # Gunakan API Telegram untuk mengirim pesan
                async with aiohttp.ClientSession() as session:
                    api_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
                    payload = {
                        "chat_id": admin.user_id,
                        "text": notification_message,
                        "parse_mode": "Markdown"
                    }
                    async with session.post(api_url, json=payload) as response:
                        if response.status == 200:
                            logger.info(f"Sent new user notification to admin {admin.user_id} via API")
                        else:
                            response_json = await response.json()
                            logger.error(f"Failed to send notification via API: {response_json}")
            except Exception as e:
                logger.error(f"Failed to send notification to admin {admin.user_id}: {e}")
    except Exception as e:
        logger.error(f"Error sending new user notification: {e}")

# Tambahkan handler untuk callback menu utama
    @client.on(events.CallbackQuery(data=b'main_menu'))
    async def main_menu_handler(event):
        """Handler untuk kembali ke menu utama"""
        try:
            user_id = event.sender_id
            user = User.get_by_id(user_id)
            
            if not user:
                await event.answer("Terjadi kesalahan. Silakan mulai ulang bot dengan /start", alert=True)
                return
                
            # Cek jika user nonaktif (kecuali admin)
            if user.role != 'admin' and not user.is_active:
                await event.edit(
                    "❌ **Akun Anda Nonaktif**\n\n"
                    "Akun Anda telah dinonaktifkan. Silakan hubungi admin untuk mengaktifkan kembali."
                )
                return
                
            # Dapatkan informasi user
            sender = await event.get_sender()
            username = sender.username
            first_name = sender.first_name
            
            # Format status user
            status = "✅ Aktif" if user.is_active else "❌ Nonaktif"
            username_display = f"@{username}" if username else "Tidak ada username"
            
            # Buat pesan dengan informasi user
            user_info = (
                f"===================================\n"
                f"**👤 Informasi Akun Anda**\n"
                f"===================================\n"
                f"**ID:** `{user_id}`\n"
                f"**Username:** {username_display}\n"
                f"**Nama:** {first_name}\n"
                f"**Saldo:** Rp {user.balance:,.0f}\n"
                f"**Status:** {status}\n"
                f"**Role:** {user.role.capitalize()}\n"
                f"====================================\n"
            )
            
            # Tampilkan menu berdasarkan role
            if user.role == 'admin':
                await event.edit(
                    f"**👋 Selamat datang Admin {first_name}!**\n\n{user_info}",
                    buttons=admin_start_menu()
                )
            else:
                await event.edit(
                    f"**👋 Selamat datang {first_name}!**\n\n{user_info}",
                    buttons=member_start_menu()
                )
                
        except Exception as e:
            logger.error(f"Error in main_menu_handler: {e}")
            await event.answer("Terjadi kesalahan. Silakan mulai ulang bot dengan /start", alert=True)

    # Handler untuk memeriksa status user sebelum mengakses fitur
    @client.on(events.CallbackQuery())
    async def check_user_status(event):
        """
        Handler untuk memeriksa status user sebelum mengakses fitur
        Ini adalah middleware yang akan dijalankan sebelum handler lainnya
        """
        # Jangan proses callback yang sudah memiliki handler spesifik
        # Ini hanya untuk memeriksa status user pada callback yang tidak ditangani oleh handler lain
        if event.data in [b'main_menu', b'check_membership']:
            return
            
        try:
            user_id = event.sender_id
            user = User.get_by_id(user_id)
            
            # Jika user tidak ditemukan, biarkan handler lain menangani
            if not user:
                return
                
            # Jika user adalah admin, izinkan akses ke semua fitur
            if user.role == 'admin':
                return
                
            # Jika user nonaktif, blokir akses ke fitur
            if not user.is_active:
                await event.answer("❌ Akun Anda nonaktif. Silakan hubungi admin untuk mengaktifkan kembali.", alert=True)
                # Batalkan event agar tidak diproses oleh handler lain
                event.handled = True
                return
                
            # Jika user aktif, biarkan handler lain menangani
            return
            
        except Exception as e:
            logger.error(f"Error in check_user_status: {e}")
            # Biarkan handler lain menangani jika terjadi error
            return
