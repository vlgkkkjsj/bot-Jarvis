import discord
from discord.ext import commands
from discord import app_commands
from discord.ext import tasks
import db
import functools
import asyncio
import time
from utils.logger import send_log 

def log_command(title_getter, fields_getter):
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(self, interaction, *args, **kwargs):
            try:
                result = await func(self, interaction, *args, **kwargs)
                if result:
                    title = title_getter(self, interaction, *args, **kwargs)
                    fields = fields_getter(self, interaction, *args, **kwargs)
                    await send_log(interaction, title, fields)
            except Exception as e:
                print(f"[ERROR] {func.__name__} falhou: {e}")
        return wrapper
    return decorator

def generic_title(self, interaction, *args, **kwargs):
    return f"Comando executado: /{interaction.command.name}"

def generic_fields(self, interaction, *args, **kwargs):
    return {
        "👤 Usuário": f"{interaction.user} ({interaction.user.id})",
        "💬 Comando": f"/{interaction.command.name}",
        "📍 Canal": f"{interaction.channel.name if interaction.channel else 'Direto'}"
    }

class Interaction(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.active_users = {}
        self.give_xp_loop.start()
        self.cooldowns = {}
        
        
        
    #XP INCREMENT VIA TEXT CHAT
    
    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return
        user_id = message.author.id
        guild_id = message.guild.id
        now = time.time()

        if user_id not in self.cooldowns or now - self.cooldowns[user_id] >= 30:
            self.cooldowns[user_id] = now
            db.add_xp(user_id, guild_id, 10)
            print(f"[XP] {message.author} ganhou 10 XP no servidor {message.guild.name}")
            
    #XP INCREMENT VIA VOICE TEXT
    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        if after.channel is not None:
            self.active_users[member.id] = (member.guild.id, time.time())

        elif before.channel is not None and after.channel is None:
            self.active_users.pop(member.id, None)

    @tasks.loop(minutes=15)
    async def give_xp_loop(self):
        for user_id, (guild_id, joined_at) in list(self.active_users.items()):
            db.add_xp(user_id, guild_id, 15)
            print(f"[VOICE XP] Usuário {user_id} ganhou 15 de XP no servidor {guild_id}")

    
  
async def setup(bot: commands.Bot):
    await bot.add_cog(Interaction(bot))