import discord
from discord.ext import commands
from discord import app_commands
import asyncio
from datetime import datetime, timedelta
import io

# ==================== 🔥 必须修改的配置 🔥 ====================
import os
BOT_TOKEN = os.getenv("BOT_TOKEN")
GUILD_ID = 1379882513106866226
WELCOME_CHANNEL_ID = 1381960351704420392
LOG_CHANNEL_ID = 1379882514339987520
AUDIT_CHANNEL_ID = 1384936557986713620
ROLE_CHANGE_CHANNEL_ID =1379882890795548743

# ==================== 🎨 审核系统配置 🎨 ====================
PENDING_ROLE_NAME = "待审核"         # 🔧 待审核角色名
VERIFIED_ROLE_NAME = "喜欢您来"        # 🔧 已验证角色名  
REJECTED_ROLE_NAME = "未通过审核"        # 🔧 被拒绝角色名
MODERATOR_ROLE_NAME = "管理员"           # 🔧 审核员角色名

# ==================== 🎨 可自定义配置 🎨 ====================
BOT_NAME = "烘焙坊门神"
WELCOME_TITLE = "欢迎进入小动物烘焙坊"
WELCOME_DESC = "{user}，喜欢您来！请吃好喝好^^"
BOT_COLOR = 0xffb3cd                     #浅粉色
BOT_PREFIX = "!"                         # 🔧 传统命令前缀

# ==================== 机器人设置 ====================
class MyBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True  # 需要启用成员权限来监听加入事件
        intents.message_content = True  # 启用消息内容权限
        super().__init__(command_prefix=BOT_PREFIX, intents=intents)
        self.start_time = datetime.now()  # 添加启动时间记录

    async def setup_hook(self):
        # 同步斜杠命令到指定服务器
        guild = discord.Object(id=GUILD_ID)
        self.tree.copy_global_to(guild=guild)
        await self.tree.sync(guild=guild)
        print(f"✅ 斜杠命令已同步到服务器 {GUILD_ID}")

        # 添加持久化视图（使按钮在bot重启后仍然工作）
        self.add_view(AuditView(None))  # 传入None作为占位符
        self.add_view(PersistentTopButtonView())  # 持久化回顶按钮视图
        self.add_view(UserAuditView())  # 用户审核提交视图

        print(f"✅ 审核按钮视图已加载")
        print(f"✅ 持久化回首楼按钮视图已加载")
        print(f"✅ 用户审核提交视图已加载")

bot = MyBot()

# ==================== 📝 日志功能 ====================
async def send_log(title: str, description: str, color: int = 0x36393f):
    """发送日志到指定频道"""
    log_channel = bot.get_channel(LOG_CHANNEL_ID)
    if log_channel:
        embed = discord.Embed(
            title=title,
            description=description,
            color=color,
            timestamp=datetime.now()
        )
        await log_channel.send(embed=embed)

# ==================== 🎭 角色变化通知功能 ====================
async def send_role_change(title: str, description: str, color: int = 0x36393f):
    """发送角色变化通知到指定频道"""
    role_change_channel = bot.get_channel(ROLE_CHANGE_CHANNEL_ID)
    if role_change_channel:
        embed = discord.Embed(
            title=title,
            description=description,
            color=color,
            timestamp=datetime.now()
        )
        await role_change_channel.send(embed=embed)

# ==================== 🎉 欢迎消息功能 ====================
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

# ==================== 🔍 审核消息功能 ====================
async def send_audit_message(title: str, description: str, color: int = 0x36393f):
    """发送审核相关消息到审核频道"""
    audit_channel = bot.get_channel(AUDIT_CHANNEL_ID)
    if audit_channel:
        embed = discord.Embed(
            title=title,
            description=description,
            color=color,
            timestamp=datetime.now()
        )
        await audit_channel.send(embed=embed)

# ==================== 📝 用户信息输入模态框 ====================
class UserInfoModal(discord.ui.Modal, title='📝 提交个人信息'):
    def __init__(self, user_view):
        super().__init__()
        self.user_view = user_view

    discord_info = discord.ui.TextInput(
        label='Discord昵称或账号',
        placeholder='请输入你的Discord昵称或完整账号',
        required=True,
        max_length=200
    )

    additional_info = discord.ui.TextInput(
        label='补充信息（可选）',
        placeholder='如有需要，可以补充其他信息...',
        required=False,
        max_length=500,
        style=discord.TextStyle.paragraph
    )

    async def on_submit(self, interaction: discord.Interaction):
        # 保存用户输入的信息
        self.user_view.discord_info = self.discord_info.value
        self.user_view.additional_info = self.additional_info.value
        
        embed = discord.Embed(
            title="✅ 文字信息已提交",
            description="你的Discord信息已记录，现在请上传支付宝截图。",
            color=0x00ff00
        )
        embed.add_field(name="Discord信息", value=self.discord_info.value, inline=False)
        if self.additional_info.value:
            embed.add_field(name="补充信息", value=self.additional_info.value, inline=False)

        await interaction.response.edit_message(embed=embed, view=self.user_view)

# ==================== 🎭 用户审核提交界面 ====================
class UserAuditView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.discord_info = None
        self.additional_info = None
        self.submitted_image = None

    @discord.ui.button(label="填写文字信息", style=discord.ButtonStyle.primary, emoji="📝", custom_id="user_text_info")
    async def submit_text_info(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = UserInfoModal(self)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="上传支付宝截图", style=discord.ButtonStyle.secondary, emoji="📸", custom_id="user_upload_image")
    async def upload_image_instruction(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="📸 上传支付宝截图",
            description="请按以下步骤操作：",
            color=BOT_COLOR
        )
        embed.add_field(
            name="📱 截图步骤",
            value="1. 打开支付宝APP\n2. 进入【我的】→【头像】→【我的主页】→【编辑个人资料】\n3. 截图该页面\n4. **重要：请将除性别外的其他信息打码处理**",
            inline=False
        )
        embed.add_field(
            name="📎 上传方式",
            value="请直接在此私信频道发送截图文件，本门神会自动识别并提交给管理员审核哼哼^^（先上传截图再填写文字信息！！不然会出bug！！）",
            inline=False
        )
        embed.set_footer(text="💡 提示：确保截图清晰且隐私信息已打码")

        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="提交审核", style=discord.ButtonStyle.success, emoji="✅", custom_id="user_submit_audit")
    async def submit_audit(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.discord_info:
            await interaction.response.send_message("❌ 请先填写文字信息！", ephemeral=True)
            return

        if not self.submitted_image:
            await interaction.response.send_message("❌ 请先上传截图！", ephemeral=True)
            return

        # 准备发送到审核频道
        audit_channel = bot.get_channel(AUDIT_CHANNEL_ID)
        if not audit_channel:
            await interaction.response.send_message("❌ 审核频道配置错误，请联系管理员！", ephemeral=True)
            return

        try:
            # 创建审核embed
            embed = discord.Embed(
                title="🆕 新用户审核申请",
                description=f"用户 {interaction.user.mention} 提交了审核资料",
                color=0xffa500,
                timestamp=datetime.now()
            )
            embed.set_thumbnail(url=interaction.user.display_avatar.url)
            embed.add_field(name="👤 用户", value=f"{interaction.user}", inline=True)
            embed.add_field(name="🆔 ID", value=f"`{interaction.user.id}`", inline=True)
            embed.add_field(name="📅 加入时间", value=f"<t:{int(datetime.now().timestamp())}:R>", inline=True)
            embed.add_field(name="📝 Discord信息", value=self.discord_info, inline=False)
            if self.additional_info:
                embed.add_field(name="📋 补充信息", value=self.additional_info, inline=False)
            embed.set_footer(text="等待管理员审核...")

            # 发送到审核频道（包含图片和按钮）
            guild = bot.get_guild(GUILD_ID)
            member = guild.get_member(interaction.user.id) if guild else None
            
            files = []
            if self.submitted_image:
                files.append(self.submitted_image)

            await audit_channel.send(
                embed=embed, 
                files=files, 
                view=AuditView(member)
            )

            # 回复用户
            success_embed = discord.Embed(
                title="✅ 审核资料已提交",
                description="你的资料已成功提交给管理员审核，请等待审核结果^^感谢！",
                color=0x00ff00
            )
            success_embed.add_field(name="📝 已提交信息", value=f"Discord信息：{self.discord_info}", inline=False)
            if self.additional_info:
                success_embed.add_field(name="📋 补充信息", value=self.additional_info, inline=False)
            success_embed.add_field(name="📸 截图", value="✅ 已上传", inline=False)
            success_embed.set_footer(text="如需修改资料，可重新点击提交按钮")

            # 禁用当前按钮
            for item in self.children:
                if item.custom_id == "user_submit_audit":
                    item.disabled = True

            await interaction.response.edit_message(embed=success_embed, view=self)

            # 记录日志
            await send_log("📋 用户提交审核", f"{interaction.user} 提交了审核资料", 0xffa500)

        except Exception as e:
            await interaction.response.send_message(f"❌ 提交失败：{e}", ephemeral=True)
            print(f"审核提交错误: {e}")

    @discord.ui.button(label="重新提交", style=discord.ButtonStyle.secondary, emoji="🔄", custom_id="user_resubmit")
    async def resubmit(self, interaction: discord.Interaction, button: discord.ui.Button):
        # 重置所有信息
        self.discord_info = None
        self.additional_info = None
        self.submitted_image = None

        # 启用提交按钮
        for item in self.children:
            item.disabled = False

        embed = discord.Embed(
            title="🔄 重新提交审核",
            description="你可以重新填写信息和上传截图。",
            color=BOT_COLOR
        )
        embed.add_field(
            name="📋 需要提交的资料",
            value="1. 📝 Discord昵称或账号\n2. 📸 支付宝个人信息截图（仅显示性别，其他请注意打码）",
            inline=False
        )
        embed.add_field(
            name="📸 截图要求",
            value="支付宝APP → 我的 → 头像 → 我的主页 → 编辑个人资料",
            inline=False
        )

        await interaction.response.edit_message(embed=embed, view=self)

# ==================== 🎭 管理员审核按钮交互组件 ====================
class AuditView(discord.ui.View):
    def __init__(self, member: discord.Member = None):
        super().__init__(timeout=None)  # 永不超时
        self.member = member

    @discord.ui.button(label="通过审核", style=discord.ButtonStyle.green, emoji="✅", custom_id="audit_approve")
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

        # 立即响应，避免交互超时
        await interaction.response.defer()

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

            # 更新消息
            await interaction.edit_original_response(embed=embed, view=self)

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
            
            # 记录日志
            await send_log("✅ 审核通过", f"{interaction.user} 通过了 {self.member} 的审核", 0x00ff00)

        except discord.Forbidden as e:
            await interaction.edit_original_response(content=f"❌ 权限不足: {e}")
        except Exception as e:
            await interaction.edit_original_response(content=f"❌ 操作失败: {e}")
            print(f"审核通过错误: {e}")
            import traceback
            traceback.print_exc()

    @discord.ui.button(label="拒绝审核", style=discord.ButtonStyle.red, emoji="❌", custom_id="audit_reject")
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

        if self.member not in interaction.guild.members:
            await interaction.response.send_message("❌ 该用户已离开服务器！", ephemeral=True)
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
        
        # 立即响应交互，避免超时
        await interaction.response.defer()
        
        try:
            # 获取相关角色
            pending_role = discord.utils.get(interaction.guild.roles, name=PENDING_ROLE_NAME)
            rejected_role = discord.utils.get(interaction.guild.roles, name=REJECTED_ROLE_NAME)
            verified_role = discord.utils.get(interaction.guild.roles, name=VERIFIED_ROLE_NAME)

            if action == "keep":
                # 保留但标记为被拒绝
                roles_to_remove = [role for role in [pending_role, verified_role] if role in self.member.roles]
                if roles_to_remove:
                    await self.member.remove_roles(*roles_to_remove)
                if rejected_role:
                    await self.member.add_roles(rejected_role)
                action_text = "已标记为被拒绝用户"
                color = 0xff6600

                # 发私信通知可以重新提交
                try:
                    dm_embed = discord.Embed(
                        title="❌ 审核未通过",
                        description=f"很抱歉，你在 **{interaction.guild.name}** 的审核未通过。\n\n你可以重新提交审核资料，请确保：\n1. Discord信息准确\n2. 支付宝截图性别信息清晰",
                        color=0xff0000
                    )
                    dm_embed.add_field(
                        name="🔄 重新提交",
                        value="请点击下方的'重新提交'按钮来重新填写资料。",
                        inline=False
                    )
                    
                    # 发送带重新提交按钮的消息
                    await self.member.send(embed=dm_embed, view=UserAuditView())
                except discord.Forbidden:
                    pass

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

            # 创建成功消息
            success_message = f"✅ 操作完成！{self.member} {action_text}"
            
            # 编辑原始交互消息
            await interaction.edit_original_response(content=success_message, view=None)

            # 创建拒绝消息embed
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

            # 尝试更新原始审核消息
            try:
                if hasattr(interaction, 'message') and interaction.message:
                    # 如果可以访问原始消息，更新它
                    original_msg = interaction.message
                    await original_msg.edit(embed=embed, view=self.original_view)
                else:
                    # 否则发送到审核频道
                    audit_channel = bot.get_channel(AUDIT_CHANNEL_ID)
                    if audit_channel:
                        await audit_channel.send(embed=embed)
            except Exception as e:
                print(f"警告: 无法更新原始消息: {e}")
                # 发送到审核频道作为备选
                audit_channel = bot.get_channel(AUDIT_CHANNEL_ID)
                if audit_channel:
                    await audit_channel.send(embed=embed)

            # 记录日志
            await send_log("❌ 审核拒绝", f"{interaction.user} 拒绝了 {self.member}\n操作：{action_text}", color)

        except discord.Forbidden as e:
            error_message = f"❌ 权限不足！无法执行此操作: {e}"
            await interaction.edit_original_response(content=error_message, view=None)
        except Exception as e:
            error_message = f"❌ 操作失败: {e}"
            await interaction.edit_original_response(content=error_message, view=None)
            print(f"拒绝操作错误: {e}")
            import traceback
            traceback.print_exc()

# ==================== 🤖 基础事件 ====================
@bot.event
async def on_ready():
    print(f'🎯 {bot.user} 已在Vultr上线！')
    print(f'📊 在 {len(bot.guilds)} 个服务器运行')
    
    # 检查重要配置
    guild = bot.get_guild(GUILD_ID)
    if guild:
        print(f'✅ 连接到服务器: {guild.name}')
        
        # 检查角色
        pending_role = discord.utils.get(guild.roles, name=PENDING_ROLE_NAME)
        verified_role = discord.utils.get(guild.roles, name=VERIFIED_ROLE_NAME)
        rejected_role = discord.utils.get(guild.roles, name=REJECTED_ROLE_NAME)
        
        print(f'🔍 角色检查:')
        print(f'  - 待审核: {"✅" if pending_role else "❌"} {pending_role}')
        print(f'  - 喜欢您来: {"✅" if verified_role else "❌"} {verified_role}')
        print(f'  - 未通过审核: {"✅" if rejected_role else "❌"} {rejected_role}')
        
        # 检查频道
        audit_channel = bot.get_channel(AUDIT_CHANNEL_ID)
        welcome_channel = bot.get_channel(WELCOME_CHANNEL_ID)
        log_channel = bot.get_channel(LOG_CHANNEL_ID)
        
        print(f'🔍 频道检查:')
        print(f'  - 审核频道: {"✅" if audit_channel else "❌"} {audit_channel}')
        print(f'  - 欢迎频道: {"✅" if welcome_channel else "❌"} {welcome_channel}')
        print(f'  - 日志频道: {"✅" if log_channel else "❌"} {log_channel}')
        
        # 检查bot权限
        bot_member = guild.get_member(bot.user.id)
        if bot_member:
            perms = bot_member.guild_permissions
            print(f'🔍 权限检查:')
            print(f'  - 管理角色: {"✅" if perms.manage_roles else "❌"}')
            print(f'  - 发送消息: {"✅" if perms.send_messages else "❌"}')
            print(f'  - 嵌入链接: {"✅" if perms.embed_links else "❌"}')
            
            # 检查角色位置
            bot_top_role = bot_member.top_role
            print(f'🔍 Bot最高角色: {bot_top_role.name} (位置: {bot_top_role.position})')
            if pending_role:
                if bot_top_role.position > pending_role.position:
                    print(f'✅ Bot角色位置正确，高于待审核角色')
                else:
                    print(f'❌ 警告: Bot角色位置过低！需要将Bot角色移动到待审核角色之上')
    else:
        print(f'❌ 找不到指定的服务器 (ID: {GUILD_ID})')
    
    await bot.change_presence(activity=discord.Game(name="🚀 Vultr稳定运行"))
    print(f'✅ Bot初始化完成！使用 /debug 命令检查详细配置')

# 新成员自动进入审核流程（修改为私信方式）
@bot.event
async def on_member_join(member):
    """新成员加入自动审核流程"""
    print(f"🔍 [DEBUG] 新成员加入: {member} (ID: {member.id})")
    
    # 获取待审核角色
    pending_role = discord.utils.get(member.guild.roles, name=PENDING_ROLE_NAME)
    
    print(f"🔍 [DEBUG] 找到待审核角色: {pending_role}")

    if pending_role:
        try:
            # 给新成员添加待审核角色
            print(f"🔍 [DEBUG] 尝试给 {member} 添加角色 {pending_role}")
            await member.add_roles(pending_role)
            print(f"✅ [DEBUG] 成功给 {member} 添加待审核角色")

            # 发送私信审核消息
            try:
                embed = discord.Embed(
                    title="🎉 欢迎加入小动物烘焙坊！",
                    description=f"你好 {member.mention}！欢迎加入我们的服务器！\n\n为了确保社区安全，请提交一些资料（支付宝性别截图，仅查看性别）进行审核^^感谢理解！",
                    color=BOT_COLOR,
                    timestamp=datetime.now()
                )
                
                embed.add_field(
                    name="📋 需要提交的资料",
                    value="1. 📝 Discord昵称或账号\n2. 📸 支付宝个人信息截图（仅显示性别，其他打码）",
                    inline=False
                )
                
                embed.add_field(
                    name="📸 截图要求",
                    value="请提交支付宝个人信息截图（我的→头像→我的主页→编辑个人资料），仅查看性别，其他信息请自行打码",
                    inline=False
                )
                
                embed.add_field(
                    name="🚀 开始审核",
                    value="点击下方按钮开始提交审核资料！",
                    inline=False
                )
                
                embed.set_footer(text="审核通过后即可访问所有频道！")

                # 发送私信并附带审核按钮
                await member.send(embed=embed, view=UserAuditView())
                print(f"✅ [DEBUG] 成功向 {member} 发送私信审核消息")

            except discord.Forbidden:
                print(f"❌ [DEBUG] 无法向 {member} 发送私信，可能用户关闭了私信")
                # 如果无法发私信，在审核频道提醒管理员
                audit_channel = bot.get_channel(AUDIT_CHANNEL_ID)
                if audit_channel:
                    embed = discord.Embed(
                        title="⚠️ 无法发送私信",
                        description=f"{member.mention} 加入了服务器，但无法发送私信进行审核（用户可能关闭了私信功能）",
                        color=0xffaa00,
                        timestamp=datetime.now()
                    )
                    embed.add_field(name="建议", value="请管理员手动联系用户或使用其他方式进行审核", inline=False)
                    await audit_channel.send(embed=embed)

            # 记录日志
            await send_log("🆕 新成员加入", f"{member} 已自动分配到待审核状态，私信审核流程已启动", 0xffa500)
            print(f"✅ [DEBUG] 成功记录日志")

        except discord.Forbidden as e:
            print(f"❌ [DEBUG] 权限错误: {e}")
            await send_log("❌ 权限错误", f"无法给 {member} 分配待审核角色 - 错误: {e}", 0xff0000)
        except Exception as e:
            print(f"❌ [DEBUG] 其他错误: {e}")
            await send_log("❌ 未知错误", f"处理新成员 {member} 时出错: {e}", 0xff0000)
    else:
        print(f"❌ [DEBUG] 找不到'{PENDING_ROLE_NAME}'角色")
        await send_log("❌ 角色错误", f"找不到'{PENDING_ROLE_NAME}'角色", 0xff0000)

# 监听私信中的图片上传
@bot.event
async def on_message(message):
    # 忽略机器人自己的消息
    if message.author == bot.user:
        return
    
    # 只处理私信
    if isinstance(message.channel, discord.DMChannel):
        # 检查用户是否在待审核状态
        guild = bot.get_guild(GUILD_ID)
        if guild:
            member = guild.get_member(message.author.id)
            if member:
                pending_role = discord.utils.get(guild.roles, name=PENDING_ROLE_NAME)
                if pending_role and pending_role in member.roles:
                    # 检查消息是否包含图片
                    if message.attachments:
                        for attachment in message.attachments:
                            if attachment.content_type and attachment.content_type.startswith('image/'):
                                # 找到用户的审核视图（这里简化处理，实际可能需要更复杂的状态管理）
                                # 下载图片并准备转发
                                try:
                                    image_data = await attachment.read()
                                    image_file = discord.File(io.BytesIO(image_data), filename=attachment.filename)
                                    
                                    # 创建确认消息
                                    embed = discord.Embed(
                                        title="📸 图片已接收",
                                        description="你的图片文件已接收！现在请确保：\n\n1. 📝 已填写Discord信息\n2. 📸 已上传支付宝截图\n\n然后点击'提交审核'按钮完成提交。",
                                        color=0x00ff00
                                    )
                                    
                                    # 创建新的视图实例并设置图片
                                    user_view = UserAuditView()
                                    user_view.submitted_image = image_file
                                    
                                    await message.channel.send(embed=embed, view=user_view)
                                    
                                except Exception as e:
                                    await message.channel.send(f"❌ 处理图片时出错：{e}")
                                break
    
    # 处理其他命令
    await bot.process_commands(message)

# ==================== 🎭 审核按钮交互组件 ====================
def is_moderator_or_admin(interaction: discord.Interaction) -> bool:
    """检查用户是否为管理员或审核员"""
    user_roles = [role.name for role in interaction.user.roles]
    return (
        interaction.user.guild_permissions.administrator or
        MODERATOR_ROLE_NAME in user_roles
    )

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
            pass  # 用户关闭了私信

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

@bot.tree.command(name="reaudit", description="重新审核被拒绝的用户")
@app_commands.describe(member="要重新审核的用户")
async def reaudit_member(interaction: discord.Interaction, member: discord.Member):
    if not is_moderator_or_admin(interaction):
        await interaction.response.send_message("❌ 你没有审核权限！", ephemeral=True)
        return

    # 获取相关角色
    rejected_role = discord.utils.get(interaction.guild.roles, name=REJECTED_ROLE_NAME)
    pending_role = discord.utils.get(interaction.guild.roles, name=PENDING_ROLE_NAME)

    if not rejected_role or not pending_role:
        await interaction.response.send_message("❌ 找不到必要的角色！", ephemeral=True)
        return

    if rejected_role not in member.roles:
        await interaction.response.send_message("❌ 该用户不在被拒绝列表中！", ephemeral=True)
        return

    try:
        # 移除被拒绝角色，添加待审核角色
        await member.remove_roles(rejected_role)
        await member.add_roles(pending_role)

        embed = discord.Embed(
            title="🔄 重新审核",
            description=f"{member.mention} 已重新进入审核流程",
            color=0xffa500,
            timestamp=datetime.now()
        )
        embed.add_field(name="🛡️ 操作员", value=f"{interaction.user}", inline=True)

        await interaction.response.send_message(embed=embed)

        # 通知用户可以重新提交
        try:
            dm_embed = discord.Embed(
                title="🔄 重新审核机会",
                description=f"管理员已为你重新开启审核流程，你可以重新提交审核资料。",
                color=0xffa500
            )
            await member.send(embed=dm_embed, view=UserAuditView())
        except discord.Forbidden:
            pass

        # 记录日志
        await send_log("🔄 重新审核", f"{interaction.user} 将 {member} 重新加入审核流程", 0xffa500)

    except discord.Forbidden:
        await interaction.response.send_message("❌ 我没有权限修改用户角色！", ephemeral=True)

@bot.tree.command(name="kick", description="踢出一个成员")
@app_commands.describe(
    member="要踢出的成员",
    reason="踢出原因"
)
async def kick_slash(interaction: discord.Interaction, member: discord.Member, reason: str = "未提供原因"):
    if not interaction.user.guild_permissions.kick_members:
        await interaction.response.send_message("❌ 你没有踢出成员的权限！", ephemeral=True)
        return

    try:
        await member.kick(reason=reason)
        embed = discord.Embed(title="👢 成员已踢出", color=0xff9900, timestamp=datetime.now())
        embed.add_field(name="用户", value=f"{member}", inline=True)
        embed.add_field(name="执行者", value=f"{interaction.user}", inline=True)
        embed.add_field(name="原因", value=reason, inline=False)

        await interaction.response.send_message(embed=embed)
        await send_log("👢 踢出成员", f"{interaction.user} 踢出了 {member}\n原因：{reason}", 0xff9900)
    except discord.Forbidden:
        await interaction.response.send_message("❌ 我没有权限踢出这个用户！", ephemeral=True)

@bot.tree.command(name="ban", description="封禁一个成员")
@app_commands.describe(
    member="要封禁的成员",
    reason="封禁原因"
)
async def ban_slash(interaction: discord.Interaction, member: discord.Member, reason: str = "未提供原因"):
    if not interaction.user.guild_permissions.ban_members:
        await interaction.response.send_message("❌ 你没有封禁成员的权限！", ephemeral=True)
        return

    try:
        await member.ban(reason=reason)
        embed = discord.Embed(title="🔨 成员已封禁", color=0xff0000, timestamp=datetime.now())
        embed.add_field(name="用户", value=f"{member}", inline=True)
        embed.add_field(name="执行者", value=f"{interaction.user}", inline=True)
        embed.add_field(name="原因", value=reason, inline=False)

        await interaction.response.send_message(embed=embed)
        await send_log("🔨 封禁成员", f"{interaction.user} 封禁了 {member}\n原因：{reason}", 0xff0000)
    except discord.Forbidden:
        await interaction.response.send_message("❌ 我没有权限封禁这个用户！", ephemeral=True)

@bot.tree.command(name="timeout", description="禁言一个成员")
@app_commands.describe(
    member="要禁言的成员",
    duration="禁言时长（分钟）",
    reason="禁言原因"
)
async def timeout_slash(interaction: discord.Interaction, member: discord.Member, duration: int, reason: str = "未提供原因"):
    if not interaction.user.guild_permissions.moderate_members:
        await interaction.response.send_message("❌ 你没有禁言成员的权限！", ephemeral=True)
        return

    if duration > 1440:  # 24小时限制
        await interaction.response.send_message("❌ 禁言时长不能超过24小时（1440分钟）！", ephemeral=True)
        return

    try:
        until = discord.utils.utcnow() + timedelta(minutes=duration)
        await member.timeout(until, reason=reason)

        embed = discord.Embed(title="🔇 成员已禁言", color=0xffaa00, timestamp=datetime.now())
        embed.add_field(name="用户", value=f"{member}", inline=True)
        embed.add_field(name="时长", value=f"{duration} 分钟", inline=True)
        embed.add_field(name="解除时间", value=f"<t:{int(until.timestamp())}:R>", inline=True)
        embed.add_field(name="执行者", value=f"{interaction.user}", inline=True)
        embed.add_field(name="原因", value=reason, inline=False)

        await interaction.response.send_message(embed=embed)
        await send_log("🔇 禁言成员", f"{interaction.user} 禁言了 {member} {duration}分钟\n原因：{reason}", 0xffaa00)
    except discord.Forbidden:
        await interaction.response.send_message("❌ 我没有权限禁言这个用户！", ephemeral=True)

@bot.tree.command(name="untimeout", description="解除成员禁言")
@app_commands.describe(member="要解除禁言的成员")
async def untimeout_slash(interaction: discord.Interaction, member: discord.Member):
    if not interaction.user.guild_permissions.moderate_members:
        await interaction.response.send_message("❌ 你没有解除禁言的权限！", ephemeral=True)
        return

    try:
        await member.timeout(None)
        embed = discord.Embed(title="🔊 禁言已解除", color=0x00ff00, timestamp=datetime.now())
        embed.add_field(name="用户", value=f"{member}", inline=True)
        embed.add_field(name="执行者", value=f"{interaction.user}", inline=True)

        await interaction.response.send_message(embed=embed)
        await send_log("🔊 解除禁言", f"{interaction.user} 解除了 {member} 的禁言", 0x00ff00)
    except discord.Forbidden:
        await interaction.response.send_message("❌ 我没有权限解除这个用户的禁言！", ephemeral=True)

# ==================== 💬 消息管理斜杠命令 ====================

@bot.tree.command(name="clear", description="清理频道消息")
@app_commands.describe(
    amount="要删除的消息数量（1-100）",
    user="只删除特定用户的消息（可选）"
)
async def clear_slash(interaction: discord.Interaction, amount: int, user: discord.Member = None):
    if not interaction.user.guild_permissions.manage_messages:
        await interaction.response.send_message("❌ 你没有管理消息的权限！", ephemeral=True)
        return

    if amount > 100 or amount < 1:
        await interaction.response.send_message("❌ 消息数量必须在1-100之间！", ephemeral=True)
        return

    await interaction.response.defer()

    try:
        if user:
            # 修复：使用 interaction.channel 而不是 interaction.followup.channel
            deleted = await interaction.channel.purge(limit=amount, check=lambda m: m.author == user)
        else:
            # 修复：使用 interaction.channel 而不是 interaction.followup.channel
            deleted = await interaction.channel.purge(limit=amount)

        embed = discord.Embed(title="🗑️ 消息已清理", color=0x00ff00, timestamp=datetime.now())
        embed.add_field(name="删除数量", value=f"{len(deleted)} 条", inline=True)
        embed.add_field(name="执行者", value=f"{interaction.user}", inline=True)
        if user:
            embed.add_field(name="目标用户", value=f"{user}", inline=True)

        # 发送结果消息，3秒后自动删除
        msg = await interaction.followup.send(embed=embed)
        await asyncio.sleep(3)
        await msg.delete()

        log_text = f"{interaction.user} 在 {interaction.channel} 删除了 {len(deleted)} 条消息"
        if user:
            log_text += f"（来自 {user}）"
        await send_log("🗑️ 清理消息", log_text, 0x00ff00)

    except discord.Forbidden:
        await interaction.followup.send("❌ 我没有权限删除消息！", ephemeral=True)
    except Exception as e:
        # 添加更好的错误处理
        await interaction.followup.send(f"❌ 清理消息时出错: {e}", ephemeral=True)

# ==================== 📢 公告功能 ====================

@bot.tree.command(name="announce", description="发送服务器公告")
@app_commands.describe(
    channel="发送公告的频道",
    title="公告标题",
    content="公告内容",
    mention_everyone="是否@everyone"
)
async def announce_slash(interaction: discord.Interaction, channel: discord.TextChannel, title: str, content: str, mention_everyone: bool = False):
    if not interaction.user.guild_permissions.mention_everyone:
        await interaction.response.send_message("❌ 你没有发送公告的权限！", ephemeral=True)
        return

    embed = discord.Embed(title=f"📢 {title}", description=content, color=BOT_COLOR, timestamp=datetime.now())
    embed.set_footer(text=f"发布者: {interaction.user}", icon_url=interaction.user.display_avatar.url)

    mention_text = "@everyone" if mention_everyone else ""
    await channel.send(mention_text, embed=embed)
    await interaction.response.send_message(f"✅ 公告已发送到 {channel.mention}！", ephemeral=True)
    await send_log("📢 发送公告", f"{interaction.user} 在 {channel} 发送了公告：{title}", BOT_COLOR)

# ==================== 📊 投票功能 ====================

@bot.tree.command(name="poll", description="创建投票")
@app_commands.describe(
    question="投票问题",
    option1="选项1",
    option2="选项2",
    option3="选项3（可选）",
    option4="选项4（可选）",
    option5="选项5（可选）"
)
async def poll_slash(interaction: discord.Interaction, question: str, option1: str, option2: str, 
                    option3: str = None, option4: str = None, option5: str = None):

    options = [option1, option2]
    if option3: options.append(option3)
    if option4: options.append(option4)
    if option5: options.append(option5)

    reactions = ['1️⃣', '2️⃣', '3️⃣', '4️⃣', '5️⃣']

    embed = discord.Embed(title="📊 投票", description=question, color=BOT_COLOR, timestamp=datetime.now())

    for i, option in enumerate(options):
        embed.add_field(name=f"{reactions[i]} 选项 {i+1}", value=option, inline=False)

    embed.set_footer(text=f"发起者: {interaction.user}")

    await interaction.response.send_message(embed=embed)
    message = await interaction.original_response()

    for i in range(len(options)):
        await message.add_reaction(reactions[i])

# ==================== ℹ️ 信息查看 ====================

@bot.tree.command(name="userinfo", description="查看用户信息")
@app_commands.describe(user="要查看的用户（可选，默认自己）")
async def userinfo_slash(interaction: discord.Interaction, user: discord.Member = None):
    if user is None:
        user = interaction.user

    embed = discord.Embed(title=f"👤 {user.display_name} 的信息", color=BOT_COLOR, timestamp=datetime.now())
    embed.set_thumbnail(url=user.display_avatar.url)
    embed.add_field(name="用户名", value=f"{user}", inline=True)
    embed.add_field(name="ID", value=f"`{user.id}`", inline=True)
    embed.add_field(name="昵称", value=user.display_name, inline=True)
    embed.add_field(name="账户创建", value=f"<t:{int(user.created_at.timestamp())}:R>", inline=True)
    embed.add_field(name="加入时间", value=f"<t:{int(user.joined_at.timestamp())}:R>", inline=True)
    embed.add_field(name="角色数量", value=f"{len(user.roles)-1}", inline=True)
    embed.add_field(name="最高角色", value=user.top_role.mention if user.top_role.name != "@everyone" else "无", inline=True)

    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="serverinfo", description="查看服务器信息")
async def serverinfo_slash(interaction: discord.Interaction):
    guild = interaction.guild
    embed = discord.Embed(title=f"🏠 {guild.name}", color=BOT_COLOR, timestamp=datetime.now())

    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)

    embed.add_field(name="服务器ID", value=f"`{guild.id}`", inline=True)
    embed.add_field(name="所有者", value=f"{guild.owner}", inline=True)
    embed.add_field(name="创建时间", value=f"<t:{int(guild.created_at.timestamp())}:R>", inline=True)
    embed.add_field(name="成员数量", value=f"{guild.member_count}", inline=True)
    embed.add_field(name="频道数量", value=f"{len(guild.channels)}", inline=True)
    embed.add_field(name="角色数量", value=f"{len(guild.roles)}", inline=True)
    embed.add_field(name="加成等级", value=f"{guild.premium_tier}", inline=True)
    embed.add_field(name="加成用户", value=f"{guild.premium_subscription_count}", inline=True)

    await interaction.response.send_message(embed=embed)

# ==================== 🎭 反应角色功能 ====================

# 🔧 在这里修改你的反应角色配置
REACTION_ROLES = {
    '🐕': 'Wer',
    '🐈‍⬛': 'Meow',
    '🍔': '芝士汉堡',
    '🧁': '纸杯蛋糕',
    '👩🏻‍🍳': '好厨子',
    '🍴': '大吃一口'
}

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

# 反应角色事件监听
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

# ==================== 🚀 一键回顶功能 ====================

class TopButtonView(discord.ui.View):
    """临时回顶按钮视图"""
    def __init__(self):
        super().__init__(timeout=30)

    @discord.ui.button(label="🚀 再次回首楼", style=discord.ButtonStyle.primary, emoji="🚀")
    async def top_again_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            # 获取频道的第一条消息
            messages = []
            async for message in interaction.channel.history(limit=None, oldest_first=True):
                messages.append(message)
                break

            if not messages:
                await interaction.response.send_message("❌ 这个频道还没有消息呢！", ephemeral=True)
                return

            first_message = messages[0]
            jump_url = f"https://discord.com/channels/{interaction.guild.id}/{interaction.channel.id}/{first_message.id}"

            cute_messages = [
                f"🐕 汪！[又回到首楼了呢～]({jump_url})",
                f"✨ [再次传送成功！]({jump_url})",
                f"🎉 [咻咻咻～]({jump_url})",
                f"🌟 [无限回首楼模式！]({jump_url})",
                f"🏃‍♂️ [来回跑真开心！]({jump_url})"
            ]

            import random
            await interaction.response.send_message(
                random.choice(cute_messages), 
                ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message("❌ 获取第一条消息时出错了！", ephemeral=True)

class PersistentTopButtonView(discord.ui.View):
    """持久化回顶按钮视图"""
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🚀 回到首楼", style=discord.ButtonStyle.primary, emoji="🚀", custom_id="persistent_top_button")
    async def persistent_top_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            # 获取频道的第一条消息
            messages = []
            async for message in interaction.channel.history(limit=None, oldest_first=True):
                messages.append(message)
                break

            if not messages:
                await interaction.response.send_message("❌ 这个频道还没有消息呢！", ephemeral=True)
                return

            first_message = messages[0]
            jump_url = f"https://discord.com/channels/{interaction.guild.id}/{interaction.channel.id}/{first_message.id}"

            cute_messages = [
                f"🐕 汪！[瞬间回首楼！]({jump_url})",
                f"✨ [咻～传送完成！]({jump_url})",
                f"🎉 [成功抵达首楼！]({jump_url})",
                f"🌟 [时光倒流成功！]({jump_url})",
                f"🏃‍♂️ [闪现回首楼！]({jump_url})"
            ]

            import random
            await interaction.response.send_message(
                random.choice(cute_messages), 
                ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message("❌ 获取第一条消息时出错了！", ephemeral=True)

@bot.tree.command(name="top", description="一键回到频道第一条消息")
async def top_slash(interaction: discord.Interaction):
    try:
        # 获取频道的第一条消息
        messages = []
        async for message in interaction.channel.history(limit=None, oldest_first=True):
            messages.append(message)
            break  # 只要第一条消息

        if not messages:
            await interaction.response.send_message("❌ 这个频道还没有消息呢！", ephemeral=True)
            return

        first_message = messages[0]

        # 创建跳转链接
        jump_url = f"https://discord.com/channels/{interaction.guild.id}/{interaction.channel.id}/{first_message.id}"

        embed = discord.Embed(
            title="🚀 咻～回到首楼啦！",
            description=f"[点击这里跳转到第一条消息]({jump_url})",
            color=BOT_COLOR,
            timestamp=datetime.now()
        )

        # 添加一些可爱的随机回复
        cute_messages = [
            "🐕 汪！主人回到首楼了呢～",
            "✨ 传送成功！欢迎回到起点～",
            "🎉 嗖的一下就回到开头了！",
            "🌟 时光机启动成功！",
            "🏃‍♂️ 跑得比光还快！",
            "🎯 精准定位到第一条消息！"
        ]

        import random
        embed.add_field(
            name="💫 温馨提示", 
            value=random.choice(cute_messages), 
            inline=False
        )

        embed.add_field(
            name="📅 首楼时间", 
            value=f"<t:{int(first_message.created_at.timestamp())}:R>", 
            inline=True
        )

        embed.add_field(
            name="👤 楼主", 
            value=f"{first_message.author.mention}", 
            inline=True
        )

        embed.set_footer(text=f"请求者: {interaction.user.display_name}", icon_url=interaction.user.display_avatar.url)

        # 发送消息并附带按钮
        await interaction.response.send_message(embed=embed, view=TopButtonView())

        # 5秒后删除消息（给用户时间看到和点击按钮）
        await asyncio.sleep(5)
        try:
            message = await interaction.original_response()
            await message.delete()
        except:
            pass  # 如果消息已被删除就忽略错误

    except Exception as e:
        await interaction.response.send_message("❌ 获取第一条消息时出错了！", ephemeral=True)

@bot.tree.command(name="totop", description="快速回到频道第一条消息")
async def totop_slash(interaction: discord.Interaction):
    try:
        # 获取频道的第一条消息
        messages = []
        async for message in interaction.channel.history(limit=None, oldest_first=True):
            messages.append(message)
            break  # 只要第一条消息

        if not messages:
            await interaction.response.send_message("❌ 这个频道还没有消息呢！", ephemeral=True)
            return

        first_message = messages[0]

        # 创建跳转链接
        jump_url = f"https://discord.com/channels/{interaction.guild.id}/{interaction.channel.id}/{first_message.id}"

        # 更简洁的版本
        cute_emojis = ["🚀", "✨", "🌟", "💫", "⭐", "🎯", "🏃‍♂️", "🐕"]
        import random

        emoji = random.choice(cute_emojis)
        message_text = f"{emoji} {interaction.user.mention} [回到首楼啦！]({jump_url})"

        await interaction.response.send_message(message_text, ephemeral=False)

        # 2秒后删除
        await asyncio.sleep(2)
        try:
            msg = await interaction.original_response()
            await msg.delete()
        except:
            pass

    except Exception as e:
        await interaction.response.send_message("❌ 获取第一条消息时出错了！", ephemeral=True)

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

    # 使用已定义的持久化按钮视图
    view = PersistentTopButtonView()

    await interaction.response.send_message(embed=embed, view=view)
    await interaction.followup.send("✅ 回首楼按钮已设置完成！", ephemeral=True)

    # 记录日志
    await send_log("🚀 设置回首楼按钮", f"{interaction.user} 在 {interaction.channel} 设置了回首楼按钮", BOT_COLOR)

# ==================== 🆘 帮助命令 ====================

@bot.tree.command(name="debug", description="检查bot权限和角色配置")
async def debug_command(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ 只有管理员可以使用此命令！", ephemeral=True)
        return
    
    embed = discord.Embed(title="🔍 权限诊断报告", color=0xff9900)
    
    # 检查角色是否存在
    pending_role = discord.utils.get(interaction.guild.roles, name=PENDING_ROLE_NAME)
    verified_role = discord.utils.get(interaction.guild.roles, name=VERIFIED_ROLE_NAME)
    rejected_role = discord.utils.get(interaction.guild.roles, name=REJECTED_ROLE_NAME)
    
    role_status = f"待审核: {'✅' if pending_role else '❌'}"
    if pending_role:
        role_status += f" (位置: {pending_role.position})"
    role_status += f"\n喜欢您来: {'✅' if verified_role else '❌'}"
    if verified_role:
        role_status += f" (位置: {verified_role.position})"
    role_status += f"\n未通过审核: {'✅' if rejected_role else '❌'}"
    if rejected_role:
        role_status += f" (位置: {rejected_role.position})"
    
    embed.add_field(name="角色检查", value=role_status, inline=False)
    
    # 检查频道权限
    audit_channel = bot.get_channel(AUDIT_CHANNEL_ID)
    welcome_channel = bot.get_channel(WELCOME_CHANNEL_ID)
    log_channel = bot.get_channel(LOG_CHANNEL_ID)
    
    channel_status = f"审核频道: {'✅' if audit_channel else '❌'}\n"
    channel_status += f"欢迎频道: {'✅' if welcome_channel else '❌'}\n"
    channel_status += f"日志频道: {'✅' if log_channel else '❌'}"
    
    embed.add_field(name="频道检查", value=channel_status, inline=False)
    
    # 检查bot权限
    bot_member = interaction.guild.get_member(bot.user.id)
    perms = bot_member.guild_permissions
    
    perm_status = f"管理角色: {'✅' if perms.manage_roles else '❌'}\n"
    perm_status += f"发送消息: {'✅' if perms.send_messages else '❌'}\n"
    perm_status += f"嵌入链接: {'✅' if perms.embed_links else '❌'}\n"
    perm_status += f"查看频道: {'✅' if perms.view_channel else '❌'}"
    
    embed.add_field(name="权限检查", value=perm_status, inline=False)
    
    # 检查bot角色位置
    bot_role = bot_member.top_role
    bot_role_info = f"Bot最高角色: {bot_role.name} (位置: {bot_role.position})\n"
    
    if pending_role:
        if bot_role.position > pending_role.position:
            bot_role_info += f"✅ Bot角色高于待审核角色"
        else:
            bot_role_info += f"❌ Bot角色低于待审核角色！需要提升Bot角色位置"
    
    embed.add_field(name="角色层级检查", value=bot_role_info, inline=False)
    
    # 添加解决建议
    suggestions = ""
    if not pending_role:
        suggestions += "• 创建名为'待审核'的角色\n"
    if not perms.manage_roles:
        suggestions += "• 给Bot添加'管理角色'权限\n"
    if pending_role and bot_role.position <= pending_role.position:
        suggestions += "• 将Bot角色拖拽到'待审核'角色之上\n"
    if not audit_channel:
        suggestions += "• 检查审核频道ID是否正确\n"
    
    if suggestions:
        embed.add_field(name="🔧 建议修复", value=suggestions, inline=False)
    else:
        embed.add_field(name="✅ 状态", value="配置看起来正常！", inline=False)
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="testjoin", description="模拟新成员加入（测试用）")
async def test_join_command(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ 只有管理员可以使用此命令！", ephemeral=True)
        return
    
    print(f"🔍 [TEST] 管理员 {interaction.user} 触发测试加入事件")
    
    # 模拟 on_member_join 事件
    try:
        await on_member_join(interaction.user)
        await interaction.response.send_message("✅ 测试完成！请检查控制台输出和审核频道。", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"❌ 测试时出错: {e}", ephemeral=True)

@bot.tree.command(name="help", description="查看所有可用命令")
async def help_slash(interaction: discord.Interaction):
    embed = discord.Embed(title=f"🤖 {BOT_NAME} 命令帮助", color=BOT_COLOR)

    # 审核系统命令（管理员/审核员专用）
    if is_moderator_or_admin(interaction):
        embed.add_field(
            name="🔍 审核系统",
            value="`/approve` - 批准用户\n`/reject` - 拒绝用户\n`/pending` - 待审核列表\n`/reaudit` - 重新审核",
            inline=False
        )

    if interaction.user.guild_permissions.administrator:
        embed.add_field(
            name="🛠️ 调试工具",
            value="`/debug` - 检查权限配置\n`/testjoin` - 测试新成员加入",
            inline=False
        )

    embed.add_field(
        name="👥 用户管理",
        value="`/kick` - 踢出用户\n`/ban` - 封禁用户\n`/timeout` - 禁言用户\n`/untimeout` - 解除禁言",
        inline=False
    )

    embed.add_field(
        name="💬 消息管理",
        value="`/clear` - 清理消息\n`/announce` - 发送公告",
        inline=False
    )

    embed.add_field(
        name="📊 实用工具",
        value="`/poll` - 创建投票\n`/userinfo` - 用户信息\n`/serverinfo` - 服务器信息",
        inline=False
    )

    embed.add_field(
        name="🎭 其他功能",
        value="`/setup_roles` - 设置反应角色\n`/top` - 回到频道首楼\n`/totop` - 快速回首楼\n`/topbutton` - 设置回首楼按钮",
        inline=False
    )

    embed.add_field(name="部署平台", value="Vultr", inline=False)
    embed.add_field(name="🆕 新功能", value="私信审核系统", inline=False)
    embed.set_footer(text="使用斜杠命令 (/) 来调用这些功能！")

    await interaction.response.send_message(embed=embed)

# ==================== 🌐 Web服务器（保持Vultr活跃） ====================
from flask import Flask, jsonify
import threading

app = Flask(__name__)

@app.route('/')
def home():
    uptime = datetime.now() - bot.start_time if hasattr(bot, 'start_time') else "启动中"
    return f"""
    <html>
        <head><title>🤖 {BOT_NAME}</title></head>
        <body style="background:#2c2f33;color:#fff;font-family:Arial;text-align:center;padding:50px;">
            <h1>🤖 {BOT_NAME}</h1>
            <p>✅ 状态: {'在线' if bot.is_ready() else '启动中'}</p>
            <p>🕐 运行时间: {uptime}</p>
            <p>🏠 服务器数: {len(bot.guilds) if bot.is_ready() else 0}</p>
            <p>🚀 Vultr部署成功！</p>
            <p>🎉 告别断线烦恼！</p>
            <p>📱 新增私信审核系统！</p>
        </body>
    </html>
    """

@app.route('/health')
def health():
    return jsonify({
        "status": "healthy" if bot.is_ready() else "starting",
        "bot_name": BOT_NAME,
        "guilds": len(bot.guilds) if bot.is_ready() else 0,
        "platform": "Vultr",
        "audit_system": "DM_Based"
    })

def run_flask():
    PORT = int(os.getenv("PORT", 8080))
    app.run(host='0.0.0.0', port=PORT, debug=False)

async def main():
    """异步启动函数"""
    # 启动Flask服务器
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    print(f"🌐 Flask服务器启动在端口 {os.getenv('PORT', 8080)}")
    
    # 启动机器人
    try:
        await bot.start(BOT_TOKEN)
    except Exception as e:
        print(f"❌ 机器人启动失败: {e}")

# ==================== 🚀 启动机器人 ====================
if __name__ == "__main__":
    if not BOT_TOKEN:
        print("❌ 请设置BOT_TOKEN环境变量！")
        exit(1)
    
    print(f"🚀 在Vultr上启动 {BOT_NAME}...")
    print(f"📱 新审核系统: 私信提交模式")
    asyncio.run(main())
