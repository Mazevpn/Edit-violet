import time
import hashlib
import hmac
import json
import aiohttp
import logging
from core.config import XL_API_CONFIG

logger = logging.getLogger(__name__)

class PulsaChecker:
    """Kelas untuk mengecek pulsa XL menggunakan API"""
    
    @classmethod
    async def cek_pulsa(cls, msisdn):
        """
        Mengecek pulsa untuk nomor tertentu
        
        Args:
            msisdn (str): Nomor telepon dalam format 628xxx
            
        Returns:
            dict: Hasil pengecekan pulsa dengan format:
                {
                    'success': bool,
                    'data': {
                        'remaining_balance': int,
                        'expired_at': str
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
            api_url = f"{base_url.rstrip('/')}/cek-pulsa"
            
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
            logger.debug(f"Cek pulsa request: URL={api_url}, Headers={headers}, Data={data}")
            
            # Kirim request
            async with aiohttp.ClientSession() as session:
                async with session.post(api_url, headers=headers, json=data) as response:
                    status_code = response.status
                    response_data = await response.json()
                    
                    # Log response untuk debugging
                    logger.debug(f"Cek pulsa response: Status={status_code}, Data={response_data}")
                    
                    if status_code == 200 and response_data.get('success', False):
                        return {
                            'success': True,
                            'data': response_data.get('data', {})
                        }
                    else:
                        return {
                            'success': False,
                            'error': response_data.get('message', 'Terjadi kesalahan saat cek pulsa'),
                            'data': {}
                        }
        except Exception as e:
            logger.error(f"Error cek pulsa: {e}")
            return {
                'success': False,
                'error': f"Terjadi kesalahan: {str(e)}",
                'data': {}
            }
