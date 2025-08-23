import discord
from discord.ext import commands
import os
import asyncio
import db
from utils.logger import send_log
from dotenv import load_dotenv


load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.all()
bot = commands.Bot(command_prefix='/', intents=intents, help_command=None)
db.init_db()

@bot.event
async def on_ready():
    print(f'🤖 Logado como {bot.user}')
    for guild in bot.guilds:
        db.ensure_guild_shop_exists(guild.id)

    synced = await bot.tree.sync()
    print(f'Synced {len(synced)} slash commands')

async def load_extensions():
    for ext in [
        "cogs.admin",
        "cogs.XP",
        "cogs.loja",
        "cogs.misc",
        "cogs.interaction",
        "cogs.moderation",
        "cogs.social",
        "cogs.champion"
    ]:
        try:
            await bot.load_extension(ext)
            print(f"✅ Cog Loaded: {ext}")
        except Exception as e:
            print(f"❌ Error loading {ext}: {e}")

async def main():
    async with bot:
        await load_extensions()
        await bot.start(TOKEN)

if __name__ == "__main__":
    asyncio.run(main())
