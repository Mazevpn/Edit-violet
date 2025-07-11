import time
import logging
import aiohttp
import json
from core.config import XL_API_CONFIG
from core.helpers import format_phone_number, generate_signature

logger = logging.getLogger(__name__)

class XLApi:
    """Kelas untuk berinteraksi dengan API XL"""
    
    @staticmethod
    async def _make_request(endpoint, data):
        """
        Membuat request ke API XL
        
        Args:
            endpoint (str): Endpoint API
            data (dict): Data yang akan dikirim
            
        Returns:
            dict: Response dari API
        """
        # Pastikan tidak ada trailing slash di base_url
        base_url = XL_API_CONFIG['base_url'].rstrip('/')
        url = f"{base_url}/{endpoint}"
        
        username = XL_API_CONFIG['username']
        api_key = XL_API_CONFIG['api_key']
        
        # Generate timestamp dan signature
        timestamp = int(time.time())
        signature = generate_signature(username, timestamp, api_key)
        
        # Set headers
        headers = {
            'X-API-USERNAME': username,
            'X-TIMESTAMP': str(timestamp),
            'X-SIGNATURE': signature,
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        }
        
        # Log request untuk debugging
        logger.info(f"API Request ({endpoint}): URL={url}, Headers={headers}, Data={data}")
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=data, headers=headers) as response:
                    response_text = await response.text()
                    
                    try:
                        response_data = json.loads(response_text)
                    except json.JSONDecodeError:
                        logger.error(f"Invalid JSON response: {response_text}")
                        response_data = {"error": "Invalid JSON response", "raw": response_text}
                    
                    logger.info(f"API Response ({endpoint}): {response.status} - {response_data}")
                    
                    return {
                        'status_code': response.status,
                        'data': response_data
                    }
        except Exception as e:
            logger.error(f"API Request Error ({endpoint}): {str(e)}")
            return {
                'status_code': 500,
                'data': {
                    'success': False,
                    'data': {
                        'message': f"Error: {str(e)}"
                    }
                }
            }
    
    @staticmethod
    async def check_number(phone_number):
        """
        Memeriksa nomor telepon XL
        
        Args:
            phone_number (str): Nomor telepon
            
        Returns:
            dict: Response dari API
        """
        formatted_number = format_phone_number(phone_number)
        data = {'msisdn': formatted_number}
        return await XLApi._make_request('cek-nomor', data)
    
    @staticmethod
    async def request_otp(phone_number):
        """
        Meminta OTP untuk login
        
        Args:
            phone_number (str): Nomor telepon
            
        Returns:
            dict: Response dari API
        """
        formatted_number = format_phone_number(phone_number)
        data = {'msisdn': formatted_number}
        return await XLApi._make_request('req-otp', data)
    
    @staticmethod
    async def verify_otp(phone_number, otp):
        """
        Memverifikasi OTP
        
        Args:
            phone_number (str): Nomor telepon
            otp (str): Kode OTP
            
        Returns:
            dict: Response dari API
        """
        formatted_number = format_phone_number(phone_number)
        data = {
            'msisdn': formatted_number,
            'otp': otp
        }
        return await XLApi._make_request('ver-otp', data)
