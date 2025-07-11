from telethon import events, Button
from models.user import User
from scripts.bayar import XLPaymentAPI
import logging
from datetime import datetime
import time
import aiohttp
from core.config import BOT_NOTIFICATION
from models.riwayat_transaksi import RiwayatTransaksi

logger = logging.getLogger(__name__)

# Dictionary untuk menyimpan proses pembayaran
payment_states = {}

# Fungsi helper untuk mendapatkan nama metode pembayaran yang lebih user-friendly
def get_payment_method_name(payment_method):
    """Mendapatkan nama metode pembayaran yang lebih user-friendly
    
    Args:
        payment_method (str): Kode metode pembayaran
        
    Returns:
        str: Nama metode pembayaran yang user-friendly
    """
    payment_methods = {
        "BALANCE": "PULSA",
        "DANA": "DANA",
        "GOPAY": "GOPAY"
    }
    return payment_methods.get(payment_method, payment_method)

async def setup_payment_handlers(client):
    @client.on(events.CallbackQuery(data=lambda d: d.startswith(b'pay_')))
    async def payment_method_handler(event):
        """Handler untuk memilih metode pembayaran"""
        user_id = event.sender_id
        
        if user_id not in payment_states:
            await event.answer("❌ Sesi pembayaran telah berakhir.")
            return
        
        # Ekstrak metode pembayaran dari data
        payment_method = event.data.decode('utf-8').split('_', 1)[1]
        product = payment_states[user_id]['product']
        
        # Dapatkan user balance
        user = User.get_by_id(user_id)
        user_balance = user.balance if user else 0
        
        # Format harga
        harga_jual = int(product.harga_jual)
        harga_jual_formatted = f"Rp {harga_jual:,}".replace(',', '.')
        
        # Cek balance user untuk semua metode pembayaran
        if user_balance < harga_jual:
            await event.edit(
                f"❌ Saldo Anda tidak mencukupi untuk membeli produk ini.\n\n"
                f"**Saldo Anda:** Rp {user_balance:,}".replace(',', '.') + f"\n"
                f"**Harga Produk:** {harga_jual_formatted}\n\n"
                f"Silakan isi saldo Anda terlebih dahulu.",
                buttons=[
                    [Button.inline("💰 Isi Saldo", b"topup_balance")],
                    [Button.inline("🔙 Kembali ke Produk", b"back_to_products")],
                    [Button.inline("🔙 Kembali ke Menu", b"back_to_menu")]
                ]
            )
            return
        
        # Simpan metode pembayaran yang dipilih
        payment_states[user_id]['payment_method'] = payment_method
        payment_states[user_id]['step'] = 'confirm_payment'
        
        # Tampilkan konfirmasi pembayaran
        await event.edit(
            f"**🛒 Konfirmasi Pembayaran**\n\n"
            f"**Produk:** {product.nama_produk}\n"
            f"**Kode Produk:** {product.produk_code}\n"
            f"**Harga:** {harga_jual_formatted}\n"
            f"**Metode Pembayaran:** {get_payment_method_name(payment_method)}\n\n"
            f"Apakah Anda yakin ingin melanjutkan pembayaran?",
            buttons=[
                [Button.inline("✅ Ya, Bayar Sekarang", b"confirm_payment")],
                [Button.inline("❌ Batal", b"cancel_payment")]
            ]
        )
    @client.on(events.CallbackQuery(data=b'confirm_payment'))
    async def confirm_payment_handler(event):
        """Handler untuk konfirmasi pembayaran"""
        user_id = event.sender_id
        
        if user_id not in payment_states or payment_states[user_id]['step'] != 'confirm_payment':
            await event.answer("❌ Sesi pembayaran telah berakhir.")
            return
        
        # Ambil data pembayaran
        product = payment_states[user_id]['product']
        payment_method = payment_states[user_id]['payment_method']
        
        # Dapatkan nomor telepon dari berbagai sumber
        from handlers.login_handlers import phone_number_cache
        phone_number = None
        
        # 1. Cek di phone_number_cache global
        if user_id in phone_number_cache:
            phone_number = phone_number_cache[user_id]
            logger.info(f"Using phone number from cache: {phone_number}")
        
        # 2. Cek di login_states
        if not phone_number:
            from handlers.login_handlers import login_states
            if user_id in login_states and 'phone_number' in login_states[user_id]:
                phone_number = login_states[user_id]['phone_number']
                # Simpan ke cache untuk penggunaan berikutnya
                phone_number_cache[user_id] = phone_number
                logger.info(f"Using phone number from login_states: {phone_number}")
        
        # 3. Cek di global_session_data
        if not phone_number and hasattr(client, 'global_session_data') and user_id in client.global_session_data:
            phone_number = client.global_session_data[user_id].get('phone_number')
            if phone_number:
                # Simpan ke cache untuk penggunaan berikutnya
                phone_number_cache[user_id] = phone_number
                logger.info(f"Using phone number from global_session_data: {phone_number}")
        
        # 4. Cek di database user
        if not phone_number:
            user = User.get_by_id(user_id)
            if user:
                # Coba berbagai atribut yang mungkin menyimpan nomor telepon
                for attr in ['msisdn', 'number', 'phone', 'phone_number', 'nomor']:
                    if hasattr(user, attr):
                        phone_number = getattr(user, attr)
                        if phone_number:
                            # Simpan ke cache untuk penggunaan berikutnya
                            phone_number_cache[user_id] = phone_number
                            logger.info(f"Using phone number from user model ({attr}): {phone_number}")
                            break
        
        if not phone_number:
            await event.edit(
                "❌ Nomor telepon tidak ditemukan. Silakan login terlebih dahulu.",
                buttons=[
                    [Button.inline("🔑 Login", b"session_login")],
                    [Button.inline("🔙 Kembali ke Menu", b"back_to_menu")]
                ]
            )
            return
        
        # Tampilkan pesan loading
        await event.edit("⏳ Memproses pembayaran...")
        
        # Proses pembayaran
        payment_result = await XLPaymentAPI.process_payment(
            msisdn=phone_number,
            produk_code=product.produk_code,
            metode_pembayaran=payment_method
        )
        
        # Cek hasil pembayaran
        if payment_result['status_code'] == 200:
            # Ambil data dari response
            payment_data = payment_result['data'].get('data', {})
            success = payment_result['data'].get('success', False)
            message = payment_data.get('message', '')
            link_pembayaran = payment_data.get('link_pembayaran')
            trx_id = payment_data.get('trx_id', 'N/A')
            produk_name = payment_data.get('produk', product.nama_produk)
            
            # Jika pembayaran berhasil
            if success:
                # Kurangi balance user untuk semua metode pembayaran
                user = User.get_by_id(user_id)
                if user:
                    # Perbaikan: Gunakan metode update_balance dengan parameter yang benar
                    # Parameter kedua adalah jumlah yang akan dikurangkan
                    # Parameter ketiga adalah is_addition=False untuk mengurangi saldo
                    harga_produk = int(product.harga_jual)
                    user.update_balance(user_id, harga_produk, is_addition=False)
                    logger.info(f"Balance updated for user {user_id} after successful payment")
                
                # Simpan transaksi berhasil ke dalam riwayat_transaksi
                try:
                    # Hitung jumlah transaksi user sebelumnya
                    jumlah_trx_user = RiwayatTransaksi.get_user_transaction_count(user_id) + 1
                    
                    # Simpan ke database dengan status 'success'
                    transaksi = RiwayatTransaksi.create(
                        trx_id=trx_id,
                        user_id=user_id,
                        nama_produk=produk_name,
                        kategori=product.kategori,
                        harga_jual=float(product.harga_jual),
                        jumlah_trx_user=jumlah_trx_user,
                        status='success'
                    )
                    
                    if transaksi:
                        logger.info(f"Transaksi berhasil disimpan ke riwayat: trx_id={trx_id}, user_id={user_id}")
                    else:
                        logger.warning(f"Gagal menyimpan transaksi ke riwayat: trx_id={trx_id}, user_id={user_id}")
                except Exception as e:
                    logger.error(f"Error menyimpan transaksi ke riwayat: {e}", exc_info=True)
                
                # Siapkan tombol default
                buttons = [
                    [Button.inline("📱 Belanja Lagi", b"show_categories")],
                    [Button.inline("🔙 Kembali ke Menu", b"back_to_menu")]
                ]
                
                # Jika ada link pembayaran, tambahkan tombol untuk membuka link
                message_text = f"✅ Pembayaran berhasil!\n\n"
                
                if link_pembayaran:
                    message_text += f"**Produk:** {produk_name}\n"
                    message_text += f"**Nomor Tujuan:** {phone_number}\n"
                    message_text += f"**ID Transaksi:** {trx_id}\n"
                    message_text += f"**Metode Pembayaran:** {get_payment_method_name(payment_method)}\n\n"
                    message_text += f"Untuk menyelesaikan transaksi, silakan klik tombol di bawah ini:"
                    
                    # Tambahkan tombol untuk membuka link pembayaran
                    buttons.insert(0, [Button.url("💳 Bayar Sekarang", link_pembayaran)])
                else:
                    message_text += f"**Produk:** {produk_name}\n"
                    message_text += f"**Nomor Tujuan:** {phone_number}\n"
                    message_text += f"**ID Transaksi:** {trx_id}\n"
                    message_text += f"**Metode Pembayaran:** {get_payment_method_name(payment_method)}\n\n"
                    message_text += f"Terima kasih telah berbelanja."
                
                # Tampilkan pesan sukses dengan atau tanpa tombol pembayaran
                await event.edit(message_text, buttons=buttons)
                
                # Kirim notifikasi ke admin tentang transaksi berhasil
                try:
                    await send_transaction_notification(user, product, payment_method, trx_id, phone_number)
                except Exception as e:
                    logger.error(f"Failed to send transaction notification: {e}")
                
                # Kirim notifikasi ke user yang melakukan transaksi
                try:
                    await send_user_transaction_notification(user_id, product, payment_method, trx_id, phone_number, link_pembayaran)
                except Exception as e:
                    logger.error(f"Failed to send user transaction notification: {e}")
                
                # Hapus state pembayaran
                del payment_states[user_id]
            else:
                # Jika pembayaran gagal atau memerlukan tindakan lebih lanjut
                # Siapkan tombol default
                buttons = [
                    [Button.inline("🔄 Coba Lagi", b"retry_payment")],
                    [Button.inline("🔙 Kembali ke Produk", b"back_to_products")],
                    [Button.inline("🔙 Kembali ke Menu", b"back_to_menu")]
                ]
                
                # Jika ada link pembayaran, tambahkan tombol untuk membuka link
                if link_pembayaran:
                    buttons.insert(0, [Button.url("💳 Bayar Sekarang", link_pembayaran)])
                
                # Tampilkan pesan error dari API jika ada
                error_message = f"⚠️ {message}" if message else "⚠️ Pembayaran gagal"
                
                await event.edit(
                    f"❌ Pembayaran gagal!\n\n"
                    f"{error_message}\n\n"
                    f"**Produk:** {produk_name}\n"
                    f"**Nomor Tujuan:** {phone_number}\n"
                    f"**ID Transaksi:** {trx_id}\n"
                    f"**Metode Pembayaran:** {get_payment_method_name(payment_method)}\n\n"
                    f"Silakan coba lagi nanti atau pilih metode pembayaran lain.",
                    buttons=buttons
                )
                
                # Kirim notifikasi ke user dengan link pembayaran jika ada
                if link_pembayaran:
                    try:
                        await send_user_transaction_notification(user_id, product, payment_method, trx_id, phone_number, link_pembayaran)
                    except Exception as e:
                        logger.error(f"Failed to send user transaction notification: {e}")
                
                # Simpan transaksi ke dalam riwayat_transaksi dengan status 'failed'
                try:
                    # Hitung jumlah transaksi user sebelumnya
                    jumlah_trx_user = RiwayatTransaksi.get_user_transaction_count(user_id) + 1
                    
                    # Simpan ke database dengan status 'failed' karena success=False
                    transaksi = RiwayatTransaksi.create(
                        trx_id=trx_id,
                        user_id=user_id,
                        nama_produk=produk_name,
                        kategori=product.kategori,
                        harga_jual=float(product.harga_jual),
                        jumlah_trx_user=jumlah_trx_user,
                        status='failed'
                    )
                    
                    if transaksi:
                        logger.info(f"Transaksi gagal disimpan ke riwayat: trx_id={trx_id}, user_id={user_id}")
                    else:
                        logger.warning(f"Gagal menyimpan transaksi gagal ke riwayat: trx_id={trx_id}, user_id={user_id}")
                except Exception as e:
                    logger.error(f"Error menyimpan transaksi gagal ke riwayat: {e}", exc_info=True)
        else:
            # Jika ada error pada API
            error_message = payment_result.get('message', f"Terjadi kesalahan pada server: Kode {payment_result['status_code']}")
            
            await event.edit(
                f"❌ {error_message}\n\n"
                f"Silakan coba lagi nanti.",
                buttons=[
                    [Button.inline("🔄 Coba Lagi", b"retry_payment")],
                    [Button.inline("🔙 Kembali ke Menu", b"back_to_menu")]
                ]
            )
            
            # Simpan transaksi gagal ke dalam riwayat_transaksi
            try:
                # Hitung jumlah transaksi user sebelumnya
                jumlah_trx_user = RiwayatTransaksi.get_user_transaction_count(user_id) + 1
                
                # Simpan ke database dengan status 'failed'
                transaksi = RiwayatTransaksi.create(
                    trx_id=f"ERR-{int(time.time())}", # Generate ID error dengan timestamp
                    user_id=user_id,
                    nama_produk=product.nama_produk,
                    kategori=product.kategori,
                    harga_jual=float(product.harga_jual),
                    jumlah_trx_user=jumlah_trx_user,
                    status='failed'
                )
                
                if transaksi:
                    logger.info(f"Transaksi gagal disimpan ke riwayat: user_id={user_id}")
                else:
                    logger.warning(f"Gagal menyimpan transaksi gagal ke riwayat: user_id={user_id}")
            except Exception as e:
                logger.error(f"Error menyimpan transaksi gagal ke riwayat: {e}", exc_info=True)


    # Fungsi untuk mengirim notifikasi transaksi ke admin
    async def send_transaction_notification(user, product, payment_method, trx_id, phone_number):
        """
        Mengirim notifikasi ke admin saat transaksi berhasil menggunakan API Telegram
        
        Args:
            user: Objek User yang melakukan transaksi
            product: Objek Product yang dibeli
            payment_method: Metode pembayaran yang digunakan
            trx_id: ID transaksi
            phone_number: Nomor telepon tujuan
        """
        try:
            # Dapatkan semua admin dari database
            admin_users = User.get_all_users(role='admin')
            
            if not admin_users:
                logger.warning("No admin users found in database for transaction notifications")
                return
            
            # Format pesan notifikasi
            username_display = f"@{user.username}" if hasattr(user, 'username') and user.username else "Tidak ada username"
            
            # Format harga dengan pemisah ribuan
            try:
                harga_formatted = f"{int(product.harga_jual):,}".replace(',', '.')
            except (ValueError, TypeError):
                harga_formatted = str(product.harga_jual)
            
            notification_message = (
                f"💰 *Transaksi Berhasil*\n\n"
                f"*ID Transaksi:* `{trx_id}`\n"
                f"*Produk:* {product.nama_produk}\n"
                f"*Harga:* Rp {harga_formatted}\n"
                f"*Metode Pembayaran:* {get_payment_method_name(payment_method)}\n"
                f"*Nomor Tujuan:* {phone_number}\n\n"
                f"*Pembeli:*\n"
                f"*ID:* `{user.user_id}`\n"
                f"*Username:* {username_display}\n"
                f"*Nama:* {user.first_name if hasattr(user, 'first_name') else 'N/A'}\n"
                f"*Waktu:* {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
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
                                logger.info(f"Sent transaction notification to admin {admin.user_id} via API")
                            else:
                                response_json = await response.json()
                                logger.error(f"Failed to send transaction notification via API: {response_json}")
                except Exception as e:
                    logger.error(f"Failed to send transaction notification to admin {admin.user_id}: {e}")
        except Exception as e:
            logger.error(f"Error sending transaction notification: {e}")
            # Re-raise exception untuk penanganan di caller
            raise

    # Fungsi untuk mengirim notifikasi transaksi ke user yang melakukan transaksi
    async def send_user_transaction_notification(user_id, product, payment_method, trx_id, phone_number, link_pembayaran=None):
        """
        Mengirim notifikasi ke user yang melakukan transaksi
        
        Args:
            user_id: ID user yang melakukan transaksi
            product: Objek Product yang dibeli
            payment_method: Metode pembayaran yang digunakan
            trx_id: ID transaksi
            phone_number: Nomor telepon tujuan
            link_pembayaran: Link pembayaran (opsional)
        """
        try:            
            # Format harga dengan pemisah ribuan
            try:
                harga_formatted = f"{int(product.harga_jual):,}".replace(',', '.')
            except (ValueError, TypeError):
                harga_formatted = str(product.harga_jual)
            
            # Buat pesan notifikasi
            notification_message = (
                f"🛒 *Detail Transaksi Anda*\n\n"
                f"*ID Transaksi:* `{trx_id}`\n"
                f"*Produk:* {product.nama_produk}\n"
                f"*Harga:* Rp {harga_formatted}\n"
                f"*Metode Pembayaran:* {get_payment_method_name(payment_method)}\n"
                f"*Nomor Tujuan:* {phone_number}\n"
                f"*Waktu:* {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            )
            
            # Tambahkan informasi link pembayaran jika ada
            if link_pembayaran:
                notification_message += "Gunakan tombol di bawah ini untuk melanjutkan pembayaran."
            else:
                notification_message += "Terima kasih telah berbelanja dengan kami! 🙏"
            
            # Siapkan tombol jika ada link pembayaran
            buttons = None
            if link_pembayaran:
                # Gunakan inline keyboard untuk mengirim tombol
                buttons = {
                    "inline_keyboard": [
                        [{"text": "💳 Bayar Sekarang", "url": link_pembayaran}]
                    ]
                }
            # Gunakan bot token dari konfigurasi
            bot_token = BOT_NOTIFICATION.get('bot_token')
            if not bot_token:
                logger.error("Bot token not found in configuration")
                return
            # Kirim notifikasi ke user menggunakan API Telegram
            async with aiohttp.ClientSession() as session:
                api_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
                payload = {
                    "chat_id": user_id,
                    "text": notification_message,
                    "parse_mode": "Markdown"
                }
                
                # Tambahkan tombol jika ada
                if buttons:
                    payload["reply_markup"] = buttons
                
                async with session.post(api_url, json=payload) as response:
                    if response.status == 200:
                        logger.info(f"Sent transaction notification to user {user_id}")
                    else:
                        response_json = await response.json()
                        logger.error(f"Failed to send user transaction notification via API: {response_json}")
                        
                        # Coba kirim tanpa format Markdown jika ada error
                        if response.status == 400:
                            # Hapus format Markdown dan coba lagi
                            plain_message = notification_message.replace('*', '').replace('`', '')
                            payload["text"] = plain_message
                            payload["parse_mode"] = ""
                            
                            async with session.post(api_url, json=payload) as retry_response:
                                if retry_response.status == 200:
                                    logger.info(f"Sent plain text transaction notification to user {user_id}")
                                else:
                                    retry_json = await retry_response.json()
                                    logger.error(f"Failed to send plain text notification: {retry_json}")
        
        except Exception as e:
            logger.error(f"Error sending user transaction notification: {e}")
            # Re-raise exception untuk penanganan di caller
            raise

    @client.on(events.CallbackQuery(data=b'retry_payment'))
    async def retry_payment_handler(event):
        """Handler untuk mencoba pembayaran lagi"""
        user_id = event.sender_id
        
        if user_id in payment_states and 'product' in payment_states[user_id]:
            # Reset step ke select_payment
            payment_states[user_id]['step'] = 'select_payment'
            
            # Tampilkan kembali detail produk dengan pilihan metode pembayaran
            product = payment_states[user_id]['product']
            harga_jual = f"Rp {int(product.harga_jual):,}".replace(',', '.')
            
            await event.edit(
                f"**📱 {product.nama_produk}**\n\n"
                f"**Kategori:** {product.kategori}\n"
                f"**Kode Produk:** {product.produk_code}\n"
                f"**Harga:** {harga_jual}\n\n"
                f"**Deskripsi:**\n{product.deskripsi or 'Tidak ada deskripsi'}\n\n"
                f"Pilih metode pembayaran:",
                buttons=[
                    [Button.inline("💰 PULSA", b"pay_BALANCE")],
                    [Button.inline("💳 DANA", b"pay_DANA")],
                    [Button.inline("💳 GOPAY", b"pay_GOPAY")],
                    [Button.inline("🔙 Kembali ke Produk", b"back_to_products")],
                    [Button.inline("🔙 Kembali ke Menu", b"back_to_menu")]
                ]
            )
        else:
            await event.answer("❌ Sesi pembayaran telah berakhir.")

    @client.on(events.CallbackQuery(data=b'cancel_payment'))
    async def cancel_payment_handler(event):
        """Handler untuk membatalkan pembayaran"""
        user_id = event.sender_id
        
        if user_id in payment_states and 'product' in payment_states[user_id]:
            # Tampilkan kembali detail produk
            product = payment_states[user_id]['product']
            harga_jual = f"Rp {int(product.harga_jual):,}".replace(',', '.')
            
            await event.edit(
                f"**📱 {product.nama_produk}**\n\n"
                f"**Kategori:** {product.kategori}\n"
                f"**Kode Produk:** {product.produk_code}\n"
                f"**Harga:** {harga_jual}\n\n"
                f"**Deskripsi:**\n{product.deskripsi or 'Tidak ada deskripsi'}\n\n"
                f"Pilih metode pembayaran:",
                buttons=[
                    [Button.inline("💰 PULSA", b"pay_BALANCE")],
                    [Button.inline("💳 DANA", b"pay_DANA")],
                    [Button.inline("💳 GOPAY", b"pay_GOPAY")],
                    [Button.inline("🔙 Kembali ke Produk", b"back_to_products")],
                    [Button.inline("🔙 Kembali ke Menu", b"back_to_menu")]
                ]
            )
        else:
            await event.answer("❌ Sesi pembayaran telah berakhir.")
            await event.edit(
                "❌ Sesi pembayaran telah berakhir. Silakan mulai kembali.",
                buttons=[[Button.inline("🔙 Kembali ke Menu", b"back_to_menu")]]
            )

