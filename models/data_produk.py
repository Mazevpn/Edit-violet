import logging
from datetime import datetime
from core.database import *

logger = logging.getLogger(__name__)

class XLProduct:
    """Model untuk produk XL dalam database"""
    
    def __init__(self, id=None, nama_produk=None, kategori=None, produk_code=None,
                 harga_panel=None, harga_bayar=None, harga_jual=None,
                 deskripsi=None, status='aktif', created_at=None, updated_at=None):
        self.id = id
        self.nama_produk = nama_produk
        self.kategori = kategori
        self.produk_code = produk_code
        self.harga_panel = harga_panel
        self.harga_bayar = harga_bayar
        self.harga_jual = harga_jual
        self.deskripsi = deskripsi
        self.status = status
        self.created_at = created_at
        self.updated_at = updated_at

    @classmethod
    def sync_products_from_api(cls, api_products):
        """Sinkronisasi produk dari API response dengan database
        
        Args:
            api_products (list): Daftar produk dari API response
            
        Returns:
            dict: Statistik sinkronisasi (inserted, updated, deactivated)
        """
        stats = {
            'inserted': 0,
            'updated': 0,
            'deactivated': 0,
            'errors': 0
        }
        
        try:
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)
            
            # Ambil semua produk code yang ada di API
            api_product_codes = set()
            for product_data in api_products:
                produk_code = product_data.get('produk_code')
                if produk_code:
                    api_product_codes.add(produk_code)
            
            logger.info(f"API memiliki {len(api_product_codes)} produk")
            
            # Ambil semua produk code yang ada di database dengan status aktif
            cursor.execute("SELECT produk_code FROM data_xl WHERE status = 'aktif'")
            db_product_codes = set(row['produk_code'] for row in cursor.fetchall())
            
            logger.info(f"Database memiliki {len(db_product_codes)} produk aktif")
            
            # Cari produk yang ada di database tapi tidak ada di API (harus dinonaktifkan)
            missing_from_api = db_product_codes - api_product_codes
            
            if missing_from_api:
                logger.info(f"Menonaktifkan {len(missing_from_api)} produk yang tidak ada di API")
                
                # Nonaktifkan produk yang tidak ada di API
                for produk_code in missing_from_api:
                    try:
                        cursor.execute("""
                            UPDATE data_xl 
                            SET status = 'nonaktif', updated_at = %s 
                            WHERE produk_code = %s AND status = 'aktif'
                        """, (datetime.now(), produk_code))
                        
                        if cursor.rowcount > 0:
                            stats['deactivated'] += 1
                            logger.info(f"Produk dinonaktifkan: {produk_code}")
                    except Exception as e:
                        logger.error(f"Error menonaktifkan produk {produk_code}: {e}")
                        stats['errors'] += 1
            
            # Proses setiap produk dari API
            for product_data in api_products:
                try:
                    result = cls.save_from_api(product_data)
                    if result == "inserted":
                        stats['inserted'] += 1
                    elif result == "updated":
                        stats['updated'] += 1
                except Exception as e:
                    logger.error(f"Error memproses produk dari API: {e}")
                    stats['errors'] += 1
            
            conn.commit()
            cursor.close()
            conn.close()
            
            logger.info(f"Sinkronisasi selesai - Ditambah: {stats['inserted']}, "
                       f"Diperbarui: {stats['updated']}, Dinonaktifkan: {stats['deactivated']}, "
                       f"Error: {stats['errors']}")
            
            return stats
            
        except Exception as e:
            logger.error(f"Error dalam sinkronisasi produk: {e}")
            stats['errors'] += 1
            return stats

    @classmethod
    def save_from_api(cls, product_data):
        """Menyimpan data produk dari respons API ke database
        
        Args:
            product_data (dict): Data produk dari API
            
        Returns:
            str atau None: "inserted", "updated", atau None jika gagal
        """
        try:
            # Ekstrak data produk dari respons API
            nama_produk = product_data.get('nama_produk')
            kategori = product_data.get('kategori')
            produk_code = product_data.get('produk_code')
            
            # Konversi harga dari string ke float jika perlu
            harga_panel_str = product_data.get('harga_panel', '0.00')
            try:
                harga_panel = float(harga_panel_str)
            except (ValueError, TypeError):
                logger.warning(f"Gagal mengkonversi harga_panel: {harga_panel_str}")
                harga_panel = 0.0
            
            # harga_bayar biasanya sudah dalam bentuk integer
            harga_bayar = product_data.get('harga_bayar', 0)
            
            # Deskripsi dari API (akan digunakan hanya untuk produk baru)
            api_deskripsi = product_data.get('deskripsi', '')
            status = product_data.get('status', 'aktif')
            
            # Log data yang diekstrak untuk debugging
            logger.debug(f"Data yang diekstrak: nama={nama_produk}, kode={produk_code}, kategori={kategori}, "
                        f"harga_panel={harga_panel}, harga_bayar={harga_bayar}")
            
            # Validasi field yang diperlukan
            if not all([nama_produk, produk_code, kategori]):
                logger.error(f"Field yang diperlukan tidak lengkap: {product_data}")
                return None
            
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)
            
            # Periksa apakah produk sudah ada
            cursor.execute("SELECT id, harga_jual, deskripsi, status FROM data_xl WHERE produk_code = %s",
                          (produk_code,))
            existing_product = cursor.fetchone()
            
            result = None
            now = datetime.now()
            
            # Hitung harga jual yang benar (10% dari harga panel)
            expected_harga_jual = round(harga_panel * 1.1)
            
            if existing_product:
                # Produk sudah ada
                existing_harga_jual = existing_product.get('harga_jual')
                existing_deskripsi = existing_product.get('deskripsi')
                existing_status = existing_product.get('status')
                
                # PERBAIKAN: Periksa apakah harga jual perlu diperbarui
                if existing_harga_jual is None:
                    # Jika harga jual belum diatur, gunakan perhitungan 10% dari harga panel
                    harga_jual = expected_harga_jual
                    logger.info(f"Menetapkan harga jual baru untuk {produk_code}: {harga_jual} (10% dari harga panel {harga_panel})")
                else:
                    # Periksa apakah harga jual yang ada sudah sesuai dengan 10% dari harga panel
                    margin_error = 1  # Toleransi perbedaan 1 satuan karena pembulatan
                    if abs(existing_harga_jual - expected_harga_jual) > margin_error:
                        # Jika harga jual berbeda signifikan, perbarui ke nilai yang benar
                        harga_jual = expected_harga_jual
                        logger.info(f"Memperbarui harga jual untuk {produk_code} dari {existing_harga_jual} ke {harga_jual} "
                                   f"(10% dari harga panel {harga_panel})")
                    else:
                        # Jika harga jual sudah benar atau hampir benar, pertahankan
                        harga_jual = existing_harga_jual
                        logger.debug(f"Harga jual untuk {produk_code} sudah benar: {harga_jual}")
                
                # Gunakan deskripsi yang sudah ada jika ada
                deskripsi = existing_deskripsi if existing_deskripsi else api_deskripsi
                
                # Jika produk sebelumnya nonaktif, aktifkan kembali
                if existing_status == 'nonaktif':
                    logger.info(f"Mengaktifkan kembali produk: {nama_produk} ({produk_code})")
                
                # Update produk yang sudah ada, termasuk harga_jual jika perlu diperbarui
                cursor.execute("""
                    UPDATE data_xl 
                    SET nama_produk = %s,
                        kategori = %s,
                        harga_panel = %s,
                        harga_bayar = %s,
                        harga_jual = %s,
                        deskripsi = %s,
                        status = %s,
                        updated_at = %s
                    WHERE produk_code = %s
                """, (nama_produk,
                      kategori,
                      harga_panel,
                      harga_bayar,
                      harga_jual,
                      deskripsi,
                      status,
                      now,
                      produk_code))
                
                logger.info(f"Produk diperbarui: {nama_produk} ({produk_code}), harga jual: {harga_jual}")
                result = "updated"
            else:
                # Tambahkan produk baru dengan harga jual 10% dari harga panel
                harga_jual = expected_harga_jual
                deskripsi = api_deskripsi
                
                logger.info(f"Menambahkan produk baru: {nama_produk} ({produk_code}), "
                           f"harga panel: {harga_panel}, harga jual: {harga_jual}")
                
                cursor.execute("""
                    INSERT INTO data_xl (nama_produk, kategori, produk_code,
                                        harga_panel, harga_bayar, harga_jual, deskripsi, status,
                                        created_at, updated_at) 
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (nama_produk,
                      kategori,
                      produk_code,
                      harga_panel,
                      harga_bayar,
                      harga_jual,
                      deskripsi,
                      status,
                      now,
                      now))
                
                logger.info(f"Produk baru ditambahkan: {nama_produk} ({produk_code})")
                result = "inserted"
            
            conn.commit()
            cursor.close()
            conn.close()
            
            return result
            
        except Exception as e:
            logger.error(f"Error menyimpan produk ke database: {e}")
            return None

    @classmethod
    def reactivate_product(cls, produk_code):
        """Mengaktifkan kembali produk yang sebelumnya nonaktif
        
        Args:
            produk_code (str): Kode produk
            
        Returns:
            bool: True jika berhasil, False jika gagal
        """
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                UPDATE data_xl 
                SET status = 'aktif', updated_at = %s 
                WHERE produk_code = %s
            """, (datetime.now(), produk_code))
            
            success = cursor.rowcount > 0
            
            conn.commit()
            cursor.close()
            conn.close()
            
            if success:
                logger.info(f"Produk {produk_code} berhasil diaktifkan kembali")
            
            return success
            
        except Exception as e:
            logger.error(f"Error mengaktifkan produk {produk_code}: {e}")
            return False

    @classmethod
    def deactivate_product(cls, produk_code):
        """Menonaktifkan produk
        
        Args:
            produk_code (str): Kode produk
            
        Returns:
            bool: True jika berhasil, False jika gagal
        """
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                UPDATE data_xl 
                SET status = 'nonaktif', updated_at = %s 
                WHERE produk_code = %s
            """, (datetime.now(), produk_code))
            
            success = cursor.rowcount > 0
            
            conn.commit()
            cursor.close()
            conn.close()
            
            if success:
                logger.info(f"Produk {produk_code} berhasil dinonaktifkan")
            
            return success
            
        except Exception as e:
            logger.error(f"Error menonaktifkan produk {produk_code}: {e}")
            return False

    @classmethod
    def get_all(cls, status='aktif'):
        """Mengambil semua produk dari database
        
        Args:
            status (str): Filter berdasarkan status ('aktif', 'nonaktif', atau 'all')
            
        Returns:
            list: Daftar objek XLProduct
        """
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        try:
            if status.lower() == 'all':
                cursor.execute("SELECT * FROM data_xl ORDER BY kategori, nama_produk")
            else:
                cursor.execute("SELECT * FROM data_xl WHERE status = %s ORDER BY kategori, nama_produk", (status,))
            
            products = []
            for row in cursor.fetchall():
                product = cls(
                    id=row['id'],
                    nama_produk=row['nama_produk'],
                    kategori=row['kategori'],
                    produk_code=row['produk_code'],
                    harga_panel=row['harga_panel'],
                    harga_bayar=row['harga_bayar'],
                    harga_jual=row.get('harga_jual'),
                    deskripsi=row['deskripsi'],
                    status=row['status'],
                    created_at=row.get('created_at'),
                    updated_at=row.get('updated_at')
                )
                products.append(product)
            
            return products
            
        finally:
            cursor.close()
            conn.close()

    @classmethod
    def get_by_category(cls, category, status='aktif'):
        """Mengambil produk berdasarkan kategori
        
        Args:
            category (str): Kategori produk
            status (str): Filter berdasarkan status ('aktif', 'nonaktif', atau 'all')
            
        Returns:
            list: Daftar objek XLProduct
        """
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        try:
            if status.lower() == 'all':
                cursor.execute("SELECT * FROM data_xl WHERE kategori = %s ORDER BY nama_produk",
                              (category,))
            else:
                cursor.execute("SELECT * FROM data_xl WHERE kategori = %s AND status = %s ORDER BY nama_produk",
                              (category, status))
            
            products = []
            for row in cursor.fetchall():
                product = cls(
                    id=row['id'],
                    nama_produk=row['nama_produk'],
                    kategori=row['kategori'],
                    produk_code=row['produk_code'],
                    harga_panel=row['harga_panel'],
                    harga_bayar=row['harga_bayar'],
                    harga_jual=row.get('harga_jual'),
                    deskripsi=row['deskripsi'],
                    status=row['status'],
                    created_at=row.get('created_at'),
                    updated_at=row.get('updated_at')
                )
                products.append(product)
            
            return products
            
        finally:
            cursor.close()
            conn.close()

    @classmethod
    def get_by_code(cls, produk_code):
        """Mengambil produk berdasarkan kode produk
        
        Args:
            produk_code (str): Kode produk
            
        Returns:
            XLProduct atau None: Objek produk jika ditemukan, None jika tidak
        """
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        try:
            cursor.execute("SELECT * FROM data_xl WHERE produk_code = %s",
                          (produk_code,))
            row = cursor.fetchone()
            
            if not row:
                return None
            
            product = cls(
                id=row['id'],
                nama_produk=row['nama_produk'],
                kategori=row['kategori'],
                produk_code=row['produk_code'],
                harga_panel=row['harga_panel'],
                harga_bayar=row['harga_bayar'],
                harga_jual=row.get('harga_jual'),
                deskripsi=row['deskripsi'],
                status=row['status'],
                created_at=row.get('created_at'),
                updated_at=row.get('updated_at')
            )
            
            return product
            
        finally:
            cursor.close()
            conn.close()

    @classmethod
    def get_categories(cls, status='aktif'):
        """Mengambil semua kategori produk yang unik
        
        Args:
            status (str): Filter berdasarkan status ('aktif', 'nonaktif', atau 'all')
            
        Returns:
            list: Daftar kategori unik
        """
        conn = get_db_connection()
        cursor = conn.cursor()
        
        try:
            if status.lower() == 'all':
                cursor.execute("SELECT DISTINCT kategori FROM data_xl ORDER BY kategori")
            else:
                cursor.execute("SELECT DISTINCT kategori FROM data_xl WHERE status = %s ORDER BY kategori",
                              (status,))
            
            categories = [row[0] for row in cursor.fetchall()]
            return categories
            
        finally:
            cursor.close()
            conn.close()

    @classmethod
    def get_inactive_products(cls):
        """Mengambil semua produk yang statusnya nonaktif
        
        Returns:
            list: Daftar objek XLProduct dengan status nonaktif
        """
        return cls.get_all(status='nonaktif')

    @classmethod
    def cleanup_old_inactive_products(cls, days=30):
        """Menghapus produk nonaktif yang sudah lama (opsional)
        
        Args:
            days (int): Jumlah hari sejak produk dinonaktifkan
            
        Returns:
            int: Jumlah produk yang dihapus
        """
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # Hapus produk yang sudah nonaktif lebih dari X hari
            cursor.execute("""
                DELETE FROM data_xl 
                WHERE status = 'nonaktif' 
                AND updated_at < DATE_SUB(NOW(), INTERVAL %s DAY)
            """, (days,))
            
            deleted_count = cursor.rowcount
            
            conn.commit()
            cursor.close()
            conn.close()
            
            if deleted_count > 0:
                logger.info(f"Menghapus {deleted_count} produk nonaktif yang sudah lama")
            
            return deleted_count
            
        except Exception as e:
            logger.error(f"Error menghapus produk nonaktif lama: {e}")
            return 0

    def save(self):
        """Menyimpan perubahan produk ke database
        
        Returns:
            bool: True jika berhasil, False jika gagal
        """
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            now = datetime.now()
            
            if self.id:
                # Update produk yang sudah ada
                cursor.execute("""
                    UPDATE data_xl 
                    SET nama_produk = %s, kategori = %s, produk_code = %s,
                        harga_panel = %s, harga_bayar = %s, harga_jual = %s,
                        deskripsi = %s, status = %s, updated_at = %s
                    WHERE id = %s
                """, (self.nama_produk, self.kategori, self.produk_code,
                      self.harga_panel, self.harga_bayar, self.harga_jual,
                      self.deskripsi, self.status, now, self.id))
            else:
                # Insert produk baru
                cursor.execute("""
                    INSERT INTO data_xl (nama_produk, kategori, produk_code,
                                        harga_panel, harga_bayar, harga_jual,
                                        deskripsi, status, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (self.nama_produk, self.kategori, self.produk_code,
                      self.harga_panel, self.harga_bayar, self.harga_jual,
                      self.deskripsi, self.status, now, now))
                
                self.id = cursor.lastrowid
            
            self.updated_at = now
            if not self.created_at:
                self.created_at = now
            
            conn.commit()
            cursor.close()
            conn.close()
            
            return True
            
        except Exception as e:
            logger.error(f"Error menyimpan produk: {e}")
            return False
