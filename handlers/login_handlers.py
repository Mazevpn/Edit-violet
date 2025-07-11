from telethon import events, Button
from telethon.events import StopPropagation
from scripts.session_msisdn import XLApi
from scripts.cek_pulsa import PulsaChecker
from scripts.cek_kuota import KuotaChecker
from keyboards.member_keyboards import back_button, otp_buttons
from core.helpers import format_phone_number
from models.user import User
import logging

logger = logging.getLogger(__name__)

# Dictionary untuk menyimpan state login sementara
login_states = {}

# Dictionary global untuk menyimpan nomor telepon user
phone_number_cache = {}

async def setup_login_handlers(client):
    @client.on(events.CallbackQuery(data=b'session_login'))
    async def session_login_handler(event):
        """Handler untuk tombol login sesi"""
        try:
            user_id = event.sender_id
            # Tampilkan form untuk input nomor
            await event.edit("===================================\n"
                           "**🔑 Login Sesi XL**\n\n"
                           "Silakan masukkan nomor telepon XL Anda.\n"
                           "Format: `08xxxxxxx` atau `62xxxxxxx`\n\n"
                           "Kirim nomor telepon atau klik Batal untuk membatalkan.\n"
                           "===================================\n",
                           buttons=back_button())
            
            # Set state untuk menunggu input nomor
            login_states[user_id] = {'step': 'waiting_number'}
        except Exception as e:
            logger.error(f"Error in session login handler: {e}")
            await event.edit("❌ Terjadi kesalahan saat memproses permintaan login.",
                           buttons=back_button())

    @client.on(events.CallbackQuery(data=b'resend_otp'))
    async def resend_otp_handler(event):
        """Handler untuk tombol kirim ulang OTP"""
        user_id = event.sender_id
        
        # Cek apakah user sedang dalam proses login
        if user_id in login_states and login_states[user_id]['step'] == 'waiting_otp':
            phone_number = login_states[user_id]['phone_number']
            
            # Tampilkan pesan loading
            await event.edit("⏳ Mengirim ulang kode OTP...")
            
            # Request OTP
            otp_result = await XLApi.request_otp(phone_number)
            
            if otp_result['status_code'] != 200 or not otp_result['data'].get('success', False):
                # Jika gagal, tampilkan pesan error
                error_msg = otp_result['data'].get('data', {}).get('message', 'Terjadi kesalahan saat meminta OTP')
                await event.edit(f"❌ TERJADI KESALAHAN\n\n"
                               f"Silakan coba lagi nanti.",
                               buttons=back_button())
                return
            
            # Jika berhasil, minta user memasukkan OTP
            await event.edit(f"✅ OTP telah dikirim ulang ke nomor {phone_number}.\n\n"
                           f"Silakan masukkan kode OTP yang Anda terima:",
                           buttons=otp_buttons())
        else:
            # Jika tidak dalam proses login, kembali ke menu
            await event.edit("❌ Sesi login telah berakhir. Silakan mulai kembali.",
                           buttons=back_button())

    @client.on(events.CallbackQuery(data=b'cek_kuota'))
    async def cek_kuota_handler(event):
        """Handler untuk tombol cek kuota"""
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
            user = User.get_by_id(user_id)
            if user:
                for attr in ['msisdn', 'number', 'phone', 'phone_number', 'nomor']:
                    if hasattr(user, attr):
                        phone_number = getattr(user, attr)
                        if phone_number:
                            break
        
        if not phone_number:
            await event.answer("❌ Nomor telepon tidak ditemukan. Silakan login terlebih dahulu.", alert=True)
            return
        
        # Tampilkan pesan loading
        await event.edit("⏳ Mengecek kuota...")
        
        # Panggil API cek kuota
        kuota_result = await KuotaChecker.cek_kuota(phone_number)
        
        if kuota_result['success']:
            kuota_data = kuota_result['data']
            kuota_info = kuota_data.get('kuota', 'Informasi kuota tidak tersedia')
            
            # Tampilkan hasil cek kuota
            await event.edit(f"📊 **Informasi Kuota XL**\n\n"
                           f"**Nomor:** {phone_number}\n\n"
                           f"{kuota_info}",
                           buttons=[[Button.inline("🔄 Refresh", b"cek_kuota")],
                                   [Button.inline("📱 Lihat Produk", b"show_categories")],
                                   [Button.inline("🏠 Menu Utama", b"start")]])
        else:
            error_msg = kuota_result.get('error', 'Terjadi kesalahan saat mengecek kuota')
            await event.edit(f"❌ **Gagal Mengecek Kuota**\n\n"
                           f"{error_msg}",
                           buttons=[[Button.inline("🔄 Coba Lagi", b"cek_kuota")],
                                   [Button.inline("📱 Lihat Produk", b"show_categories")],
                                   [Button.inline("🏠 Menu Utama", b"start")]])

    @client.on(events.NewMessage())
    async def message_handler(event):
        """Handler untuk menerima pesan dari user"""
        user_id = event.sender_id
        
        # Cek apakah user sedang dalam proses login
        if user_id in login_states:
            current_step = login_states[user_id]['step']
            
            # Proses input nomor telepon
            if current_step == 'waiting_number':
                phone_number = event.message.text.strip()
                
                # Validasi format nomor telepon
                if not phone_number.isdigit() and not (phone_number.startswith('+') and phone_number[1:].isdigit()):
                    await event.respond("❌ Format nomor telepon tidak valid. Silakan masukkan hanya angka.\n\n"
                                      "Contoh: `08xxxxxxxxxx` atau `62xxxxxxxxxx`",
                                      buttons=back_button())
                    return
                
                # Format nomor telepon
                formatted_number = format_phone_number(phone_number)
                
                # Tampilkan pesan loading
                loading_msg = await event.respond("⏳ Memeriksa nomor telepon...")
                
                # Cek nomor telepon
                check_result = await XLApi.check_number(formatted_number)
                
                # Hapus pesan loading
                await loading_msg.delete()
                
                # Simpan nomor telepon di login_states terlepas dari hasil cek
                login_states[user_id]['phone_number'] = formatted_number
                
                # Simpan di cache global
                phone_number_cache[user_id] = formatted_number
                
                # Simpan di database user jika perlu
                try:
                    user = User.get_by_id(user_id)
                    if user:
                        # Coba berbagai atribut yang mungkin menyimpan nomor telepon
                        for attr in ['msisdn', 'number', 'phone', 'phone_number', 'nomor']:
                            if hasattr(user, attr):
                                setattr(user, attr, formatted_number)
                                user.save()
                                logger.info(f"Saved phone number to user.{attr}: {formatted_number}")
                                break
                except Exception as e:
                    logger.error(f"Error saving phone number to user: {e}")
                
                # Cek hasil dari check_number
                if check_result['status_code'] == 200 and check_result['data'].get('success', False):
                    # Jika cek nomor berhasil dengan success: true
                    check_message = check_result['data'].get('data', {}).get('message', '')
                    
                    # Cek apakah token berhasil diperbarui (tidak perlu OTP)
                    if 'Token berhasil diperbarui' in check_message or 'Token successfully refreshed' in check_message:
                        logger.info(f"Token refreshed successfully for {formatted_number}, skipping OTP")
                        
                        # Langsung proses login tanpa OTP
                        await handle_successful_login(event, user_id, formatted_number, client)
                        
                        # Hapus state login
                        del login_states[user_id]
                        
                        # Hentikan propagasi event
                        raise StopPropagation
                    else:
                        # Jika perlu OTP, lanjutkan ke proses OTP
                        await request_and_handle_otp(event, user_id, formatted_number)
                else:
                    # Jika cek nomor gagal, tetap lanjutkan ke proses OTP
                    await request_and_handle_otp(event, user_id, formatted_number)
                
                # Hentikan propagasi event
                raise StopPropagation
            
            # Proses input OTP
            elif current_step == 'waiting_otp':
                otp = event.message.text.strip()
                
                # Validasi format OTP
                if not otp.isdigit():
                    await event.respond("❌ Format OTP tidak valid. Silakan masukkan hanya angka.",
                                      buttons=otp_buttons())
                    return
                
                phone_number = login_states[user_id]['phone_number']
                
                # Tampilkan pesan loading
                loading_msg = await event.respond("⏳ Memverifikasi OTP...")
                
                # Verifikasi OTP
                verify_result = await XLApi.verify_otp(phone_number, otp)
                
                # Hapus pesan loading
                await loading_msg.delete()
                
                if verify_result['status_code'] == 200 and verify_result['data'].get('success', False):
                    # Jika verifikasi berhasil
                    await handle_successful_login(event, user_id, phone_number, client)
                    
                    # Hapus state login
                    del login_states[user_id]
                else:
                    # Jika verifikasi gagal
                    error_msg = verify_result['data'].get('data', {}).get('message', 'Terjadi kesalahan saat memverifikasi OTP')
                    await event.respond(f"❌ TERJADI KESALAHAN\n\n"
                                      f"Silakan coba lagi.",
                                      buttons=otp_buttons())
                    return
                
                # Hentikan propagasi event
                raise StopPropagation

# Fungsi helper untuk menangani login yang berhasil
async def handle_successful_login(event, user_id, phone_number, client):
    """Menangani proses setelah login berhasil"""
    # Simpan nomor telepon di berbagai tempat untuk memastikan tersedia saat dibutuhkan
    # 1. Simpan di cache global
    phone_number_cache[user_id] = phone_number
    
    # 2. Simpan di global_session_data
    if not hasattr(client, 'global_session_data'):
        client.global_session_data = {}
    client.global_session_data[user_id] = {'phone_number': phone_number}
    
    # 3. Log untuk debugging
    logger.info(f"Login successful. Phone number saved: {phone_number}")
    
    # Cek pulsa otomatis setelah login berhasil
    loading_msg = await event.respond("⏳ Mengecek informasi pulsa...")
    
    # Panggil API cek pulsa
    pulsa_result = await PulsaChecker.cek_pulsa(phone_number)
    
    # Hapus pesan loading
    await loading_msg.delete()
    
    # Tampilkan hasil cek pulsa
    if pulsa_result['success']:
        pulsa_data = pulsa_result['data']
        remaining_balance = pulsa_data.get('remaining_balance', 0)
        expired_at = pulsa_data.get('expired_at', 'Tidak diketahui')
        
        await event.respond(f"✅ Login berhasil!\n\n"
                          f"**Informasi Akun XL**\n"
                          f"**Nomor:** {phone_number}\n"
                          f"**Status:** Aktif\n"
                          f"**Sisa Pulsa:** Rp {remaining_balance:,}\n"
                          f"**Masa Aktif:** {expired_at}\n\n"
                          f"Sekarang Anda dapat melihat produk XL atau cek kuota.",
                          buttons=[[Button.inline("📱 Lihat Produk", b"show_categories")],
                                  [Button.inline("📊 Cek Kuota", b"cek_kuota")],
                                  [Button.inline("🏠 Menu Utama", b"start")]])
    else:
        # Jika gagal cek pulsa, tampilkan info tanpa pulsa
        await event.respond(f"✅ Login berhasil!\n\n"
                          f"**Informasi Akun XL**\n"
                          f"**Nomor:** {phone_number}\n"
                          f"**Status:** Aktif\n\n"
                          f"Sekarang Anda dapat melihat produk XL atau cek kuota.",
                          buttons=[[Button.inline("📱 Lihat Produk", b"show_categories")],
                                  [Button.inline("📊 Cek Kuota", b"cek_kuota")],
                                  [Button.inline("🏠 Menu Utama", b"start")]])

# Fungsi helper untuk request OTP dan menangani proses OTP
async def request_and_handle_otp(event, user_id, phone_number):
    """Request OTP dan menangani proses OTP"""
    # Set state untuk menunggu OTP
    login_states[user_id]['step'] = 'waiting_otp'
    
    # Tampilkan pesan loading
    loading_msg = await event.respond("⏳ Meminta kode OTP...")
    
    # Request OTP
    otp_result = await XLApi.request_otp(phone_number)
    
    # Hapus pesan loading
    await loading_msg.delete()
    
    if otp_result['status_code'] != 200 or not otp_result['data'].get('success', False):
        # Jika gagal, tampilkan pesan error
        error_msg = otp_result['data'].get('data', {}).get('message', 'Terjadi kesalahan saat meminta OTP')
        await event.respond(f"❌ TERJADI KESALAHAN\n\n"
                          f"Silakan coba lagi nanti.",
                          buttons=back_button())
        # Reset state
        login_states[user_id]['step'] = 'waiting_number'
        return
    
    # Jika berhasil, minta user memasukkan OTP
    await event.respond(f"✅ OTP telah dikirim ke nomor {phone_number}.\n\n"
                      f"Silakan masukkan kode OTP yang Anda terima:",
                      buttons=otp_buttons())
