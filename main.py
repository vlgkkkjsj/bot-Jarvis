import discord
from discord.ext import commands
import os
import asyncio
import db
from utils import logger
from dotenv import load_dotenv
import threading
from web import app
import wavelink 


def run_web():
    app.run(host="0.0.0.0", port=8080)


threading.Thread(target=run_web, daemon=True).start()

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.all()
bot = commands.Bot(command_prefix='/', intents=intents, help_command=None)
db.init_db()


@bot.event
async def on_ready():
    print(f'🤖 Logado como {bot.user}')
    
    for guild in bot.guilds:
        db.update_guild_name(guild.id , guild.name)
        db.ensure_guild_shop_exists(guild.id)
    
    synced = await bot.tree.sync()
    print(f"🌐 Synced {len(synced)} slash commands.")

    for guild in bot.guilds:
        total= 0
        for member in guild.members:
            if not member.bot:
                db.ensure_user_exists(member.id, guild.id)
                total +=1
        print(f"[STARTUP SYNC] {total} membros verificados/cadastrados no servidor {guild.name}.")

@bot.event
async def on_guild_join(guild):
    db.update_guild_name(guild.id, guild.name)
    db.ensure_guild_shop_exists(guild.id)
    for member in guild.members:
        if not member.bot:
            db.ensure_user_exists(member.id, guild.id)
    print(f"✅ Novo servidor adicionado: {guild.name} ({guild.id})")



@bot.event
async def on_guild_remove(guild):
    print(f"🧹 Servidor removido: {guild.name} ({guild.id}) — limpando banco...")
    db.delete_guild_data(guild.id)



@bot.event
async def on_member_remove(member):
    db.delete_user(member.id, member.guild.id)


@bot.event
async def on_command_completion(ctx: commands.Context):
    await logger.log_command(ctx, success=True)


@bot.event
async def on_command_error(ctx: commands.Context, error: Exception):
    await logger.log_command(ctx, success=False)
    await logger.log_error(ctx, error)


@bot.event
async def on_interaction(interaction: discord.Interaction):
    if interaction.type == discord.InteractionType.application_command:
        try:
            await logger.log_command(interaction, success=True)
        except Exception as e:
            await logger.log_error(interaction, e)


async def handle_app_command_error(interaction: discord.Interaction, error: Exception):
    await logger.log_command(interaction, success=False)
    await logger.log_error(interaction, error)

bot.tree.on_error = handle_app_command_error



@bot.event
async def on_message_delete(message: discord.Message):
    await logger.log_message_delete(message)


@bot.event
async def on_message_edit(before: discord.Message, after: discord.Message):
    await logger.log_message_edit(before, after)



async def load_extensions():
    for ext in [
        "cogs.admin",
        "cogs.XP",
        "cogs.loja",
        "cogs.misc",
        "cogs.interaction",
        "cogs.moderation",
        "cogs.social",
        "cogs.champion",
        "cogs.music",
        "cogs.challenge"
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
