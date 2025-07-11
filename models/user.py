import logging
from datetime import datetime
from core.database import get_db_connection

logger = logging.getLogger(__name__)

class User:
    """Model untuk user dalam database"""
    
    def __init__(self, user_id=None, username=None, first_name=None, role='member',
                 balance=0.0, is_active=True, created_at=None, updated_at=None):
        self.user_id = user_id
        self.username = username
        self.first_name = first_name
        self.role = role
        self.balance = balance
        self.is_active = is_active
        self.created_at = created_at
        self.updated_at = updated_at
    
    @classmethod
    def get_by_id(cls, user_id):
        """
        Mengambil user berdasarkan ID Telegram
        
        Args:
            user_id (int): ID Telegram user
            
        Returns:
            User atau None: Objek user jika ditemukan, None jika tidak
        """
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
            row = cursor.fetchone()
            
            if not row:
                return None
                
            return cls(
                user_id=row['user_id'],
                username=row['username'],
                first_name=row['first_name'],
                role=row['role'],
                balance=float(row['balance']),
                is_active=bool(row['is_active']),
                created_at=row['created_at'],
                updated_at=row['updated_at']
            )
        except Exception as e:
            logger.error(f"Error getting user by ID: {e}")
            return None
        finally:
            cursor.close()
            conn.close()
    
    @classmethod
    def create_or_update(cls, user_id, username=None, first_name=None):
        """
        Membuat user baru atau memperbarui user yang sudah ada
        
        Args:
            user_id (int): ID Telegram user
            username (str, optional): Username Telegram
            first_name (str, optional): Nama depan user
            
        Returns:
            User atau None: Objek user yang dibuat/diperbarui, None jika gagal
        """
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            # Cek apakah user sudah ada
            cursor.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
            existing_user = cursor.fetchone()
            
            now = datetime.now()
            
            if existing_user:
                # Update user yang sudah ada
                cursor.execute("""
                    UPDATE users 
                    SET username = %s, first_name = %s, updated_at = %s
                    WHERE user_id = %s
                """, (username, first_name, now, user_id))
                
                logger.info(f"User updated: {user_id} ({username or 'No username'})")
            else:
                # Buat user baru
                cursor.execute("""
                    INSERT INTO users (user_id, username, first_name, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s)
                """, (user_id, username, first_name, now, now))
                
                logger.info(f"New user created: {user_id} ({username or 'No username'})")
            
            conn.commit()
            
            # Ambil user yang baru dibuat/diperbarui
            return cls.get_by_id(user_id)
        except Exception as e:
            logger.error(f"Error creating/updating user: {e}")
            conn.rollback()
            return None
        finally:
            cursor.close()
            conn.close()
    
    @classmethod
    def get_role(cls, user_id):
        """
        Mengambil role user berdasarkan ID Telegram
        
        Args:
            user_id (int): ID Telegram user
            
        Returns:
            str: Role user ('admin', 'member', dll)
        """
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute("SELECT role FROM users WHERE user_id = %s", (user_id,))
            result = cursor.fetchone()
            return result['role'] if result else 'member'
        except Exception as e:
            logger.error(f"Error getting user role: {e}")
            return 'member'
        finally:
            cursor.close()
            conn.close()
    
    @classmethod
    def set_role(cls, user_id, role):
        """
        Mengubah role user
        
        Args:
            user_id (int): ID Telegram user
            role (str): Role baru ('admin', 'member', dll)
            
        Returns:
            bool: True jika berhasil, False jika gagal
        """
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("UPDATE users SET role = %s WHERE user_id = %s", (role, user_id))
            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Error setting user role: {e}")
            conn.rollback()
            return False
        finally:
            cursor.close()
            conn.close()
    
    @classmethod
    def update_balance(cls, user_id, amount, is_addition=True):
        """
        Memperbarui saldo user
        
        Args:
            user_id (int): ID Telegram user
            amount (float): Jumlah yang akan ditambahkan/dikurangkan
            is_addition (bool): True untuk menambah, False untuk mengurangi
            
        Returns:
            float atau None: Saldo baru jika berhasil, None jika gagal
        """
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            # Ambil saldo saat ini
            cursor.execute("SELECT balance FROM users WHERE user_id = %s", (user_id,))
            result = cursor.fetchone()
            
            if not result:
                logger.warning(f"User not found when updating balance: {user_id}")
                return None
            
            current_balance = float(result['balance'])
            
            # Hitung saldo baru
            new_balance = current_balance + amount if is_addition else current_balance - amount
            
            # Pastikan saldo tidak negatif
            if new_balance < 0:
                logger.warning(f"Attempted to set negative balance for user {user_id}")
                return None
            
            # Update saldo
            cursor.execute("UPDATE users SET balance = %s WHERE user_id = %s", (new_balance, user_id))
            conn.commit()
            
            logger.info(f"Balance updated for user {user_id}: {current_balance} -> {new_balance}")
            return new_balance
        except Exception as e:
            logger.error(f"Error updating user balance: {e}")
            conn.rollback()
            return None
        finally:
            cursor.close()
            conn.close()
    
    @classmethod
    def get_all_users(cls, role=None, is_active=None):
        """
        Mengambil semua user
        
        Args:
            role (str, optional): Filter berdasarkan role
            is_active (bool, optional): Filter berdasarkan status aktif
            
        Returns:
            list: Daftar objek User
        """
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            query = "SELECT * FROM users"
            params = []
            
            # Tambahkan filter jika diperlukan
            conditions = []
            if role is not None:
                conditions.append("role = %s")
                params.append(role)
            
            if is_active is not None:
                conditions.append("is_active = %s")
                params.append(is_active)
            
            if conditions:
                query += " WHERE " + " AND ".join(conditions)
            
            query += " ORDER BY created_at DESC"
            
            cursor.execute(query, params)
            
            users = []
            for row in cursor.fetchall():
                user = cls(
                    user_id=row['user_id'],
                    username=row['username'],
                    first_name=row['first_name'],
                    role=row['role'],
                    balance=float(row['balance']),
                    is_active=bool(row['is_active']),
                    created_at=row['created_at'],
                    updated_at=row['updated_at']
                )
                users.append(user)
            
            return users
        except Exception as e:
            logger.error(f"Error getting all users: {e}")
            return []
        finally:
            cursor.close()
            conn.close()

    @classmethod
    def get_all_admins(cls):
        """
        Mengambil semua user dengan role admin yang aktif
        
        Returns:
            list: Daftar objek User dengan role admin
        """
        return cls.get_all_users(role='admin', is_active=True)


    @classmethod
    def set_active_status(cls, user_id, is_active):
        """
        Mengubah status aktif/nonaktif user
        
        Args:
            user_id (int): ID user yang akan diubah statusnya
            is_active (bool): Status baru (True untuk aktif, False untuk nonaktif)
            
        Returns:
            bool: True jika berhasil, False jika gagal
        """
        try:
            from core.database import get_db_connection
            
            conn = get_db_connection()
            cursor = conn.cursor()
            try:
                cursor.execute(
                    "UPDATE users SET is_active = %s WHERE user_id = %s",
                    (is_active, user_id)
                )
                conn.commit()
                return cursor.rowcount > 0
            finally:
                cursor.close()
                conn.close()
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error setting user active status: {e}")
            return False

