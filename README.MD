#BOT DATA XL

```
xl_data_bot/
│
├── core/
│   ├── __init__.py
│   ├── config.py           # Konfigurasi API_ID, API_HASH, dll
│   ├── database.py         # Handler database (SQLite/PostgreSQL)
│   └── helpers.py          # Fungsi utilitas (validasi, format, dll)
│
├── handlers/
│   ├── __init__.py
│   ├── admin_handlers.py   # Handler perintah admin
│   ├── user_handlers.py    # Handler perintah user
│   └── callback_handlers.py # Handler callback tombol
│
├── keyboards/
│   ├── __init__.py
│   ├── admin_keyboard.py   # Tombol menu admin
│   └── user_keyboard.py    # Tombol menu user
│
├── models/
│   ├── __init__.py
│   ├── user.py             # Model User (role, saldo, dll)
│   ├── product.py          # Model Produk XL
│   └── transaction.py      # Model Transaksi
│
├── scripts/
│   ├── __init__.py
│   └── xl_api.py          # Simulasi API pembelian paket XL
│
├── bot.py                 # Main bot (client & event loop)
└── requirements.txt        # Dependencies (Telethon, dll)
```
