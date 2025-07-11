import logging
from telethon import events, Button
from datetime import datetime
from models.user import User
from handlers.member_chat import chat_messages

logger = logging.getLogger(__name__)

# Dictionary to store admin states
admin_states = {}

async def handle_admin_chat_callback(event, client):
    """
    Handle admin chat functionality for callback queries
    """
    admin_id = event.sender_id
    
    # Check if the button was clicked
    if event.data == b'daftar_chat_member':
        await show_chat_list(event, client, admin_id)
        return
    
    # Check if admin is replying to a member
    if event.data and event.data.startswith(b'reply_'):
        user_id = int(event.data[6:].decode())
        await start_reply_to_member(event, client, admin_id, user_id)
        return
    
    # Check if admin is viewing a specific chat
    if event.data and event.data.startswith(b'view_chat_'):
        user_id = int(event.data[10:].decode())
        await view_chat_history(event, client, admin_id, user_id)
        return
    
    # Check if this is a cancel reply command
    if event.data == b'cancel_reply':
        await exit_reply_mode(event, admin_id)
        return
    
    # Check if admin wants to broadcast a message
    if event.data == b'broadcast_message':
        await start_broadcast_message(event, client, admin_id)
        return
    
    # Check if admin wants to cancel broadcast
    if event.data == b'cancel_broadcast':
        if admin_id in admin_states:
            del admin_states[admin_id]
        
        await event.edit(
            "✅ Mode broadcast dibatalkan.",
            buttons=[[Button.inline("🔙 Kembali", b'daftar_chat_member')]]
        )
        return
    
    # Check if admin confirms broadcast
    if event.data == b'confirm_broadcast':
        if admin_id in admin_states and admin_states[admin_id].get('broadcast_message'):
            await send_broadcast_message(event, client, admin_id)
        return

async def handle_admin_chat_message(event, client):
    """
    Handle admin chat functionality for regular messages
    """
    admin_id = event.sender_id
    
    # Check if this is a /start command
    if hasattr(event, 'message') and event.message.text == '/start':
        # Exit reply mode if active
        if admin_id in admin_states and admin_states[admin_id].get('reply_to'):
            await exit_reply_mode(event, admin_id)
            return True
        # Exit broadcast mode if active
        elif admin_id in admin_states and admin_states[admin_id].get('broadcast_mode'):
            if admin_id in admin_states:
                del admin_states[admin_id]
            
            from keyboards.admin_keyboards import admin_start_menu
            
            await event.respond(
                "🏠 **Menu Admin**\n\n"
                "Silakan pilih layanan yang Anda butuhkan:",
                buttons=admin_start_menu
            )
            return True
    
    # Check if admin is in reply mode
    if admin_id in admin_states and admin_states[admin_id].get('reply_to'):
        await send_reply_to_member(event, client, admin_id)
        return True
    
    # Check if admin is in broadcast mode
    if admin_id in admin_states and admin_states[admin_id].get('broadcast_mode'):
        # Save the broadcast message
        admin_states[admin_id]['broadcast_message'] = event.message
        
        # Ask for confirmation
        await event.respond(
            "📢 **Konfirmasi Broadcast**\n\n"
            "Pesan ini akan dikirim ke semua pengguna yang terdaftar.\n"
            "Apakah Anda yakin ingin melanjutkan?",
            buttons=[
                [Button.inline("✅ Ya, Kirim", b'confirm_broadcast')],
                [Button.inline("❌ Batal", b'cancel_broadcast')]
            ]
        )
        return True
    
    return False

async def exit_reply_mode(event, admin_id):
    """
    Exit reply mode and return to chat list
    """
    if admin_id in admin_states:
        del admin_states[admin_id]
    
    # Check if this is a callback query or a message
    if hasattr(event, 'edit'):
        # This is a callback query
        await event.edit(
            "✅ Mode balas dibatalkan.",
            buttons=[[Button.inline("🔙 Kembali", b'daftar_chat_member')]]
        )
    else:
        # This is a message
        await event.respond(
            "✅ Mode balas dibatalkan.",
            buttons=[[Button.inline("🔙 Kembali", b'daftar_chat_member')]]
        )

async def show_chat_list(event, client, admin_id):
    """
    Show list of member chats, prioritizing unread messages
    """
    try:
        # Create message
        message = "📲 **Daftar Chat Member**\n\n"
        
        # Get unread chats
        unread_chats = []
        for user_id, messages in chat_messages.items():
            # Check if there are unread messages from this user
            unread_count = sum(1 for msg in messages if not msg['is_from_admin'] and not msg['is_read'])
            if unread_count > 0:
                # Get user info
                user = User.get_by_id(user_id)
                if user:
                    last_message_time = max(msg['timestamp'] for msg in messages)
                    unread_chats.append({
                        'user_id': user_id,
                        'first_name': user.first_name,
                        'username': user.username,
                        'message_count': unread_count,
                        'last_message_time': last_message_time
                    })
        
        # Sort unread chats by last message time (newest first)
        unread_chats.sort(key=lambda x: x['last_message_time'], reverse=True)
        
        # Get all chats
        all_chats = []
        for user_id, messages in chat_messages.items():
            # Get user info
            user = User.get_by_id(user_id)
            if user:
                last_message_time = max(msg['timestamp'] for msg in messages)
                all_chats.append({
                    'user_id': user_id,
                    'first_name': user.first_name,
                    'username': user.username,
                    'message_count': len(messages),
                    'last_message_time': last_message_time
                })
        
        # Sort all chats by last message time (newest first)
        all_chats.sort(key=lambda x: x['last_message_time'], reverse=True)
        
        # Show unread chats first
        if unread_chats:
            message += "🔴 **Pesan Belum Dibaca:**\n"
            for chat in unread_chats:
                username = f"@{chat['username']}" if chat['username'] else "No username"
                message += f"👤 {chat['first_name']} ({username})\n"
                message += f"   {chat['message_count']} pesan | Terakhir: {chat['last_message_time'].strftime('%d/%m/%Y %H:%M')}\n\n"
        
        # Show all chats
        if all_chats:
            if unread_chats:
                message += "📋 **Semua Percakapan:**\n"
            
            buttons = []
            for chat in all_chats:
                username = f"@{chat['username']}" if chat['username'] else "No username"
                name_display = f"{chat['first_name']} ({username})"
                
                # Check if this chat has unread messages
                is_unread = any(u['user_id'] == chat['user_id'] for u in unread_chats)
                prefix = "🔴 " if is_unread else "🔵 "
                
                buttons.append([Button.inline(
                    f"{prefix}{name_display}",
                    f"view_chat_{chat['user_id']}".encode()
                )])
        else:
            message += "Tidak ada percakapan yang tersedia."
            buttons = []
        
        # Add broadcast button
        buttons.append([Button.inline("📢 Kirim Pesan ke Semua User", b'broadcast_message')])
        
        # Add back button
        buttons.append([Button.inline("🔙 Kembali", b'back_to_admin_menu')])
        
        await event.edit(message, buttons=buttons)
        
    except Exception as e:
        logger.error(f"Error showing chat list: {e}")
        await event.edit(
            "❌ Terjadi kesalahan saat memuat daftar chat.",
            buttons=[[Button.inline("🔙 Kembali", b'back_to_admin_menu')]]
        )

async def view_chat_history(event, client, admin_id, user_id):
    """
    View chat history with a specific member
    """
    try:
        # Get user information
        user = User.get_by_id(user_id)
        if not user:
            await event.edit(
                "❌ User tidak ditemukan.",
                buttons=[[Button.inline("🔙 Kembali", b'daftar_chat_member')]]
            )
            return
        
        # Get chat history
        messages = chat_messages.get(user_id, [])
        
        # Mark messages as read
        for msg in messages:
            if not msg['is_from_admin']:
                msg['is_read'] = True
        
        # Create message
        username = f"@{user.username}" if user.username else "No username"
        header = f"💬 **Chat dengan {user.first_name}** ({username})\n"
        header += f"ID: `{user_id}`\n\n"
        
        chat_history = ""
        if messages:
            # Sort messages by timestamp (oldest first)
            sorted_messages = sorted(messages, key=lambda x: x['timestamp'])
            
            for msg in sorted_messages:
                time_str = msg['timestamp'].strftime('%d/%m/%Y %H:%M')
                
                # Check if message has media
                media_indicator = ""
                if msg.get('media_type'):
                    if msg['media_type'] == 'photo':
                        media_indicator = " [📷 Foto]"
                    elif msg['media_type'] == 'document':
                        media_indicator = " [📎 Dokumen]"
                    elif msg['media_type'] == 'video':
                        media_indicator = " [🎥 Video]"
                    elif msg['media_type'] == 'voice':
                        media_indicator = " [🎤 Pesan Suara]"
                    else:
                        media_indicator = " [📤 Media]"
                
                if msg['is_from_admin']:
                    chat_history += f"🔹 **Admin ({time_str}):** {msg['message']}{media_indicator}\n\n"
                else:
                    chat_history += f"🔸 **Member ({time_str}):** {msg['message']}{media_indicator}\n\n"
        else:
            chat_history = "Tidak ada riwayat chat."
        
        # Create buttons
        buttons = [
            [Button.inline("💬 Balas", f"reply_{user_id}".encode())],
            [Button.inline("🔙 Kembali", b'daftar_chat_member')]
        ]
        
        # Send message in chunks if too long
        if len(header + chat_history) > 4000:
            await event.edit(header)
            
            # Split chat history into chunks
            chunks = [chat_history[i:i+4000] for i in range(0, len(chat_history), 4000)]
            for i, chunk in enumerate(chunks):
                if i == len(chunks) - 1:  # Last chunk
                    await client.send_message(admin_id, chunk, buttons=buttons)
                else:
                    await client.send_message(admin_id, chunk)
        else:
            await event.edit(header + chat_history, buttons=buttons)
        
    except Exception as e:
        logger.error(f"Error viewing chat history: {e}")
        await event.edit(
            "❌ Terjadi kesalahan saat memuat riwayat chat.",
            buttons=[[Button.inline("🔙 Kembali", b'daftar_chat_member')]]
        )

async def start_reply_to_member(event, client, admin_id, user_id):
    """
    Start replying to a member
    """
    # Set admin state
    admin_states[admin_id] = {'reply_to': user_id}
    
    # Get user information
    user = User.get_by_id(user_id)
    username = f"@{user.username}" if user and user.username else "No username"
    name = user.first_name if user else "Member"
    
    await event.edit(
        f"💬 **Balas ke {name}** ({username})\n\n"
        "Ketik pesan balasan Anda. Pesan akan langsung dikirim ke member.\n"
        "Anda juga dapat mengirim foto, video, atau dokumen.\n"
        "Untuk keluar dari mode balas, klik tombol di bawah atau ketik /start.",
        buttons=[[Button.inline("❌ Batal", b'cancel_reply')]]
    )

async def send_reply_to_member(event, client, admin_id):
    """
    Send admin's reply to the member
    """
    # Get the member ID from admin state
    if admin_id not in admin_states or not admin_states[admin_id].get('reply_to'):
        return
    
    user_id = admin_states[admin_id]['reply_to']
    
    # Get user and admin information
    user = User.get_by_id(user_id)
    admin = User.get_by_id(admin_id)
    
    if not user:
        await event.respond(
            "❌ User tidak ditemukan.",
            buttons=[[Button.inline("🔙 Kembali", b'daftar_chat_member')]]
        )
        return
    
    # Check message type and content
    if hasattr(event, 'message'):
        message = event.message
        message_content = message.text or ""
        media_type = None
        
        try:
            # Check if message has media
            if message.media:
                # Prepare header for media message
                header = f"💬 **Balasan dari Admin:**\n\n"
                if message.text:
                    header += f"{message.text}"
                
                # Forward the media message
                await message.forward_to(user_id)
                
                # For media messages, also send a text notification
                if not message.text:
                    await client.send_message(user_id, "💬 **Admin mengirim media kepada Anda**")
                
                # Determine media type
                if message.photo:
                    media_type = "photo"
                elif message.document:
                    media_type = "document"
                elif message.video:
                    media_type = "video"
                elif message.voice:
                    media_type = "voice"
                else:
                    media_type = "other"
            else:
                # Text message
                await client.send_message(
                    user_id,
                    f"💬 **Balasan dari Admin:**\n\n{message_content}"
                )
            
            # Save message to memory
            if user_id not in chat_messages:
                chat_messages[user_id] = []
            
            chat_messages[user_id].append({
                'message': message_content,
                'is_from_admin': True,
                'admin_id': admin_id,
                'timestamp': datetime.now(),
                'is_read': True,
                'media_type': media_type
            })
            
            # Confirm to admin
            await event.respond(
                "✅ Pesan terkirim ke member.\n\n"
                "Anda dapat mengirim pesan lain atau keluar dari mode balas.",
                buttons=[[Button.inline("❌ Keluar", b'cancel_reply')]]
            )
        except Exception as e:
            logger.error(f"Failed to send reply to member {user_id}: {e}")
            await event.respond(
                "❌ Gagal mengirim pesan ke member. Mungkin member telah memblokir bot.",
                buttons=[[Button.inline("❌ Keluar", b'cancel_reply')]]
            )

async def start_broadcast_message(event, client, admin_id):
    """
    Start broadcast message mode
    """
    # Set admin state
    admin_states[admin_id] = {'broadcast_mode': True}
    
    await event.edit(
        "📢 **Kirim Pesan Broadcast**\n\n"
        "Ketik pesan yang ingin Anda kirim ke semua pengguna terdaftar.\n"
        "Anda juga dapat mengirim foto, video, atau dokumen.\n"
        "Untuk keluar dari mode broadcast, klik tombol di bawah atau ketik /start.",
        buttons=[[Button.inline("❌ Batal", b'cancel_broadcast')]]
    )

async def send_broadcast_message(event, client, admin_id):
    """
    Send broadcast message to all users and pin it automatically
    """
    try:
        # Get the broadcast message
        if admin_id not in admin_states or not admin_states[admin_id].get('broadcast_message'):
            await event.edit(
                "❌ Tidak ada pesan broadcast yang ditemukan.",
                buttons=[[Button.inline("🔙 Kembali", b'daftar_chat_member')]]
            )
            return
        
        broadcast_message = admin_states[admin_id]['broadcast_message']
        
        # Get all users
        all_users = User.get_all_users()
        
        if not all_users:
            await event.edit(
                "❌ Tidak ada pengguna yang terdaftar.",
                buttons=[[Button.inline("🔙 Kembali", b'daftar_chat_member')]]
            )
            return
        
        # Start progress message
        progress_msg = await event.edit(
            "📤 **Mengirim pesan broadcast...**\n\n"
            "0% selesai (0/{} pengguna)".format(len(all_users))
        )
        
        # Send message to all users
        success_count = 0
        failed_count = 0
        pin_success_count = 0
        pin_failed_count = 0
        
        for i, user in enumerate(all_users):
            try:
                sent_message = None
                
                # Check if message has media
                if broadcast_message.media:
                    # Prepare header for media message
                    header = "📢 **Pengumuman dari Admin:**\n\n"
                    if broadcast_message.text:
                        header += f"{broadcast_message.text}"
                    
                    # Send notification first for media messages
                    if not broadcast_message.text:
                        await client.send_message(user.user_id, "📢 **Admin mengirim pengumuman dengan media**")
                    
                    # Forward the media message
                    sent_message = await broadcast_message.forward_to(user.user_id)
                else:
                    # Text message
                    sent_message = await client.send_message(
                        user.user_id,
                        f"📢 **Pengumuman dari Admin:**\n\n{broadcast_message.text}"
                    )
                
                # Try to pin the message
                try:
                    if sent_message:
                        await client.pin_message(user.user_id, sent_message.id)
                        pin_success_count += 1
                except Exception as pin_error:
                    logger.error(f"Failed to pin message for user {user.user_id}: {pin_error}")
                    pin_failed_count += 1
                
                success_count += 1
            except Exception as e:
                logger.error(f"Failed to send broadcast to user {user.user_id}: {e}")
                failed_count += 1
            
            # Update progress every 5 users or at the end
            if (i + 1) % 5 == 0 or i == len(all_users) - 1:
                progress_percent = round((i + 1) / len(all_users) * 100)
                await progress_msg.edit(
                    f"📤 **Mengirim pesan broadcast...**\n\n"
                    f"{progress_percent}% selesai ({i+1}/{len(all_users)} pengguna)"
                )
        
        # Clear admin state
        if admin_id in admin_states:
            del admin_states[admin_id]
        
        # Show final result
        await progress_msg.edit(
            f"✅ **Broadcast selesai**\n\n"
            f"✓ Berhasil terkirim: {success_count} pengguna\n"
            f"✗ Gagal terkirim: {failed_count} pengguna\n\n"
            f"📌 **Status Pin:**\n"
            f"✓ Berhasil di-pin: {pin_success_count} pesan\n"
            f"✗ Gagal di-pin: {pin_failed_count} pesan\n\n"
            f"Catatan: Pesan gagal di-pin mungkin karena bot tidak memiliki izin untuk menyematkan pesan atau pengguna belum memulai percakapan dengan bot.",
            buttons=[[Button.inline("🔙 Kembali", b'daftar_chat_member')]]
        )
        
    except Exception as e:
        logger.error(f"Error sending broadcast: {e}")
        await event.edit(
            "❌ Terjadi kesalahan saat mengirim pesan broadcast.",
            buttons=[[Button.inline("🔙 Kembali", b'daftar_chat_member')]]
        )


# Register handlers
async def register_handlers(client):
    """
    Register all handlers for admin chat
    """
    @client.on(events.CallbackQuery(pattern=b'daftar_chat_member'))
    async def on_chat_list_button(event):
        # Check if user is admin
        user_id = event.sender_id
        if User.get_role(user_id) != 'admin':
            await event.answer("Anda tidak memiliki akses ke fitur ini.", alert=True)
            return
        await handle_admin_chat_callback(event, client)
    
    @client.on(events.CallbackQuery(pattern=b'view_chat_'))
    async def on_view_chat_button(event):
        # Check if user is admin
        user_id = event.sender_id
        if User.get_role(user_id) != 'admin':
            await event.answer("Anda tidak memiliki akses ke fitur ini.", alert=True)
            return
        await handle_admin_chat_callback(event, client)
    
    @client.on(events.CallbackQuery(pattern=b'reply_'))
    async def on_reply_button(event):
        # Check if user is admin
        user_id = event.sender_id
        if User.get_role(user_id) != 'admin':
            await event.answer("Anda tidak memiliki akses ke fitur ini.", alert=True)
            return
        await handle_admin_chat_callback(event, client)
    
    @client.on(events.CallbackQuery(pattern=b'cancel_reply'))
    async def on_cancel_reply(event):
        # Check if user is admin
        user_id = event.sender_id
        if User.get_role(user_id) != 'admin':
            await event.answer("Anda tidak memiliki akses ke fitur ini.", alert=True)
            return
        await handle_admin_chat_callback(event, client)
    
    @client.on(events.CallbackQuery(pattern=b'broadcast_message'))
    async def on_broadcast_button(event):
        # Check if user is admin
        user_id = event.sender_id
        if User.get_role(user_id) != 'admin':
            await event.answer("Anda tidak memiliki akses ke fitur ini.", alert=True)
            return
        await handle_admin_chat_callback(event, client)
    
    @client.on(events.CallbackQuery(pattern=b'cancel_broadcast'))
    async def on_cancel_broadcast(event):
        # Check if user is admin
        user_id = event.sender_id
        if User.get_role(user_id) != 'admin':
            await event.answer("Anda tidak memiliki akses ke fitur ini.", alert=True)
            return
        await handle_admin_chat_callback(event, client)
    
    @client.on(events.CallbackQuery(pattern=b'confirm_broadcast'))
    async def on_confirm_broadcast(event):
        # Check if user is admin
        user_id = event.sender_id
        if User.get_role(user_id) != 'admin':
            await event.answer("Anda tidak memiliki akses ke fitur ini.", alert=True)
            return
        await handle_admin_chat_callback(event, client)
    
    @client.on(events.CallbackQuery(pattern=b'back_to_admin_menu'))
    async def on_back_to_menu(event):
        # Check if user is admin
        user_id = event.sender_id
        if User.get_role(user_id) != 'admin':
            await event.answer("Anda tidak memiliki akses ke fitur ini.", alert=True)
            return
        
        # Clear admin state
        if user_id in admin_states:
            del admin_states[user_id]
        
        # Import keyboard admin
        from keyboards.admin_keyboards import admin_start_menu
        
        await event.edit(
            "🏠 **Menu Admin**\n\n"
            "Silakan pilih layanan yang Anda butuhkan:",
            buttons=admin_start_menu
        )
    
    @client.on(events.NewMessage())
    async def on_new_message(event):
        # Only process messages from private chats (not groups/channels)
        if event.is_private:
            user_id = event.sender_id
            
            # Check if user is admin
            if User.get_role(user_id) == 'admin':
                # Handle admin chat messages
                handled = await handle_admin_chat_message(event, client)
                
                # If message was handled by chat handler, don't process further
                if handled:
                    return
    
    logger.info("Admin chat handlers registered successfully")
    return True
