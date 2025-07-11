import time
import hmac
import hashlib
import json
import logging
import aiohttp
from typing import Dict, Any, Optional
from core.config import XL_API_CONFIG

logger = logging.getLogger(__name__)

class XLPaymentAPI:
    """Kelas untuk menangani pembayaran produk XL"""
    
    @classmethod
    async def process_payment(cls, msisdn: str, produk_code: str, metode_pembayaran: str) -> Dict[str, Any]:
        """Memproses pembayaran produk XL
        
        Args:
            msisdn (str): Nomor telepon yang akan diisi
            produk_code (str): Kode produk XL
            metode_pembayaran (str): Metode pembayaran (BALANCE, DANA, GOPAY)
            
        Returns:
            Dict[str, Any]: Hasil respons API
        """
        try:
            # Ambil konfigurasi dari core/config.py
            API_USERNAME = XL_API_CONFIG['username']
            API_KEY = XL_API_CONFIG['api_key']
            BASE_URL = XL_API_CONFIG['base_url']
            API_URL = f"{BASE_URL}bayar"
            
            # Buat timestamp (waktu sekarang dalam format UNIX timestamp)
            timestamp = str(int(time.time()))
            
            # Buat string yang akan di-hash
            string_to_sign = f"{API_USERNAME}:{timestamp}"
            
            # Buat signature dengan HMAC SHA-256
            signature = hmac.new(
                API_KEY.encode(),
                string_to_sign.encode(),
                hashlib.sha256
            ).hexdigest()
            
            # Data yang akan dikirim sebagai JSON
            post_data = {
                'msisdn': msisdn,
                'produk_code': produk_code,
                'metode_pembayaran': metode_pembayaran
            }
            
            # Headers untuk request
            headers = {
                'X-API-USERNAME': API_USERNAME,
                'X-TIMESTAMP': timestamp,
                'X-SIGNATURE': signature,
                'Accept': 'application/json',
                'Content-Type': 'application/json'
            }
            
            # Log request details
            logger.info(f"API Request (bayar): URL={API_URL}, Headers={headers}, Data={post_data}")
            
            # Kirim request
            async with aiohttp.ClientSession() as session:
                async with session.post(API_URL, headers=headers, json=post_data) as response:
                    status_code = response.status
                    response_data = await response.json()
                    
                    # Log response
                    logger.info(f"API Response (bayar): {status_code} - {response_data}")
                    
                    return {
                        'status_code': status_code,
                        'data': response_data
                    }
        except Exception as e:
            logger.error(f"Error processing payment: {e}")
            return {
                'status_code': 500,
                'data': {
                    'success': False,
                    'data': {
                        'message': f"Error: {str(e)}"
                    }
                }
            }
