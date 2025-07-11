from telethon import events, Button
from telethon.errors import UserNotParticipantError
import logging
import re
from models.user import User
from models.riwayat_transaksi import RiwayatTransaksi
from keyboards.admin_keyboards import (
    user_settings_menu,
    user_list_buttons,
    user_detail_buttons,
    role_selection_buttons,
    balance_management_menu
)
from core.config import LOG_CONFIG

# Setup logging
logger = logging.getLogger(__name__)

# Dictionary untuk menyimpan state pencarian user
search_states = {}

# Dictionary untuk menyimpan state pengeditan saldo
balance_states = {}

async def register_setting_user_handlers(client):
    """Mendaftarkan semua handler untuk pengaturan user"""
    
    @client.on(events.CallbackQuery(data=b'setting_user'))
    async def setting_user_handler(event):
        """Handler untuk menu pengaturan user"""
        # Verifikasi bahwa pengguna adalah admin
        user_id = event.sender_id
        user = User.get_by_id(user_id)
        if not user or user.role != 'admin':
            await event.answer("⛔ Anda tidak memiliki akses ke menu ini", alert=True)
            return
        
        await event.edit(
            "🛠️ **Pengaturan User**\n\n"
            "Silakan pilih opsi di bawah ini:",
            buttons=user_settings_menu()
        )

    @client.on(events.CallbackQuery(data=b'list_users'))
    async def list_users_handler(event):
        """Handler untuk menampilkan daftar user"""
        # Verifikasi bahwa pengguna adalah admin
        user_id = event.sender_id
        user = User.get_by_id(user_id)
        if not user or user.role != 'admin':
            await event.answer("⛔ Anda tidak memiliki akses ke menu ini", alert=True)
            return
        
        # Ambil semua user dari database
        users = User.get_all_users()
        
        if not users:
            await event.edit(
                "👥 **Daftar User**\n\n"
                "Tidak ada user yang terdaftar.",
                buttons=[[Button.inline("🔙 Kembali", b'setting_user')]]
            )
            return
        
        # Tampilkan daftar user dengan paginasi
        await event.edit(
            "👥 **Daftar User**\n\n"
            "Pilih user untuk melihat detail:",
            buttons=user_list_buttons(users)
        )

    @client.on(events.CallbackQuery(pattern=r'^user_page_(\d+)$'))
    async def user_page_handler(event):
        """Handler untuk navigasi halaman daftar user"""
        # Verifikasi bahwa pengguna adalah admin
        user_id = event.sender_id
        user = User.get_by_id(user_id)
        if not user or user.role != 'admin':
            await event.answer("⛔ Anda tidak memiliki akses ke menu ini", alert=True)
            return
        
        # Ambil nomor halaman dari callback data
        page = int(event.data_match.group(1).decode())
        
        # Ambil semua user dari database
        users = User.get_all_users()
        
        # Tampilkan daftar user dengan paginasi
        await event.edit(
            "👥 **Daftar User**\n\n"
            "Pilih user untuk melihat detail:",
            buttons=user_list_buttons(users, page=page)
        )

    @client.on(events.CallbackQuery(pattern=r'^user_(\d+)$'))
    async def user_detail_handler(event):
        """Handler untuk menampilkan detail user"""
        # Verifikasi bahwa pengguna adalah admin
        admin_id = event.sender_id
        admin = User.get_by_id(admin_id)
        if not admin or admin.role != 'admin':
            await event.answer("⛔ Anda tidak memiliki akses ke menu ini", alert=True)
            return
        
        # Ambil user_id dari callback data
        user_id = int(event.data_match.group(1).decode())
        
        # Ambil data user dari database
        user = User.get_by_id(user_id)
        if not user:
            await event.answer("❌ User tidak ditemukan", alert=True)
            return
        
        # Ambil jumlah transaksi user
        total_trx = RiwayatTransaksi.get_user_transaction_count(user_id)
        successful_trx = RiwayatTransaksi.get_user_successful_transaction_count(user_id)
        
        # Format informasi user
        status_text = "Aktif ✅" if user.is_active else "Nonaktif ❌"
        user_info = (
            f"👤 **Detail User**\n\n"
            f"**ID:** `{user.user_id}`\n"
            f"**Username:** {user.username or 'Tidak ada'}\n"
            f"**Nama:** {user.first_name or 'Tidak ada'}\n"
            f"**Role:** {user.role}\n"
            f"**Status:** {status_text}\n"
            f"**Saldo:** Rp {user.balance:,}\n"
            f"**Total Transaksi:** {total_trx} (Sukses: {successful_trx})\n"
            f"**Terdaftar:** {user.created_at.strftime('%d-%m-%Y %H:%M')}\n"
        )
        
        # Tampilkan detail user dengan tombol aksi
        await event.edit(
            user_info,
            buttons=user_detail_buttons(user_id)
        )

    @client.on(events.CallbackQuery(pattern=r'^edit_role_(\d+)$'))
    async def edit_role_handler(event):
        """Handler untuk tombol edit role dari detail user"""
        # Verifikasi bahwa pengguna adalah admin
        admin_id = event.sender_id
        admin = User.get_by_id(admin_id)
        if not admin or admin.role != 'admin':
            await event.answer("⛔ Anda tidak memiliki akses ke menu ini", alert=True)
            return
        
        # Ambil user_id dari callback data
        user_id = int(event.data_match.group(1).decode())
        
        # Ambil data user dari database
        user = User.get_by_id(user_id)
        if not user:
            await event.answer("❌ User tidak ditemukan", alert=True)
            return
        
        # Jangan izinkan admin mengubah role dirinya sendiri
        if user_id == admin_id:
            await event.answer("⚠️ Anda tidak dapat mengubah role diri sendiri", alert=True)
            return
        
        # Tampilkan pilihan role
        await event.edit(
            f"👑 **Ubah Role User**\n\n"
            f"**User:** {user.username or user.first_name or f'User {user.user_id}'}\n"
            f"**Role Saat Ini:** {user.role}\n\n"
            f"Pilih role baru:",
            buttons=role_selection_buttons(user_id)
        )

    @client.on(events.CallbackQuery(pattern=r'^set_role_(\d+)_(\w+)$'))
    async def set_role_handler(event):
        """Handler untuk menetapkan role baru"""
        # Verifikasi bahwa pengguna adalah admin
        admin_id = event.sender_id
        admin = User.get_by_id(admin_id)
        if not admin or admin.role != 'admin':
            await event.answer("⛔ Anda tidak memiliki akses ke menu ini", alert=True)
            return
        
        # Ambil user_id dan role dari callback data
        user_id = int(event.data_match.group(1).decode())
        new_role = event.data_match.group(2).decode()
        
        # Ambil data user dari database
        user = User.get_by_id(user_id)
        if not user:
            await event.answer("❌ User tidak ditemukan", alert=True)
            return
        
        # Jangan izinkan admin mengubah role dirinya sendiri
        if user_id == admin_id:
            await event.answer("⚠️ Anda tidak dapat mengubah role diri sendiri", alert=True)
            return
        
        # Simpan role lama untuk ditampilkan nanti
        old_role = user.role
        
        # Gunakan metode set_role dari kelas User
        success = User.set_role(user_id, new_role)
        if not success:
            await event.answer("❌ Gagal mengubah role user", alert=True)
            return
        
        # Log perubahan role
        logger.info(f"Admin {admin_id} updated role for user {user_id} from {old_role} to {new_role}")
        
        # Tampilkan konfirmasi
        await event.edit(
            f"✅ **Role Berhasil Diubah**\n\n"
            f"**User:** {user.username or user.first_name or f'User {user.user_id}'}\n"
            f"**Role Lama:** {old_role}\n"
            f"**Role Baru:** {new_role}",
            buttons=[[Button.inline("🔙 Kembali", f"user_{user_id}".encode())]]
        )

    @client.on(events.CallbackQuery(pattern=r'^toggle_status_(\d+)$'))
    async def toggle_user_status_handler(event):
        """Handler untuk mengubah status aktif/nonaktif user"""
        # Verifikasi bahwa pengguna adalah admin
        admin_id = event.sender_id
        admin = User.get_by_id(admin_id)
        if not admin or admin.role != 'admin':
            await event.answer("⛔ Anda tidak memiliki akses ke menu ini", alert=True)
            return
        
        # Ambil user_id dari callback data
        user_id = int(event.data_match.group(1).decode())
        
        # Ambil data user dari database
        user = User.get_by_id(user_id)
        if not user:
            await event.answer("❌ User tidak ditemukan", alert=True)
            return
        
        # Jangan izinkan admin mengubah status dirinya sendiri
        if user_id == admin_id:
            await event.answer("⚠️ Anda tidak dapat mengubah status diri sendiri", alert=True)
            return
        
        # Simpan status lama untuk ditampilkan nanti
        old_status = "Aktif" if user.is_active else "Nonaktif"
        
        # Toggle status user
        new_status_bool = not user.is_active
        success = User.set_active_status(user_id, new_status_bool)
        if not success:
            await event.answer("❌ Gagal mengubah status user", alert=True)
            return
        
        # Status baru setelah diubah
        new_status = "Aktif" if new_status_bool else "Nonaktif"
        
        # Log perubahan status
        logger.info(f"Admin {admin_id} updated status for user {user_id} from {old_status} to {new_status}")
        
        # Ambil data user yang sudah diperbarui
        user = User.get_by_id(user_id)
        
        # Ambil jumlah transaksi user
        total_trx = RiwayatTransaksi.get_user_transaction_count(user_id)
        successful_trx = RiwayatTransaksi.get_user_successful_transaction_count(user_id)
        
        # Tampilkan konfirmasi dengan data yang diperbarui
        status_text = "Aktif ✅" if user.is_active else "Nonaktif ❌"
        await event.edit(
            f"👤 **Detail User**\n\n"
            f"**ID:** `{user.user_id}`\n"
            f"**Username:** {user.username or 'Tidak ada'}\n"
            f"**Nama:** {user.first_name or 'Tidak ada'}\n"
            f"**Role:** {user.role}\n"
            f"**Status:** {status_text}\n"
            f"**Saldo:** Rp {user.balance:,}\n"
            f"**Total Transaksi:** {total_trx} (Sukses: {successful_trx})\n"
            f"**Terdaftar:** {user.created_at.strftime('%d-%m-%Y %H:%M')}\n\n"
            f"✅ Status user berhasil diubah dari {old_status} menjadi {new_status}",
            buttons=user_detail_buttons(user_id)
        )

    @client.on(events.CallbackQuery(data=b'manage_balance'))
    async def manage_balance_handler(event):
        """Handler untuk menu manajemen saldo"""
        # Verifikasi bahwa pengguna adalah admin
        user_id = event.sender_id
        user = User.get_by_id(user_id)
        if not user or user.role != 'admin':
            await event.answer("⛔ Anda tidak memiliki akses ke menu ini", alert=True)
            return
        
        await event.edit(
            "💰 **Kelola Saldo User**\n\n"
            "Pilih operasi yang ingin dilakukan:",
            buttons=balance_management_menu()
        )

    @client.on(events.CallbackQuery(data=b'add_balance'))
    async def add_balance_menu_handler(event):
        """Handler untuk menu tambah saldo"""
        # Verifikasi bahwa pengguna adalah admin
        user_id = event.sender_id
        user = User.get_by_id(user_id)
        if not user or user.role != 'admin':
            await event.answer("⛔ Anda tidak memiliki akses ke menu ini", alert=True)
            return
        
        # Simpan state untuk menambah saldo
        balance_states[user_id] = {'action': 'add', 'step': 'input_user_id'}
        
        await event.edit(
            "➕ **Tambah Saldo User**\n\n"
            "Silakan masukkan ID atau username user yang ingin ditambahkan saldonya.\n\n"
            "Format: `ID` atau `@username`",
            buttons=[[Button.inline("🔙 Kembali", b'manage_balance')]]
        )

    @client.on(events.CallbackQuery(data=b'reduce_balance'))
    async def reduce_balance_menu_handler(event):
        """Handler untuk menu kurangi saldo"""
        # Verifikasi bahwa pengguna adalah admin
        user_id = event.sender_id
        user = User.get_by_id(user_id)
        if not user or user.role != 'admin':
            await event.answer("⛔ Anda tidak memiliki akses ke menu ini", alert=True)
            return
        
        # Simpan state untuk mengurangi saldo
        balance_states[user_id] = {'action': 'reduce', 'step': 'input_user_id'}
        
        await event.edit(
            "➖ **Kurangi Saldo User**\n\n"
            "Silakan masukkan ID atau username user yang ingin dikurangi saldonya.\n\n"
            "Format: `ID` atau `@username`",
            buttons=[[Button.inline("🔙 Kembali", b'manage_balance')]]
        )

    @client.on(events.CallbackQuery(pattern=r'^add_balance_(\d+)$'))
    async def add_balance_handler(event):
        """Handler untuk menambah saldo user tertentu"""
        # Verifikasi bahwa pengguna adalah admin
        admin_id = event.sender_id
        admin = User.get_by_id(admin_id)
        if not admin or admin.role != 'admin':
            await event.answer("⛔ Anda tidak memiliki akses ke menu ini", alert=True)
            return
        
        # Ambil user_id dari callback data
        user_id = int(event.data_match.group(1).decode())
        
        # Ambil data user dari database
        user = User.get_by_id(user_id)
        if not user:
            await event.answer("❌ User tidak ditemukan", alert=True)
            return
        
        # Simpan state untuk menambah saldo
        balance_states[admin_id] = {
            'action': 'add',
            'step': 'input_amount',
            'target_user_id': user_id
        }
        
        await event.edit(
            f"➕ **Tambah Saldo User**\n\n"
            f"**User:** {user.username or user.first_name or f'User {user.user_id}'}\n"
            f"**Saldo Saat Ini:** Rp {user.balance:,}\n\n"
            f"Silakan masukkan jumlah saldo yang ingin ditambahkan (dalam Rupiah):",
            buttons=[[Button.inline("🔙 Kembali", f"user_{user_id}".encode())]]
        )

    @client.on(events.CallbackQuery(pattern=r'^reduce_balance_(\d+)$'))
    async def reduce_balance_handler(event):
        """Handler untuk mengurangi saldo user tertentu"""
        # Verifikasi bahwa pengguna adalah admin
        admin_id = event.sender_id
        admin = User.get_by_id(admin_id)
        if not admin or admin.role != 'admin':
            await event.answer("⛔ Anda tidak memiliki akses ke menu ini", alert=True)
            return
        
        # Ambil user_id dari callback data
        user_id = int(event.data_match.group(1).decode())
        
        # Ambil data user dari database
        user = User.get_by_id(user_id)
        if not user:
            await event.answer("❌ User tidak ditemukan", alert=True)
            return
        
        # Simpan state untuk mengurangi saldo
        balance_states[admin_id] = {
            'action': 'reduce',
            'step': 'input_amount',
            'target_user_id': user_id
        }
        
        await event.edit(
            f"➖ **Kurangi Saldo User**\n\n"
            f"**User:** {user.username or user.first_name or f'User {user.user_id}'}\n"
            f"**Saldo Saat Ini:** Rp {user.balance:,}\n\n"
            f"Silakan masukkan jumlah saldo yang ingin dikurangi (dalam Rupiah):",
            buttons=[[Button.inline("🔙 Kembali", f"user_{user_id}".encode())]]
        )

    @client.on(events.CallbackQuery(data=b'search_user'))
    async def search_user_handler(event):
        """Handler untuk menu pencarian user"""
        # Verifikasi bahwa pengguna adalah admin
        user_id = event.sender_id
        user = User.get_by_id(user_id)
        if not user or user.role != 'admin':
            await event.answer("⛔ Anda tidak memiliki akses ke menu ini", alert=True)
            return
        
        # Simpan state untuk pencarian user
        search_states[user_id] = {'step': 'input_search'}
        
        await event.edit(
            "🔍 **Cari User**\n\n"
            "Silakan masukkan ID, username, atau nama user yang ingin dicari:",
            buttons=[[Button.inline("🔙 Kembali", b'setting_user')]]
        )

    @client.on(events.CallbackQuery(data=b'change_role'))
    async def change_role_menu_handler(event):
        """Handler untuk menu ubah role"""
        # Verifikasi bahwa pengguna adalah admin
        user_id = event.sender_id
        user = User.get_by_id(user_id)
        if not user or user.role != 'admin':
            await event.answer("⛔ Anda tidak memiliki akses ke menu ini", alert=True)
            return
        
        # Simpan state untuk pencarian user untuk ubah role
        search_states[user_id] = {'step': 'input_search_for_role'}
        
        await event.edit(
            "👑 **Ubah Role User**\n\n"
            "Silakan masukkan ID atau username user yang ingin diubah rolenya:\n\n"
            "Format: `ID` atau `@username`",
            buttons=[[Button.inline("🔙 Kembali", b'setting_user')]]
        )

    @client.on(events.NewMessage(func=lambda e: e.is_private))
    async def handle_user_input(event):
        """Handler untuk input pesan dari user"""
        user_id = event.sender_id
        message_text = event.message.text
        
        # Cek apakah user sedang dalam state pencarian
        if user_id in search_states:
            search_state = search_states[user_id]
            
            # Pencarian user biasa
            if search_state['step'] == 'input_search':
                # Hapus state pencarian
                del search_states[user_id]
                
                # Cari user berdasarkan input
                search_term = message_text.strip()
                
                # Coba cari berdasarkan ID jika input adalah angka
                if search_term.isdigit():
                    user = User.get_by_id(int(search_term))
                    if user:
                        # Ambil jumlah transaksi user
                        total_trx = RiwayatTransaksi.get_user_transaction_count(user.user_id)
                        successful_trx = RiwayatTransaksi.get_user_successful_transaction_count(user.user_id)
                        
                        # Tampilkan detail user
                        status_text = "Aktif ✅" if user.is_active else "Nonaktif ❌"
                        user_info = (
                            f"👤 **Detail User**\n\n"
                            f"**ID:** `{user.user_id}`\n"
                            f"**Username:** {user.username or 'Tidak ada'}\n"
                            f"**Nama:** {user.first_name or 'Tidak ada'}\n"
                            f"**Role:** {user.role}\n"
                            f"**Status:** {status_text}\n"
                            f"**Saldo:** Rp {user.balance:,}\n"
                            f"**Total Transaksi:** {total_trx} (Sukses: {successful_trx})\n"
                            f"**Terdaftar:** {user.created_at.strftime('%d-%m-%Y %H:%M')}\n"
                        )
                        await event.respond(
                            user_info,
                            buttons=user_detail_buttons(user.user_id)
                        )
                        return
                
                # Coba cari berdasarkan username (hapus @ jika ada)
                if search_term.startswith('@'):
                    search_term = search_term[1:]
                
                # Cari user berdasarkan username atau nama
                users = User.search_users(search_term)
                
                if not users:
                    await event.respond(
                        "❌ **User Tidak Ditemukan**\n\n"
                        f"Tidak ada user yang cocok dengan pencarian '{message_text}'.",
                        buttons=[[Button.inline("🔙 Kembali", b'search_user')]]
                    )
                    return
                
                # Jika hanya ada 1 user, tampilkan detailnya
                if len(users) == 1:
                    user = users[0]
                    # Ambil jumlah transaksi user
                    total_trx = RiwayatTransaksi.get_user_transaction_count(user.user_id)
                    successful_trx = RiwayatTransaksi.get_user_successful_transaction_count(user.user_id)
                    
                    status_text = "Aktif ✅" if user.is_active else "Nonaktif ❌"
                    user_info = (
                        f"👤 **Detail User**\n\n"
                        f"**ID:** `{user.user_id}`\n"
                        f"**Username:** {user.username or 'Tidak ada'}\n"
                        f"**Nama:** {user.first_name or 'Tidak ada'}\n"
                        f"**Role:** {user.role}\n"
                        f"**Status:** {status_text}\n"
                        f"**Saldo:** Rp {user.balance:,}\n"
                        f"**Total Transaksi:** {total_trx} (Sukses: {successful_trx})\n"
                        f"**Terdaftar:** {user.created_at.strftime('%d-%m-%Y %H:%M')}\n"
                    )
                    await event.respond(
                        user_info,
                        buttons=user_detail_buttons(user.user_id)
                    )
                    return
                
                # Jika ada lebih dari 1 user, tampilkan daftar
                await event.respond(
                    f"🔍 **Hasil Pencarian**\n\n"
                    f"Ditemukan {len(users)} user yang cocok dengan '{message_text}'.\n"
                    f"Pilih user untuk melihat detail:",
                    buttons=user_list_buttons(users)
                )
                return
            
            # Pencarian user untuk ubah role
            elif search_state['step'] == 'input_search_for_role':
                # Hapus state pencarian
                del search_states[user_id]
                
                # Cari user berdasarkan input
                search_term = message_text.strip()
                target_user = None
                
                # Coba cari berdasarkan ID jika input adalah angka
                if search_term.isdigit():
                    target_user = User.get_by_id(int(search_term))
                # Coba cari berdasarkan username (hapus @ jika ada)
                elif search_term.startswith('@'):
                    username = search_term[1:]
                    users = User.search_users(username)
                    if users and len(users) == 1:
                        target_user = users[0]
                
                if not target_user:
                    await event.respond(
                        "❌ **User Tidak Ditemukan**\n\n"
                        f"Tidak ada user yang cocok dengan '{message_text}'.\n"
                        f"Silakan coba lagi dengan ID atau username yang valid.",
                        buttons=[[Button.inline("🔙 Kembali", b'change_role')]]
                    )
                    return
                
                # Jangan izinkan admin mengubah role dirinya sendiri
                if target_user.user_id == user_id:
                    await event.respond(
                        "⚠️ **Tidak Diizinkan**\n\n"
                        "Anda tidak dapat mengubah role diri sendiri.",
                        buttons=[[Button.inline("🔙 Kembali", b'change_role')]]
                    )
                    return
                
                # Tampilkan pilihan role
                await event.respond(
                    f"👑 **Ubah Role User**\n\n"
                    f"**User:** {target_user.username or target_user.first_name or f'User {target_user.user_id}'}\n"
                    f"**Role Saat Ini:** {target_user.role}\n\n"
                    f"Pilih role baru:",
                    buttons=role_selection_buttons(target_user.user_id)
                )
                return
        
        # Cek apakah user sedang dalam state pengeditan saldo
        if user_id in balance_states:
            state = balance_states[user_id]
            
            # Jika sedang input user_id
            if state['step'] == 'input_user_id':
                search_term = message_text.strip()
                target_user = None
                
                # Coba cari berdasarkan ID jika input adalah angka
                if search_term.isdigit():
                    target_user = User.get_by_id(int(search_term))
                # Coba cari berdasarkan username (hapus @ jika ada)
                elif search_term.startswith('@'):
                    username = search_term[1:]
                    users = User.search_users(username)
                    if users and len(users) == 1:
                        target_user = users[0]
                
                if not target_user:
                    await event.respond(
                        "❌ **User Tidak Ditemukan**\n\n"
                        f"Tidak ada user yang cocok dengan '{message_text}'.\n"
                        f"Silakan coba lagi dengan ID atau username yang valid.",
                        buttons=[[Button.inline("🔙 Kembali", b'manage_balance')]]
                    )
                    # Hapus state
                    del balance_states[user_id]
                    return
                
                # Update state dengan target user
                state['step'] = 'input_amount'
                state['target_user_id'] = target_user.user_id
                action_text = "ditambahkan" if state['action'] == 'add' else "dikurangi"
                action_emoji = "➕" if state['action'] == 'add' else "➖"
                
                await event.respond(
                    f"{action_emoji} **{state['action'].capitalize()} Saldo User**\n\n"
                    f"**User:** {target_user.username or target_user.first_name or f'User {target_user.user_id}'}\n"
                    f"**Saldo Saat Ini:** Rp {target_user.balance:,}\n\n"
                    f"Silakan masukkan jumlah saldo yang ingin {action_text} (dalam Rupiah):",
                    buttons=[[Button.inline("🔙 Kembali", b'manage_balance')]]
                )
                return
            
            # Jika sedang input jumlah
            elif state['step'] == 'input_amount':
                # Hapus state
                amount_str = message_text.strip()
                
                # Validasi input jumlah
                try:
                    # Hapus karakter non-digit (seperti Rp, koma, titik)
                    amount_str = re.sub(r'[^\d]', '', amount_str)
                    amount = int(amount_str)
                    
                    if amount <= 0:
                        raise ValueError("Jumlah harus lebih dari 0")
                    
                    # Ambil data user target
                    target_user_id = state['target_user_id']
                    target_user = User.get_by_id(target_user_id)
                    
                    if not target_user:
                        await event.respond(
                            "❌ **Error**\n\n"
                            "User tidak ditemukan. Operasi dibatalkan.",
                            buttons=[[Button.inline("🔙 Kembali", b'manage_balance')]]
                        )
                        del balance_states[user_id]
                        return
                    
                    # Cek saldo cukup jika mengurangi
                    if state['action'] == 'reduce' and amount > target_user.balance:
                        await event.respond(
                            "❌ **Saldo Tidak Cukup**\n\n"
                            f"Saldo user saat ini adalah Rp {target_user.balance:,}, "
                            f"tidak cukup untuk dikurangi sebesar Rp {amount:,}.",
                            buttons=[[Button.inline("🔙 Kembali", b'manage_balance')]]
                        )
                        del balance_states[user_id]
                        return
                    
                    # Lakukan operasi saldo
                    old_balance = target_user.balance
                    if state['action'] == 'add':
                        new_balance = User.update_balance(target_user_id, amount, is_addition=True)
                        action_text = "ditambahkan ke"
                        action_emoji = "➕"
                    else: # reduce
                        new_balance = User.update_balance(target_user_id, amount, is_addition=False)
                        action_text = "dikurangi dari"
                        action_emoji = "➖"
                    
                    if new_balance is None:
                        await event.respond(
                            "❌ **Error**\n\n"
                            "Gagal memperbarui saldo. Operasi dibatalkan.",
                            buttons=[[Button.inline("🔙 Kembali", b'manage_balance')]]
                        )
                        del balance_states[user_id]
                        return
                    
                    # Kirim konfirmasi
                    await event.respond(
                        f"✅ **Saldo Berhasil Diperbarui**\n\n"
                        f"**User:** {target_user.username or target_user.first_name or f'User {target_user.user_id}'}\n"
                        f"**Operasi:** {action_emoji} Rp {amount:,} {action_text} saldo\n"
                        f"**Saldo Lama:** Rp {old_balance:,}\n"
                        f"**Saldo Baru:** Rp {new_balance:,}",
                        buttons=[[Button.inline("🔙 Kembali", b'manage_balance')]]
                    )
                    
                    # Log operasi
                    logger.info(
                        f"Admin {user_id} {state['action']}ed balance for user {target_user_id}. "
                        f"Amount: {amount}, Old balance: {old_balance}, New balance: {new_balance}"
                    )
                
                except ValueError as e:
                    await event.respond(
                        "❌ **Input Tidak Valid**\n\n"
                        f"Silakan masukkan jumlah yang valid dalam bentuk angka.\n"
                        f"Contoh: 50000",
                        buttons=[[Button.inline("🔙 Kembali", b'manage_balance')]]
                    )
                
                # Hapus state setelah selesai
                del balance_states[user_id]
                return

    # Tambahkan handler untuk kembali ke menu admin
    @client.on(events.CallbackQuery(data=b'back_to_admin'))
    async def back_to_admin_handler(event):
        """Handler untuk kembali ke menu admin"""
        from handlers.admin_handlers import admin_menu_handler
        await admin_menu_handler(event)

# Fungsi untuk menambahkan semua handler ke client
async def setup_setting_user_handlers(client):
    """Setup semua handler untuk pengaturan user"""
    await register_setting_user_handlers(client)
