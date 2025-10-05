import discord
from discord.ext import commands, tasks
from discord import app_commands
import db
import time
import logging
import datetime

logging.basicConfig(level=logging.INFO, format="[Interaction] %(message)s")


TEXT_XP = 10
TEXT_COOLDOWN_MINUTES = 10
VOICE_XP = 15
VOICE_INTERVAL_HOURS = 1
REALTIME_UPDATE_INTERVAL_SECONDS = 5

TEXT_COOLDOWN = TEXT_COOLDOWN_MINUTES * 60 
VOICE_INTERVAL = VOICE_INTERVAL_HOURS * 3600  
REALTIME_UPDATE_INTERVAL = REALTIME_UPDATE_INTERVAL_SECONDS

class Interaction(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.active_users = {}    
        self.cooldowns = {}       

        self.give_xp_loop.start()
        self.update_call_time_loop.start()


    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or message.guild is None:
            return

        user_id = message.author.id
        guild_id = message.guild.id
        now = time.time()

        db.increment_message_count(user_id, guild_id, 1)

        cooldown_key = (guild_id, user_id)
        if cooldown_key not in self.cooldowns or (now - self.cooldowns[cooldown_key]) >= TEXT_COOLDOWN :
            self.cooldowns[cooldown_key] = now
            db.add_xp(user_id, guild_id, TEXT_XP)
            logging.info(f"{message.author} ganhou {TEXT_XP} XP em {message.guild.name}")

            embed = discord.Embed(
                title="🎉 XP Ganhado!",
                description=f"Você ganhou **{TEXT_XP} XP** no servidor **{message.guild.name}** 💬",
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
                delta_seconds = int (now - joined_at)
                
                db.add_call_time(user_id,guild_id,delta_seconds)
                
                self.active_users[user_id] = (guild_id, now)
                
            
                
                db.add_xp(user_id, guild_id, VOICE_XP)
                logging.info(f"Usuário {user_id} ganhou {VOICE_XP} XP (voz) em {guild_id}")

                guild = self.bot.get_guild(guild_id)
                if guild:
                    member = guild.get_member(user_id)
                    if member:
                        embed = discord.Embed(
                            title="🎤 XP por Call!",
                            description=f"Você ganhou **{VOICE_XP} XP** por estar em call no servidor **{guild.name}** 🔊",
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

        user_id = member.id
        guild_id = guild.id

        msg_count = db.get_message_count(user_id, guild_id) or 0
        total_seconds = db.get_call_time(user_id, guild_id) or 0
        user_data = db.get_user_data(user_id, guild_id)

        xp, vitorias, derrotas = user_data if user_data else (0, 0, 0)

        def format_time(seconds: int):
            h, r = divmod(seconds, 3600)
            m, s = divmod(r, 60)
            return f"{h}h {m}m {s}s"

        roles = [role.mention for role in member.roles if role != guild.default_role]
        roles_str = ", ".join(roles) if roles else "Nenhum cargo"

        embed = discord.Embed(
            title=f"ℹ️ Informações de {member.display_name}",
            color=discord.Color.orange(),
            timestamp=datetime.datetime.now(datetime.timezone.utc)
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="👤 Usuário", value=member.name, inline=True)
        embed.add_field(name="📛 Nickname", value=member.display_name, inline=True)
        embed.add_field(name="✨ XP", value=f"{xp}", inline=True)
        embed.add_field(name="🏆 Vitórias", value=f"{vitorias}", inline=True)
        embed.add_field(name="💀 Derrotas", value=f"{derrotas}", inline=True)
        embed.add_field(name="🕒 Tempo em call", value=format_time(total_seconds), inline=True)
        embed.add_field(name="💬 Mensagens enviadas", value=f"{msg_count}", inline=True)
        embed.add_field(name="🎭 Cargos", value=roles_str, inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @info.autocomplete("user_input")
    async def user_autocomplete(self, interaction: discord.Interaction, current: str):
        choices = []
        for member in interaction.guild.members:
            if (current.lower() in member.display_name.lower() 
                or current.lower() in member.name.lower() 
                or current in str(member.id)):
                choices.append(app_commands.Choice(name=f"{member.display_name} ({member.id})", value=str(member.id)))
            if len(choices) >= 25:
                break
        return choices


async def setup(bot: commands.Bot):
    await bot.add_cog(Interaction(bot))
