import hashlib
import hmac
import re

def format_phone_number(phone_number):
    """
    Format nomor telepon ke format standar (62xxxxxxxxxx)
    
    Args:
        phone_number (str): Nomor telepon yang akan diformat
        
    Returns:
        str: Nomor telepon yang sudah diformat
    """
    # Hapus semua karakter non-digit
    digits_only = re.sub(r'\D', '', phone_number)
    
    # Jika dimulai dengan 0, ganti dengan 62
    if digits_only.startswith('0'):
        return '62' + digits_only[1:]
    
    # Jika dimulai dengan 62, kembalikan apa adanya
    if digits_only.startswith('62'):
        return digits_only
    
    # Jika dimulai dengan +62, hapus + dan kembalikan
    if digits_only.startswith('62'):
        return digits_only
    
    # Jika tidak dimulai dengan 0 atau 62, tambahkan 62 di depan
    return '62' + digits_only

def generate_signature(username, timestamp, api_key):
    """
    Generate signature untuk API request
    
    Args:
        username (str): Username API
        timestamp (int): Timestamp saat ini
        api_key (str): API key
        
    Returns:
        str: Signature yang dihasilkan
    """
    # Format string yang sama dengan PHP: username:timestamp
    data = f"{username}:{timestamp}"
    
    # Generate HMAC SHA-256 signature
    signature = hmac.new(
        api_key.encode(),
        data.encode(),
        hashlib.sha256
    ).hexdigest()
    
    return signature


def format_currency(amount):
    """
    Format angka menjadi format mata uang
    
    Args:
        amount (float): Jumlah yang akan diformat
        
    Returns:
        str: Jumlah yang sudah diformat
    """
    return f"Rp {amount:,.0f}"

def validate_otp(otp):
    """
    Validasi format OTP
    
    Args:
        otp (str): OTP yang akan divalidasi
        
    Returns:
        bool: True jika OTP valid, False jika tidak
    """
    # OTP harus berupa angka dan panjangnya 4-6 digit
    return bool(re.match(r'^\d{4,6}$', otp))

def mask_phone_number(phone_number):
    """
    Samarkan sebagian nomor telepon untuk keamanan
    
    Args:
        phone_number (str): Nomor telepon yang akan disamarkan
        
    Returns:
        str: Nomor telepon yang sudah disamarkan
    """
    # Format nomor telepon terlebih dahulu
    formatted = format_phone_number(phone_number)
    
    # Samarkan digit tengah, sisakan 4 digit pertama dan 2 digit terakhir
    if len(formatted) > 6:
        visible_prefix = formatted[:4]
        visible_suffix = formatted[-2:]
        masked_part = '*' * (len(formatted) - 6)
        return f"{visible_prefix}{masked_part}{visible_suffix}"
    
    # Jika nomor terlalu pendek, kembalikan apa adanya
    return formatted
