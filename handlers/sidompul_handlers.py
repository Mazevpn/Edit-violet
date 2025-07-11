from telethon import events, Button
from scripts.sidompul_kuota import SidompulChecker
from core.helpers import format_phone_number
from models.user import User
import logging

logger = logging.getLogger(__name__)

# Dictionary global untuk menyimpan nomor telepon user
phone_number_cache = {}

async def setup_sidompul_handlers(client):
    """Mendaftarkan semua handler Sidompul ke client
    
    Args:
        client: Telethon client
    """
    @client.on(events.CallbackQuery(data=b'sidompul'))
    async def sidompul_handler(event):
        """Handler untuk tombol cek Sidompul"""
        user_id = event.sender_id
        
        # Tampilkan form untuk input nomor
        await event.edit("**📊 Cek Kuota Sidompul XL**\n\n"
                        "Silakan masukkan nomor telepon XL yang ingin dicek.\n"
                        "Format: `08xxxxxxxxxx` atau `62xxxxxxxxxx`\n\n"
                        "Kirim nomor telepon atau klik Batal untuk membatalkan.",
                        buttons=[[Button.inline("🔙 Kembali", b'back_to_menu')]])
        
        # Set state untuk menunggu input nomor
        if not hasattr(client, 'conversation_state'):
            client.conversation_state = {}
        client.conversation_state[user_id] = {'waiting_for': 'sidompul_number'}

    @client.on(events.CallbackQuery(data=b'refresh_sidompul'))
    async def refresh_sidompul_handler(event):
        """Handler untuk tombol refresh Sidompul"""
        user_id = event.sender_id
        
        # Cek apakah user memiliki nomor telepon tersimpan
        phone_number = None
        
        # Cek di cache global
        if user_id in phone_number_cache:
            phone_number = phone_number_cache[user_id]
        
        # Cek di global_session_data jika belum ditemukan
        if not phone_number and hasattr(client, 'global_session_data') and user_id in client.global_session_data:
            phone_number = client.global_session_data[user_id].get('phone_number')
        
        # Cek di database user jika belum ditemukan
        if not phone_number:
            try:
                user = User.get_by_id(user_id)
                if user:
                    for attr in ['msisdn', 'number', 'phone', 'phone_number', 'nomor']:
                        if hasattr(user, attr):
                            phone_number = getattr(user, attr)
                            if phone_number:
                                break
            except Exception as e:
                logger.error(f"Error getting user from database: {e}")
        
        if not phone_number:
            await event.answer("❌ Nomor telepon tidak ditemukan. Silakan masukkan nomor terlebih dahulu.", alert=True)
            return
        
        # Tampilkan pesan loading
        await event.edit("⏳ Mengecek kuota Sidompul...")
        
        # Panggil API cek Sidompul
        sidompul_result = await SidompulChecker.cek_sidompul(phone_number)
        
        if sidompul_result['success']:
            # Format informasi Sidompul
            sidompul_info = SidompulChecker.format_sidompul_info(sidompul_result['data'])
            
            # Tampilkan hasil cek Sidompul
            await event.edit(sidompul_info,
                            buttons=[[Button.inline("🔄 Refresh", b"refresh_sidompul")],
                                    [Button.inline("🏠 Menu Utama", b"start")]])
        else:
            error_msg = sidompul_result.get('error', 'Terjadi kesalahan saat mengecek Sidompul')
            await event.edit(f"❌ **Gagal Mengecek Sidompul**\n\n"
                            f"{error_msg}",
                            buttons=[[Button.inline("🔄 Coba Lagi", b"refresh_sidompul")],
                                    [Button.inline("🏠 Menu Utama", b"start")]])

    # Handler untuk menerima nomor telepon untuk cek Sidompul
    @client.on(events.NewMessage())
    async def sidompul_message_handler(event):
        """Handler untuk menerima pesan dari user untuk cek Sidompul"""
        user_id = event.sender_id
        
        # Cek apakah user sedang dalam state menunggu input nomor untuk Sidompul
        if hasattr(client, 'conversation_state') and user_id in client.conversation_state:
            state = client.conversation_state[user_id]
            if state.get('waiting_for') == 'sidompul_number':
                # Hapus state
                del client.conversation_state[user_id]
                
                phone_number = event.message.text.strip()
                
                # Validasi format nomor telepon
                if not (phone_number.isdigit() or (phone_number.startswith('+') and phone_number[1:].isdigit())):
                    await event.respond("❌ Format nomor telepon tidak valid. Silakan masukkan hanya angka.\n\n"
                                        "Contoh: `08xxxxxxxxxx` atau `62xxxxxxxxxx`",
                                        buttons=[[Button.inline("🔙 Kembali", b'back_to_menu')]])
                    return
                
                # Format nomor telepon
                formatted_number = format_phone_number(phone_number)
                
                # Simpan nomor telepon di cache
                phone_number_cache[user_id] = formatted_number
                
                # Simpan juga di global_session_data jika ada
                if hasattr(client, 'global_session_data'):
                    if user_id not in client.global_session_data:
                        client.global_session_data[user_id] = {}
                    client.global_session_data[user_id]['phone_number'] = formatted_number
                
                # Tampilkan pesan loading
                loading_msg = await event.respond("⏳ Mengecek kuota Sidompul...")
                
                # Panggil API cek Sidompul
                sidompul_result = await SidompulChecker.cek_sidompul(formatted_number)
                
                # Hapus pesan loading
                await loading_msg.delete()
                
                if sidompul_result['success']:
                    # Format informasi Sidompul
                    sidompul_info = SidompulChecker.format_sidompul_info(sidompul_result['data'])
                    
                    # Tampilkan hasil cek Sidompul
                    await event.respond(sidompul_info,
                                        buttons=[[Button.inline("🔄 Refresh", b"refresh_sidompul")],
                                                [Button.inline("🏠 Menu Utama", b"start")]])
                else:
                    error_msg = sidompul_result.get('error', 'Terjadi kesalahan saat mengecek Sidompul')
                    await event.respond(f"❌ **Gagal Mengecek Sidompul**\n\n"
                                        f"{error_msg}",
                                        buttons=[[Button.inline("🔄 Coba Lagi", b"sidompul")],
                                                [Button.inline("🏠 Menu Utama", b"start")]])
                
                # Tandai event sebagai sudah ditangani
                event._handled = True
                return True
    
    # Mengembalikan nilai yang bukan None agar bisa di-await
    return True
