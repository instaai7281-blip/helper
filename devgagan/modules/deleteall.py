import asyncio
from pyrogram import filters, enums
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from devgagan import app
from devgagan.core.func import chk_user

@app.on_message(filters.command("deleteall"))
async def delete_all_cmd(_, message):
    chat_id = message.chat.id
    
    # 1. Direct check: only works in channels or groups
    if message.chat.type not in [enums.ChatType.CHANNEL, enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
        await message.reply("❌ **Error:** This command can only be used in channels or groups.")
        return

    # 2. Check authorization of the sender (if sent by a user)
    if message.from_user:
        user_id = message.from_user.id
        if await chk_user(message, user_id) != 0:
            # Check if they are admin in this chat
            try:
                member = await app.get_chat_member(chat_id, user_id)
                if member.status not in [enums.ChatMemberStatus.OWNER, enums.ChatMemberStatus.ADMINISTRATOR]:
                    await message.reply("❌ **Access Denied:** Only administrators or the bot owner can use this command.")
                    return
            except Exception:
                await message.reply("❌ **Access Denied:** You are not authorized here.")
                return

    # 3. Send confirmation message with buttons
    buttons = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🗑️ Delete All", callback_data="confirm_delete_all"),
            InlineKeyboardButton("❌ Cancel", callback_data="cancel_delete_all")
        ]
    ])
    
    await message.reply(
        "⚠️ **WARNING:**\n\n"
        "Are you absolutely sure you want to delete **all messages** in this chat?\n"
        "This action is permanent and cannot be undone!",
        reply_markup=buttons
    )

@app.on_callback_query(filters.regex(r"^(confirm_delete_all|cancel_delete_all)$"))
async def delete_all_callback(_, callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    chat_id = callback_query.message.chat.id
    
    # Verify clicker's rights (Must be owner, premium, or chat administrator)
    authorized = False
    if await chk_user(callback_query.message, user_id) == 0:
        authorized = True
    else:
        try:
            member = await app.get_chat_member(chat_id, user_id)
            if member.status in [enums.ChatMemberStatus.OWNER, enums.ChatMemberStatus.ADMINISTRATOR]:
                authorized = True
        except Exception:
            pass

    if not authorized:
        await callback_query.answer("❌ You are not authorized to perform this action!", show_alert=True)
        return

    if callback_query.data == "cancel_delete_all":
        await callback_query.message.edit_text("❌ **Operation cancelled.** No messages were deleted.")
        return

    # Confirm delete all
    await callback_query.message.edit_text("⌛ **Initializing mass deletion...**")
    
    deleted_count = 0
    message_ids = []
    
    try:
        # Scan and delete all history
        async for msg in app.get_chat_history(chat_id, limit=5000):
            # Skip the confirmation message itself
            if msg.id == callback_query.message.id:
                continue
                
            message_ids.append(msg.id)
            
            # Batch delete in groups of 100 for high efficiency
            if len(message_ids) >= 100:
                try:
                    await app.delete_messages(chat_id, message_ids)
                    deleted_count += len(message_ids)
                    message_ids = []
                    # Simple delay to avoid rate limits
                    await asyncio.sleep(1.0)
                except Exception:
                    pass
                    
        # Clean up remaining messages
        if message_ids:
            try:
                await app.delete_messages(chat_id, message_ids)
                deleted_count += len(message_ids)
            except Exception:
                pass
                
        await callback_query.message.edit_text(
            f"✅ **Success!**\n\n"
            f"Deleted `{deleted_count}` messages successfully."
        )
        
    except Exception as e:
        await callback_query.message.edit_text(f"❌ **An error occurred during deletion:** `{str(e)}`")
