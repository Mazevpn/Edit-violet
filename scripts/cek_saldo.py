import time
import hashlib
import hmac
import json
import requests
import sys
import os
import logging
import warnings
from urllib3.exceptions import InsecureRequestWarning

# Tambahkan path root project ke sys.path agar bisa mengimpor modul dari core
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.config import XL_API_CONFIG

# Setup logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Suppress only the InsecureRequestWarning from urllib3
warnings.simplefilter('ignore', InsecureRequestWarning)

def check_balance():
    """Fungsi untuk mengecek saldo pada API"""
    try:
        # Ambil konfigurasi dari config.py
        api_username = XL_API_CONFIG['username']
        api_key = XL_API_CONFIG['api_key']
        base_url = XL_API_CONFIG['base_url']
        
        # Buat URL lengkap
        api_base = base_url.split('/api/')[0] + '/api'
        api_url = f"{api_base}/saldo"
        
        # Buat timestamp
        timestamp = str(int(time.time()))
        
        # Buat string untuk signature
        string_to_sign = f"{api_username}:{timestamp}"
        
        # Buat signature dengan HMAC SHA-256
        signature = hmac.new(api_key.encode(),
                           string_to_sign.encode(),
                           hashlib.sha256).hexdigest()
        
        # Siapkan headers
        headers = {
            "X-API-USERNAME": api_username,
            "X-TIMESTAMP": timestamp,
            "X-SIGNATURE": signature,
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        # Log request untuk debugging
        logger.debug(f"Cek saldo request: URL={api_url}, Headers={headers}")
        
        # Kirim request dengan verify=False untuk melewati verifikasi SSL
        response = requests.post(api_url, headers=headers, verify=False)
        status_code = response.status_code
        
        # Parse response sebagai JSON
        response_data = response.json()
        
        # Log response untuk debugging
        logger.debug(f"Cek saldo response: Status={status_code}, Data={response_data}")
        
        # Jika berhasil, ambil informasi saldo
        if status_code == 200 and response_data.get('success', False):
            data = response_data.get('data', {})
            return {
                'success': True,
                'name': data.get('name', 'N/A'),
                'email': data.get('email', 'N/A'),
                'role': data.get('role', 'N/A'),
                'saldo': data.get('saldo', 0),
                'points': data.get('points', 0),
                'timestamp': data.get('timestamp', 'N/A')
            }
        else:
            return {
                'success': False,
                'message': response_data.get('message', 'Terjadi kesalahan saat cek saldo')
            }
    except Exception as e:
        logger.error(f"Error cek saldo: {e}")
        return {
            'success': False,
            'message': str(e)
        }

async def get_panel_balance():
    """Fungsi async untuk mengecek saldo panel"""
    try:
        result = check_balance()
        return result
    except Exception as e:
        logger.error(f"Error getting panel balance: {e}")
        return {
            'success': False,
            'message': str(e)
        }
