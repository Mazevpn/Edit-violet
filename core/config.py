# Telegram Configuration
TG_CONFIG = {
    'api_id': '',
    'api_hash': '',
    'bot_token': ''
}

# Database Configuration
DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': '',
    'database': 'bot_telegram'
}

# XL Products API Configuration
XL_API_CONFIG = {
    'username': '',
    'api_key': '',
    'base_url': 'https://www./api/xl/v2/'
}

#Bot notification
BOT_NOTIFICATION = {
    'bot_token': ',
    'bot_username': '@mazenotip_bot',
}

# Cek channel - Menggunakan ID numerik channel
CHANNEL_TELEGRAM = {
    'channel1': {
        'name': 'Channel Utama',
        'url': 'https://t.me/MazeStoreOfficial',
        'entity': -1001740128574  # Menggunakan ID numerik channel
        },
    'channel2': {
        'name': 'Channel Backup',
        'url': 'https://t.me/backupmaze',
        'entity': -1002657760827  # Menggunakan ID numerik channel
        },
    'channel3': {
        'name': 'Group Diskusi',
        'url': 'https://t.me/mazegroupofficial',
        'entity': -1002663121768  # Menggunakan ID numerik channel
    },
}

#AUTO BACKUP DATABASE TO CHANNEL TELEGRAM   
BACKUP_CHANNEL_TELEGRAM = {
    'id': -1002598795228,  # ID channel untuk backup
}

#QRIS ORDER KUOTA
QRIS_API_CONFIG = {
    'merchant_code': 'OK2410975',
    'api_key': '610664217459340192410975OKCTA903BA961E168D919BAA24097088C9E2',
    'base_url': 'https://gateway.okeconnect.com/api/mutasi/qris/',
    'qris_string': '00020101021126670016COM.NOBUBANK.WWW01189360050300000879140214131055126964150303UMI51440014ID.CO.QRIS.WWW0215ID20253994883810303UMI5204481253033605802ID5920MAZE CELL  OK24109756006MALANG61056511162070703A0163047D6F',
    'biaya_trx': 0.3
}

# Logging Configuration
LOG_CONFIG = {
    'level': 'INFO',
    'format': '[%(levelname)s] %(asctime)s - %(message)s'
}
