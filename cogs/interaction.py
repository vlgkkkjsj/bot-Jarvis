import discord
from discord.ext import commands, tasks
from discord import app_commands, Interaction, TextStyle
from discord.ui import View, Select, Modal, TextInput
import time
import datetime
import logging
from utils import profile_utils
import db

logging.basicConfig(level=logging.INFO, format="[Interaction] %(message)s")

# Configurações XP
TEXT_XP = 10
TEXT_COOLDOWN_MINUTES = 1
VOICE_XP = 1
VOICE_INTERVAL_HOURS = 1
REALTIME_UPDATE_INTERVAL_SECONDS = 5

TEXT_COOLDOWN = TEXT_COOLDOWN_MINUTES * 60 
VOICE_INTERVAL = VOICE_INTERVAL_HOURS * 3600  
REALTIME_UPDATE_INTERVAL = REALTIME_UPDATE_INTERVAL_SECONDS

class InteractionCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.active_users = {}    
        self.cooldowns = {}       

        self.give_xp_loop.start()
        self.update_call_time_loop.start()
        self.cleanup_boost_loop.start()  
        
    @tasks.loop(hours=24)
    async def cleanup_boost_loop(self):
        db.cleanup_expired_boosts()

    @cleanup_boost_loop.before_loop
    async def before_cleanup_boost_loop(self):
        await self.bot.wait_until_ready()

    
    def get_boost_multiplier(self, member: discord.Member, guild_id: int) -> float:

        if not member:
            return 1.0


        has_boost_role = any(role.name == "⚡ BoostXP" for role in member.roles)

        if has_boost_role:
            return db.get_active_boost_multiplier(member.id, guild_id)
        else:

            if db.check_boost_active(member.id, guild_id):
                db.remove_boost(member.id, guild_id)
            return 1.0
    
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or message.guild is None:
            return

        user_id = message.author.id
        guild_id = message.guild.id
        now = time.time()

        db.increment_message_count(user_id, guild_id, 1)

        cooldown_key = (guild_id, user_id)
        if cooldown_key not in self.cooldowns or (now - self.cooldowns[cooldown_key]) >= TEXT_COOLDOWN:
            self.cooldowns[cooldown_key] = now
            
            base_xp = TEXT_XP
            multiplier = self.get_boost_multiplier(message.author, message.guild.id)
            xp_to_add = int(base_xp * multiplier)
            db.add_xp(user_id, guild_id, xp_to_add)

            logging.info(f"{message.author} ganhou {xp_to_add} XP em {message.guild.name} (multiplicador {multiplier}x)")

            embed = discord.Embed(
                title="🎉 XP Ganhado!",
                description=f"Você ganhou **{xp_to_add} XP** no servidor **{message.guild.name}** 💬\nMultiplicador ativo: **{multiplier}x**",
                color=discord.Color.blue()
            )
            embed.set_thumbnail(url=message.author.display_avatar.url)
            embed.set_footer(text="Continue participando para ganhar mais XP!")

            try:
                await message.author.send(embed=embed)
            except discord.Forbidden:
                pass

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        guild_id = member.guild.id
        user_id = member.id

        if after.channel is not None: 
            self.active_users[user_id] = (guild_id, time.time())
        elif before.channel is not None and after.channel is None: 
            if user_id in self.active_users:
                joined_at = self.active_users[user_id][1]
                total_time = int(time.time() - joined_at)
                db.add_call_time(user_id, guild_id, total_time)
                self.active_users.pop(user_id, None)

    @tasks.loop(seconds=REALTIME_UPDATE_INTERVAL)
    async def update_call_time_loop(self):
        now = time.time()
        for user_id, (guild_id, joined_at) in list(self.active_users.items()):
            delta = int(now - joined_at)
            if delta >= REALTIME_UPDATE_INTERVAL:
                db.add_call_time(user_id, guild_id, REALTIME_UPDATE_INTERVAL)
                self.active_users[user_id] = (guild_id, now)
                logging.debug(f"[Tempo em tempo real] {user_id} +{REALTIME_UPDATE_INTERVAL}s em {guild_id}")
                
    @update_call_time_loop.before_loop
    async def before_update_call_time_loop(self):
        await self.bot.wait_until_ready()
            
    @tasks.loop(hours=VOICE_INTERVAL_HOURS)
    async def give_xp_loop(self):
        try:
            for user_id, (guild_id, joined_at) in list(self.active_users.items()):
                now = time.time()
                delta_seconds = int(now - joined_at)
                db.add_call_time(user_id, guild_id, delta_seconds)
                self.active_users[user_id] = (guild_id, now)
                
                base_xp = VOICE_XP
                guild = self.bot.get_guild(guild_id)
                member = guild.get_member(user_id) if guild else None
                multiplier = self.get_boost_multiplier(member, guild_id) if member else 1.0
                xp_to_add = int(base_xp * multiplier)
                db.add_xp(user_id, guild_id, xp_to_add)

                logging.info(f"Usuário {user_id} ganhou {xp_to_add} XP (voz) em {guild_id}, multiplicador {multiplier}x")

                guild = self.bot.get_guild(guild_id)
                if guild:
                    member = guild.get_member(user_id)
                    if member:
                        embed = discord.Embed(
                            title="🎤 XP por Call!",
                            description=f"Você ganhou **{xp_to_add} XP** por estar em call no servidor **{guild.name}** 🔊\nMultiplicador ativo: **{multiplier}x**",
                            color=discord.Color.green()
                        )
                        embed.set_thumbnail(url=member.display_avatar.url)
                        embed.set_footer(text="Aproveite sua call e acumule XP!")

                        try:
                            await member.send(embed=embed)
                        except discord.Forbidden:
                            pass
        except Exception as e:
            logging.error(f"Erro no give_xp_loop: {e}")
    
    @give_xp_loop.before_loop
    async def before_give_xp_loop(self):
        await self.bot.wait_until_ready()

    @app_commands.command(name="info", description="Veja informações de um usuário do servidor")
    @app_commands.describe(user_input="Nome, nickname ou ID do usuário")
    async def info(self, interaction: discord.Interaction, user_input: str):
        guild = interaction.guild
        member = None

        if user_input.isdigit():
            member = guild.get_member(int(user_input))
        if not member:
            for m in guild.members:
                if user_input.lower() in m.display_name.lower() or user_input.lower() in m.name.lower():
                    member = m
                    break
        if not member:
            await interaction.response.send_message("Usuário não encontrado.", ephemeral=True)
            return

        user_id, guild_id = member.id, guild.id

        msg_count = db.get_message_count(user_id, guild_id) or 0
        total_seconds = db.get_call_time(user_id, guild_id) or 0
        user_data = db.get_user_data(user_id, guild_id)
        xp, level, vitorias, derrotas = user_data if user_data else (0, 0, 0, 0)
        multiplier = self.get_boost_multiplier(member, guild_id)

        level_data = profile_utils.calculate_level(xp)
        level = level_data["level"]
        progress_pct = int(level_data["progress"] * 100)


        new_badges = profile_utils.check_and_award_badges(db, user_id, guild_id, xp, msg_count, total_seconds)
        badges = profile_utils.get_badges(db, user_id, guild_id)
        badges_str = profile_utils.render_badges(badges)

        if new_badges:
            try:
                dm = discord.Embed(
                    title="🏅 Novas Badges!",
                    description="Você ganhou novas badges: " + profile_utils.render_badges(new_badges),
                    color=discord.Color.gold()
                )
                await member.send(embed=dm)
            except discord.Forbidden:
                pass

        buffer = profile_utils.generate_profile_image(member, xp, msg_count, total_seconds, vitorias, derrotas, badges)
        file = discord.File(fp=buffer, filename="perfil.png")

        def format_time(seconds: int):
            h, r = divmod(seconds, 3600)
            m, s = divmod(r, 60)
            return f"{h}h {m}m {s}s"

        multiplier_text = f"x{multiplier}" if multiplier > 1 else "Nenhum boost ativo"

        embed = discord.Embed(
            title=f"ℹ️ Informações de {member.display_name}",
            description=profile_utils.generate_profile_text(xp, msg_count, total_seconds, vitorias, derrotas),
            color=discord.Color.orange(),
            timestamp=datetime.datetime.now(datetime.timezone.utc)
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_image(url="attachment://perfil.png")
        embed.add_field(name="👤 Usuário", value=member.name, inline=True)
        embed.add_field(name="📛 Nickname", value=member.display_name, inline=True)
        embed.add_field(name="✨ XP", value=f"{xp}", inline=True)
        embed.add_field(name="🏆 Vitórias", value=f"{vitorias}", inline=True)
        embed.add_field(name="💀 Derrotas", value=f"{derrotas}", inline=True)
        embed.add_field(name="🕒 Tempo em call", value=format_time(total_seconds), inline=True)
        embed.add_field(name="💬 Mensagens enviadas", value=f"{msg_count}", inline=True)
        roles = [role.mention for role in member.roles if role != guild.default_role]
        embed.add_field(name="🎭 Cargos", value=", ".join(roles) if roles else "Nenhum cargo", inline=False)
        embed.add_field(name="🏅 Nível", value=f"{level} ({progress_pct}% do próximo nível)", inline=True)
        embed.add_field(name="⚡ Multiplicador de XP", value=multiplier_text, inline=False)
        embed.add_field(name="🏅 Badges", value=badges_str or "Nenhuma ainda 💤", inline=False)

        await interaction.response.send_message(embed=embed, file=file, ephemeral=True)

    @info.autocomplete("user_input")
    async def user_autocomplete(self, interaction: discord.Interaction, current: str):
        current = current.lower()
        choices = []
    
        for member in interaction.guild.members:
            if (current in member.display_name.lower() or
                current in member.name.lower()):
                choices.append(
                    app_commands.Choice(
                        name=member.display_name,  
                        value=str(member.id)      
                    )
                )
    
            if len(choices) >= 25:  
                break
    
        return choices
    
    
    @app_commands.command(name="givebadge", description="Dar uma badge a um usuário (admin apenas)")
    @app_commands.describe(user="Usuário que receberá a badge")
    @app_commands.checks.has_permissions(administrator=True)
    async def givebadge(self, interaction: Interaction, user: discord.Member):
        view = GiveBadgeView(user)
        await interaction.response.send_message(
            f"Selecione a badge que deseja dar para {user.display_name}:",
            view=view,
            ephemeral=True
        )

    @app_commands.command(name="removebadge", description="Remover badges de um usuário (admin apenas)")
    @app_commands.checks.has_permissions(administrator=True)
    async def removebadge(self, interaction: Interaction):
        modal = RemoveBadgeModal(interaction.user, interaction.guild)
        await interaction.response.send_modal(modal)

class RemoveBadgeModal(Modal):
    def __init__(self, admin: discord.Member, guild: discord.Guild):
        super().__init__(title="Remover Badge")
        self.admin = admin
        self.guild = guild

        self.user_input = TextInput(
            label="Usuário (nome, nickname ou ID)",
            style=TextStyle.short,
            placeholder="Digite o usuário...",
            required=True
        )
        self.add_item(self.user_input)

    async def on_submit(self, interaction: Interaction):
        user_input = self.user_input.value
        member = None

        if user_input.isdigit():
            member = self.guild.get_member(int(user_input))
        if not member:
            for m in self.guild.members:
                if user_input.lower() in m.display_name.lower() or user_input.lower() in m.name.lower():
                    member = m
                    break

        if not member:
            await interaction.response.send_message("Usuário não encontrado.", ephemeral=True)
            return

        user_badges = [b["badge_key"] for b in db.get_user_badges(member.id, self.guild.id)]
        if not user_badges:
            await interaction.response.send_message(f"{member.display_name} não possui badges.", ephemeral=True)
            return

        view = RemoveBadgeView(member, user_badges)
        await interaction.response.send_message(
            f"Selecione as badges que deseja remover de {member.display_name}:",
            view=view,
            ephemeral=True
        )

class RemoveBadgeView(View):
    def __init__(self, member: discord.Member, badges: list):
        super().__init__(timeout=60)
        self.member = member
        self.badges = badges

        self.select = Select(
            placeholder="Selecione badges para remover",
            min_values=1,
            max_values=len(badges),
            options=[discord.SelectOption(label=badge, emoji=profile_utils.BADGE_EMOJIS.get(badge, "")) for badge in badges]
        )
        self.select.callback = self.select_callback
        self.add_item(self.select)

    async def select_callback(self, interaction: Interaction):
        selected = self.select.values
        for badge in selected:
            db.remove_user_badge(self.member.id, interaction.guild.id, badge)

        await interaction.response.send_message(
            f"As badges {', '.join([profile_utils.BADGE_EMOJIS.get(b,b) for b in selected])} foram removidas de {self.member.display_name} ✅",
            ephemeral=True
        )
        self.stop()
        
        
class GiveBadgeView(View):
    def __init__(self, target_member: discord.Member):
        super().__init__(timeout=60)
        self.target_member = target_member

        self.select = Select(
            placeholder="Selecione a badge para conceder",
            min_values=1,
            max_values=1,
            options=[
                discord.SelectOption(label=name, emoji=profile_utils.BADGE_EMOJIS[name])
                for name in profile_utils.BADGE_EMOJIS.keys()
            ]
        )
        self.select.callback = self.select_callback
        self.add_item(self.select)

    async def select_callback(self, interaction: Interaction):
        badge = self.select.values[0].lower()
        db.add_user_badge(self.target_member.id, interaction.guild.id, badge)

        try:
            dm = discord.Embed(
                title="🏅 Nova Badge!",
                description=f"Você recebeu a badge {profile_utils.BADGE_EMOJIS[badge]}!",
                color=discord.Color.gold()
            )
            await self.target_member.send(embed=dm)
        except discord.Forbidden:
            pass

        await interaction.response.send_message(
            f"A badge {profile_utils.BADGE_EMOJIS[badge]} foi concedida a {self.target_member.display_name} ✅",
            ephemeral=True
        )
        self.stop()

async def setup(bot: commands.Bot):
    await bot.add_cog(InteractionCog(bot))
