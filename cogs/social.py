import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
import random
import asyncio
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


class Social(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        self.subreddits = ["MemesBR"]

    @app_commands.command(name="meme", description="Envia um meme aleatório de subreddits variados")
    async def meme(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)

        subreddit = random.choice(self.subreddits)
        url = f"https://meme-api.com/gimme/{subreddit}"

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as resp:
                    if resp.status != 200:
                        await interaction.followup.send(
                            f"❌ Não consegui buscar meme de `{subreddit}`. Tente novamente."
                        )
                        return
                    data = await resp.json()

            if not all(key in data for key in ["title", "postLink", "url", "subreddit"]):
                await interaction.followup.send("⚠️ Não encontrei um meme válido.")
                return

            embed = discord.Embed(
                title=data["title"],
                url=data["postLink"],
                color=discord.Color.random()
            )
            embed.set_image(url=data["url"])
            embed.set_footer(text=f"Subreddit: {data['subreddit']}")

            await interaction.followup.send(embed=embed)

        except asyncio.TimeoutError:
            await interaction.followup.send("⏳ A API demorou demais para responder.")
        except Exception as e:
            print(f"[ERROR] meme command falhou: {e}")
            await interaction.followup.send("⚠️ Ocorreu um erro ao tentar buscar um meme.")


async def setup(bot: commands.Bot):
    await bot.add_cog(Social(bot))
