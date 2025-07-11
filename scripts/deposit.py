import time
import random
import string
import qrcode
import json
import logging
import requests
import mysql.connector
from io import BytesIO
from base64 import b64encode
from models.deposit import Deposit
from models.user import User
from core.config import *

logger = logging.getLogger(__name__)

class DepositManager:
    @staticmethod
    async def create_qris_deposit(amount, user_id, username=None):
        """Membuat deposit QRIS
        
        Args:
            amount: Jumlah deposit (dalam Rupiah)
            user_id: ID pengguna Telegram
            username: Username Telegram (opsional)
            
        Returns:
            dict: Hasil pembuatan deposit QRIS
        """
        try:
            # Validasi jumlah deposit
            if amount < 10000:
                return {
                    'success': False,
                    'error': 'Jumlah deposit minimal Rp 10.000',
                    'data': None
                }
            
            if amount > 5000000:
                return {
                    'success': False,
                    'error': 'Jumlah deposit maksimal Rp 5.000.000',
                    'data': None
                }
            
            # Hitung biaya transaksi (sesuai konfigurasi)
            fee_percentage = QRIS_API_CONFIG.get('biaya_trx', 0.3) / 100
            fee_amount = int(amount * fee_percentage)
            
            # Pastikan fee minimal Rp 1
            if fee_amount < 1:
                fee_amount = 1
            
            # Buat kode unik (1-999)
            unique_code = random.randint(1, 999)
            
            # Jumlah yang harus dibayarkan (amount + fee + unique_code)
            total_amount = amount + fee_amount + unique_code
            
            # Jumlah bersih yang masuk ke saldo (sama dengan amount)
            net_amount = amount + fee_amount + unique_code
            
            # Buat ID pesanan unik
            timestamp = int(time.time())
            random_suffix = ''.join(random.choices(string.digits, k=4))
            order_id = f"DEP{user_id}{timestamp}{random_suffix}"
            
            # Buat QRIS dinamis dengan jumlah pembayaran
            qris_data = await DepositManager.generate_dynamic_qris(
                amount=total_amount,
                order_id=order_id,
                user_id=user_id
            )
            
            if not qris_data:
                return {
                    'success': False,
                    'error': 'Gagal membuat QRIS',
                    'data': None
                }
            
            # Data QRIS untuk disimpan
            qris_data_to_save = {
                'qris_string': qris_data.get('qris_string', ''),
                'qris_image_base64': qris_data.get('qris_image_base64', ''),
                'amount': amount,
                'fee_amount': fee_amount,
                'unique_code': unique_code,
                'total_amount': total_amount,
                'net_amount': net_amount,
                'external_id': order_id
            }
            
            # Simpan data deposit ke database
            deposit = Deposit.create(
                user_id=user_id,
                order_id=order_id,
                amount=amount,
                fee=fee_amount,
                unique_code=unique_code,
                net_amount=net_amount,
                payment_method='qris',
                qris_data=qris_data_to_save,
                status='pending'
            )
            
            if not deposit:
                logger.error(f"Failed to save deposit to database: {order_id}")
                return {
                    'success': False,
                    'error': 'Gagal menyimpan data deposit',
                    'data': None
                }
            
            # Ambil gambar QR code dari data
            qris_image_base64 = qris_data.get('qris_image_base64', '')
            
            # Log hasil
            logger.info(f"QRIS deposit created: {order_id} for user {user_id}, amount: {amount}, fee: {fee_amount}, unique_code: {unique_code}, total_amount: {total_amount}")
            
            return {
                'success': True,
                'data': {
                    'order_id': order_id,
                    'amount': amount,
                    'fee_amount': fee_amount,
                    'unique_code': unique_code,
                    'total_amount': total_amount,
                    'net_amount': net_amount,
                    'qris_string': qris_data.get('qris_string', ''),
                    'qris_image': qris_image_base64,
                    'created_at': int(time.time())
                }
            }
            
        except Exception as e:
            logger.error(f"Unexpected error in create_qris_deposit: {str(e)}")
            return {
                'success': False,
                'error': f"Terjadi kesalahan: {str(e)}",
                'data': None
            }
    
    @staticmethod
    async def generate_dynamic_qris(amount, order_id, user_id):
        """Membuat QRIS dinamis dengan jumlah pembayaran
        
        Args:
            amount: Jumlah pembayaran (dalam Rupiah)
            order_id: ID pesanan
            user_id: ID pengguna
            
        Returns:
            dict: Data QRIS
        """
        try:
            # Ambil qris_string dari konfigurasi
            qris_string_template = QRIS_API_CONFIG.get('qris_string')
            
            if not qris_string_template:
                logger.error("QRIS string template is missing in configuration")
                return None
            
            # Hapus 4 karakter terakhir (CRC16)
            qris_string_without_crc = qris_string_template[:-4]
            
            # Ubah versi QRIS dari 01 menjadi 02 (dinamis)
            # Ganti "010211" dengan "010212"
            if "010211" in qris_string_without_crc:
                qris_string_without_crc = qris_string_without_crc.replace("010211", "010212")
            
            # Pisahkan string pada "5802ID"
            parts = qris_string_without_crc.split("5802ID")
            
            if len(parts) != 2:
                logger.error("Invalid QRIS string format, cannot find '5802ID'")
                return None
            
            # Format jumlah pembayaran (dalam Rupiah, bukan sen)
            amount_str = str(int(amount))
            amount_field = f"54{len(amount_str):02d}{amount_str}"
            
            # Gabungkan kembali dengan menambahkan amount_field sebelum "5802ID"
            modified_qris_string = parts[0] + amount_field + "5802ID" + parts[1]
            
            # Hitung CRC16 dan tambahkan ke string QRIS
            crc = DepositManager.calculate_crc16(modified_qris_string)
            final_qris_string = modified_qris_string + crc
            
            # Buat QR code dari string QRIS yang telah dimodifikasi
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=4,
            )
            qr.add_data(final_qris_string)
            qr.make(fit=True)
            
            img = qr.make_image(fill_color="black", back_color="white")
            
            # Konversi gambar ke base64
            buffered = BytesIO()
            img.save(buffered, format="PNG")
            qris_image_base64 = f"data:image/png;base64,{b64encode(buffered.getvalue()).decode()}"
            
            # Data QRIS
            return {
                'qris_string': final_qris_string,
                'qris_image_base64': qris_image_base64,
                'external_id': order_id
            }
                
        except Exception as e:
            logger.error(f"Error generating dynamic QRIS: {str(e)}")
            return None

    @staticmethod
    def calculate_crc16(string):
        """Menghitung CRC16 untuk string QRIS
        
        Args:
            string: String QRIS
            
        Returns:
            str: CRC16 dalam format hexadecimal
        """
        crc = 0xFFFF
        for char in string:
            crc ^= (ord(char) << 8)
            for _ in range(8):
                if crc & 0x8000:
                    crc = ((crc << 1) ^ 0x1021) & 0xFFFF
                else:
                    crc = (crc << 1) & 0xFFFF
        
        # Konversi ke hexadecimal dan pastikan panjangnya 4 karakter
        hex_crc = format(crc, '04X')
        return hex_crc

    
    @staticmethod
    async def check_deposit_status(order_id):
        """Memeriksa status deposit
        
        Args:
            order_id: ID pesanan deposit
            
        Returns:
            dict: Status deposit
        """
        try:
            # Cek status di database
            deposit = Deposit.get_by_order_id(order_id)
            
            if not deposit:
                return {
                    'success': False,
                    'error': 'Deposit tidak ditemukan',
                    'data': None
                }
            
            # Jika status sudah success, langsung kembalikan
            if deposit.status == 'success':
                return {
                    'success': True,
                    'data': {
                        'order_id': deposit.order_id,
                        'status': deposit.status,
                        'is_paid': True,
                        'payment_time': deposit.payment_time
                    }
                }
            
            # Jika status expired, langsung kembalikan
            if deposit.status == 'expired':
                return {
                    'success': True,
                    'data': {
                        'order_id': deposit.order_id,
                        'status': deposit.status,
                        'is_paid': False,
                        'payment_time': None
                    }
                }
            
            # Cek status pembayaran di API
            payment_status = await DepositManager.check_payment_status_api(deposit)
            
            if payment_status.get('is_paid'):
                # Jika sudah dibayar, proses deposit
                await DepositManager.process_successful_deposit(
                    user_id=deposit.user_id,
                    order_id=deposit.order_id
                )
                
                return {
                    'success': True,
                    'data': {
                        'order_id': deposit.order_id,
                        'status': 'success',
                        'is_paid': True,
                        'payment_time': payment_status.get('payment_time')
                    }
                }
            
            # Jika belum dibayar
            return {
                'success': True,
                'data': {
                    'order_id': deposit.order_id,
                    'status': deposit.status,
                    'is_paid': False,
                    'payment_time': None
                }
            }
            
        except Exception as e:
            logger.error(f"Error checking deposit status: {str(e)}")
            return {
                'success': False,
                'error': f"Terjadi kesalahan: {str(e)}",
                'data': None
            }
    
    @staticmethod
    async def check_payment_status_api(deposit):
        """Memeriksa status pembayaran di API QRIS
        
        Args:
            deposit: Objek Deposit
            
        Returns:
            dict: Status pembayaran
        """
        try:
            # Ambil data QRIS
            qris_data = deposit.qris_data
            
            if not qris_data or not isinstance(qris_data, dict):
                return {'is_paid': False}
            
            # Ambil total amount yang harus dibayar
            total_amount = str(qris_data.get('total_amount', 0))
            
            # Gunakan konfigurasi API QRIS dari config
            merchant_code = QRIS_API_CONFIG.get('merchant_code')
            api_key = QRIS_API_CONFIG.get('api_key')
            base_url = QRIS_API_CONFIG.get('base_url')
            
            if not merchant_code or not api_key or not base_url:
                logger.error("QRIS API configuration is missing")
                return {'is_paid': False}
            
            # Format URL dengan merchant_code dan api_key
            api_url = f"{base_url}/{merchant_code}/{api_key}"
            
            # Kirim request ke API
            response = requests.get(api_url)
            
            # Cek response
            if response.status_code == 200:
                response_data = response.json()
                
                # Handle kasus "no data"
                if response_data.get('status') == 'success' and response_data.get('message') == 'no data':
                    logger.info(f"No transactions found for deposit {deposit.order_id}")
                    return {'is_paid': False}
                
                # Handle kasus ada data transaksi
                if response_data.get('status') == 'success' and 'data' in response_data:
                    transactions = response_data['data']
                    
                    # Cari transaksi yang sesuai dengan jumlah deposit
                    for transaction in transactions:
                        if (transaction.get('amount') == total_amount and 
                            transaction.get('type') == 'CR'):
                            # Transaksi ditemukan
                            logger.info(f"Found matching transaction for deposit {deposit.order_id}")
                            return {
                                'is_paid': True,
                                'payment_time': transaction.get('date'),
                                'brand_name': transaction.get('brand_name', 'QRIS'),
                                'issuer_reff': transaction.get('issuer_reff', '-'),
                                'buyer_reff': transaction.get('buyer_reff', '-')
                            }
                    
                    logger.info(f"No matching transaction found for deposit {deposit.order_id}")
                    return {'is_paid': False}
                
            # Log error jika response tidak sesuai
            logger.error(f"Invalid API response for deposit {deposit.order_id}: {response.text}")
            return {'is_paid': False}
            
        except Exception as e:
            logger.error(f"Error checking payment status via API for deposit {deposit.order_id}: {str(e)}")
            return {'is_paid': False}
    
    @staticmethod
    async def process_successful_deposit(user_id, order_id, db_connection=None):
        """Memproses deposit yang berhasil
        
        Args:
            user_id: ID pengguna Telegram
            order_id: ID pesanan deposit
            db_connection: Koneksi database (opsional)
            
        Returns:
            bool: True jika berhasil, False jika gagal
        """
        conn = db_connection
        try:
            # Jika tidak ada koneksi database, buat koneksi baru
            if not conn:
                conn = mysql.connector.connect(**DB_CONFIG)
                
            # Dapatkan deposit dari database
            deposit = Deposit.get_by_order_id(order_id)
            if not deposit:
                logger.error(f"Deposit not found: {order_id}")
                return False
                
            # Jika status sudah success, kembalikan True
            if deposit.status == 'success':
                logger.info(f"Deposit already processed: {order_id}")
                return True
                
            # Cek status pembayaran di API
            payment_status = await DepositManager.check_payment_status_api(deposit)
            if not payment_status.get('is_paid'):
                logger.error(f"Payment not verified: {order_id}")
                return False
                
            # Mulai transaksi
            cursor = conn.cursor()
            try:
                # Set autocommit ke False untuk memulai transaksi
                conn.autocommit = False
                
                # 1. Update status deposit menjadi success
                # Pastikan status yang digunakan valid sesuai dengan definisi kolom di database
                # Biasanya kolom status adalah ENUM atau VARCHAR dengan panjang terbatas
                update_deposit_query = """
                UPDATE deposits
                SET status = %s, payment_time = %s, updated_at = NOW()
                WHERE order_id = %s AND status = 'pending'
                """
                payment_time = payment_status.get('payment_time')
                cursor.execute(update_deposit_query, ('success', payment_time, order_id))
                
                # Jika tidak ada baris yang diupdate, berarti deposit sudah diproses atau tidak ada
                if cursor.rowcount == 0:
                    logger.warning(f"No deposit updated: {order_id}")
                    conn.rollback()
                    return False
                    
                # 2. Tambahkan saldo user (termasuk fee dan kode unik)
                # Gunakan total_amount yang dibayarkan, bukan net_amount
                # total_amount = amount + fee_amount + unique_code
                total_amount = deposit.amount + deposit.fee + deposit.unique_code
                
                update_balance_query = """
                UPDATE users
                SET balance = balance + %s, updated_at = NOW()
                WHERE id = %s
                """
                cursor.execute(update_balance_query, (total_amount, user_id))
                
                # Jika tidak ada baris yang diupdate, berarti user tidak ditemukan
                if cursor.rowcount == 0:
                    logger.error(f"User not found: {user_id}")
                    conn.rollback()
                    return False
                    
                # 3. Tambahkan transaksi ke tabel transactions
                insert_transaction_query = """
                INSERT INTO transactions
                (user_id, type, amount, description, reference_id, status, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, NOW(), NOW())
                """
                
                # Dapatkan informasi pembayaran
                brand_name = payment_status.get('brand_name', 'QRIS')
                issuer_reff = payment_status.get('issuer_reff', '-')
                buyer_reff = payment_status.get('buyer_reff', '-')
                description = f"Deposit via QRIS ({brand_name}) - {issuer_reff}"
                
                # Pastikan status yang digunakan valid
                cursor.execute(insert_transaction_query, 
                            (user_id, 'deposit', total_amount, description, order_id, 'success'))
                
                # Commit transaksi
                conn.commit()
                
                # Log hasil
                logger.info(f"Deposit processed successfully: {order_id} for user {user_id}, amount: {total_amount} (including fee {deposit.fee} and unique code {deposit.unique_code})")
                
                return True
                
            except Exception as e:
                # Rollback jika terjadi error
                conn.rollback()
                logger.error(f"Error processing deposit transaction: {str(e)}")
                return False
                
            finally:
                # Tutup cursor
                cursor.close()
                
                # Tutup koneksi jika dibuat di dalam fungsi ini
                if not db_connection and conn:
                    conn.close()
                    
        except Exception as e:
            logger.error(f"Error processing successful deposit: {str(e)}")
            
            # Tutup koneksi jika dibuat di dalam fungsi ini
            if not db_connection and 'conn' in locals() and conn:
                conn.close()
                
            return False

    
    @staticmethod
    async def check_pending_deposits():
        """Memeriksa semua deposit yang masih pending
        
        Returns:
            int: Jumlah deposit yang berhasil diproses
        """
        try:
            # Dapatkan semua deposit pending yang sudah dibuat lebih dari 5 menit
            pending_deposits = Deposit.get_pending_deposits(older_than_minutes=5)
            
            if not pending_deposits:
                return 0
            
            # Buat koneksi database
            conn = mysql.connector.connect(**DB_CONFIG)
            
            # Proses setiap deposit
            processed_count = 0
            for deposit in pending_deposits:
                try:
                    # Cek status pembayaran
                    payment_status = await DepositManager.check_payment_status_api(deposit)
                    
                    if payment_status.get('is_paid'):
                        # Proses deposit
                        success = await DepositManager.process_successful_deposit(
                            user_id=deposit.user_id,
                            order_id=deposit.order_id,
                            db_connection=conn
                        )
                        
                        if success:
                            processed_count += 1
                            
                except Exception as e:
                    logger.error(f"Error processing pending deposit {deposit.order_id}: {str(e)}")
            
            # Tutup koneksi
            conn.close()
            
            return processed_count
            
        except Exception as e:
            logger.error(f"Error checking pending deposits: {str(e)}")
            return 0
    
    @staticmethod
    async def expire_old_deposits():
        """Mengubah status deposit yang sudah kedaluwarsa menjadi 'expired'
        
        Returns:
            int: Jumlah deposit yang diperbarui
        """
        try:
            # Buat koneksi database
            conn = mysql.connector.connect(**DB_CONFIG)
            cursor = conn.cursor()
            
            # Query untuk mengupdate deposit yang sudah kedaluwarsa
            # Pastikan status yang digunakan valid sesuai dengan definisi kolom di database
            update_query = """
            UPDATE deposits
            SET status = %s, updated_at = NOW()
            WHERE status = 'pending' AND created_at < DATE_SUB(NOW(), INTERVAL 30 MINUTE)
            """
            
            # Eksekusi query dengan parameter status yang valid
            cursor.execute(update_query, ('expired',))
            
            # Dapatkan jumlah baris yang diupdate
            updated_count = cursor.rowcount
            
            # Commit perubahan
            conn.commit()
            
            # Log hasil
            if updated_count > 0:
                logger.info(f"Expired {updated_count} old deposits")
                
            # Tutup koneksi
            cursor.close()
            conn.close()
            
            return updated_count
            
        except Exception as e:
            logger.error(f"Error expiring old deposits: {str(e)}")
            return 0
