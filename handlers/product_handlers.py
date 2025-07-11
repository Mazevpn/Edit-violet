from telethon import events
from keyboards.admin_keyboards import *
from scripts.data_produk import get_xl_products, update_product_database
from models.data_produk import XLProduct
from core.database import get_db_connection
import logging
import re 

logger = logging.getLogger(__name__)

async def setup_product_handlers(client):
    @client.on(events.CallbackQuery(data=b'product_mgmt'))
    async def product_management_handler(event):
        try:
            await event.edit("**📦 Produk Management**",
                            buttons=product_management_menu())
        except Exception as e:
            logger.error(f"Error in product management menu: {e}")

    @client.on(events.CallbackQuery(pattern=b'back_to_admin'))
    async def back_to_admin_menu(event):
        """Handler untuk kembali ke menu admin utama"""
        await event.edit("Menu Admin:", buttons=admin_start_menu())
        
    @client.on(events.CallbackQuery(pattern=b'back_to_product_mgmt'))
    async def back_to_product_mgmt(event):
        """Handler untuk kembali ke menu manajemen produk"""
        await event.edit("**📦 Produk Management**", buttons=product_management_menu())

    @client.on(events.CallbackQuery(data=b'list_products'))
    async def list_products_handler(event):
        """Handler untuk menampilkan daftar kategori produk"""
        try:
            # Ambil semua kategori produk
            categories = XLProduct.get_categories()
            
            if not categories:
                await event.respond("❌ Tidak ada kategori produk yang ditemukan!")
                await event.edit("**📦 Produk Management**", buttons=product_management_menu())
                return
                
            # Tampilkan daftar kategori sebagai tombol
            await event.edit(
                "**📋 Pilih Kategori Produk:**", 
                buttons=category_buttons(categories)
            )
        except Exception as e:
            logger.error(f"Error listing product categories: {e}")
            await event.respond(f"❌ Error: {str(e)}")
            await event.edit("**📦 Produk Management**", buttons=product_management_menu())
    
    @client.on(events.CallbackQuery(pattern=b'^cat_'))
    async def category_products_handler(event):
        """Handler untuk menampilkan produk dalam kategori yang dipilih"""
        try:
            # Ekstrak nama kategori dari callback data
            category = event.data.decode('utf-8')[4:]  # Hapus 'cat_' dari awal
            
            # Ambil produk dalam kategori ini
            products = XLProduct.get_by_category(category)
            
            if not products:
                await event.respond(f"❌ Tidak ada produk dalam kategori '{category}'!")
                await event.edit(
                    "**📋 Pilih Kategori Produk:**", 
                    buttons=category_buttons(XLProduct.get_categories())
                )
                return
                
            # Tampilkan daftar produk sebagai tombol
            await event.edit(
                f"**📋 Produk dalam Kategori '{category}':**\n"
                f"Total: {len(products)} produk", 
                buttons=product_buttons(products, category)
            )
        except Exception as e:
            logger.error(f"Error listing products in category: {e}")
            await event.respond(f"❌ Error: {str(e)}")
            try:
                await event.edit(
                    "**📋 Pilih Kategori Produk:**", 
                    buttons=category_buttons(XLProduct.get_categories())
                )
            except:
                await event.edit("**📦 Produk Management**", buttons=product_management_menu())
    
    @client.on(events.CallbackQuery(pattern=b'^prod_'))
    async def product_detail_handler(event):
        """Handler untuk menampilkan detail produk yang dipilih"""
        try:
            # Ekstrak kode produk dari callback data
            produk_code = event.data.decode('utf-8')[5:]  # Hapus 'prod_' dari awal
            
            # Ambil detail produk
            product = XLProduct.get_by_code(produk_code)
            
            if not product:
                await event.respond(f"❌ Produk dengan kode '{produk_code}' tidak ditemukan!")
                await event.edit(
                    "**📋 Pilih Kategori Produk:**", 
                    buttons=category_buttons(XLProduct.get_categories())
                )
                return
                
            # Format detail produk
            detail_text = (
                f"**📦 Detail Produk**\n\n"
                f"**Nama:** {product.nama_produk}\n"
                f"**Kategori:** {product.kategori}\n"
                f"**Kode:** {product.produk_code}\n"
                f"**Harga Panel:** Rp {product.harga_panel:,.0f}\n"
                f"**Harga Bayar:** Rp {product.harga_bayar:,.0f}\n"
                f"**Harga Jual:** Rp {product.harga_jual:,.0f}\n"
                f"**Status:** {product.status}\n\n"
                f"**Deskripsi:**\n{product.deskripsi or 'Tidak ada deskripsi'}"
            )
            
            # Tampilkan detail produk dengan tombol edit
            await event.edit(
                detail_text, 
                buttons=product_detail_buttons(produk_code)
            )
        except Exception as e:
            logger.error(f"Error showing product details: {e}")
            await event.respond(f"❌ Error: {str(e)}")
            try:
                # Coba kembali ke daftar kategori
                await event.edit(
                    "**📋 Pilih Kategori Produk:**", 
                    buttons=category_buttons(XLProduct.get_categories())
                )
            except:
                await event.edit("**📦 Produk Management**", buttons=product_management_menu())
    
    @client.on(events.CallbackQuery(pattern=b'^edit_price_'))
    async def edit_price_handler(event):
        """Handler untuk mengedit harga produk"""
        try:
            # Ekstrak kode produk dari callback data
            produk_code = event.data.decode('utf-8')[11:]  # Hapus 'edit_price_' dari awal
            
            # Ambil detail produk
            product = XLProduct.get_by_code(produk_code)
            
            if not product:
                await event.respond(f"❌ Produk dengan kode '{produk_code}' tidak ditemukan!")
                return
                
            # Kirim pesan untuk meminta input harga baru
            await event.respond(
                f"Silakan masukkan harga jual baru untuk produk '{product.nama_produk}'.\n"
                f"Harga jual saat ini: Rp {product.harga_jual:,.0f}\n\n"
                f"Format: `/setharga {produk_code} <harga_baru>`\n"
                f"Contoh: `/setharga {produk_code} 15000`"
            )
            
            # Tetap tampilkan detail produk
            await event.edit(
                f"**📦 Detail Produk - Mode Edit Harga**\n\n"
                f"**Nama:** {product.nama_produk}\n"
                f"**Kategori:** {product.kategori}\n"
                f"**Kode:** {product.produk_code}\n"
                f"**Harga Panel:** Rp {product.harga_panel:,.0f}\n"
                f"**Harga Bayar:** Rp {product.harga_bayar:,.0f}\n"
                f"**Harga Jual:** Rp {product.harga_jual:,.0f}\n"
                f"**Status:** {product.status}\n\n"
                f"**Deskripsi:**\n{product.deskripsi or 'Tidak ada deskripsi'}",
                buttons=product_detail_buttons(produk_code)
            )
        except Exception as e:
            logger.error(f"Error in edit price handler: {e}")
            await event.respond(f"❌ Error: {str(e)}")
    
    @client.on(events.CallbackQuery(pattern=b'^edit_desc_'))
    async def edit_description_handler(event):
        """Handler untuk mengedit deskripsi produk"""
        try:
            # Ekstrak kode produk dari callback data
            produk_code = event.data.decode('utf-8')[10:]  # Hapus 'edit_desc_' dari awal
            
            # Ambil detail produk
            product = XLProduct.get_by_code(produk_code)
            
            if not product:
                await event.respond(f"❌ Produk dengan kode '{produk_code}' tidak ditemukan!")
                return
                
            # Kirim pesan untuk meminta input deskripsi baru
            await event.respond(
                f"Silakan masukkan deskripsi baru untuk produk '{product.nama_produk}'.\n"
                f"Deskripsi saat ini:\n{product.deskripsi or 'Tidak ada deskripsi'}\n\n"
                f"Format: `/setdesc {produk_code} <deskripsi_baru>`\n"
                f"Contoh: `/setdesc {produk_code} Paket internet unlimited 24 jam`"
            )
            
            # Tetap tampilkan detail produk
            await event.edit(
                f"**📦 Detail Produk - Mode Edit Deskripsi**\n\n"
                f"**Nama:** {product.nama_produk}\n"
                f"**Kategori:** {product.kategori}\n"
                f"**Kode:** {product.produk_code}\n"
                f"**Harga Panel:** Rp {product.harga_panel:,.0f}\n"
                f"**Harga Bayar:** Rp {product.harga_bayar:,.0f}\n"
                f"**Harga Jual:** Rp {product.harga_jual:,.0f}\n"
                f"**Status:** {product.status}\n\n"
                f"**Deskripsi:**\n{product.deskripsi or 'Tidak ada deskripsi'}",
                buttons=product_detail_buttons(produk_code)
            )
        except Exception as e:
            logger.error(f"Error in edit description handler: {e}")
            await event.respond(f"❌ Error: {str(e)}")
    
    @client.on(events.NewMessage(pattern=r'^/setharga\s+(\S+)\s+(\d+)'))
    async def set_price_command(event):
        """Handler untuk command mengubah harga produk (hanya untuk admin)"""
        try:
            # Cek apakah pengguna adalah admin
            user_id = event.sender_id
            user_role = User.get_role(user_id)
            
            # Hanya admin yang bisa mengakses fitur ini
            if user_role != 'admin':
                await event.respond("❌ Anda tidak memiliki izin untuk mengubah harga produk!")
                return
            
            # Ekstrak kode produk dan harga baru dari pesan
            match = event.pattern_match
            produk_code = match.group(1)
            new_price = int(match.group(2))
            
            # Ambil detail produk
            product = XLProduct.get_by_code(produk_code)
            if not product:
                await event.respond(f"❌ Produk dengan kode '{produk_code}' tidak ditemukan!")
                return
            
            # Simpan harga lama untuk ditampilkan dalam pesan konfirmasi
            old_price = product.harga_jual
            
            # Update harga jual di database
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE data_xl SET harga_jual = %s WHERE produk_code = %s",
                (new_price, produk_code)
            )
            conn.commit()
            cursor.close()
            conn.close()
            
            # Ambil produk yang sudah diupdate
            updated_product = XLProduct.get_by_code(produk_code)
            
            # Kirim pesan konfirmasi
            await event.respond(
                f"✅ Harga jual produk '{updated_product.nama_produk}' berhasil diubah!\n\n"
                f"Harga lama: Rp {old_price:,.0f}\n"
                f"Harga baru: Rp {updated_product.harga_jual:,.0f}"
            )
            
            # Tampilkan detail produk yang diperbarui
            detail_text = (
                f"**📦 Detail Produk (Diperbarui)**\n\n"
                f"**Nama:** {updated_product.nama_produk}\n"
                f"**Kategori:** {updated_product.kategori}\n"
                f"**Kode:** {updated_product.produk_code}\n"
                f"**Harga Panel:** Rp {updated_product.harga_panel:,.0f}\n"
                f"**Harga Bayar:** Rp {updated_product.harga_bayar:,.0f}\n"
                f"**Harga Jual:** Rp {updated_product.harga_jual:,.0f}\n"
                f"**Status:** {updated_product.status}\n\n"
                f"**Deskripsi:**\n{updated_product.deskripsi or 'Tidak ada deskripsi'}"
            )
            
            await event.respond(
                detail_text,
                buttons=product_detail_buttons(produk_code)
            )
            
            # Kirim notifikasi ke semua admin lain
            try:
                admin_users = User.get_all_admins()
                for admin in admin_users:
                    # Jangan kirim notifikasi ke admin yang melakukan perubahan
                    if admin.user_id != user_id:
                        await client.send_message(
                            admin.user_id,
                            f"🔔 **Notifikasi Perubahan Harga**\n\n"
                            f"Admin @{event.sender.username or 'Unknown'} telah mengubah harga produk:\n\n"
                            f"**Produk:** {updated_product.nama_produk}\n"
                            f"**Kode:** {updated_product.produk_code}\n"
                            f"**Harga Lama:** Rp {old_price:,.0f}\n"
                            f"**Harga Baru:** Rp {updated_product.harga_jual:,.0f}\n\n"
                            f"Waktu: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                        )
            except Exception as e:
                logger.error(f"Error sending admin notifications: {e}")
                
        except Exception as e:
            logger.error(f"Error updating product price: {e}")
            await event.respond(f"❌ Error saat mengubah harga produk: {str(e)}")
        
    @client.on(events.NewMessage())
    async def set_description_command(event):
        """Handler untuk command mengubah deskripsi produk (hanya untuk admin)"""
        # Periksa apakah pesan dimulai dengan /setdesc
        if not event.raw_text.startswith('/setdesc'):
            return
        
        try:
            # Cek apakah pengguna adalah admin
            user_id = event.sender_id
            user_role = User.get_role(user_id)
            
            # Hanya admin yang bisa mengakses fitur ini
            if user_role != 'admin':
                await event.respond("❌ Anda tidak memiliki izin untuk mengubah deskripsi produk!")
                return
            
            # Gunakan regex dengan flag DOTALL untuk mendukung garis baru
            match = re.match(r'^/setdesc\s+(\S+)\s+(.+)', event.raw_text, re.DOTALL)
            if not match:
                await event.respond("❌ Format tidak valid. Gunakan: `/setdesc kode_produk deskripsi`")
                return
            
            produk_code = match.group(1)
            new_description = match.group(2).strip()
            
            # Proses karakter escape \n menjadi garis baru sebenarnya
            new_description = new_description.replace('\\n', '\n')
            
            # Ambil detail produk
            product = XLProduct.get_by_code(produk_code)
            if not product:
                await event.respond(f"❌ Produk dengan kode '{produk_code}' tidak ditemukan!")
                return
            
            # Simpan deskripsi lama untuk ditampilkan dalam pesan konfirmasi
            old_description = product.deskripsi
            
            # Update deskripsi di database
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE data_xl SET deskripsi = %s WHERE produk_code = %s",
                (new_description, produk_code)
            )
            conn.commit()
            cursor.close()
            conn.close()
            
            # Ambil produk yang sudah diupdate
            updated_product = XLProduct.get_by_code(produk_code)
            
            # Kirim pesan konfirmasi
            await event.respond(
                f"✅ Deskripsi produk '{updated_product.nama_produk}' berhasil diubah!\n\n"
                f"Deskripsi lama:\n{old_description or 'Tidak ada deskripsi'}\n\n"
                f"Deskripsi baru:\n{updated_product.deskripsi}"
            )
            
            # Tampilkan detail produk yang diperbarui
            detail_text = (
                f"**📦 Detail Produk (Diperbarui)**\n\n"
                f"**Nama:** {updated_product.nama_produk}\n"
                f"**Kategori:** {updated_product.kategori}\n"
                f"**Kode:** {updated_product.produk_code}\n"
                f"**Harga Panel:** Rp {updated_product.harga_panel:,.0f}\n"
                f"**Harga Bayar:** Rp {updated_product.harga_bayar:,.0f}\n"
                f"**Harga Jual:** Rp {updated_product.harga_jual:,.0f}\n"
                f"**Status:** {updated_product.status}\n\n"
                f"**Deskripsi:**\n{updated_product.deskripsi or 'Tidak ada deskripsi'}"
            )
            
            await event.respond(
                detail_text,
                buttons=product_detail_buttons(produk_code)
            )
            
            # Kirim notifikasi ke semua admin lain
            try:
                admin_users = User.get_all_admins()
                for admin in admin_users:
                    # Jangan kirim notifikasi ke admin yang melakukan perubahan
                    if admin.user_id != user_id:
                        # Buat versi singkat dari deskripsi untuk notifikasi
                        short_old_desc = (old_description[:100] + '...') if old_description and len(old_description) > 100 else (old_description or 'Tidak ada deskripsi')
                        short_new_desc = (new_description[:100] + '...') if len(new_description) > 100 else new_description
                        
                        await client.send_message(
                            admin.user_id,
                            f"🔔 **Notifikasi Perubahan Deskripsi**\n\n"
                            f"Admin @{event.sender.username or 'Unknown'} telah mengubah deskripsi produk:\n\n"
                            f"**Produk:** {updated_product.nama_produk}\n"
                            f"**Kode:** {updated_product.produk_code}\n"
                            f"**Deskripsi Lama:** {short_old_desc}\n"
                            f"**Deskripsi Baru:** {short_new_desc}\n\n"
                            f"Waktu: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                        )
            except Exception as e:
                logger.error(f"Error sending admin notifications: {e}")
                
        except Exception as e:
            logger.error(f"Error updating product description: {e}")
            await event.respond(f"❌ Error saat mengubah deskripsi produk: {str(e)}")


    @client.on(events.CallbackQuery(data=b'refresh_products'))
    async def refresh_products_handler(event):
        try:
            # Show loading message
            await event.edit("🔄 Memperbarui produk dari API...")
            
            # Get response from API
            api_response = get_xl_products()
            if not api_response:
                logger.error("API returned None response")
                await event.respond("❌ Gagal terhubung ke API! Coba lagi nanti.")
                await event.edit("**📦 Produk Management**", buttons=product_management_menu())
                return
                
            # Check if response has data key
            if 'data' not in api_response:
                logger.error(f"API response missing 'data' key. Keys: {list(api_response.keys())}")
                await event.respond("❌ Format response API tidak valid!")
                await event.edit("**📦 Produk Management**", buttons=product_management_menu())
                return
                
            # Get products from response
            products = api_response.get('data', [])
            product_count = len(products)
            if product_count == 0:
                logger.warning("API returned 0 products")
                await event.respond("⚠️ API tidak mengembalikan produk apapun!")
                await event.edit("**📦 Produk Management**", buttons=product_management_menu())
                return
                
            logger.info(f"Received {product_count} products from API")
            
            # Update database with products
            await event.edit("💾 Menyimpan produk ke database...")
            
            # Call the update function that handles database operations
            success, errors, new, updated = update_product_database()
            
            # Prepare result message
            if success > 0:
                result_message = (f"✅ Berhasil memperbarui produk!\n\n"
                                f"📊 Statistik:\n"
                                f"- Total produk dari API: {product_count}\n"
                                f"- Berhasil disimpan: {success}\n"
                                f"- Produk baru: {new}\n"
                                f"- Produk diperbarui: {updated}\n"
                                f"- Gagal: {errors}")
                await event.respond(result_message)
            else:
                await event.respond("❌ Gagal menyimpan produk ke database!")
                
            # Return to product management menu
            await event.edit("**📦 Produk Management**", buttons=product_management_menu())
        except Exception as e:
            logger.error(f"Refresh products error: {e}")
            await event.respond(f"❌ Error saat memperbarui produk: {str(e)}")
            try:
                await event.edit("**📦 Produk Management**", buttons=product_management_menu())
            except:
                # If we can't edit the original message, send a new one
                await event.respond("**📦 Produk Management**", buttons=product_management_menu())
