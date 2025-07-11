import logging
from datetime import datetime
from core.database import get_db_connection

logger = logging.getLogger(__name__)

class RiwayatTransaksi:
    def __init__(self, trx_id, user_id, nama_produk, kategori, harga_jual, jumlah_trx_user=1,
                waktu_transaksi=None, status='pending', id=None):
        self.id = id
        self.trx_id = trx_id
        self.user_id = user_id
        self.nama_produk = nama_produk
        self.kategori = kategori
        self.harga_jual = harga_jual
        self.jumlah_trx_user = jumlah_trx_user
        self.waktu_transaksi = waktu_transaksi or datetime.now()
        self.status = status

    @classmethod
    def create(cls, trx_id, user_id, nama_produk, kategori, harga_jual, jumlah_trx_user=1, status='pending'):
        """Membuat entri transaksi baru di database
        
        Args:
            trx_id (str): ID transaksi
            user_id (int): ID pengguna Telegram
            nama_produk (str): Nama produk yang dibeli
            kategori (str): Kategori produk
            harga_jual (float): Harga jual produk
            jumlah_trx_user (int, optional): Jumlah transaksi user. Default 1.
            status (str, optional): Status transaksi. Default 'pending'.
            
        Returns:
            RiwayatTransaksi: Instance dari transaksi yang dibuat
        """
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # Periksa apakah tabel memiliki kolom status
            try:
                query = """
                INSERT INTO riwayat_transaksi
                (trx_id, user_id, nama_produk, kategori, harga_jual, jumlah_trx_user, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """
                cursor.execute(query, (trx_id, user_id, nama_produk, kategori, harga_jual, jumlah_trx_user, status))
            except Exception as column_error:
                # Jika error karena kolom status tidak ada, coba tanpa kolom status
                if "Unknown column 'status'" in str(column_error):
                    logger.warning("Column 'status' not found in table. Using alternative query.")
                    query = """
                    INSERT INTO riwayat_transaksi
                    (trx_id, user_id, nama_produk, kategori, harga_jual, jumlah_trx_user)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """
                    cursor.execute(query, (trx_id, user_id, nama_produk, kategori, harga_jual, jumlah_trx_user))
                else:
                    # Jika error bukan karena kolom status, lempar error kembali
                    raise column_error
            
            conn.commit()
            
            # Get the auto-generated ID
            last_id = cursor.lastrowid
            cursor.close()
            conn.close()
            
            return cls(
                id=last_id,
                trx_id=trx_id,
                user_id=user_id,
                nama_produk=nama_produk,
                kategori=kategori,
                harga_jual=harga_jual,
                jumlah_trx_user=jumlah_trx_user,
                status=status,
                waktu_transaksi=datetime.now()
            )
        except Exception as e:
            logger.error(f"Error creating transaction record: {e}")
            return None

    @classmethod
    def get_by_trx_id(cls, trx_id):
        """Mendapatkan transaksi berdasarkan ID transaksi
        
        Args:
            trx_id (str): ID transaksi
            
        Returns:
            RiwayatTransaksi: Instance dari transaksi yang ditemukan atau None
        """
        try:
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)
            query = "SELECT * FROM riwayat_transaksi WHERE trx_id = %s"
            cursor.execute(query, (trx_id,))
            result = cursor.fetchone()
            cursor.close()
            conn.close()
            
            if result:
                # Periksa apakah kolom status ada dalam hasil
                status = result.get('status', 'pending')
                
                return cls(
                    id=result['id'],
                    trx_id=result['trx_id'],
                    user_id=result['user_id'],
                    nama_produk=result['nama_produk'],
                    kategori=result['kategori'],
                    harga_jual=result['harga_jual'],
                    jumlah_trx_user=result['jumlah_trx_user'],
                    status=status,
                    waktu_transaksi=result['waktu_transaksi']
                )
            return None
        except Exception as e:
            logger.error(f"Error getting transaction by trx_id: {e}")
            return None

    @classmethod
    def get_by_user_id(cls, user_id, limit=10):
        """Mendapatkan daftar transaksi berdasarkan ID pengguna
        
        Args:
            user_id (int): ID pengguna Telegram
            limit (int, optional): Batas jumlah transaksi yang diambil. Default 10.
            
        Returns:
            list: Daftar instance RiwayatTransaksi
        """
        try:
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)
            query = "SELECT * FROM riwayat_transaksi WHERE user_id = %s ORDER BY waktu_transaksi DESC LIMIT %s"
            cursor.execute(query, (user_id, limit))
            results = cursor.fetchall()
            cursor.close()
            conn.close()
            
            transactions = []
            for row in results:
                # Periksa apakah kolom status ada dalam hasil
                status = row.get('status', 'pending')
                
                transactions.append(cls(
                    id=row['id'],
                    trx_id=row['trx_id'],
                    user_id=row['user_id'],
                    nama_produk=row['nama_produk'],
                    kategori=row['kategori'],
                    harga_jual=row['harga_jual'],
                    jumlah_trx_user=row['jumlah_trx_user'],
                    status=status,
                    waktu_transaksi=row['waktu_transaksi']
                ))
            return transactions
        except Exception as e:
            logger.error(f"Error getting transactions by user_id: {e}")
            return []

    def update_status(self, new_status):
        """Memperbarui status transaksi
        
        Args:
            new_status (str): Status baru
            
        Returns:
            bool: True jika berhasil, False jika gagal
        """
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # Periksa apakah tabel memiliki kolom status
            try:
                query = "UPDATE riwayat_transaksi SET status = %s WHERE trx_id = %s"
                cursor.execute(query, (new_status, self.trx_id))
            except Exception as column_error:
                # Jika error karena kolom status tidak ada, log warning
                if "Unknown column 'status'" in str(column_error):
                    logger.warning(f"Cannot update status: Column 'status' not found in table for trx_id {self.trx_id}")
                    return False
                else:
                    # Jika error bukan karena kolom status, lempar error kembali
                    raise column_error
            
            conn.commit()
            cursor.close()
            conn.close()
            
            self.status = new_status
            return True
        except Exception as e:
            logger.error(f"Error updating transaction status: {e}")
            return False

    @classmethod
    def get_user_transaction_count(cls, user_id):
        """Mendapatkan jumlah transaksi yang dilakukan oleh pengguna
        
        Args:
            user_id (int): ID pengguna Telegram
            
        Returns:
            int: Jumlah transaksi
        """
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            query = "SELECT COUNT(*) FROM riwayat_transaksi WHERE user_id = %s"
            cursor.execute(query, (user_id,))
            result = cursor.fetchone()[0]
            cursor.close()
            conn.close()
            return result
        except Exception as e:
            logger.error(f"Error getting user transaction count: {e}")
            return 0

    @classmethod
    def get_user_successful_transaction_count(cls, user_id):
        """Mendapatkan jumlah transaksi sukses yang dilakukan oleh pengguna
        
        Args:
            user_id (int): ID pengguna Telegram
            
        Returns:
            int: Jumlah transaksi sukses
        """
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # Periksa apakah tabel memiliki kolom status
            try:
                query = "SELECT COUNT(*) FROM riwayat_transaksi WHERE user_id = %s AND status = 'success'"
                cursor.execute(query, (user_id,))
            except Exception as column_error:
                # Jika error karena kolom status tidak ada, gunakan query alternatif
                if "Unknown column 'status'" in str(column_error):
                    logger.warning("Column 'status' not found in table. Returning total count instead.")
                    query = "SELECT COUNT(*) FROM riwayat_transaksi WHERE user_id = %s"
                    cursor.execute(query, (user_id,))
                else:
                    # Jika error bukan karena kolom status, lempar error kembali
                    raise column_error
            
            result = cursor.fetchone()[0]
            cursor.close()
            conn.close()
            return result
        except Exception as e:
            logger.error(f"Error getting user successful transaction count: {e}")
            return 0

    @classmethod
    def get_total_transactions(cls, status=None):
        """Mendapatkan jumlah total transaksi, opsional berdasarkan status
        
        Args:
            status (str, optional): Status transaksi. Default None (semua status).
            
        Returns:
            int: Jumlah total transaksi
        """
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            if status:
                try:
                    query = "SELECT COUNT(*) FROM riwayat_transaksi WHERE status = %s"
                    cursor.execute(query, (status,))
                except Exception as column_error:
                    # Jika error karena kolom status tidak ada, gunakan query alternatif
                    if "Unknown column 'status'" in str(column_error):
                        logger.warning("Column 'status' not found in table. Returning total count instead.")
                        query = "SELECT COUNT(*) FROM riwayat_transaksi"
                        cursor.execute(query)
                    else:
                        # Jika error bukan karena kolom status, lempar error kembali
                        raise column_error
            else:
                query = "SELECT COUNT(*) FROM riwayat_transaksi"
                cursor.execute(query)
            
            result = cursor.fetchone()[0]
            cursor.close()
            conn.close()
            return result
        except Exception as e:
            logger.error(f"Error getting total transactions: {e}")
            return 0

    @classmethod
    def get_total_revenue(cls, status='success'):
        """Mendapatkan total pendapatan dari transaksi sukses
        
        Args:
            status (str, optional): Status transaksi. Default 'success'.
            
        Returns:
            float: Total pendapatan
        """
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            try:
                query = "SELECT SUM(harga_jual) FROM riwayat_transaksi WHERE status = %s"
                cursor.execute(query, (status,))
            except Exception as column_error:
                # Jika error karena kolom status tidak ada, gunakan query alternatif
                if "Unknown column 'status'" in str(column_error):
                    logger.warning("Column 'status' not found in table. Returning total revenue instead.")
                    query = "SELECT SUM(harga_jual) FROM riwayat_transaksi"
                    cursor.execute(query)
                else:
                    # Jika error bukan karena kolom status, lempar error kembali
                    raise column_error
            
            result = cursor.fetchone()[0] or 0
            cursor.close()
            conn.close()
            return float(result)
        except Exception as e:
            logger.error(f"Error getting total revenue: {e}")
            return 0
