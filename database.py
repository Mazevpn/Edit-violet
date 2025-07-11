import mysql.connector
import logging
from core.config import DB_CONFIG

logger = logging.getLogger(__name__)

def get_db_connection():
    """
    Create and return a database connection
    
    Returns:
        mysql.connector.connection.MySQLConnection: Database connection
    """
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        return conn
    except Exception as e:
        logger.error(f"Database connection error: {e}")
        raise

async def get_user_role(user_id: int):
    """
    Get user role from database
    
    Args:
        user_id (int): Telegram user ID
        
    Returns:
        str: User role ('admin', 'member', etc.)
    """
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT role FROM users WHERE user_id = %s", (user_id,))
        result = cursor.fetchone()
        return result['role'] if result else 'member'
    finally:
        cursor.close()
        conn.close()
