import os
import sys
import subprocess
import asyncio
import logging
import pytz
import io
import shutil
from datetime import datetime, time, timedelta
import aiohttp

# Tambahkan root project ke Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from core.config import DB_CONFIG, BOT_NOTIFICATION, BACKUP_CHANNEL_TELEGRAM

# Konfigurasi logger
logger = logging.getLogger(__name__)

# Set zona waktu Jakarta
JAKARTA_TZ = pytz.timezone('Asia/Jakarta')

# Batasan ukuran file Telegram Bot API (50 MB)
MAX_TELEGRAM_FILE_SIZE = 50 * 1024 * 1024  # 50 MB dalam bytes

# Interval backup dalam detik (5 menit = 300 detik)
BACKUP_INTERVAL = 5 * 60  # 5 menit

async def kirim_file_telegram(file_path, caption):
    """Mengirim file backup ke Telegram"""
    try:
        # Baca file ke memory terlebih dahulu
        with open(file_path, 'rb') as f_in:
            file_content = f_in.read()
        
        file_name = os.path.basename(file_path)
        url = f"https://api.telegram.org/bot{BOT_NOTIFICATION['bot_token']}/sendDocument"
        
        # Gunakan session baru untuk setiap pengiriman
        async with aiohttp.ClientSession() as session:
            form = aiohttp.FormData()
            form.add_field('chat_id', str(BACKUP_CHANNEL_TELEGRAM['id']))
            form.add_field('caption', caption)
            form.add_field('parse_mode', 'Markdown')
            
            # Gunakan BytesIO untuk mengirim file dari memory
            form.add_field('document',
                          io.BytesIO(file_content),
                          filename=file_name,
                          content_type='application/octet-stream')
            
            async with session.post(url, data=form) as response:
                if response.status != 200:
                    response_text = await response.text()
                    raise Exception(f"API Error: {response_text}")
                
                logger.info(f"File {file_name} berhasil dikirim ke Telegram")
                return True
                
    except Exception as e:
        logger.error(f"Error saat mengirim file: {str(e)}", exc_info=True)
        raise Exception(f"Gagal mengirim file: {str(e)}")

async def kirim_pesan_telegram(text):
    """Mengirim pesan ke Telegram"""
    try:
        url = f"https://api.telegram.org/bot{BOT_NOTIFICATION['bot_token']}/sendMessage"
        payload = {
            "chat_id": BACKUP_CHANNEL_TELEGRAM['id'],
            "text": text,
            "parse_mode": "Markdown"
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as response:
                if response.status != 200:
                    raise Exception(await response.text())
                return True
                
    except Exception as e:
        logger.error(f"Gagal mengirim pesan: {str(e)}")
        return False

def simpan_backup_permanen(file_path):
    """Menyimpan file backup ke lokasi permanen"""
    try:
        # Buat direktori backup di folder project
        backup_dir = os.path.join(project_root, "backups")
        if not os.path.exists(backup_dir):
            os.makedirs(backup_dir)
            logger.info(f"Folder backup dibuat: {backup_dir}")
        
        # Salin file ke lokasi permanen
        file_name = os.path.basename(file_path)
        permanent_location = os.path.join(backup_dir, file_name)
        shutil.copy2(file_path, permanent_location)
        
        # Batasi jumlah file backup (simpan 20 terakhir karena backup lebih sering)
        all_backups = sorted([
            os.path.join(backup_dir, f) for f in os.listdir(backup_dir)
            if f.startswith("backup_") and f.endswith(".zip")
        ], key=os.path.getmtime)  # Sort berdasarkan waktu modifikasi
        
        # Hapus file lama jika lebih dari 20
        while len(all_backups) > 20:
            oldest_backup = all_backups.pop(0)
            os.remove(oldest_backup)
            logger.info(f"Menghapus backup lama: {os.path.basename(oldest_backup)}")
        
        return permanent_location
        
    except Exception as e:
        logger.error(f"Gagal menyimpan backup permanen: {str(e)}")
        return None

async def backup_database():
    """Membuat backup database dan mengirimkannya ke channel Telegram"""
    try:
        # Pastikan folder /tmp ada
        tmp_dir = "/tmp"
        if not os.path.exists(tmp_dir):
            os.makedirs(tmp_dir)
            logger.info(f"Folder {tmp_dir} dibuat karena belum ada")
        
        # Format nama file backup dengan timestamp yang lebih detail
        timestamp = datetime.now(JAKARTA_TZ).strftime('%Y%m%d_%H%M%S')
        nama_file = f"backup_{DB_CONFIG['database']}_{timestamp}.sql"
        lokasi_file = os.path.join(tmp_dir, nama_file)
        
        # Buat backup menggunakan mysqldump
        perintah_backup = [
            'mysqldump',
            f"--host={DB_CONFIG['host']}",
            f"--user={DB_CONFIG['user']}",
            f"--password={DB_CONFIG['password']}",
            '--single-transaction',  # Untuk konsistensi data
            '--routines',            # Include stored procedures
            '--triggers',            # Include triggers
            DB_CONFIG['database']
        ]
        
        # Jalankan perintah backup
        with open(lokasi_file, 'w') as f:
            proses = subprocess.Popen(
                perintah_backup,
                stdout=f,
                stderr=subprocess.PIPE
            )
            _, stderr = proses.communicate()
            
            if proses.returncode != 0:
                raise Exception(f"Error backup: {stderr.decode()}")
        
        # Cek ukuran file
        file_size = os.path.getsize(lokasi_file)
        if file_size == 0:
            raise Exception("File backup kosong (0 byte)")
        
        # Kompres file backup
        lokasi_zip = f"{lokasi_file}.zip"
        perintah_kompres = f"zip -j {lokasi_zip} {lokasi_file}"
        kompres_result = os.system(perintah_kompres)
        
        if kompres_result != 0:
            logger.warning(f"Perintah kompresi mengembalikan kode: {kompres_result}")
        
        # Verifikasi file zip ada
        if not os.path.exists(lokasi_zip):
            raise Exception(f"File zip tidak dibuat: {lokasi_zip}")
        
        # Cek ukuran file zip
        zip_size = os.path.getsize(lokasi_zip)
        zip_size_kb = zip_size / 1024
        zip_size_mb = zip_size_kb / 1024
        
        # Format ukuran file untuk caption
        if zip_size_mb >= 1:
            size_display = f"{zip_size_mb:.2f} MB"
        else:
            size_display = f"{zip_size_kb:.2f} KB"
        
        # Format caption dengan informasi interval
        caption = (
            "📥 *BACKUP DATABASE OTOMATIS*\n\n"
            f"🗂 Database: `{DB_CONFIG['database']}`\n"
            f"⏰ Waktu: `{datetime.now(JAKARTA_TZ).strftime('%d/%m/%Y %H:%M:%S')} WIB`\n"
            f"📦 File: `{nama_file}.zip`\n"
            f"📊 Ukuran: `{size_display}`\n"
            f"🔄 Interval: `{BACKUP_INTERVAL // 60} menit`"
        )
        
        # Simpan backup ke lokasi permanen
        permanent_location = simpan_backup_permanen(lokasi_zip)
        
        # Cek apakah ukuran file melebihi batas Telegram
        if zip_size > MAX_TELEGRAM_FILE_SIZE:
            logger.warning(f"Ukuran file backup ({size_display}) melebihi batas Telegram Bot API (50 MB)")
            
            # Kirim pesan notifikasi saja
            teks_notif = (
                "📥 *BACKUP DATABASE BERHASIL*\n\n"
                f"🗂 Database: `{DB_CONFIG['database']}`\n"
                f"⏰ Waktu: `{datetime.now(JAKARTA_TZ).strftime('%d/%m/%Y %H:%M:%S')} WIB`\n"
                f"📦 File: `{nama_file}.zip`\n"
                f"📊 Ukuran: `{size_display}`\n"
                f"🔄 Interval: `{BACKUP_INTERVAL // 60} menit`\n\n"
                "⚠️ *File terlalu besar untuk dikirim melalui Telegram*\n"
                f"📁 Lokasi: `{permanent_location}`"
            )
            await kirim_pesan_telegram(teks_notif)
            logger.info(f"Backup database berhasil (terlalu besar untuk dikirim): {nama_file}")
        else:
            # Kirim file backup jika ukurannya dalam batas
            await kirim_file_telegram(lokasi_zip, caption)
            logger.info(f"Backup database berhasil dikirim: {nama_file}")
        
        # Hapus file sementara setelah berhasil dikirim
        try:
            if os.path.exists(lokasi_file):
                os.remove(lokasi_file)
                logger.debug(f"File SQL dihapus: {lokasi_file}")
            
            if os.path.exists(lokasi_zip) and permanent_location:
                # Hanya hapus file zip dari /tmp jika sudah disimpan di lokasi permanen
                os.remove(lokasi_zip)
                logger.debug(f"File ZIP dihapus dari lokasi sementara: {lokasi_zip}")
                
        except Exception as e:
            logger.warning(f"Gagal menghapus file sementara: {str(e)}")
            
    except Exception as e:
        pesan_error = f"Error backup database: {str(e)}"
        logger.error(pesan_error)
        
        # Kirim notifikasi error
        try:
            teks_error = (
                "⚠️ *ERROR BACKUP DATABASE*\n\n"
                f"❌ Error: `{str(e)}`\n"
                f"⏰ Waktu: `{datetime.now(JAKARTA_TZ).strftime('%d/%m/%Y %H:%M:%S')} WIB`\n"
                f"🔄 Interval: `{BACKUP_INTERVAL // 60} menit`"
            )
            await kirim_pesan_telegram(teks_error)
        except Exception as error_notif:
            logger.error(f"Gagal mengirim notifikasi error: {str(error_notif)}")

async def tunggu_backup_berikutnya():
    """Menunggu interval backup berikutnya (5 menit)"""
    try:
        sekarang = datetime.now(JAKARTA_TZ)
        
        # Hitung waktu backup berikutnya (5 menit dari sekarang)
        backup_berikutnya = sekarang + timedelta(seconds=BACKUP_INTERVAL)
        
        # Hitung waktu tunggu dalam detik
        detik_tunggu = BACKUP_INTERVAL
        
        menit_tunggu = detik_tunggu / 60
        logger.info(f"Menunggu {menit_tunggu:.1f} menit untuk backup berikutnya pada {backup_berikutnya.strftime('%Y-%m-%d %H:%M:%S')} WIB")
        
        await asyncio.sleep(detik_tunggu)
        
    except Exception as e:
        logger.error(f"Error dalam menghitung waktu tunggu: {str(e)}")
        # Fallback: tunggu 5 menit jika terjadi error
        logger.info("Menggunakan fallback: menunggu 5 menit")
        await asyncio.sleep(BACKUP_INTERVAL)

async def jalankan_backup():
    """Menjalankan backup database setiap 5 menit"""
    # Kirim notifikasi bahwa scheduler dimulai
    try:
        pesan_mulai = (
            "🚀 *BACKUP SCHEDULER DIMULAI*\n\n"
            f"🗂 Database: `{DB_CONFIG['database']}`\n"
            f"⏰ Dimulai: `{datetime.now(JAKARTA_TZ).strftime('%d/%m/%Y %H:%M:%S')} WIB`\n"
            f"🔄 Interval: `{BACKUP_INTERVAL // 60} menit`\n"
            f"📁 Maks backup tersimpan: `20 file`"
        )
        await kirim_pesan_telegram(pesan_mulai)
        logger.info("Scheduler backup database dimulai")
    except Exception as e:
        logger.error(f"Gagal mengirim notifikasi mulai: {str(e)}")
    
    backup_count = 0
    
    while True:
        try:
            backup_count += 1
            logger.info(f"Memulai backup ke-{backup_count}")
            
            await backup_database()
            
            # Tunggu interval berikutnya
            await tunggu_backup_berikutnya()
            
        except Exception as e:
            logger.error(f"Error dalam siklus backup ke-{backup_count}: {str(e)}", exc_info=True)
            
            # Kirim notifikasi error dengan informasi backup count
            try:
                teks_error = (
                    "⚠️ *ERROR DALAM SIKLUS BACKUP*\n\n"
                    f"❌ Error: `{str(e)}`\n"
                    f"📊 Backup ke: `{backup_count}`\n"
                    f"⏰ Waktu: `{datetime.now(JAKARTA_TZ).strftime('%d/%m/%Y %H:%M:%S')} WIB`\n"
                    f"🔄 Mencoba lagi dalam: `1 menit`"
                )
                await kirim_pesan_telegram(teks_error)
            except Exception as error_notif:
                logger.error(f"Gagal mengirim notifikasi error siklus: {str(error_notif)}")
            
            # Tunggu 1 menit sebelum mencoba lagi jika terjadi error
            logger.info("Menunggu 1 menit sebelum mencoba backup lagi...")
            await asyncio.sleep(60)

async def backup_manual():
    """Menjalankan backup manual (untuk testing)"""
    try:
        logger.info("Memulai backup manual...")
        
        # Kirim notifikasi backup manual dimulai
        pesan_manual = (
            "🔧 *BACKUP MANUAL DIMULAI*\n\n"
            f"🗂 Database: `{DB_CONFIG['database']}`\n"
            f"⏰ Waktu: `{datetime.now(JAKARTA_TZ).strftime('%d/%m/%Y %H:%M:%S')} WIB`\n"
            f"👤 Dipicu: `Manual`"
        )
        await kirim_pesan_telegram(pesan_manual)
        
        await backup_database()
        logger.info("Backup manual selesai")
        
    except Exception as e:
        logger.error(f"Error backup manual: {str(e)}")
        
        # Kirim notifikasi error backup manual
        try:
            teks_error_manual = (
                "⚠️ *ERROR BACKUP MANUAL*\n\n"
                f"❌ Error: `{str(e)}`\n"
                f"⏰ Waktu: `{datetime.now(JAKARTA_TZ).strftime('%d/%m/%Y %H:%M:%S')} WIB`"
            )
            await kirim_pesan_telegram(teks_error_manual)
        except Exception as error_notif:
            logger.error(f"Gagal mengirim notifikasi error manual: {str(error_notif)}")

async def mulai_backup_scheduler():
    """Memulai scheduler backup database"""
    try:
        logger.info(f"Memulai scheduler backup database dengan interval {BACKUP_INTERVAL // 60} menit...")
        
        # Create the backup task
        backup_task = asyncio.create_task(jalankan_backup())
        
        # Return task untuk bisa di-monitor atau di-cancel jika diperlukan
        return backup_task
        
    except Exception as e:
        logger.error(f"Error scheduler: {str(e)}")
        
        # Kirim notifikasi error scheduler
        try:
            teks_error_scheduler = (
                "⚠️ *ERROR SCHEDULER BACKUP*\n\n"
                f"❌ Error: `{str(e)}`\n"
                f"⏰ Waktu: `{datetime.now(JAKARTA_TZ).strftime('%d/%m/%Y %H:%M:%S')} WIB`"
            )
            await kirim_pesan_telegram(teks_error_scheduler)
        except Exception as error_notif:
            logger.error(f"Gagal mengirim notifikasi error scheduler: {str(error_notif)}")
        
        return None

async def hentikan_backup_scheduler(backup_task):
    """Menghentikan scheduler backup database"""
    try:
        if backup_task and not backup_task.done():
            backup_task.cancel()
            
            # Kirim notifikasi scheduler dihentikan
            pesan_stop = (
                "🛑 *BACKUP SCHEDULER DIHENTIKAN*\n\n"
                f"🗂 Database: `{DB_CONFIG['database']}`\n"
                f"⏰ Dihentikan: `{datetime.now(JAKARTA_TZ).strftime('%d/%m/%Y %H:%M:%S')} WIB`"
            )
            await kirim_pesan_telegram(pesan_stop)
            logger.info("Scheduler backup database dihentikan")
            
            return True
    except Exception as e:
        logger.error(f"Error menghentikan scheduler: {str(e)}")
        return False

def get_backup_stats():
    """Mendapatkan statistik backup"""
    try:
        backup_dir = os.path.join(project_root, "backups")
        
        if not os.path.exists(backup_dir):
            return {
                'total_backups': 0,
                'total_size': 0,
                'oldest_backup': None,
                'newest_backup': None,
                'backup_dir': backup_dir
            }
        
        # Dapatkan semua file backup
        backup_files = [
            os.path.join(backup_dir, f) for f in os.listdir(backup_dir)
            if f.startswith("backup_") and f.endswith(".zip")
        ]
        
        if not backup_files:
            return {
                'total_backups': 0,
                'total_size': 0,
                'oldest_backup': None,
                'newest_backup': None,
                'backup_dir': backup_dir
            }
        
        # Hitung total size
        total_size = sum(os.path.getsize(f) for f in backup_files)
        
        # Dapatkan file tertua dan terbaru
        backup_files_with_time = [(f, os.path.getmtime(f)) for f in backup_files]
        backup_files_with_time.sort(key=lambda x: x[1])
        
        oldest_backup = backup_files_with_time[0]
        newest_backup = backup_files_with_time[-1]
        
        return {
            'total_backups': len(backup_files),
            'total_size': total_size,
            'total_size_mb': total_size / (1024 * 1024),
            'oldest_backup': {
                'file': os.path.basename(oldest_backup[0]),
                'time': datetime.fromtimestamp(oldest_backup[1], JAKARTA_TZ)
            },
            'newest_backup': {
                'file': os.path.basename(newest_backup[0]),
                'time': datetime.fromtimestamp(newest_backup[1], JAKARTA_TZ)
            },
            'backup_dir': backup_dir
        }
        
    except Exception as e:
        logger.error(f"Error mendapatkan statistik backup: {str(e)}")
        return None

async def kirim_laporan_backup():
    """Mengirim laporan statistik backup"""
    try:
        stats = get_backup_stats()
        
        if not stats:
            await kirim_pesan_telegram("❌ Gagal mendapatkan statistik backup")
            return
        
        if stats['total_backups'] == 0:
            laporan = (
                "📊 *LAPORAN BACKUP DATABASE*\n\n"
                f"📁 Direktori: `{stats['backup_dir']}`\n"
                f"📦 Total backup: `0 file`\n"
                f"💾 Total ukuran: `0 MB`\n\n"
                "ℹ️ Belum ada file backup"
            )
        else:
            laporan = (
                "📊 *LAPORAN BACKUP DATABASE*\n\n"
                f"📁 Direktori: `{stats['backup_dir']}`\n"
                f"📦 Total backup: `{stats['total_backups']} file`\n"
                f"💾 Total ukuran: `{stats['total_size_mb']:.2f} MB`\n"
                f"🔄 Interval: `{BACKUP_INTERVAL // 60} menit`\n\n"
                f"📅 *Backup Tertua:*\n"
                f"   • File: `{stats['oldest_backup']['file']}`\n"
                f"   • Waktu: `{stats['oldest_backup']['time'].strftime('%d/%m/%Y %H:%M:%S')} WIB`\n\n"
                f"📅 *Backup Terbaru:*\n"
                f"   • File: `{stats['newest_backup']['file']}`\n"
                f"   • Waktu: `{stats['newest_backup']['time'].strftime('%d/%m/%Y %H:%M:%S')} WIB`"
            )
        
        await kirim_pesan_telegram(laporan)
        logger.info("Laporan backup berhasil dikirim")
        
    except Exception as e:
        logger.error(f"Error mengirim laporan backup: {str(e)}")

async def bersihkan_backup_lama(max_files=10):
    """Membersihkan backup lama, menyisakan sejumlah file terbaru"""
    try:
        backup_dir = os.path.join(project_root, "backups")
        
        if not os.path.exists(backup_dir):
            logger.info("Direktori backup tidak ada")
            return 0
        
        # Dapatkan semua file backup
        backup_files = [
            os.path.join(backup_dir, f) for f in os.listdir(backup_dir)
            if f.startswith("backup_") and f.endswith(".zip")
        ]
        
        if len(backup_files) <= max_files:
            logger.info(f"Jumlah backup ({len(backup_files)}) tidak melebihi batas ({max_files})")
            return 0
        
        # Sort berdasarkan waktu modifikasi (terbaru di akhir)
        backup_files.sort(key=os.path.getmtime)
        
        # Hapus file lama
        files_to_delete = backup_files[:-max_files]
        deleted_count = 0
        
        for file_path in files_to_delete:
            try:
                os.remove(file_path)
                deleted_count += 1
                logger.info(f"Menghapus backup lama: {os.path.basename(file_path)}")
            except Exception as e:
                logger.error(f"Gagal menghapus {file_path}: {str(e)}")
        
        # Kirim notifikasi pembersihan
        if deleted_count > 0:
            pesan_bersih = (
                "🧹 *PEMBERSIHAN BACKUP LAMA*\n\n"
                f"🗑️ File dihapus: `{deleted_count} file`\n"
                f"📦 File tersisa: `{len(backup_files) - deleted_count} file`\n"
                f"📁 Batas maksimal: `{max_files} file`\n"
                f"⏰ Waktu: `{datetime.now(JAKARTA_TZ).strftime('%d/%m/%Y %H:%M:%S')} WIB`"
            )
            await kirim_pesan_telegram(pesan_bersih)
        
        return deleted_count
        
    except Exception as e:
        logger.error(f"Error membersihkan backup lama: {str(e)}")
        return 0

def test_konfigurasi():
    """Test konfigurasi backup"""
    try:
        logger.info("=== TEST KONFIGURASI BACKUP ===")
        logger.info(f"Database: {DB_CONFIG['database']}")
        logger.info(f"Host: {DB_CONFIG['host']}")
        logger.info(f"User: {DB_CONFIG['user']}")
        logger.info(f"Interval backup: {BACKUP_INTERVAL // 60} menit")
        logger.info(f"Maksimal file size Telegram: {MAX_TELEGRAM_FILE_SIZE / (1024*1024):.1f} MB")
        logger.info(f"Bot token tersedia: {'Ya' if BOT_NOTIFICATION.get('bot_token') else 'Tidak'}")
        logger.info(f"Channel ID tersedia: {'Ya' if BACKUP_CHANNEL_TELEGRAM.get('id') else 'Tidak'}")
        
        # Test direktori backup
        backup_dir = os.path.join(project_root, "backups")
        logger.info(f"Direktori backup: {backup_dir}")
        logger.info(f"Direktori backup ada: {'Ya' if os.path.exists(backup_dir) else 'Tidak'}")
        
        # Test mysqldump
        try:
            result = subprocess.run(['mysqldump', '--version'], 
                                  capture_output=True, text=True)
            if result.returncode == 0:
                logger.info(f"mysqldump tersedia: {result.stdout.strip()}")
            else:
                logger.warning("mysqldump tidak tersedia atau error")
        except FileNotFoundError:
            logger.error("mysqldump tidak ditemukan di sistem")
        
        logger.info("=== SELESAI TEST KONFIGURASI ===")
        
    except Exception as e:
        logger.error(f"Error test konfigurasi: {str(e)}")

# Fungsi utama untuk menjalankan backup scheduler
if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Test konfigurasi terlebih dahulu
    test_konfigurasi()
    
    # Pilihan mode menjalankan
    import sys
    
    if len(sys.argv) > 1:
        mode = sys.argv[1].lower()
        
        if mode == "manual":
            # Backup manual
            asyncio.run(backup_manual())
        elif mode == "stats":
            # Tampilkan statistik
            asyncio.run(kirim_laporan_backup())
        elif mode == "clean":
            # Bersihkan backup lama
            max_files = int(sys.argv[2]) if len(sys.argv) > 2 else 10
            asyncio.run(bersihkan_backup_lama(max_files))
        elif mode == "test":
            # Test konfigurasi saja
            pass
        else:
            print("Mode tidak dikenal. Gunakan: manual, stats, clean, test")
    else:
        # Jalankan scheduler otomatis
        async def main():
            backup_task = await mulai_backup_scheduler()
            if backup_task:
                try:
                    await backup_task
                except asyncio.CancelledError:
                    logger.info("Backup scheduler dibatalkan")
                except Exception as e:
                    logger.error(f"Error dalam backup scheduler: {str(e)}")
        
        try:
            asyncio.run(main())
        except KeyboardInterrupt:
            logger.info("Backup scheduler dihentikan oleh user (Ctrl+C)")
        except Exception as e:
            logger.error(f"Error menjalankan backup scheduler: {str(e)}")
