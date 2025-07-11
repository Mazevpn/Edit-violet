from telethon import events, Button
from models.data_produk import XLProduct
import logging

logger = logging.getLogger(__name__)

# Dictionary untuk menyimpan state produk yang dipilih user
product_states = {}

async def setup_product_item_handlers(client):
    """Setup handlers untuk produk item"""
    
    @client.on(events.CallbackQuery(data=b'show_categories'))
    async def show_categories_handler(event):
        """Handler untuk menampilkan kategori produk untuk pembeli"""
        try:
            # Ambil semua kategori produk
            categories = XLProduct.get_categories()
            
            if not categories:
                await event.edit(
                    "❌ Tidak ada kategori produk yang tersedia saat ini.",
                    buttons=[[Button.inline("🔙 Kembali ke Menu", b"back_to_menu")]]
                )
                return
            
            # Buat tombol untuk setiap kategori
            buttons = []
            for category in categories:
                buttons.append([Button.inline(f"📱 {category}", f"customer_cat_{category}".encode())])
            
            # Tambahkan tombol kembali
            buttons.append([Button.inline("🔙 Kembali ke Menu", b"back_to_menu")])
            
            # Tampilkan kategori
            await event.edit(
                "**📱 Kategori Produk**\n\n"
                "Silakan pilih kategori produk yang ingin Anda lihat:",
                buttons=buttons
            )
        except Exception as e:
            logger.error(f"Error showing categories: {e}")
            await event.edit(
                "❌ Terjadi kesalahan saat memuat kategori produk.",
                buttons=[[Button.inline("🔙 Kembali ke Menu", b"back_to_menu")]]
            )
    
    @client.on(events.CallbackQuery(data=lambda d: d.startswith(b'customer_cat_')))
    async def category_products_handler(event):
        """Handler untuk menampilkan produk dalam kategori yang dipilih"""
        try:
            # Ekstrak nama kategori dari callback data
            category = event.data.decode('utf-8').split('_', 2)[2]
            
            # Ambil produk dalam kategori ini
            products = XLProduct.get_by_category(category)
            
            if not products:
                await event.edit(
                    f"❌ Tidak ada produk dalam kategori '{category}'.",
                    buttons=[
                        [Button.inline("🔙 Kembali ke Kategori", b"show_categories")],
                        [Button.inline("🔙 Kembali ke Menu", b"back_to_menu")]
                    ]
                )
                return
            
            # Buat tombol untuk setiap produk
            buttons = []
            for product in products:
                # Format harga
                harga_jual = f"Rp {int(product.harga_jual):,}".replace(',', '.')
                buttons.append([
                    Button.inline(
                        f"{product.nama_produk} - {harga_jual}",
                        f"customer_prod_{product.produk_code}".encode()  # Gunakan produk_code sebagai identifier
                    )
                ])
            
            # Tambahkan tombol kembali
            buttons.append([Button.inline("🔙 Kembali ke Kategori", b"show_categories")])
            buttons.append([Button.inline("🔙 Kembali ke Menu", b"back_to_menu")])
            
            # Tampilkan produk
            await event.edit(
                f"**📱 Produk dalam Kategori '{category}'**\n\n"
                f"Total: {len(products)} produk\n\n"
                f"Silakan pilih produk yang ingin Anda beli:",
                buttons=buttons
            )
        except Exception as e:
            logger.error(f"Error showing products in category: {e}")
            await event.edit(
                "❌ Terjadi kesalahan saat memuat produk.",
                buttons=[
                    [Button.inline("🔙 Kembali ke Kategori", b"show_categories")],
                    [Button.inline("🔙 Kembali ke Menu", b"back_to_menu")]
                ]
            )
    
    @client.on(events.CallbackQuery(data=lambda d: d.startswith(b'customer_prod_')))
    async def product_detail_handler(event):
        """Handler untuk menampilkan detail produk yang dipilih"""
        try:
            # Ekstrak kode produk dari callback data
            produk_code = event.data.decode('utf-8').split('_', 2)[2]
            
            # Ambil detail produk menggunakan get_by_code bukan get_by_id
            product = XLProduct.get_by_code(produk_code)
            
            if not product:
                await event.edit(
                    "❌ Produk tidak ditemukan atau telah dihapus.",
                    buttons=[
                        [Button.inline("🔙 Kembali ke Kategori", b"show_categories")],
                        [Button.inline("🔙 Kembali ke Menu", b"back_to_menu")]
                    ]
                )
                return
            
            # Simpan produk yang dipilih ke state
            user_id = event.sender_id
            from handlers.payment_handlers import payment_states
            
            payment_states[user_id] = {
                'product': product,
                'step': 'select_payment'
            }
            
            # Format harga
            harga_jual = f"Rp {int(product.harga_jual):,}".replace(',', '.')
            
            # Tampilkan detail produk dengan tombol beli
            await event.edit(
                f"**📱 {product.nama_produk}**\n\n"
                f"**Kategori:** {product.kategori}\n"
                f"**Kode Produk:** {product.produk_code}\n"
                f"**Harga:** {harga_jual}\n\n"
                f"**Deskripsi:**\n{product.deskripsi or 'Tidak ada deskripsi'}\n\n"
                f"Pilih metode pembayaran:",
                buttons=[
                    [Button.inline("💰 PULSA", b"pay_BALANCE")],
                    [Button.inline("💳 DANA", b"pay_DANA")],
                    [Button.inline("💳 GOPAY", b"pay_GOPAY")],
                    [Button.inline("🔙 Kembali ke Produk", b"back_to_products")],
                    [Button.inline("🔙 Kembali ke Menu", b"back_to_menu")]
                ]
            )
        except Exception as e:
            logger.error(f"Error showing product details: {e}")
            await event.edit(
                "❌ Terjadi kesalahan saat memuat detail produk.",
                buttons=[
                    [Button.inline("🔙 Kembali ke Kategori", b"show_categories")],
                    [Button.inline("🔙 Kembali ke Menu", b"back_to_menu")]
                ]
            )
    
    @client.on(events.CallbackQuery(data=b'back_to_products'))
    async def back_to_products_handler(event):
        """Handler untuk kembali ke daftar produk"""
        user_id = event.sender_id
        
        # Cek apakah user memiliki state produk
        from handlers.payment_handlers import payment_states
        
        if user_id in payment_states and 'product' in payment_states[user_id]:
            # Ambil kategori dari produk yang terakhir dilihat
            product = payment_states[user_id]['product']
            category = product.kategori
            
            # Ambil produk dalam kategori ini
            products = XLProduct.get_by_category(category)
            
            if not products:
                await event.edit(
                    f"❌ Tidak ada produk dalam kategori '{category}'.",
                    buttons=[
                        [Button.inline("🔙 Kembali ke Kategori", b"show_categories")],
                        [Button.inline("🔙 Kembali ke Menu", b"back_to_menu")]
                    ]
                )
                return
            
            # Buat tombol untuk setiap produk
            buttons = []
            for product in products:
                # Format harga
                harga_jual = f"Rp {int(product.harga_jual):,}".replace(',', '.')
                buttons.append([
                    Button.inline(
                        f"{product.nama_produk} - {harga_jual}",
                        f"customer_prod_{product.produk_code}".encode()  # Gunakan produk_code sebagai identifier
                    )
                ])
            
            # Tambahkan tombol kembali
            buttons.append([Button.inline("🔙 Kembali ke Kategori", b"show_categories")])
            buttons.append([Button.inline("🔙 Kembali ke Menu", b"back_to_menu")])
            
            # Tampilkan produk
            await event.edit(
                f"**📱 Produk dalam Kategori '{category}'**\n\n"
                f"Total: {len(products)} produk\n\n"
                f"Silakan pilih produk yang ingin Anda beli:",
                buttons=buttons
            )
        else:
            # Jika tidak ada state, kembali ke kategori
            await event.edit(
                "Silakan pilih kategori produk:",
                buttons=[[Button.inline("🔙 Lihat Kategori", b"show_categories")]]
            )
