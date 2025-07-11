import time
import hashlib
import hmac
import json
import aiohttp
import logging
from core.config import XL_API_CONFIG

logger = logging.getLogger(__name__)

class SidompulChecker:
    """Kelas untuk mengecek kuota Sidompul XL menggunakan API"""
    
    @classmethod
    async def cek_sidompul(cls, msisdn):
        """
        Mengecek kuota Sidompul untuk nomor tertentu
        
        Args:
            msisdn (str): Nomor telepon dalam format 628xxx
            
        Returns:
            dict: Hasil pengecekan Sidompul dengan format:
                {
                    'success': bool,
                    'data': {
                        'result': {
                            'msisdn': str,
                            'category': str,
                            'owner': str,
                            'dukcapil': str,
                            'tenure': str,
                            'status': str,
                            'expDate': str,
                            'SPExpDate': str,
                            'data': {
                                'packageInfo': list,
                                'packageInfoSP': list,
                                'lastUpdate': str
                            }
                        }
                    },
                    'error': str (jika ada error)
                }
        """
        try:
            # Ambil konfigurasi dari config.py
            api_username = XL_API_CONFIG['username']
            api_key = XL_API_CONFIG['api_key']
            base_url = XL_API_CONFIG['base_url']
            
            # Buat URL lengkap
            api_url = f"{base_url.rstrip('/')}/cek-sidompul"
            
            # Buat timestamp
            timestamp = str(int(time.time()))
            
            # Buat string untuk signature
            string_to_sign = f"{api_username}:{timestamp}"
            
            # Buat signature dengan HMAC SHA-256
            signature = hmac.new(
                api_key.encode(),
                string_to_sign.encode(),
                hashlib.sha256
            ).hexdigest()
            
            # Siapkan headers
            headers = {
                "X-API-USERNAME": api_username,
                "X-TIMESTAMP": timestamp,
                "X-SIGNATURE": signature,
                "Content-Type": "application/json",
                "Accept": "application/json"
            }
            
            # Siapkan data
            data = {
                "msisdn": msisdn
            }
            
            # Log request untuk debugging
            logger.debug(f"Cek Sidompul request: URL={api_url}, Headers={headers}, Data={data}")
            
            # Kirim request
            async with aiohttp.ClientSession() as session:
                async with session.post(api_url, headers=headers, json=data) as response:
                    status_code = response.status
                    response_data = await response.json()
                    
                    # Log response untuk debugging
                    logger.debug(f"Cek Sidompul response: Status={status_code}, Data={response_data}")
                    
                    if status_code == 200 and response_data.get('success', False):
                        return {
                            'success': True,
                            'data': response_data.get('data', {})
                        }
                    else:
                        return {
                            'success': False,
                            'error': response_data.get('message', 'Terjadi kesalahan saat cek Sidompul'),
                            'data': {}
                        }
        except Exception as e:
            logger.error(f"Error cek Sidompul: {e}")
            return {
                'success': False,
                'error': f"Terjadi kesalahan: {str(e)}",
                'data': {}
            }
    
    @classmethod
    def format_sidompul_info(cls, data):
        """
        Memformat data Sidompul menjadi teks yang mudah dibaca
        
        Args:
            data (dict): Data hasil cek Sidompul
            
        Returns:
            str: Teks terformat yang berisi informasi Sidompul
        """
        try:
            if not data or not data.get('result'):
                return "❌ Data Sidompul tidak tersedia"
            
            result = data['result']
            msisdn = result.get('msisdn', 'Tidak diketahui')
            category = result.get('category', 'Tidak diketahui')
            owner = result.get('owner', 'Tidak diketahui')
            dukcapil = result.get('dukcapil', 'Tidak diketahui')
            tenure = result.get('tenure', 'Tidak diketahui')
            status = result.get('status', 'Tidak diketahui')
            exp_date = result.get('expDate', 'Tidak diketahui')
            sp_exp_date = result.get('SPExpDate', 'Tidak diketahui')
            
            # Informasi dasar
            info_text = f"📱 **Informasi Sidompul XL**\n"
            info_text += f"===========================\n"
            info_text += f"**🧿 Nomor:** {msisdn}\n"
            info_text += f"**🧿 Kategori:** {category}\n"
            info_text += f"**🧿 Provider:** {owner}\n"
            info_text += f"**🧿 Dukcapil:** {dukcapil}\n"
            info_text += f"**🧿 Masa Aktif:** {tenure}\n"
            info_text += f"**🧿 Status:** {status}\n"
            info_text += f"**🧿 Masa Berlaku:** {exp_date}\n"
            info_text += f"**🧿 SP Exp Date:** {sp_exp_date}\n\n"
            info_text += f"===========================\n"
            # Informasi paket
            package_data = result.get('data', {})
            package_info = package_data.get('packageInfo', [])
            last_update = package_data.get('lastUpdate', 'Tidak diketahui')
            
            if package_info:
                info_text += "📊 **Informasi Paket:**\n\n"
                
                for package_group in package_info:
                    for package in package_group:
                        package_details = package.get('packages', {})
                        package_name = package_details.get('name', 'Tidak diketahui')
                        package_exp = package_details.get('expDate', 'Tidak diketahui')
                        
                        # Format tanggal kedaluwarsa
                        if 'T' in package_exp:
                            package_exp = package_exp.split('T')[0]
                        
                        info_text += f"🎁 **{package_name}**\n"
                        info_text += f"└⌛️ {package_exp}\n"
                        
                        benefits = package.get('benefits', [])
                        if benefits:
                            for benefit in benefits:
                                benefit_name = benefit.get('bname', 'Tidak diketahui')
                                benefit_quota = benefit.get('quota', 'Tidak diketahui')
                                benefit_remaining = benefit.get('remaining', 'Tidak diketahui')
                                
                                info_text += f"└{benefit_name}: {benefit_remaining}/{benefit_quota}\n"
                        
                        info_text += "\n"
            
            # Informasi terakhir update
            info_text += f"📆 **Terakhir Update:** {last_update}"
            
            return info_text
        except Exception as e:
            logger.error(f"Error formatting Sidompul info: {e}")
            return f"❌ Terjadi kesalahan saat memformat informasi Sidompul: {str(e)}"
