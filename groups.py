# Group management API module

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from logger_config import logger
from db import (
    create_group, add_user_to_group, remove_user_from_group, get_user_group,
    get_group_members, get_all_groups, delete_group
)

def get_persistent_keyboard():
    """Create persistent buttons that are always available."""
    keyboard = [
        [
            InlineKeyboardButton("📅 Date Search", callback_data="persistent_calendar"),
            InlineKeyboardButton("📊 Summary", callback_data="persistent_summary")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

async def show_group_info(update: Update, context: ContextTypes.DEFAULT_TYPE, check_user_access_func):
    """Show current group information for the user."""
    user = update.effective_user
    logger.info(f"[GROUPS] Group info command received from user {user.full_name} (ID: {user.id})")
    
    if not await check_user_access_func(update, context):
        logger.warning(f"[GROUPS] Access denied for group info command from user {user.id}")
        return
    
    try:
        user_group = get_user_group(update.effective_user.id)
        if not user_group:
            await update.message.reply_text(
                "You are not currently in any group.\n\n"
                "To join a group, use /joingroup GROUP_ID\n"
                "To create a new group (admin only), use /creategroup DESCRIPTION",
                reply_markup=get_persistent_keyboard()
            )
            logger.info(f"[GROUPS] User {user.id} is not in any group")
            return
        
        # Get group members
        members = get_group_members(user_group.group_id)
        member_names = [f"• {member.name} (ID: {member.user_id})" for member in members]
        
        group_text = (
            f"📊 Your Group: {user_group.description}\n"
            f"Group ID: {user_group.group_id}\n\n"
            f"Members ({len(members)}):\n"
            + "\n".join(member_names) +
            "\n\n💡 All receipts from group members are included in your lists, summaries, and searches."
        )
        
        await update.message.reply_text(group_text, reply_markup=get_persistent_keyboard())
        logger.info(f"[GROUPS] Displayed group info for user {user.id}, group: {user_group.description}")
        
    except Exception as e:
        logger.error(f"[GROUPS] Error showing group info for user {update.effective_user.id}: {str(e)}", exc_info=True)
        await update.message.reply_text(f"❌ Failed to get group information: {str(e)}", reply_markup=get_persistent_keyboard())

async def create_group_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE, check_user_access_func, get_admin_user_id_func):
    """Create a new group (admin only)."""
    user = update.effective_user
    logger.info(f"[GROUPS] Create group command received from user {user.full_name} (ID: {user.id})")
    
    if not await check_user_access_func(update, context):
        logger.warning(f"[GROUPS] Access denied for create group command from user {user.id}")
        return
    
    # Check if user is admin
    if user.id != get_admin_user_id_func():
        logger.warning(f"[GROUPS] Non-admin user {user.id} attempted to create group")
        await update.message.reply_text("❌ Only the admin can create groups.", reply_markup=get_persistent_keyboard())
        return
    
    # Extract the description after /creategroup
    description = " ".join(context.args) if context.args else ""
    if not description:
        logger.warning(f"[GROUPS] Admin {user.id} attempted to create group without description")
        await update.message.reply_text(
            "Please provide a group description after /creategroup. Example: /creategroup Family Expenses",
            reply_markup=get_persistent_keyboard()
        )
        return
    
    try:
        group_id = create_group(description)
        await update.message.reply_text(
            f"✅ Group created successfully!\n\n"
            f"Group ID: {group_id}\n"
            f"Description: {description}\n\n"
            f"Share the Group ID {group_id} with others so they can join using /joingroup {group_id}",
            reply_markup=get_persistent_keyboard()
        )
        logger.info(f"[GROUPS] Admin {user.id} successfully created group {group_id}: {description}")
        
    except Exception as e:
        logger.error(f"[GROUPS] Error creating group for user {user.id}: {str(e)}", exc_info=True)
        await update.message.reply_text(f"❌ Failed to create group: {str(e)}", reply_markup=get_persistent_keyboard())

async def join_group_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE, check_user_access_func):
    """Join a group.
    
    SECURITY WARNING: This function is currently disabled because it presents a security risk.
    Anyone who discovers a group ID can join and access all group members' expense data.
    Group membership should be managed by the admin only to protect privacy.
    
    To re-enable, uncomment the handler in main() and implement proper authorization:
    - Require admin approval for group joins
    - Or implement invite codes/links
    - Or restrict to pre-authorized users only
    """
    user = update.effective_user
    logger.warning(f"[GROUPS] SECURITY: Disabled join group command attempted by user {user.full_name} (ID: {user.id})")
    
    if not await check_user_access_func(update, context):
        logger.warning(f"[GROUPS] Access denied for join group command from user {user.id}")
        return
    
    await update.message.reply_text(
        "🔒 Group joining is currently disabled for security reasons.\n\n"
        "Group membership is managed by the admin to protect expense privacy.\n"
        "Contact the admin if you need to be added to a group.",
        reply_markup=get_persistent_keyboard()
    )

async def leave_group_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE, check_user_access_func):
    """Leave current group."""
    user = update.effective_user
    logger.info(f"[GROUPS] Leave group command received from user {user.full_name} (ID: {user.id})")
    
    if not await check_user_access_func(update, context):
        logger.warning(f"[GROUPS] Access denied for leave group command from user {user.id}")
        return
    
    try:
        # Check if user is in a group
        current_group = get_user_group(update.effective_user.id)
        if not current_group:
            logger.info(f"[GROUPS] User {user.id} attempted to leave group but is not in any group")
            await update.message.reply_text(
                "❌ You are not currently in any group.",
                reply_markup=get_persistent_keyboard()
            )
            return
        
        # Remove user from group
        success = remove_user_from_group(update.effective_user.id, current_group.group_id)
        if success:
            await update.message.reply_text(
                f"✅ Successfully left group '{current_group.description}' (ID: {current_group.group_id}).\n\n"
                f"You will now only see your own receipts in lists and summaries.",
                reply_markup=get_persistent_keyboard()
            )
            logger.info(f"[GROUPS] User {user.id} successfully left group {current_group.group_id}: {current_group.description}")
        else:
            logger.warning(f"[GROUPS] Failed to remove user {user.id} from group {current_group.group_id}")
            await update.message.reply_text(
                f"❌ Error leaving group.",
                reply_markup=get_persistent_keyboard()
            )
        
    except Exception as e:
        logger.error(f"[GROUPS] Error leaving group for user {user.id}: {str(e)}", exc_info=True)
        await update.message.reply_text(f"❌ Failed to leave group: {str(e)}", reply_markup=get_persistent_keyboard())

async def add_user_to_group_admin(update: Update, context: ContextTypes.DEFAULT_TYPE, check_user_access_func, get_admin_user_id_func):
    """Admin function to add a user to a group (admin only)."""
    user = update.effective_user
    logger.info(f"[GROUPS] Add user to group command received from user {user.full_name} (ID: {user.id})")
    
    if not await check_user_access_func(update, context):
        logger.warning(f"[GROUPS] Access denied for add user to group command from user {user.id}")
        return
    
    # Check if user is admin
    if user.id != get_admin_user_id_func():
        logger.warning(f"[GROUPS] Non-admin user {user.id} attempted to add user to group")
        await update.message.reply_text("❌ Only the admin can add users to groups.", reply_markup=get_persistent_keyboard())
        return
    
    # Extract user_id and group_id from arguments
    if len(context.args) != 2:
        await update.message.reply_text(
            "Please provide user ID and group ID: /addusertogroup USER_ID GROUP_ID",
            reply_markup=get_persistent_keyboard()
        )
        return
    
    try:
        target_user_id = int(context.args[0])
        group_id = int(context.args[1])
        
        success = add_user_to_group(target_user_id, group_id)
        if success:
            await update.message.reply_text(
                f"✅ Successfully added user {target_user_id} to group {group_id}.",
                reply_markup=get_persistent_keyboard()
            )
            logger.info(f"[GROUPS] Admin {user.id} successfully added user {target_user_id} to group {group_id}")
        else:
            logger.warning(f"[GROUPS] Failed to add user {target_user_id} to group {group_id}")
            await update.message.reply_text(
                f"❌ Failed to add user to group. Check if user and group exist.",
                reply_markup=get_persistent_keyboard()
            )
        
    except ValueError:
        logger.warning(f"[GROUPS] Admin {user.id} provided invalid user/group IDs")
        await update.message.reply_text(
            "❌ Invalid user ID or group ID. Please provide numeric values.",
            reply_markup=get_persistent_keyboard()
        )
    except Exception as e:
        logger.error(f"[GROUPS] Error adding user to group for admin {user.id}: {str(e)}", exc_info=True)
        await update.message.reply_text(f"❌ Failed to add user to group: {str(e)}", reply_markup=get_persistent_keyboard())

async def remove_user_from_group_admin(update: Update, context: ContextTypes.DEFAULT_TYPE, check_user_access_func, get_admin_user_id_func):
    """Admin function to remove a user from a group (admin only)."""
    user = update.effective_user
    logger.info(f"[GROUPS] Remove user from group command received from user {user.full_name} (ID: {user.id})")
    
    if not await check_user_access_func(update, context):
        logger.warning(f"[GROUPS] Access denied for remove user from group command from user {user.id}")
        return
    
    # Check if user is admin
    if user.id != get_admin_user_id_func():
        logger.warning(f"[GROUPS] Non-admin user {user.id} attempted to remove user from group")
        await update.message.reply_text("❌ Only the admin can remove users from groups.", reply_markup=get_persistent_keyboard())
        return
    
    # Extract user_id and group_id from arguments
    if len(context.args) != 2:
        await update.message.reply_text(
            "Please provide user ID and group ID: /removeuserfromgroup USER_ID GROUP_ID",
            reply_markup=get_persistent_keyboard()
        )
        return
    
    try:
        target_user_id = int(context.args[0])
        group_id = int(context.args[1])
        
        success = remove_user_from_group(target_user_id, group_id)
        if success:
            await update.message.reply_text(
                f"✅ Successfully removed user {target_user_id} from group {group_id}.",
                reply_markup=get_persistent_keyboard()
            )
            logger.info(f"[GROUPS] Admin {user.id} successfully removed user {target_user_id} from group {group_id}")
        else:
            logger.warning(f"[GROUPS] Failed to remove user {target_user_id} from group {group_id}")
            await update.message.reply_text(
                f"❌ Failed to remove user from group. Check if user is in the group.",
                reply_markup=get_persistent_keyboard()
            )
        
    except ValueError:
        logger.warning(f"[GROUPS] Admin {user.id} provided invalid user/group IDs")
        await update.message.reply_text(
            "❌ Invalid user ID or group ID. Please provide numeric values.",
            reply_markup=get_persistent_keyboard()
        )
    except Exception as e:
        logger.error(f"[GROUPS] Error removing user from group for admin {user.id}: {str(e)}", exc_info=True)
        await update.message.reply_text(f"❌ Failed to remove user from group: {str(e)}", reply_markup=get_persistent_keyboard())

async def list_all_groups_admin(update: Update, context: ContextTypes.DEFAULT_TYPE, check_user_access_func, get_admin_user_id_func):
    """Admin function to list all groups (admin only)."""
    user = update.effective_user
    logger.info(f"[GROUPS] List all groups command received from user {user.full_name} (ID: {user.id})")
    
    if not await check_user_access_func(update, context):
        logger.warning(f"[GROUPS] Access denied for list all groups command from user {user.id}")
        return
    
    # Check if user is admin
    if user.id != get_admin_user_id_func():
        logger.warning(f"[GROUPS] Non-admin user {user.id} attempted to list all groups")
        await update.message.reply_text("❌ Only the admin can list all groups.", reply_markup=get_persistent_keyboard())
        return
    
    try:
        groups = get_all_groups()
        if not groups:
            await update.message.reply_text(
                "No groups found in the system.",
                reply_markup=get_persistent_keyboard()
            )
            logger.info(f"[GROUPS] Admin {user.id} requested group list - no groups found")
            return
        
        group_text = "📊 All Groups:\n\n"
        for group in groups:
            members = get_group_members(group.group_id)
            group_text += f"• ID: {group.group_id} | {group.description} | Members: {len(members)}\n"
        
        await update.message.reply_text(group_text, reply_markup=get_persistent_keyboard())
        logger.info(f"[GROUPS] Admin {user.id} successfully listed {len(groups)} groups")
        
    except Exception as e:
        logger.error(f"[GROUPS] Error listing all groups for admin {user.id}: {str(e)}", exc_info=True)
        await update.message.reply_text(f"❌ Failed to list groups: {str(e)}", reply_markup=get_persistent_keyboard())

async def delete_group_admin(update: Update, context: ContextTypes.DEFAULT_TYPE, check_user_access_func, get_admin_user_id_func):
    """Admin function to delete a group (admin only)."""
    user = update.effective_user
    logger.info(f"[GROUPS] Delete group command received from user {user.full_name} (ID: {user.id})")
    
    if not await check_user_access_func(update, context):
        logger.warning(f"[GROUPS] Access denied for delete group command from user {user.id}")
        return
    
    # Check if user is admin
    if user.id != get_admin_user_id_func():
        logger.warning(f"[GROUPS] Non-admin user {user.id} attempted to delete group")
        await update.message.reply_text("❌ Only the admin can delete groups.", reply_markup=get_persistent_keyboard())
        return
    
    # Extract group_id from arguments
    if len(context.args) != 1:
        await update.message.reply_text(
            "Please provide group ID: /deletegroup GROUP_ID",
            reply_markup=get_persistent_keyboard()
        )
        return
    
    try:
        group_id = int(context.args[0])
        
        success = delete_group(group_id)
        if success:
            await update.message.reply_text(
                f"✅ Successfully deleted group {group_id}.",
                reply_markup=get_persistent_keyboard()
            )
            logger.info(f"[GROUPS] Admin {user.id} successfully deleted group {group_id}")
        else:
            logger.warning(f"[GROUPS] Failed to delete group {group_id} - group not found")
            await update.message.reply_text(
                f"❌ Failed to delete group. Group {group_id} not found.",
                reply_markup=get_persistent_keyboard()
            )
        
    except ValueError:
        logger.warning(f"[GROUPS] Admin {user.id} provided invalid group ID")
        await update.message.reply_text(
            "❌ Invalid group ID. Please provide a numeric value.",
            reply_markup=get_persistent_keyboard()
        )
    except Exception as e:
        logger.error(f"[GROUPS] Error deleting group for admin {user.id}: {str(e)}", exc_info=True)
        await update.message.reply_text(f"❌ Failed to delete group: {str(e)}", reply_markup=get_persistent_keyboard())