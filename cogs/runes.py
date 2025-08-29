import discord
from discord.ext import commands
from discord import app_commands
import aiohttp

class Runes(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def get_champion_data(self, champion: str):
        url = f"https://u.gg/lol/champions/{champion}/build.json"
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    return None

    @app_commands.command(name="runes", description="Mostra runas e build atualizadas de um campeão")
    @app_commands.describe(champion="Digite o nome do campeão")
    async def runes(self, interaction: discord.Interaction, champion: str):
        await interaction.response.defer(thinking=True, ephemeral=True)

        data = await self.get_champion_data(champion.lower())

        if not data:
            await interaction.followup.send(
                f"❌ Não consegui encontrar runas/builds para `{champion}` no u.gg.",
                ephemeral=True
            )
            return

        embed = discord.Embed(
            title=f"{champion.capitalize()} - Runas e Build",
            description=f"**Patch:** {data['patch']}\n[Veja mais no u.gg](https://u.gg/lol/champions/{champion.lower()}/build)",
            color=discord.Color.blurple()
        )

        # Runas
        runes_str = " ".join(f"[{rune['name']}]({rune['url']})" for rune in data['runas'])
        embed.add_field(name="🛡️ Runas", value=runes_str, inline=False)

        # Itens
        items_str = " ".join(f"[{item['name']}]({item['url']})" for item in data['items'])
        embed.add_field(name="🗡️ Itens", value=items_str, inline=False)

        await interaction.followup.send(embed=embed, ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(Runes(bot))
