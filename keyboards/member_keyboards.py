from telethon import Button
from core.config import BOT_NOTIFICATION
def member_start_menu():
    """
    Membuat menu tombol untuk pengguna
    
    Returns:
        list: Daftar baris tombol untuk menu utama
    """
    return [
        [Button.inline("🔑 Login Sesi", b'session_login')],
        [Button.inline("📊 Sidompul cek Kuota", b'sidompul')],
        [Button.inline("📦 Deposit", b'topup_balance'),
         Button.url("📊 Status TRX", f"https://t.me/{BOT_NOTIFICATION['bot_username'][1:]}")],
         [Button.inline("📲 Kirim Chat admin", b'kirim_pesan_admin')]
    ]

def back_button():
    """
    Membuat tombol kembali
    
    Returns:
        list: Daftar baris tombol kembali
    """
    return [[Button.inline("🔙 Kembali", b'back_to_menu')]]

def otp_buttons():
    """
    Membuat tombol untuk halaman OTP
    
    Returns:
        list: Daftar baris tombol untuk halaman OTP
    """
    return [
        [Button.inline("🔄 Kirim Ulang OTP", b'resend_otp')],
        [Button.inline("❌ Batal", b'back_to_menu')]
    ]
