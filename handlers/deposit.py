from telethon import events, Button
import asyncio
import logging
import aiohttp
import mysql.connector
from scripts.deposit import DepositManager
from keyboards.member_keyboards import back_button
from core.config import DB_CONFIG, BOT_NOTIFICATION
from models.user import User
from models.deposit import Deposit
import requests
from io import BytesIO
from base64 import b64decode
from datetime import datetime

logger = logging.getLogger(__name__)

# Dictionary untuk menyimpan data deposit yang sedang berlangsung
active_deposits = {}

async def setup_deposit_handlers(client):
    """
    Mendaftarkan semua handler deposit ke client
    
    Args:
        client: Telethon client
    """
    
    @client.on(events.CallbackQuery(data=b'topup_balance'))
    async def deposit_handler(event):
        """Handler untuk tombol deposit"""
        user_id = event.sender_id
        
        # Tampilkan form untuk input jumlah deposit
        await event.edit(
            "💰 **Deposit Saldo**\n\n"
            "Silakan masukkan jumlah deposit yang diinginkan (minimal Rp 10.000).\n"
            "Contoh: `50000` untuk deposit Rp 50.000\n\n"
            "bonus tambahan saldo periode sampai 3 juli 2025\n"
            "deposit 20k bonus 2k\n"
            "deposit 50k bonus 5k\n"
            "deposit 100k bonus 10k\n"
            "deposit satu juta bonus 100k\n"
            "hanya boleh **4 KALI CLAIM**\n"
            "untuk klaim saldo bonus chat ke admin bot\n\n"
            "Kirim jumlah deposit atau klik Kembali untuk membatalkan.",
            buttons=back_button()
        )
        
        # Set state untuk menunggu input jumlah deposit
        if not hasattr(client, 'conversation_state'):
            client.conversation_state = {}
        client.conversation_state[user_id] = {'waiting_for': 'deposit_amount'}
    
    @client.on(events.NewMessage())
    async def deposit_amount_handler(event):
        """Handler untuk menerima jumlah deposit dari user"""
        user_id = event.sender_id
        
        # Cek apakah user sedang dalam state menunggu input jumlah deposit
        if hasattr(client, 'conversation_state') and user_id in client.conversation_state:
            state = client.conversation_state[user_id]
            if state.get('waiting_for') == 'deposit_amount':
                # Hapus state
                del client.conversation_state[user_id]
                
                # Ambil jumlah deposit
                amount_text = event.message.text.strip()
                
                # Validasi input
                if not amount_text.isdigit():
                    await event.respond(
                        "❌ Jumlah deposit harus berupa angka.\n"
                        "Silakan coba lagi.",
                        buttons=back_button()
                    )
                    return
                
                amount = int(amount_text)
                
                # Validasi jumlah minimum
                if amount < 10000:
                    await event.respond(
                        "❌ Jumlah deposit minimal Rp 10.000.\n"
                        "Silakan coba lagi.",
                        buttons=back_button()
                    )
                    return
                
                # Validasi jumlah maksimum
                if amount > 5000000:
                    await event.respond(
                        "❌ Jumlah deposit maksimal Rp 5.000.000.\n"
                        "Silakan coba lagi.",
                        buttons=back_button()
                    )
                    return
                
                # Tampilkan pesan loading
                loading_msg = await event.respond("⏳ Membuat QR Code pembayaran...")
                
                # Dapatkan username jika ada
                sender = await event.get_sender()
                username = sender.username
                
                # Buat QRIS untuk deposit
                qris_result = await DepositManager.create_qris_deposit(
                    amount=amount,
                    user_id=user_id,
                    username=username
                )
                
                # Hapus pesan loading
                await loading_msg.delete()
                
                if not qris_result['success']:
                    await event.respond(
                        f"❌ Gagal membuat QR Code pembayaran: {qris_result.get('error', 'Terjadi kesalahan')}\n"
                        "Silakan coba lagi.",
                        buttons=back_button()
                    )
                    return
                
                # Simpan data deposit
                qris_data = qris_result['data']
                active_deposits[user_id] = {
                    'order_id': qris_data['order_id'],
                    'amount': amount,
                    'net_amount': qris_data['net_amount'],
                    'fee_amount': qris_data['fee_amount'],
                    'unique_code': qris_data['unique_code'],
                    'total_amount': qris_data['total_amount'],
                    'created_at': qris_data['created_at'],
                    'status': 'pending'
                }
                
                # Format jumlah deposit
                formatted_amount = f"{amount:,}".replace(',', '.')
                formatted_fee = f"{qris_data['fee_amount']:,}".replace(',', '.')
                formatted_unique = f"{qris_data['unique_code']:,}".replace(',', '.')
                formatted_total = f"{qris_data['total_amount']:,}".replace(',', '.')
                
                # Persiapkan pesan
                message = (
                    f"💰 **Deposit Saldo**\n\n"
                    f"Jumlah Deposit: Rp {formatted_amount}\n"
                    f"Kode Unik: Rp {formatted_unique}\n"
                    f"Total Pembayaran: Rp {formatted_total}\n"
                    f"Order ID: `{qris_data['order_id']}`\n\n"
                    f"Silakan scan QR Code di bawah ini untuk melakukan pembayaran.\n"
                    f"Pembayaran akan otomatis terverifikasi dalam 5-10 detik setelah pembayaran berhasil.\n\n"
                    f"⏱️ QR Code berlaku selama 30 menit."
                )
                
                # Tombol standar tanpa URL (karena kita menggunakan QR code lokal)
                buttons = [
                    [Button.inline("🔄 Cek Status Pembayaran", b"check_deposit_status")],
                    [Button.inline("❌ Batalkan", b"cancel_deposit")]
                ]
                
                try:
                    # Ambil gambar QR code dari data
                    qris_image_data = qris_data.get('qris_image')
                    if qris_image_data and isinstance(qris_image_data, str) and qris_image_data.startswith('data:image/png;base64,'):
                        # Ekstrak data base64
                        base64_data = qris_image_data.split(',')[1]
                        # Konversi ke BytesIO
                        qr_image = BytesIO(b64decode(base64_data))
                        qr_image.name = 'qris_payment.png'
                        # Kirim gambar QR code dengan pesan
                        await event.respond(
                            message,
                            file=qr_image,
                            buttons=buttons
                        )
                    else:
                        # Jika tidak ada gambar QR code, kirim pesan saja
                        await event.respond(
                            message + "\n\n⚠️ Tidak dapat menampilkan QR Code. Silakan gunakan kode QRIS berikut:\n\n`" + 
                            qris_data.get('qris_string', 'QRIS tidak tersedia') + "`",
                            buttons=buttons
                        )
                except Exception as e:
                    logger.error(f"Error sending QRIS image: {str(e)}")
                    # Jika gagal mengirim gambar, kirim pesan saja dengan kode QRIS
                    await event.respond(
                        message + "\n\n⚠️ Tidak dapat menampilkan QR Code. Silakan gunakan kode QRIS berikut:\n\n`" + 
                        qris_data.get('qris_string', 'QRIS tidak tersedia') + "`",
                        buttons=buttons
                    )
    
    @client.on(events.CallbackQuery(data=b'check_deposit_status'))
    async def check_deposit_status_handler(event):
        """Handler untuk tombol cek status deposit"""
        try:
            user_id = event.sender_id
            chat_id = event.chat_id
            
            # Cek apakah user memiliki deposit aktif
            if user_id not in active_deposits:
                await event.answer("❌ Tidak ada deposit aktif. Silakan buat deposit baru.", alert=True)
                return
            
            # Tampilkan pesan loading
            await event.answer("⏳ Memeriksa status pembayaran...")
            
            # Ambil data deposit
            deposit_data = active_deposits[user_id]
            order_id = deposit_data['order_id']
            
            # Periksa status deposit
            try:
                status_result = await DepositManager.check_deposit_status(order_id)
                
                if not status_result['success']:
                    await event.edit(
                        "❌ Gagal memeriksa status pembayaran.\n"
                        "Silakan coba lagi dalam beberapa saat.",
                        buttons=[
                            [Button.inline("🔄 Cek Lagi", b"check_deposit_status")], 
                            [Button.inline("❌ Batalkan", b"cancel_deposit")]
                        ]
                    )
                    return

                status_data = status_result['data']
                
                # Jika sudah dibayar
                if status_data['is_paid']:
                    payment_info = status_data.get('payment_info', {})
                    payment_method = payment_info.get('brand_name', 'QRIS')
                    payment_time = payment_info.get('date', 'Unknown')
                    
                    # Proses deposit
                    success = await process_successful_deposit(client, user_id, chat_id, order_id)
                    
                    if not success:
                        # Jika gagal memproses tapi pembayaran terdeteksi
                        logger.warning(f"Payment detected but processing failed for order {order_id}")
                        await event.edit(
                            "⚠️ Pembayaran terdeteksi tetapi terjadi kesalahan saat memproses.\n\n"
                            f"📝 Detail Pembayaran:\n"
                            f"• Metode: {payment_method}\n"
                            f"• Waktu: {payment_time}\n"
                            f"• Order ID: `{order_id}`\n\n"
                            "Tim kami akan memproses deposit Anda secara manual.\n"
                            "Mohon tunggu atau hubungi admin untuk bantuan.",
                            buttons=[[Button.inline("🏠 Kembali ke Menu", b"back_to_menu")]]
                        )
                    return

                # Jika belum dibayar
                formatted_amount = f"{deposit_data['amount']:,}".replace(',', '.')
                formatted_unique = f"{deposit_data['unique_code']:,}".replace(',', '.')
                formatted_total = f"{deposit_data['total_amount']:,}".replace(',', '.')
                
                # Hitung sisa waktu
                created_at = deposit_data['created_at']
                current_time = int(datetime.now().timestamp())
                time_passed = current_time - created_at
                time_left = max(0, 1800 - time_passed)  # 1800 detik = 30 menit
                
                # Jika waktu habis
                if time_left == 0:
                    await event.edit(
                        "⏰ **Waktu Pembayaran Habis**\n\n"
                        "QR Code sudah tidak berlaku. Silakan buat deposit baru.",
                        buttons=[[Button.inline("🏠 Kembali ke Menu", b"back_to_menu")]]
                    )
                    
                    # Hapus data deposit
                    del active_deposits[user_id]
                    
                    # Update status di database
                    deposit = Deposit.get_by_order_id(order_id)
                    if deposit:
                        deposit.update_status('expired')
                        logger.info(f"Deposit {order_id} expired")
                    
                    return
                
                # Format sisa waktu
                minutes_left = time_left // 60
                seconds_left = time_left % 60
                
                # Update pesan status
                await event.edit(
                    f"⏳ **Menunggu Pembayaran**\n\n"
                    f"💰 Jumlah Deposit: Rp {formatted_amount}\n"
                    f"🔢 Kode Unik: Rp {formatted_unique}\n"
                    f"💳 Total Pembayaran: Rp {formatted_total}\n"
                    f"🧾 Order ID: `{order_id}`\n\n"
                    f"⏰ Sisa Waktu: {minutes_left:02d}:{seconds_left:02d}\n\n"
                    f"📝 Status: Menunggu Pembayaran\n"
                    f"ℹ️ Silakan scan QR Code dan selesaikan pembayaran Anda.",
                    buttons=[
                        [Button.inline("🔄 Cek Status", b"check_deposit_status")],
                        [Button.inline("❌ Batalkan", b"cancel_deposit")]
                    ]
                )
                
            except Exception as e:
                logger.error(f"Error checking deposit status for {order_id}: {str(e)}")
                await event.edit(
                    "❌ Terjadi kesalahan saat memeriksa status.\n"
                    "Silakan coba lagi dalam beberapa saat.",
                    buttons=[
                        [Button.inline("🔄 Cek Lagi", b"check_deposit_status")],
                        [Button.inline("❌ Batalkan", b"cancel_deposit")]
                    ]
                )
                
        except Exception as e:
            logger.error(f"Error in check_deposit_status_handler: {str(e)}")
            await event.answer("❌ Terjadi kesalahan. Silakan coba lagi.", alert=True)
    
    @client.on(events.CallbackQuery(data=b'cancel_deposit'))
    async def cancel_deposit_handler(event):
        """Handler untuk tombol batalkan deposit"""
        user_id = event.sender_id
        
        # Cek apakah user memiliki deposit aktif
        if user_id not in active_deposits:
            await event.answer("Tidak ada deposit aktif untuk dibatalkan.", alert=True)
            return
        
        # Ambil order_id dari data deposit
        order_id = active_deposits[user_id]['order_id']
        
        # Hapus data deposit dari active_deposits
        del active_deposits[user_id]
        
        # Update status deposit di database menjadi 'failed'
        deposit = Deposit.get_by_order_id(order_id)
        if deposit:
            deposit.update_status('failed')  # Ubah dari 'cancelled' menjadi 'failed'
            logger.info(f"Deposit {order_id} for user {user_id} marked as failed (cancelled by user)")
        
        await event.edit(
            "✅ Deposit telah dibatalkan.\n\n"
            "Silakan pilih menu lain atau buat deposit baru.",
            buttons=[[Button.inline("🏠 Kembali ke Menu", b"back_to_menu")]]
        )

async def send_telegram_notification(bot_token, chat_id, text, parse_mode='Markdown'):
    """
    Mengirim notifikasi menggunakan API Telegram
    
    Args:
        bot_token (str): Token bot Telegram
        chat_id (int): ID chat tujuan
        text (str): Pesan yang akan dikirim
        parse_mode (str): Mode parsing pesan (Markdown/HTML)
        
    Returns:
        bool: True jika berhasil, False jika gagal
    """
    try:
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": parse_mode
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as response:
                if response.status == 200:
                    response_json = await response.json()
                    return response_json.get('ok', False)
                logger.error(f"Gagal kirim notifikasi: Status {response.status}")
                return False
                
    except Exception as e:
        logger.error(f"Error kirim notifikasi: {str(e)}")
        return False

async def process_successful_deposit(client, user_id, chat_id, order_id):
    """Memproses deposit yang berhasil"""
    try:
        # Dapatkan deposit dari database
        deposit = Deposit.get_by_order_id(order_id)
        if not deposit:
            logger.error(f"Deposit tidak ditemukan: {order_id}")
            return False
        
        # Jika status sudah success, kembalikan True
        if deposit.status == 'success':
            # Ambil saldo terbaru
            user = User.get_by_id(user_id)
            current_balance = user.balance if user else 0
            formatted_balance = f"{current_balance:,}".replace(',', '.')
            
            # Kirim pesan sukses
            await client.send_message(
                chat_id,
                f"✅ **Deposit Berhasil!**\n\n"
                f"Order ID: `{order_id}`\n"
                f"Jumlah Deposit: Rp {deposit.net_amount:,}".replace(',', '.') + f"\n"
                f"Saldo Saat Ini: Rp {formatted_balance}\n\n"
                f"Terima kasih atas deposit Anda.",
                buttons=[[Button.inline("🏠 Kembali ke Menu", b"back_to_menu")]]
            )
            return True
        
        # Update status deposit ke success
        if deposit.update_status('success'):
            # Format jumlah deposit
            formatted_amount = f"{deposit.net_amount:,}".replace(',', '.')
            
            # Ambil saldo terbaru
            user = User.get_by_id(user_id)
            current_balance = user.balance if user else 0
            formatted_balance = f"{current_balance:,}".replace(',', '.')
            
            # Kirim pesan sukses ke pengguna
            await client.send_message(
                chat_id,
                f"✅ **Deposit Berhasil!**\n\n"
                f"Order ID: `{order_id}`\n"
                f"Jumlah Deposit: Rp {formatted_amount}\n"
                f"Saldo Saat Ini: Rp {formatted_balance}\n\n"
                f"Terima kasih atas deposit Anda.",
                buttons=[[Button.inline("🏠 Kembali ke Menu", b"back_to_menu")]]
            )
            
            # Kirim notifikasi ke admin
            try:
                # Dapatkan admin dari database
                admins = User.get_all_admins()
                
                if admins:
                    # Dapatkan informasi pengguna
                    user_info = User.get_by_id(user_id)
                    username = f"@{user_info.username}" if user_info and user_info.username else f"User ID: {user_id}"
                    
                    # Format waktu
                    now = datetime.now()
                    formatted_time = now.strftime("%d/%m/%Y %H:%M:%S")
                    
                    # Buat pesan notifikasi
                    admin_notification = (
                        "🔔 *NOTIFIKASI DEPOSIT BARU*\n\n"
                        f"👤 Pengguna: {username}\n"
                        f"💰 Jumlah: Rp {formatted_amount}\n"
                        f"🧾 Order ID: `{order_id}`\n"
                        f"⏰ Waktu: {formatted_time}\n\n"
                        "✅ Status: Berhasil\n"
                        f"💼 Saldo: Rp {formatted_balance}"
                    )

                    # Ambil token bot dari config
                    bot_token = BOT_NOTIFICATION['bot_token']
                    
                    # Kirim notifikasi ke semua admin secara paralel
                    notification_tasks = []
                    for admin in admins:
                        task = send_telegram_notification(
                            bot_token=bot_token,
                            chat_id=admin.user_id,
                            text=admin_notification
                        )
                        notification_tasks.append(task)

                    # Tunggu semua notifikasi terkirim
                    results = await asyncio.gather(*notification_tasks, return_exceptions=True)

                    # Log hasil pengiriman
                    for admin, result in zip(admins, results):
                        if isinstance(result, Exception):
                            logger.error(f"Gagal kirim notifikasi ke admin {admin.user_id}: {str(result)}")
                        elif result:
                            logger.info(f"Notifikasi terkirim ke admin {admin.user_id}")
                        else:
                            logger.error(f"Gagal kirim notifikasi ke admin {admin.user_id}")
                            
            except Exception as e:
                logger.error(f"Error kirim notifikasi admin: {str(e)}")
            
            # Hapus dari active_deposits
            if user_id in active_deposits:
                del active_deposits[user_id]
            
            return True
            
        else:
            logger.error(f"Gagal update status deposit: {order_id}")
            return False
            
    except Exception as e:
        logger.error(f"Error proses deposit: {str(e)}")
        return False