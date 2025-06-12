import discord
from discord.ext import commands
from discord import app_commands
import asyncio
from datetime import datetime, timedelta
import os
import threading
from flask import Flask, jsonify

# ==================== 🔥 配置 ====================
BOT_TOKEN = os.getenv("BOT_TOKEN")
PORT = int(os.getenv("PORT", 8080))

# Discord配置
GUILD_ID = 1379882513106866226
WELCOME_CHANNEL_ID = 1381960351704420392
LOG_CHANNEL_ID = 1379882514339987520
AUDIT_CHANNEL_ID = 1381997594242449428
ROLE_CHANGE_CHANNEL_ID = 1379882890795548743

# 角色配置
PENDING_ROLE_NAME = "待审核"
VERIFIED_ROLE_NAME = "喜欢您来"
REJECTED_ROLE_NAME = "未通过审核"
MODERATOR_ROLE_NAME = "管理员"

# 机器人配置
BOT_NAME = "烘焙坊门神"
WELCOME_TITLE = "欢迎进入小动物烘焙坊"
WELCOME_DESC = "{user}，喜欢您来！请吃好喝好^^"
BOT_COLOR = 0xffb3cd
BOT_PREFIX = "!"

# 反应角色配置
REACTION_ROLES = {
    '🐕': 'Wer',
    '🐈‍⬛': 'Meow',
    '🍔': '芝士汉堡',
    '🧁': '纸杯蛋糕',
    '👩🏻‍🍳': '好厨子',
    '🍴': '大吃一口'
}

# ==================== 🤖 机器人类 ====================
class MyBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True
        intents.message_content = True
        super().__init__(command_prefix=BOT_PREFIX, intents=intents)
        self.start_time = datetime.now()

    async def setup_hook(self):
        guild = discord.Object(id=GUILD_ID)
        self.tree.copy_global_to(guild=guild)
        await self.tree.sync(guild=guild)
        print(f"✅ 斜杠命令已同步到服务器 {GUILD_ID}")

        # 添加持久化视图
        self.add_view(AuditView(None))
        self.add_view(PersistentTopButtonView())
        print(f"✅ 审核按钮视图已加载")
        print(f"✅ 持久化回首楼按钮视图已加载")

bot = MyBot()

# ==================== 🌐 Flask服务器 ====================
app = Flask(__name__)

@app.route('/')
def home():
    uptime = datetime.now() - bot.start_time
    return f"""
    <html>
        <head><title>🤖 {BOT_NAME}</title></head>
        <body style="background:#2c2f33;color:#fff;font-family:Arial;text-align:center;padding:50px;">
            <h1>🤖 {BOT_NAME}</h1>
            <p>✅ 状态: {'在线' if bot.is_ready() else '启动中'}</p>
            <p>🕐 运行时间: {uptime.days}天 {uptime.seconds//3600}小时</p>
            <p>🏠 服务器数: {len(bot.guilds) if bot.is_ready() else 0}</p>
            <p>🚀 Vultr部署成功！</p>
            <p>🎉 告别断线烦恼！</p>
        </body>
    </html>
    """

@app.route('/health')
def health():
    return jsonify({
        "status": "healthy" if bot.is_ready() else "starting",
        "bot_name": BOT_NAME,
        "uptime": str(datetime.now() - bot.start_time),
        "guilds": len(bot.guilds) if bot.is_ready() else 0,
        "platform": "Vultr"
    })

@app.route('/ping')
def ping():
    return "pong", 200

# ==================== 📝 工具函数 ====================
async def send_log(title: str, description: str, color: int = 0x36393f):
    """发送日志到指定频道"""
    log_channel = bot.get_channel(LOG_CHANNEL_ID)
    if log_channel:
        embed = discord.Embed(title=title, description=description, color=color, timestamp=datetime.now())
        await log_channel.send(embed=embed)

async def send_role_change(title: str, description: str, color: int = 0x36393f):
    """发送角色变化通知到指定频道"""
    role_change_channel = bot.get_channel(ROLE_CHANGE_CHANNEL_ID)
    if role_change_channel:
        embed = discord.Embed(title=title, description=description, color=color, timestamp=datetime.now())
        await role_change_channel.send(embed=embed)

async def send_welcome(member: discord.Member):
    """发送欢迎消息到欢迎频道"""
    welcome_channel = bot.get_channel(WELCOME_CHANNEL_ID)
    if welcome_channel:
        embed = discord.Embed(
            title=WELCOME_TITLE,
            description=WELCOME_DESC.format(user=member.mention),
            color=BOT_COLOR,
            timestamp=datetime.now()
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="👤 新成员", value=f"{member}", inline=True)
        embed.add_field(name="📅 加入时间", value=f"<t:{int(datetime.now().timestamp())}:R>", inline=True)
        await welcome_channel.send(embed=embed)

def is_moderator_or_admin(interaction: discord.Interaction) -> bool:
    """检查用户是否为管理员或审核员"""
    user_roles = [role.name for role in interaction.user.roles]
    return (interaction.user.guild_permissions.administrator or MODERATOR_ROLE_NAME in user_roles)

# ==================== 🎭 审核系统 ====================
class AuditView(discord.ui.View):
    def __init__(self, member: discord.Member = None):
        super().__init__(timeout=None)
        self.member = member

    @discord.ui.button(label="✅ 通过审核", style=discord.ButtonStyle.green, emoji="✅", custom_id="audit_approve")
    async def approve_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not is_moderator_or_admin(interaction):
            await interaction.response.send_message("❌ 你没有审核权限！", ephemeral=True)
            return

        # 获取用户信息
        if self.member is None:
            if interaction.message.embeds:
                embed = interaction.message.embeds[0]
                for field in embed.fields:
                    if "ID" in field.name and field.value:
                        user_id = field.value.strip('`')
                        try:
                            self.member = interaction.guild.get_member(int(user_id))
                            break
                        except (ValueError, AttributeError):
                            continue

        if self.member is None:
            await interaction.response.send_message("❌ 无法找到目标用户！", ephemeral=True)
            return

        if self.member not in interaction.guild.members:
            await interaction.response.send_message("❌ 该用户已离开服务器！", ephemeral=True)
            return

        # 获取相关角色
        pending_role = discord.utils.get(interaction.guild.roles, name=PENDING_ROLE_NAME)
        verified_role = discord.utils.get(interaction.guild.roles, name=VERIFIED_ROLE_NAME)
        rejected_role = discord.utils.get(interaction.guild.roles, name=REJECTED_ROLE_NAME)

        if not pending_role or not verified_role:
            await interaction.response.send_message("❌ 找不到必要的角色！", ephemeral=True)
            return

        try:
            # 移除待审核和被拒绝角色，添加已验证角色
            roles_to_remove = [role for role in [pending_role, rejected_role] if role in self.member.roles]
            if roles_to_remove:
                await self.member.remove_roles(*roles_to_remove)
            await self.member.add_roles(verified_role)

            # 创建通过消息
            embed = discord.Embed(
                title="✅ 审核通过！",
                description=f"🎉 {self.member.mention} 的审核已通过！",
                color=0x00ff00,
                timestamp=datetime.now()
            )
            embed.add_field(name="👤 用户", value=f"{self.member}", inline=True)
            embed.add_field(name="🛡️ 审核员", value=f"{interaction.user}", inline=True)
            embed.add_field(name="✨ 状态", value="已获得完整服务器权限", inline=False)

            # 禁用按钮
            for item in self.children:
                item.disabled = True

            await interaction.response.edit_message(embed=embed, view=self)

            # 发私信通知
            try:
                dm_embed = discord.Embed(
                    title="🎉 审核通过！",
                    description=f"恭喜！你在 **{interaction.guild.name}** 的审核已通过！\n\n现在你可以查看和参与所有频道了。欢迎加入小动物烘焙坊！🎉",
                    color=0x00ff00
                )
                await self.member.send(embed=dm_embed)
            except discord.Forbidden:
                pass

            # 发送欢迎消息
            await send_welcome(self.member)

        except discord.Forbidden:
            await interaction.response.send_message("❌ 权限不足！", ephemeral=True)

    @discord.ui.button(label="❌ 拒绝审核", style=discord.ButtonStyle.red, emoji="❌", custom_id="audit_reject")
    async def reject_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not is_moderator_or_admin(interaction):
            await interaction.response.send_message("❌ 你没有审核权限！", ephemeral=True)
            return

        # 获取用户信息
        if self.member is None:
            if interaction.message.embeds:
                embed = interaction.message.embeds[0]
                for field in embed.fields:
                    if "ID" in field.name and field.value:
                        user_id = field.value.strip('`')
                        try:
                            self.member = interaction.guild.get_member(int(user_id))
                            break
                        except (ValueError, AttributeError):
                            continue

        if self.member is None:
            await interaction.response.send_message("❌ 无法找到目标用户！", ephemeral=True)
            return

        # 创建拒绝选项的下拉菜单
        select_view = RejectActionView(self.member, self)
        await interaction.response.send_message("请选择拒绝后的操作：", view=select_view, ephemeral=True)

class RejectActionView(discord.ui.View):
    def __init__(self, member: discord.Member, original_view: AuditView):
        super().__init__(timeout=60)
        self.member = member
        self.original_view = original_view

    @discord.ui.select(
        placeholder="选择拒绝后的操作...",
        custom_id="reject_action_select",
        options=[
            discord.SelectOption(
                label="保留在服务器",
                description="标记为被拒绝用户，但保留在服务器",
                emoji="🔒",
                value="keep"
            ),
            discord.SelectOption(
                label="踢出服务器", 
                description="将用户踢出服务器",
                emoji="👢",
                value="kick"
            ),
            discord.SelectOption(
                label="封禁用户",
                description="永久封禁该用户",
                emoji="🔨", 
                value="ban"
            )
        ]
    )
    async def select_action(self, interaction: discord.Interaction, select: discord.ui.Select):
        action = select.values[0]

        # 获取相关角色
        pending_role = discord.utils.get(interaction.guild.roles, name=PENDING_ROLE_NAME)
        rejected_role = discord.utils.get(interaction.guild.roles, name=REJECTED_ROLE_NAME)
        verified_role = discord.utils.get(interaction.guild.roles, name=VERIFIED_ROLE_NAME)

        try:
            if action == "keep":
                # 保留但标记为被拒绝
                roles_to_remove = [role for role in [pending_role, verified_role] if role in self.member.roles]
                if roles_to_remove:
                    await self.member.remove_roles(*roles_to_remove)
                if rejected_role:
                    await self.member.add_roles(rejected_role)
                action_text = "已标记为被拒绝用户"
                color = 0xff6600

            elif action == "kick":
                # 踢出服务器
                await self.member.kick(reason="审核被拒绝")
                action_text = "已踢出服务器"
                color = 0xff9900

            elif action == "ban":
                # 封禁用户
                await self.member.ban(reason="审核被拒绝")
                action_text = "已封禁用户"
                color = 0xff0000

            # 创建拒绝消息
            embed = discord.Embed(
                title="❌ 审核被拒绝",
                description=f"💔 {self.member.mention} 的审核未通过",
                color=color,
                timestamp=datetime.now()
            )
            embed.add_field(name="👤 用户", value=f"{self.member}", inline=True)
            embed.add_field(name="🛡️ 审核员", value=f"{interaction.user}", inline=True)
            embed.add_field(name="⚡ 操作", value=action_text, inline=False)

            # 禁用原消息的按钮
            for item in self.original_view.children:
                item.disabled = True

            # 更新原消息
            await interaction.message.edit(embed=embed, view=self.original_view)

            # 给用户发私信通知（如果还在服务器里）
            if action == "keep":
                try:
                    dm_embed = discord.Embed(
                        title="❌ 审核未通过",
                        description=f"很抱歉，你在 **{interaction.guild.name}** 的审核未通过。\n\n如有疑问请联系管理员。",
                        color=0xff0000
                    )
                    await self.member.send(embed=dm_embed)
                except discord.Forbidden:
                    pass

            # 记录日志
            await send_log("❌ 审核拒绝", f"{interaction.user} 拒绝了 {self.member}\n操作：{action_text}", color)

            # 回复当前交互
            await interaction.response.edit_message(content="✅ 操作已完成！", view=None)

        except discord.Forbidden:
            await interaction.response.edit_message(content="❌ 我没有足够权限执行此操作！", view=None)

# ==================== 🚀 回首楼功能 ====================
class PersistentTopButtonView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🚀 回到首楼", style=discord.ButtonStyle.primary, emoji="🚀", custom_id="persistent_top_button")
    async def persistent_top_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            messages = []
            async for message in interaction.channel.history(limit=None, oldest_first=True):
                messages.append(message)
                break

            if not messages:
                await interaction.response.send_message("❌ 频道没有消息！", ephemeral=True)
                return

            first_message = messages[0]
            jump_url = f"https://discord.com/channels/{interaction.guild.id}/{interaction.channel.id}/{first_message.id}"

            cute_messages = [
                f"🐕 汪！[瞬间回首楼！]({jump_url})",
                f"✨ [咻～传送完成！]({jump_url})",
                f"🎉 [成功抵达首楼！]({jump_url})"
            ]

            import random
            await interaction.response.send_message(random.choice(cute_messages), ephemeral=True)

        except Exception as e:
            await interaction.response.send_message("❌ 出错了！", ephemeral=True)

# ==================== 📋 斜杠命令 ====================
@bot.tree.command(name="ping", description="检查机器人状态")
async def ping_command(interaction: discord.Interaction):
    latency = round(bot.latency * 1000)
    uptime = datetime.now() - bot.start_time

    embed = discord.Embed(title="🏓 Pong!", color=BOT_COLOR)
    embed.add_field(name="延迟", value=f"{latency}ms", inline=True)
    embed.add_field(name="运行时间", value=f"{uptime.days}天{uptime.seconds//3600}小时", inline=True)
    embed.add_field(name="平台", value="Vultr ⭐", inline=True)

    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="approve", description="批准待审核用户")
@app_commands.describe(
    member="要批准的用户",
    reason="批准原因（可选）"
)
async def approve_member(interaction: discord.Interaction, member: discord.Member, reason: str = "通过审核"):
    if not is_moderator_or_admin(interaction):
        await interaction.response.send_message("❌ 你没有审核权限！", ephemeral=True)
        return

    # 获取相关角色
    pending_role = discord.utils.get(interaction.guild.roles, name=PENDING_ROLE_NAME)
    verified_role = discord.utils.get(interaction.guild.roles, name=VERIFIED_ROLE_NAME)
    rejected_role = discord.utils.get(interaction.guild.roles, name=REJECTED_ROLE_NAME)

    if not pending_role or not verified_role:
        await interaction.response.send_message("❌ 找不到必要的角色！请检查角色配置。", ephemeral=True)
        return

    try:
        # 移除待审核和被拒绝角色，添加已验证角色
        roles_to_remove = [role for role in [pending_role, rejected_role] if role in member.roles]
        if roles_to_remove:
            await member.remove_roles(*roles_to_remove)
        await member.add_roles(verified_role)

        # 创建批准消息
        embed = discord.Embed(
            title="✅ 用户审核通过",
            color=0x00ff00,
            timestamp=datetime.now()
        )
        embed.add_field(name="👤 用户", value=f"{member}", inline=True)
        embed.add_field(name="🛡️ 审核员", value=f"{interaction.user}", inline=True)
        embed.add_field(name="📝 原因", value=reason, inline=False)

        await interaction.response.send_message(embed=embed)

        # 给用户发私信通知
        try:
            dm_embed = discord.Embed(
                title="🎉 审核通过！",
                description=f"恭喜！你在 **{interaction.guild.name}** 的审核已通过！\n\n现在你可以查看和参与所有频道了。",
                color=0x00ff00
            )
            await member.send(embed=dm_embed)
        except discord.Forbidden:
            pass

        # 发送欢迎消息到欢迎频道
        await send_welcome(member)

    except discord.Forbidden:
        await interaction.response.send_message("❌ 我没有权限修改用户角色！", ephemeral=True)

@bot.tree.command(name="reject", description="拒绝待审核用户")
@app_commands.describe(
    member="要拒绝的用户",
    reason="拒绝原因",
    action="拒绝后的操作"
)
@app_commands.choices(action=[
    app_commands.Choice(name="保留在服务器（受限权限）", value="keep"),
    app_commands.Choice(name="踢出服务器", value="kick"),
    app_commands.Choice(name="封禁用户", value="ban")
])
async def reject_member(interaction: discord.Interaction, member: discord.Member, reason: str, action: str = "keep"):
    if not is_moderator_or_admin(interaction):
        await interaction.response.send_message("❌ 你没有审核权限！", ephemeral=True)
        return

    # 获取相关角色
    pending_role = discord.utils.get(interaction.guild.roles, name=PENDING_ROLE_NAME)
    rejected_role = discord.utils.get(interaction.guild.roles, name=REJECTED_ROLE_NAME)
    verified_role = discord.utils.get(interaction.guild.roles, name=VERIFIED_ROLE_NAME)

    try:
        if action == "keep":
            # 保留但标记为被拒绝
            roles_to_remove = [role for role in [pending_role, verified_role] if role in member.roles]
            if roles_to_remove:
                await member.remove_roles(*roles_to_remove)
            if rejected_role:
                await member.add_roles(rejected_role)
            action_text = "已标记为被拒绝用户"

        elif action == "kick":
            # 踢出服务器
            await member.kick(reason=f"审核被拒绝：{reason}")
            action_text = "已踢出服务器"

        elif action == "ban":
            # 封禁用户
            await member.ban(reason=f"审核被拒绝：{reason}")
            action_text = "已封禁用户"

        # 创建拒绝消息
        embed = discord.Embed(
            title="❌ 用户审核被拒绝",
            color=0xff0000,
            timestamp=datetime.now()
        )
        embed.add_field(name="👤 用户", value=f"{member}", inline=True)
        embed.add_field(name="🛡️ 审核员", value=f"{interaction.user}", inline=True)
        embed.add_field(name="📝 原因", value=reason, inline=False)
        embed.add_field(name="⚡ 操作", value=action_text, inline=False)

        await interaction.response.send_message(embed=embed)

        # 给用户发私信通知（如果还在服务器里）
        if action == "keep":
            try:
                dm_embed = discord.Embed(
                    title="❌ 审核未通过",
                    description=f"很抱歉，你在 **{interaction.guild.name}** 的审核未通过。\n\n**原因：** {reason}\n\n如有疑问请联系管理员。",
                    color=0xff0000
                )
                await member.send(embed=dm_embed)
            except discord.Forbidden:
                pass

        # 记录日志
        await send_log("❌ 用户审核被拒绝", f"{interaction.user} 拒绝了 {member}\n原因：{reason}\n操作：{action_text}", 0xff0000)

    except discord.Forbidden:
        await interaction.response.send_message("❌ 我没有足够权限执行此操作！", ephemeral=True)

@bot.tree.command(name="pending", description="查看待审核用户列表")
async def view_pending(interaction: discord.Interaction):
    if not is_moderator_or_admin(interaction):
        await interaction.response.send_message("❌ 你没有审核权限！", ephemeral=True)
        return

    # 获取待审核角色
    pending_role = discord.utils.get(interaction.guild.roles, name=PENDING_ROLE_NAME)

    if not pending_role:
        await interaction.response.send_message("❌ 找不到待审核角色！", ephemeral=True)
        return

    # 获取待审核用户
    pending_members = [member for member in interaction.guild.members if pending_role in member.roles]

    if not pending_members:
        embed = discord.Embed(
            title="📋 待审核用户列表",
            description="当前没有待审核的用户。",
            color=BOT_COLOR
        )
    else:
        embed = discord.Embed(
            title="📋 待审核用户列表",
            description=f"共有 {len(pending_members)} 位用户等待审核：",
            color=0xffa500,
            timestamp=datetime.now()
        )

        for i, member in enumerate(pending_members[:10], 1):  # 限制显示10个
            join_time = f"<t:{int(member.joined_at.timestamp())}:R>"
            embed.add_field(
                name=f"{i}. {member.display_name}",
                value=f"**用户：** {member.mention}\n**加入：** {join_time}\n**ID：** `{member.id}`",
                inline=True
            )

        if len(pending_members) > 10:
            embed.set_footer(text=f"显示前10位，总共{len(pending_members)}位用户")

    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="setup_roles", description="设置反应角色消息")
async def setup_roles_slash(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.manage_roles:
        await interaction.response.send_message("❌ 你没有管理角色的权限！", ephemeral=True)
        return

    embed = discord.Embed(
        title="🎭 选择你的身份组",
        description="点击下面的表情来获取对应的身份组！",
        color=BOT_COLOR
    )

    role_text = ""
    for emoji, role_name in REACTION_ROLES.items():
        role_text += f"{emoji} {role_name}\n"

    embed.add_field(name="可选角色", value=role_text, inline=False)
    embed.set_footer(text="点击表情获取角色，再次点击移除角色")

    await interaction.response.send_message(embed=embed)
    message = await interaction.original_response()

    for emoji in REACTION_ROLES.keys():
        await message.add_reaction(emoji)

@bot.tree.command(name="topbutton", description="发送一个永久的回首楼按钮")
async def topbutton_slash(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.manage_messages:
        await interaction.response.send_message("❌ 你没有管理消息的权限！", ephemeral=True)
        return

    embed = discord.Embed(
        title="🚀 快速回首楼工具",
        description="点击下面的按钮可以快速回到频道第一条消息！",
        color=BOT_COLOR
    )
    embed.add_field(name="使用方法", value="点击按钮即可瞬间跳转到频道的第一条消息（首楼）", inline=False)
    embed.set_footer(text="此按钮永久有效")

    view = PersistentTopButtonView()

    await interaction.response.send_message(embed=embed, view=view)
    await interaction.followup.send("✅ 回首楼按钮已设置完成！", ephemeral=True)

    # 记录日志
    await send_log("🚀 设置回首楼按钮", f"{interaction.user} 在 {interaction.channel} 设置了回首楼按钮", BOT_COLOR)

@bot.tree.command(name="help", description="查看所有可用命令")
async def help_slash(interaction: discord.Interaction):
    embed = discord.Embed(title=f"🤖 {BOT_NAME} 命令帮助", color=BOT_COLOR)

    # 审核系统命令（管理员/审核员专用）
    if is_moderator_or_admin(interaction):
        embed.add_field(
            name="🔍 审核系统",
            value="`/approve` - 批准用户\n`/reject` - 拒绝用户\n`/pending` - 待审核列表",
            inline=False
        )

    embed.add_field(
        name="🎭 角色管理",
        value="`/setup_roles` - 设置反应角色",
        inline=False
    )

    embed.add_field(
        name="🚀 实用工具",
        value="`/topbutton` - 设置回首楼按钮\n`/ping` - 检查机器人状态",
        inline=False
    )

    embed.add_field(name="部署平台", value="Vultr - 24小时稳定运行 ✨", inline=False)
    embed.set_footer(text="现在运行在Vultr上，告别断线烦恼！")

    await interaction.response.send_message(embed=embed)

# ==================== 🎭 事件处理 ====================
@bot.event
async def on_ready():
    print(f'🎯 {bot.user} 已在Vultr上线！')
    print(f'📊 服务器数量: {len(bot.guilds)}')
    await bot.change_presence(activity=discord.Game(name="🚀 Vultr稳定运行"))

@bot.event
async def on_member_join(member):
    """新成员加入处理"""
    pending_role = discord.utils.get(member.guild.roles, name=PENDING_ROLE_NAME)
    if pending_role:
        try:
            await member.add_roles(pending_role)

            audit_channel = bot.get_channel(AUDIT_CHANNEL_ID)
            if audit_channel:
                embed = discord.Embed(
                    title="🆕 新成员需要审核",
                    description=f"欢迎 {member.mention}！\n\n请发送已在群内截图（注意打码重要信息）以及QQ号后四位等待管理员审核><",
                    color=0xffa500,
                    timestamp=datetime.now()
                )
                embed.add_field(name="用户", value=f"{member}", inline=True)
                embed.add_field(name="ID", value=f"`{member.id}`", inline=True)
                embed.add_field(name="加入时间", value=f"<t:{int(datetime.now().timestamp())}:R>", inline=True)

                await audit_channel.send(embed=embed, view=AuditView(member))

            await send_log("🆕 新成员加入", f"{member} 已自动分配到待审核状态", 0xffa500)

        except discord.Forbidden:
            await send_log("❌ 权限错误", f"无法给 {member} 分配角色", 0xff0000)

# 反应角色事件
@bot.event
async def on_raw_reaction_add(payload):
    if payload.user_id == bot.user.id:
        return

    guild = bot.get_guild(payload.guild_id)
    user = guild.get_member(payload.user_id)
    emoji = str(payload.emoji)

    if emoji in REACTION_ROLES:
        role_name = REACTION_ROLES[emoji]
        role = discord.utils.get(guild.roles, name=role_name)

        if role and role not in user.roles:
            try:
                await user.add_roles(role)
                await send_role_change("🎭 添加角色", f"{user} 获得了角色 {role.name}", 0x00ff00)
            except discord.Forbidden:
                pass

@bot.event
async def on_raw_reaction_remove(payload):
    if payload.user_id == bot.user.id:
        return

    guild = bot.get_guild(payload.guild_id)
    user = guild.get_member(payload.user_id)
    emoji = str(payload.emoji)

    if emoji in REACTION_ROLES:
        role_name = REACTION_ROLES[emoji]
        role = discord.utils.get(guild.roles, name=role_name)

        if role and role in user.roles:
            try:
                await user.remove_roles(role)
                await send_role_change("🎭 移除角色", f"{user} 失去了角色 {role.name}", 0xff9900)
            except discord.Forbidden:
                pass

# ==================== 🚀 启动函数 ====================
def run_flask():
    """运行Flask服务器"""
    app.run(host='0.0.0.0', port=PORT, debug=False)

async def main():
    """主运行函数"""
    # 启动Flask
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    print(f"🌐 Flask服务器启动在端口 {PORT}")

    # 启动机器人
    try:
        await bot.start(BOT_TOKEN)
    except Exception as e:
        print(f"❌ 机器人启动失败: {e}")

if __name__ == "__main__":
    if not BOT_TOKEN:
        print("❌ 请设置BOT_TOKEN环境变量！")
        exit(1)

    print(f"🚀 在Vultr上启动 {BOT_NAME}...")
    asyncio.run(main())
