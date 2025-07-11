import json
import logging
import mysql.connector
from datetime import datetime
from decimal import Decimal
from core.config import DB_CONFIG

logger = logging.getLogger(__name__)

class Deposit:
    def __init__(self, id, user_id, order_id, amount, fee, net_amount, payment_method, 
                 status, payment_time=None, qris_data=None, unique_code=0, created_at=None, updated_at=None):
        """Initialize Deposit object with proper data type conversions"""
        self.id = int(id) if id is not None else None
        self.user_id = int(user_id)
        self.order_id = str(order_id)
        self.amount = Decimal(str(amount))
        self.fee = Decimal(str(fee)) if fee is not None else Decimal('0.00')
        self.unique_code = int(unique_code) if unique_code is not None else 0
        self.net_amount = Decimal(str(net_amount)) if net_amount is not None else Decimal('0.00')
        self.payment_method = str(payment_method)
        self.qris_data = qris_data
        self.status = str(status)
        self.payment_time = payment_time
        self.created_at = created_at
        self.updated_at = updated_at
    
    @staticmethod
    def get_connection():
        """Mendapatkan koneksi database
        
        Returns:
            Connection: Koneksi database MySQL
        """
        try:
            return mysql.connector.connect(**DB_CONFIG)
        except Exception as e:
            logger.error(f"Error connecting to database: {str(e)}")
            return None
    
    @staticmethod
    def create(user_id, order_id, amount, fee, net_amount, payment_method, status, 
               qris_data=None, unique_code=0):
        """Membuat deposit baru
        
        Args:
            user_id: ID pengguna Telegram
            order_id: ID pesanan deposit
            amount: Jumlah deposit (dalam Rupiah)
            fee: Biaya transaksi
            net_amount: Jumlah bersih yang masuk ke saldo
            payment_method: Metode pembayaran
            status: Status deposit
            qris_data: Data QRIS (opsional)
            unique_code: Kode unik (opsional)
            
        Returns:
            Deposit: Objek deposit yang dibuat, atau None jika gagal
        """
        try:
            conn = Deposit.get_connection()
            if not conn:
                return None
                
            cursor = conn.cursor()
            
            # Konversi qris_data ke JSON jika ada
            qris_data_json = None
            if qris_data:
                qris_data_json = json.dumps(qris_data)
            
            # Buat query untuk menyimpan deposit
            query = """
            INSERT INTO deposits (
                user_id, order_id, amount, fee, unique_code, net_amount, 
                payment_method, qris_data, status, created_at, updated_at
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW()
            )
            """
            
            # Eksekusi query
            cursor.execute(
                query, 
                (
                    user_id, order_id, amount, fee, unique_code, net_amount,
                    payment_method, qris_data_json, status
                )
            )
            
            # Dapatkan ID deposit yang baru dibuat
            deposit_id = cursor.lastrowid
            
            # Commit transaksi
            conn.commit()
            
            # Tutup cursor dan koneksi
            cursor.close()
            conn.close()
            
            # Buat dan kembalikan objek Deposit
            return Deposit(
                id=deposit_id,
                user_id=user_id,
                order_id=order_id,
                amount=amount,
                fee=fee,
                unique_code=unique_code,
                net_amount=net_amount,
                payment_method=payment_method,
                qris_data=qris_data,
                status=status,
                created_at=None,
                updated_at=None
            )
            
        except Exception as e:
            logger.error(f"Error creating deposit: {str(e)}")
            if 'conn' in locals() and conn:
                conn.rollback()
                conn.close()
            return None
    
    @staticmethod
    def get_by_order_id(order_id):
        """Mendapatkan deposit berdasarkan order ID
        
        Args:
            order_id: ID pesanan deposit
            
        Returns:
            Deposit: Objek deposit, atau None jika tidak ditemukan
        """
        try:
            conn = Deposit.get_connection()
            if not conn:
                return None
                
            cursor = conn.cursor(dictionary=True)
            
            # Buat query untuk mendapatkan deposit
            query = "SELECT * FROM deposits WHERE order_id = %s"
            
            # Eksekusi query
            cursor.execute(query, (order_id,))
            
            # Dapatkan hasil
            result = cursor.fetchone()
            
            # Tutup cursor dan koneksi
            cursor.close()
            conn.close()
            
            # Jika tidak ditemukan, kembalikan None
            if not result:
                return None
            
            # Parse qris_data jika ada
            qris_data = None
            if result.get('qris_data'):
                try:
                    qris_data = json.loads(result['qris_data'])
                except:
                    qris_data = result['qris_data']
            
            # Buat dan kembalikan objek Deposit
            return Deposit(
                id=result['id'],
                user_id=result['user_id'],
                order_id=result['order_id'],
                amount=result['amount'],
                fee=result['fee'],
                unique_code=result.get('unique_code', 0),
                net_amount=result['net_amount'],
                payment_method=result['payment_method'],
                qris_data=qris_data,
                status=result['status'],
                payment_time=result['payment_time'],
                created_at=result['created_at'],
                updated_at=result['updated_at']
            )
            
        except Exception as e:
            logger.error(f"Error getting deposit by order ID: {str(e)}")
            if 'conn' in locals() and conn:
                conn.close()
            return None

    def update_status(self, new_status):
        """Memperbarui status deposit"""
        try:
            conn = Deposit.get_connection()
            if not conn:
                return False
                
            cursor = conn.cursor()
            
            # Validasi status sesuai ENUM di database
            valid_statuses = ['pending', 'success', 'failed', 'expired']
            if new_status not in valid_statuses:
                logger.error(f"Status tidak valid: {new_status}")
                return False

            try:
                # Mulai transaksi
                cursor.execute("START TRANSACTION")
                
                if new_status == 'success':
                    # Periksa dan kunci data deposit yang masih pending
                    deposit_check = """
                        SELECT d.id, d.amount, d.fee, d.unique_code, d.net_amount
                        FROM deposits d
                        WHERE d.order_id = %s 
                        AND d.status = 'pending'
                        FOR UPDATE
                    """
                    cursor.execute(deposit_check, (self.order_id,))
                    deposit_data = cursor.fetchone()
                    
                    if deposit_data:
                        # Update status deposit
                        deposit_update = """
                            UPDATE deposits d
                            SET d.status = %s,
                                d.payment_time = NOW(),
                                d.updated_at = NOW()
                            WHERE d.id = %s
                            AND d.status = 'pending'
                        """
                        cursor.execute(deposit_update, ('success', deposit_data[0]))
                        
                        # Hitung total amount
                        amount = Decimal(str(deposit_data[1]))
                        fee = Decimal(str(deposit_data[2] or 0))
                        unique_code = Decimal(str(deposit_data[3] or 0))
                        net_amount = Decimal(str(deposit_data[4] or 0))
                        total_amount = net_amount  # Gunakan net_amount yang sudah dihitung
                        
                        # Update saldo user
                        balance_update = """
                            UPDATE users u
                            SET u.balance = u.balance + %s,
                                u.updated_at = NOW()
                            WHERE u.user_id = %s
                        """
                        cursor.execute(balance_update, (str(total_amount), self.user_id))
                        
                        # Commit jika semua berhasil
                        conn.commit()
                        
                        # Update object state
                        self.status = new_status
                        self.payment_time = datetime.now()
                        
                        logger.info(f"Berhasil memproses deposit {self.order_id}")
                        return True
                    else:
                        conn.rollback()
                        logger.warning(f"Deposit pending tidak ditemukan: {self.order_id}")
                        return False
                        
                else:
                    # Update untuk status non-success
                    update_query = """
                        UPDATE deposits d
                        SET d.status = %s,
                            d.updated_at = NOW()
                        WHERE d.order_id = %s
                        AND d.status = 'pending'
                    """
                    cursor.execute(update_query, (new_status, self.order_id))
                    affected = cursor.rowcount > 0
                    
                    if affected:
                        conn.commit()
                        self.status = new_status
                        logger.info(f"Status deposit {self.order_id} diubah ke {new_status}")
                        return True
                    else:
                        logger.warning(f"Deposit pending tidak ditemukan: {self.order_id}")
                        return False
                        
            except Exception as e:
                conn.rollback()
                logger.error(f"Error transaksi: {str(e)}")
                return False
                
        except Exception as e:
            logger.error(f"Error update status: {str(e)}")
            return False
            
        finally:
            if 'cursor' in locals() and cursor:
                cursor.close()
            if 'conn' in locals() and conn:
                conn.close()

    @staticmethod
    def get_pending_deposits(older_than_minutes=5, limit=20):
        """Mendapatkan daftar deposit yang masih pending
        
        Args:
            older_than_minutes: Hanya ambil deposit yang lebih lama dari x menit (default: 5)
            limit: Batas jumlah deposit yang diambil (default: 20)
            
        Returns:
            list: Daftar objek Deposit
        """
        try:
            conn = Deposit.get_connection()
            if not conn:
                return []
                
            cursor = conn.cursor(dictionary=True)
            
            # Buat query untuk mendapatkan deposit pending
            query = """
            SELECT * FROM deposits
            WHERE status = 'pending'
            AND created_at < DATE_SUB(NOW(), INTERVAL %s MINUTE)
            ORDER BY created_at ASC
            LIMIT %s
            """
            
            # Eksekusi query
            cursor.execute(query, (older_than_minutes, limit))
            
            # Dapatkan hasil
            results = cursor.fetchall()
            
            # Tutup cursor dan koneksi
            cursor.close()
            conn.close()
            
            # Buat daftar objek Deposit
            deposits = []
            for result in results:
                # Parse qris_data jika ada
                qris_data = None
                if result.get('qris_data'):
                    try:
                        qris_data = json.loads(result['qris_data'])
                    except:
                        qris_data = result['qris_data']
                
                # Buat objek Deposit
                deposit = Deposit(
                    id=result['id'],
                    user_id=result['user_id'],
                    order_id=result['order_id'],
                    amount=result['amount'],
                    fee=result['fee'],
                    unique_code=result.get('unique_code', 0),
                    net_amount=result['net_amount'],
                    payment_method=result['payment_method'],
                    qris_data=qris_data,
                    status=result['status'],
                    payment_time=result['payment_time'],
                    created_at=result['created_at'],
                    updated_at=result['updated_at']
                )
                
                deposits.append(deposit)
            
            return deposits
            
        except Exception as e:
            logger.error(f"Error getting pending deposits: {str(e)}")
            if 'conn' in locals() and conn:
                conn.close()
            return []
    
    @staticmethod
    def expire_old_deposits(older_than_minutes=30):
        """Mengubah status deposit yang sudah kedaluwarsa menjadi 'expired'
        
        Args:
            older_than_minutes: Ubah status deposit yang lebih lama dari x menit (default: 30)
            
        Returns:
            int: Jumlah deposit yang diperbarui
        """
        try:
            conn = Deposit.get_connection()
            if not conn:
                return 0
                
            cursor = conn.cursor()
            
            # Buat query untuk memperbarui status deposit
            query = """
            UPDATE deposits
            SET status = 'expired', updated_at = NOW()
            WHERE status = 'pending'
            AND created_at < DATE_SUB(NOW(), INTERVAL %s MINUTE)
            """
            
            # Eksekusi query
            cursor.execute(query, (older_than_minutes,))
            
            # Dapatkan jumlah baris yang diperbarui
            updated_count = cursor.rowcount
            
            # Commit transaksi
            conn.commit()
            
            # Tutup cursor dan koneksi
            cursor.close()
            conn.close()
            
            return updated_count
            
        except Exception as e:
            logger.error(f"Error expiring old deposits: {str(e)}")
            if 'conn' in locals() and conn:
                conn.rollback()
                conn.close()
            return 0
