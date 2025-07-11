import asyncio
import logging
from models.deposit import Deposit
from models.user import User
from datetime import datetime

logger = logging.getLogger(__name__)

async def expire_old_deposits_task():
    """Tugas latar belakang untuk mengubah status deposit yang sudah kedaluwarsa"""
    while True:
        try:
            # Ubah status deposit yang sudah kedaluwarsa (lebih dari 30 menit)
            updated_count = Deposit.expire_old_deposits(older_than_minutes=30)
            if updated_count > 0:
                logger.info(f"Kedaluwarsa {updated_count} deposit lama")
        except Exception as e:
            logger.error(f"Error dalam expire_old_deposits_task: {str(e)}")
        
        # Tunggu 5 menit sebelum memeriksa lagi
        await asyncio.sleep(300)

async def check_pending_deposits_task():
    """Tugas latar belakang untuk memeriksa status deposit yang masih pending"""
    while True:
        try:
            # Dapatkan daftar deposit yang masih pending
            pending_deposits = Deposit.get_pending_deposits(older_than_minutes=5, limit=20)
            
            for deposit in pending_deposits:
                try:
                    logger.info(f"Memeriksa deposit: {deposit.order_id}")
                    
                    # Periksa apakah deposit masih pending
                    if deposit.status != 'pending':
                        continue

                    # Update status deposit
                    if deposit.update_status('success'):
                        # Log sukses
                        logger.info(f"Berhasil memproses deposit: {deposit.order_id}")
                        
                        # Dapatkan info user untuk notifikasi
                        user = User.get_by_id(deposit.user_id)
                        if user:
                            logger.info(
                                f"Deposit berhasil - User: {user.username or deposit.user_id}, "
                                f"Jumlah: {deposit.net_amount}, "
                                f"Order ID: {deposit.order_id}"
                            )
                    else:
                        logger.error(f"Gagal memproses deposit: {deposit.order_id}")
                
                except Exception as e:
                    logger.error(f"Error memproses deposit {deposit.order_id}: {str(e)}")
                
                # Tunggu sebentar antara setiap pengecekan
                await asyncio.sleep(1)
                
        except Exception as e:
            logger.error(f"Error dalam check_pending_deposits_task: {str(e)}")
        
        # Tunggu 2 menit sebelum memeriksa lagi
        await asyncio.sleep(120)

async def start_deposit_tasks():
    """Memulai semua tugas latar belakang terkait deposit
    
    Returns:
        bool: True jika berhasil memulai tugas
    """
    try:
        # Mulai tugas-tugas sebagai background tasks
        asyncio.create_task(expire_old_deposits_task())
        asyncio.create_task(check_pending_deposits_task())
        logger.info("Tugas latar belakang deposit dimulai")
        return True
    except Exception as e:
        logger.error(f"Gagal memulai tugas deposit: {str(e)}")
        return False