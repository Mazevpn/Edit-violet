from core.database import get_db_connection
import logging

logger = logging.getLogger(__name__)

class SettingBot:
    def __init__(self, id=None, public=False, status="tutup", created_at=None, updated_at=None):
        self.id = id
        self.public = public
        self.status = status
        self.created_at = created_at
        self.updated_at = updated_at
    
    @staticmethod
    def get_settings():
        """
        Mendapatkan pengaturan bot dari database.
        Jika tidak ada pengaturan, akan membuat pengaturan default.
        """
        conn = get_db_connection()
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT * FROM setting_bot LIMIT 1")
            result = cursor.fetchone()
            
            if result:
                return SettingBot(
                    id=result['id'],
                    public=bool(result['public']),
                    status=result['status'],
                    created_at=result['created_at'],
                    updated_at=result['updated_at']
                )
            else:
                # Jika tidak ada pengaturan, buat pengaturan default
                default_settings = SettingBot()
                default_settings.save()
                return default_settings
                
        except Exception as e:
            logger.error(f"Error getting bot settings: {str(e)}")
            return None
        finally:
            cursor.close()
            conn.close()
    
    def save(self):
        """
        Menyimpan atau memperbarui pengaturan bot.
        """
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            
            if self.id:
                # Update existing settings
                query = """
                UPDATE setting_bot 
                SET public = %s, status = %s, updated_at = NOW() 
                WHERE id = %s
                """
                cursor.execute(query, (self.public, self.status, self.id))
            else:
                # Insert new settings
                query = """
                INSERT INTO setting_bot (public, status, created_at, updated_at) 
                VALUES (%s, %s, NOW(), NOW())
                """
                cursor.execute(query, (self.public, self.status))
                self.id = cursor.lastrowid
            
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            logger.error(f"Error saving bot settings: {str(e)}")
            return False
        finally:
            cursor.close()
            conn.close()
    
    @staticmethod
    def is_bot_public():
        """
        Memeriksa apakah bot dalam mode publik.
        """
        settings = SettingBot.get_settings()
        return settings.public if settings else False
    
    @staticmethod
    def get_bot_status():
        """
        Mendapatkan status bot (buka, tutup, maintenance).
        """
        settings = SettingBot.get_settings()
        return settings.status if settings else "tutup"
    
    @staticmethod
    def set_bot_public(public_status):
        """
        Mengatur mode publik bot.
        """
        settings = SettingBot.get_settings()
        if settings:
            settings.public = public_status
            return settings.save()
        return False
    
    @staticmethod
    def set_bot_status(status):
        """
        Mengatur status bot (buka, tutup, maintenance).
        """
        if status not in ["buka", "tutup", "maintenance"]:
            return False
            
        settings = SettingBot.get_settings()
        if settings:
            settings.status = status
            return settings.save()
        return False
