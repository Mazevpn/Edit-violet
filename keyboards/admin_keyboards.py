from telethon import Button
from core.config import BOT_NOTIFICATION
from models.user import User

def admin_start_menu():
    """
    Membuat menu tombol untuk pengguna admin
    
    Returns:
        list: Daftar baris tombol untuk menu utama admin
    """
    return [
        [
            Button.inline("🛠️ Setting User", b'setting_user'),
            Button.inline("📦 Produk Management", b'product_mgmt')
        ],
        [
            Button.inline("🤖 Setting Bot", b'setting_bot'),
            Button.inline("🔑 Login Sesi", b'session_login')
        ],
        [
            Button.inline("🔄 Multi TRX", b'multi_trx'),
            Button.inline("📊 Sidompul cek Kuota", b'sidompul')
        ],
        [
            Button.url("📊 Status TRX", f"https://t.me/{BOT_NOTIFICATION['bot_username'][1:]}")
        ],
        [
            Button.inline("📲 Chat Member", b'daftar_chat_member')
        ]
    ]

def user_settings_menu():
    """
    Membuat menu tombol untuk pengaturan user
    
    Returns:
        list: Daftar baris tombol untuk menu pengaturan user
    """
    return [
        [Button.inline("👥 Daftar User", b'list_users')],
        [Button.inline("🔍 Cari User", b'search_user')],
        [Button.inline("💰 Kelola Saldo", b'manage_balance')],
        [Button.inline("👑 Ubah Role", b'change_role')],
        [Button.inline("🔙 Kembali", b'back_to_admin')]
    ]

def balance_management_menu():
    """
    Membuat menu tombol untuk manajemen saldo user
    
    Returns:
        list: Daftar baris tombol untuk menu manajemen saldo
    """
    return [
        [
            Button.inline("➕ Tambah Saldo", b'add_balance'),
            Button.inline("➖ Kurangi Saldo", b'reduce_balance')
        ],
        [Button.inline("🔙 Kembali", b'setting_user')]
    ]

def product_management_menu():
    """
    Membuat menu tombol untuk manajemen produk
    
    Returns:
        list: Daftar baris tombol untuk menu manajemen produk
    """
    return [
        [Button.inline("📋 Daftar Produk", b'list_products')],
        [Button.inline("🔄 Perbarui Produk", b'refresh_products')],
        [Button.inline("🔙 Kembali", b'back_to_admin')]
    ]

def category_buttons(categories):
    """
    Membuat tombol untuk daftar kategori produk
    
    Args:
        categories (list): Daftar kategori produk
        
    Returns:
        list: Daftar baris tombol kategori
    """
    buttons = []
    
    # Buat tombol untuk setiap kategori, 2 tombol per baris
    row = []
    for i, category in enumerate(categories):
        # Encode kategori dalam callback data
        callback_data = f"cat_{category}".encode()
        row.append(Button.inline(category, callback_data))
        
        # Setiap 2 tombol, buat baris baru
        if len(row) == 2 or i == len(categories) - 1:
            buttons.append(row)
            row = []
    
    # Tambahkan tombol kembali di baris terakhir
    buttons.append([Button.inline("🔙 Kembali", b'back_to_product_mgmt')])
    
    return buttons

def product_buttons(products, category):
    """
    Membuat tombol untuk daftar produk dalam kategori
    
    Args:
        products (list): Daftar objek produk
        category (str): Kategori produk yang dipilih
        
    Returns:
        list: Daftar baris tombol produk
    """
    buttons = []
    
    for product in products:
        # Encode produk_code dalam callback data
        callback_data = f"prod_{product.produk_code}".encode()
        buttons.append([Button.inline(product.nama_produk, callback_data)])
    
    # Tambahkan tombol kembali di baris terakhir
    buttons.append([Button.inline("🔙 Kembali ke Kategori", b'list_products')])
    
    return buttons

def product_detail_buttons(produk_code, kategori=None):
    """
    Membuat tombol untuk detail produk
    
    Args:
        produk_code (str): Kode produk
        kategori (str, optional): Kategori produk. Jika None, akan diambil dari database.
        
    Returns:
        list: Daftar baris tombol untuk detail produk
    """
    # Encode produk_code dalam callback data
    edit_price_data = f"edit_price_{produk_code}".encode()
    edit_desc_data = f"edit_desc_{produk_code}".encode()
    
    # Jika kategori tidak diberikan, ambil dari database
    if kategori is None:
        from models.data_produk import XLProduct
        product = XLProduct.get_by_code(produk_code)
        if product:
            kategori = product.kategori
        else:
            # Fallback jika produk tidak ditemukan
            kategori = "unknown"
    
    # Encode kategori untuk tombol kembali
    back_data = f"cat_{kategori}".encode()
    
    return [
        [
            Button.inline("✏️ Edit Harga", edit_price_data),
            Button.inline("📝 Edit Deskripsi", edit_desc_data)
        ],
        [Button.inline("🔙 Kembali", back_data)]
    ]

def user_list_buttons(users, page=0, page_size=5):
    """
    Membuat tombol untuk daftar user dengan paginasi
    
    Args:
        users (list): Daftar objek user
        page (int): Halaman saat ini (dimulai dari 0)
        page_size (int): Jumlah user per halaman
        
    Returns:
        list: Daftar baris tombol user dengan navigasi
    """
    buttons = []
    
    # Hitung total halaman
    total_pages = (len(users) + page_size - 1) // page_size
    
    # Ambil user untuk halaman saat ini
    start_idx = page * page_size
    end_idx = min(start_idx + page_size, len(users))
    page_users = users[start_idx:end_idx]
    
    # Buat tombol untuk setiap user
    for user in page_users:
        # Encode user_id dalam callback data
        callback_data = f"user_{user.user_id}".encode()
        
        # Tampilkan username atau first_name dan role
        display_name = user.username or user.first_name or f"User {user.user_id}"
        status_emoji = "✅" if user.is_active else "❌"
        buttons.append([Button.inline(f"{display_name} ({user.role}) {status_emoji}", callback_data)])
    
    # Tombol navigasi
    nav_buttons = []
    if page > 0:
        nav_buttons.append(Button.inline("⬅️ Prev", f"user_page_{page-1}".encode()))
    
    if total_pages > 1:
        nav_buttons.append(Button.inline(f"📄 {page+1}/{total_pages}", b"page_info"))
    
    if page < total_pages - 1:
        nav_buttons.append(Button.inline("Next ➡️", f"user_page_{page+1}".encode()))
    
    if nav_buttons:
        buttons.append(nav_buttons)
    
    # Tombol kembali
    buttons.append([Button.inline("🔙 Kembali", b'setting_user')])
    
    return buttons

def user_detail_buttons(user_id):
    """
    Membuat tombol untuk detail user
    
    Args:
        user_id (int): ID user
        
    Returns:
        list: Daftar baris tombol untuk detail user
    """
    # Dapatkan data user untuk mengetahui status aktif/nonaktif
    user = User.get_by_id(user_id)
    
    # Encode user_id dalam callback data
    edit_role_data = f"edit_role_{user_id}".encode()
    toggle_status_data = f"toggle_status_{user_id}".encode()
    add_balance_data = f"add_balance_{user_id}".encode()
    reduce_balance_data = f"reduce_balance_{user_id}".encode()
    
    # Tentukan teks dan emoji untuk tombol status
    status_text = "Nonaktifkan" if user.is_active else "Aktifkan"
    status_emoji = "🔴" if user.is_active else "🟢"
    
    return [
        [
            Button.inline("👑 Ubah Role", edit_role_data),
            Button.inline(f"{status_emoji} {status_text}", toggle_status_data)
        ],
        [
            Button.inline("➕ Tambah Saldo", add_balance_data),
            Button.inline("➖ Kurangi Saldo", reduce_balance_data)
        ],
        [Button.inline("🔙 Kembali", b'list_users')]
    ]

def role_selection_buttons(user_id):
    """
    Membuat tombol untuk pemilihan role
    
    Args:
        user_id (int): ID user
        
    Returns:
        list: Daftar baris tombol untuk pemilihan role
    """
    # Encode user_id dalam callback data
    admin_data = f"set_role_{user_id}_admin".encode()
    member_data = f"set_role_{user_id}_member".encode()
    
    return [
        [
            Button.inline("👑 Admin", admin_data),
            Button.inline("👤 Member", member_data)
        ],
        [Button.inline("🔙 Kembali", f"user_{user_id}".encode())]
    ]
