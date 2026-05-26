import asyncio
import time
import re
from datetime import timedelta
from pyrogram import filters, Client
from devgagan import app
from config import OWNER_ID, LOG_GROUP
from pyrogram.errors import FloodWait
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from devgagan.core.func import chk_user
from devgagan.core.mongo import db

@app.on_message(filters.command("logforward") & filters.private)
async def log_forward_cmd(_, message):
    user_id = message.chat.id
    
    # Check authorization (Owner or Premium User)
    if await chk_user(message, user_id) != 0:
        await message.reply("❌ **Access Denied:** Only premium users or the bot owner can use this command.")
        return

    # Check if LOG_GROUP is configured
    if not LOG_GROUP:
        await message.reply("❌ **Error:** `LOG_GROUP` is not configured in the bot environment variables.")
        return

    # 1. Ask for Target Identifier (User ID or Username)
    target_prompt = await app.ask(
        user_id,
        "🎯 **Send the User ID or Username of the target person:**\n\n*(e.g., `8014313443` or `_Himanshu_`)*\n\nSend `/cancel` to abort."
    )
    if target_prompt.text == "/cancel":
        await message.reply("❌ Process cancelled.")
        return
        
    target_val = target_prompt.text.strip()
    if not target_val:
        await message.reply("❌ Invalid input. Process cancelled.")
        return

    # 2. Ask for Destination Channel/Group ID
    dest_prompt = await app.ask(
        user_id,
        "📥 **Send the Destination Channel/Group ID:**\n\n*(Must start with `-100`)*\n\nSend `/cancel` to abort."
    )
    if dest_prompt.text == "/cancel":
        await message.reply("❌ Process cancelled.")
        return
        
    dest_chat_str = dest_prompt.text.strip()
    try:
        dest_chat_id = int(dest_chat_str)
    except ValueError:
        await message.reply("❌ Invalid chat ID format. Process cancelled.")
        return

    # 3. Ask for Scraping Depth
    depth_prompt = await app.ask(
        user_id,
        "🔍 **How many messages should I scan in the log channel?**\n\n*(Recommend 100, 500, or 1000)*\n\nSend `/cancel` to abort."
    )
    if depth_prompt.text == "/cancel":
        await message.reply("❌ Process cancelled.")
        return
        
    try:
        depth = int(depth_prompt.text.strip())
        if depth <= 0:
            raise ValueError()
    except ValueError:
        await message.reply("❌ Invalid scan depth. Process cancelled.")
        return

    status_msg = await message.reply("⌛ **Initializing scan in the log channel...**")

    success_count = 0
    fail_count = 0
    skipped_count = 0
    start_time = time.time()
    
    try:
        # Resolve target identifiers for matching
        target_val_clean = target_val.replace("@", "").lower().strip()
        # Strip underscores and spaces to ensure high-accuracy fuzzy matching
        target_val_fuzzy = re.sub(r'[\s_]+', '', target_val_clean)
        
        # LOG_GROUP can be a string or integer
        log_group_chat = int(LOG_GROUP) if str(LOG_GROUP).strip().lstrip('-').isdigit() else LOG_GROUP
        
        # Verify bot access to LOG_GROUP
        try:
            await app.get_chat(log_group_chat)
        except Exception as e:
            await status_msg.edit(f"❌ **Cannot access Log Group:** `{e}`\n\nPlease make sure the bot has access/admin in the log group channel.")
            return

        # Verify bot access to target chat
        try:
            await app.get_chat(dest_chat_id)
        except Exception as e:
            await status_msg.edit(f"❌ **Cannot access Destination Channel:** `{e}`\n\nPlease make sure the bot is an **Admin** in the target channel.")
            return

        await status_msg.edit(f"🔍 **Scanning last {depth} messages in Log Group...**")
        
        # Fetch user filters
        user_data = await db.get_data(user_id) or {}
        filters_data = user_data.get("filters", {})
        
        # Fetch log group messages
        messages_scanned = 0
        async for msg in app.get_chat_history(log_group_chat, limit=depth):
            messages_scanned += 1
            if messages_scanned % 10 == 0 or messages_scanned == depth:
                try:
                    await status_msg.edit(
                        f"🔍 **Scanning Log Group...**\n\n"
                        f"📊 **Scanned:** `{messages_scanned}/{depth}`\n"
                        f"✨ **Forwarded:** `{success_count}`\n"
                        f"⏭️ **Skipped:** `{skipped_count}`\n"
                        f"❌ **Failed:** `{fail_count}`"
                    )
                except:
                    pass

            # Check both msg.text (for text replies) and msg.caption (for media log copies)
            msg_text = msg.text or msg.caption or ""
            if msg_text and ("log info" in msg_text.lower() or "saved by" in msg_text.lower()):
                msg_text_clean = msg_text.lower()
                # Remove underscores and spaces from log text to perform high-accuracy fuzzy matching
                msg_text_fuzzy = re.sub(r'[\s_]+', '', msg_text_clean)
                
                # Check fuzzy match
                if (target_val_clean in msg_text_clean) or (target_val_fuzzy and target_val_fuzzy in msg_text_fuzzy):
                    parent_media_id = None
                    
                    # Case 1: The message is a reply to the media message
                    if msg.reply_to_message:
                        parent_media_id = msg.reply_to_message.id
                    elif getattr(msg, "reply_to_message_id", None):
                        parent_media_id = msg.reply_to_message_id
                        
                    # Case 2: The message itself is the media message
                    if not parent_media_id and (msg.video or msg.photo or msg.document or msg.audio or msg.voice):
                        parent_media_id = msg.id

                    if parent_media_id:
                        try:
                            # Fetch the actual media message to evaluate its type against filters
                            media_msg = await app.get_messages(log_group_chat, parent_media_id)
                            
                            # Determine media type
                            media_type = None
                            if media_msg.video:
                                media_type = "video"
                            elif media_msg.photo:
                                media_type = "photo"
                            elif media_msg.document:
                                media_type = "document"
                            elif media_msg.audio or media_msg.voice:
                                media_type = "audio"
                            elif media_msg.text:
                                media_type = "text"
                            
                            # Skip if media type is turned OFF in settings
                            if media_type and not filters_data.get(media_type, True):
                                skipped_count += 1
                                continue
                            
                            # Forward the parent media message to the destination
                            await app.copy_message(
                                chat_id=dest_chat_id,
                                from_chat_id=log_group_chat,
                                message_id=parent_media_id
                            )
                            success_count += 1
                            # Delay to prevent FloodWait rate limits
                            await asyncio.sleep(1.2)
                        except FloodWait as e:
                            await asyncio.sleep(e.value + 2)
                            try:
                                await app.copy_message(
                                    chat_id=dest_chat_id,
                                    from_chat_id=log_group_chat,
                                    message_id=parent_media_id
                                )
                                success_count += 1
                            except:
                                fail_count += 1
                        except Exception as e:
                            print(f"Failed to forward message {parent_media_id}: {e}")
                            fail_count += 1

        elapsed_time = time.time() - start_time
        
        await status_msg.edit(
            f"✅ **Log Forwarding Completed!**\n\n"
            f"👤 **Filter:** `{target_val}`\n"
            f"📥 **Destination:** `{dest_chat_id}`\n"
            f"✨ **Successfully Forwarded:** `{success_count}`\n"
            f"⏭️ **Skipped (Filters):** `{skipped_count}`\n"
            f"❌ **Failed:** `{fail_count}`\n"
            f"⏱ **Time Elapsed:** `{int(elapsed_time)}s`"
        )
        
    except Exception as e:
        await status_msg.edit(f"❌ **An error occurred during log forwarding:** `{str(e)}`")

