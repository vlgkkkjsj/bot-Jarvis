import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
import random
import urllib.parse

LANE_TAGS = {
    "TOP": ["Fighter", "Tank"],
    "JUNGLE": ["Fighter", "Tank", "Assassin"],
    "MID": ["Mage", "Assassin"],
    "ADC": ["Marksman"],
    "SUP": ["Support", "Tank"]
}

TAG_EMOJIS = {
    "Fighter": "⚔️",
    "Tank": "🛡️",
    "Assassin": "🗡️",
    "Mage": "🔮",
    "Marksman": "🏹",
    "Support": "💖"
}

TAG_COLORS = {
    "Fighter": discord.Color.red(),
    "Tank": discord.Color.dark_grey(),
    "Assassin": discord.Color.dark_red(),
    "Mage": discord.Color.purple(),
    "Marksman": discord.Color.gold(),
    "Support": discord.Color.green()
}

ABILITY_EMOJIS = ["🇶", "🇼", "🇪", "🇷"]

class Champion(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.patch = None
        self.champions = {}
        self.champ_details = {}
        self.session = aiohttp.ClientSession()
        self.bot.loop.create_task(self.load_data())

    async def get_latest_patch(self):
        url = "https://ddragon.leagueoflegends.com/api/versions.json"
        async with self.session.get(url) as resp:
            data = await resp.json()
            return data[0]

    async def load_data(self):
        self.patch = await self.get_latest_patch()
        champ_url = f"https://ddragon.leagueoflegends.com/cdn/{self.patch}/data/pt_BR/champion.json"
        async with self.session.get(champ_url) as resp:
            data = await resp.json()
        self.champions = data["data"]
        print(f"[League] Carregado patch {self.patch} com {len(self.champions)} campeões.")

    async def get_champion_details(self, champ_name):
        if champ_name in self.champ_details:
            return self.champ_details[champ_name]

        champ_details_url = f"https://ddragon.leagueoflegends.com/cdn/{self.patch}/data/pt_BR/champion/{champ_name}.json"
        async with self.session.get(champ_details_url) as resp:
            if resp.status == 200:
                details = (await resp.json())["data"][champ_name]
                self.champ_details[champ_name] = details
                return details
        return None

    async def lane_autocomplete(self, interaction: discord.Interaction, current: str):
        return [
            app_commands.Choice(name=lane, value=lane)
            for lane in LANE_TAGS.keys()
            if current.lower() in lane.lower()
        ]

    @app_commands.command(name="champion", description="Sugere um campeão random para lane")
    @app_commands.describe(lane="Escolha a lane que deseja jogar")
    @app_commands.autocomplete(lane=lane_autocomplete)
    async def champion(self, interaction: discord.Interaction, lane: str):
        await interaction.response.defer(thinking=True, ephemeral=True)

        if not self.champions:
            await interaction.followup.send("⚠️ Campeões ainda não foram carregados.", ephemeral=True)
            return

        possible_champs = [
            champ for champ in self.champions.values()
            if any(tag in LANE_TAGS[lane] for tag in champ.get("tags", []))
        ]

        if not possible_champs:
            await interaction.followup.send("⚠️ Nenhum campeão encontrado para essa lane.", ephemeral=True)
            return

        champ_data = random.choice(possible_champs)
        champ_name = champ_data["id"]
        champ_display_name = champ_data["name"]
        champ_title = champ_data["title"].capitalize()
        champ_tags = champ_data.get("tags", [])
        champ_icon_static = f"https://ddragon.leagueoflegends.com/cdn/{self.patch}/img/champion/{champ_name}.png"
        champ_icon_gif = f"https://ddragon.leagueoflegends.com/cdn/img/champion/loading/{champ_name}_0.jpg"  # fallback gif
        champ_details = await self.get_champion_details(champ_name)

        embed_color = TAG_COLORS.get(champ_tags[0], discord.Color.blurple())
        tags_text = " | ".join(f"{TAG_EMOJIS.get(tag, '')} {tag}" for tag in champ_tags)

        stats = champ_data.get("stats", {})
        stats_text = (
            f"❤️ HP: {stats.get('hp', 'N/A')}\n"
            f"🔹 Mana: {stats.get('mp', 'N/A')}\n"
            f"⚔️ Ataque: {stats.get('attackdamage', 'N/A')}\n"
            f"💨 Velocidade Ataque: {stats.get('attackspeed', 'N/A'):.2f}\n"
            f"🛡️ Defesa: {stats.get('armor', 'N/A')}\n"
            f"🌀 Resistência Mágica: {stats.get('spellblock', 'N/A')}\n"
            f"🏃 Velocidade Movimento: {stats.get('movespeed', 'N/A')}"
        )

        
        if champ_details:
            passive = champ_details.get("passive", {})
            spells = champ_details.get("spells", [])
            passive_text = f"🛡 **{passive.get('name','Passiva')}**: {passive.get('description','N/A')}"
            spells_text = ""
            for idx, spell in enumerate(spells):
                emoji = ABILITY_EMOJIS[idx] if idx < 4 else ""
                spells_text += f"{emoji} **{spell['name']}**: {spell.get('description','N/A')}\n\n"
        else:
            passive_text = "N/A"
            spells_text = "N/A"

        query = urllib.parse.quote(f"{champ_display_name} LoL guia")
        video_link = f"https://www.youtube.com/results?search_query={query}"

        embed = discord.Embed(
            title=f"{champ_display_name} - {champ_title}",
            description=f"{tags_text}",
            color=embed_color
        )
        embed.set_image(url=champ_icon_gif)
        embed.set_thumbnail(url=champ_icon_static)
        embed.add_field(name="📊 Stats Base", value=stats_text, inline=False)
        embed.add_field(name="💤 Passiva", value=passive_text, inline=False)
        embed.add_field(name="💥 Habilidades", value=spells_text, inline=False)
        embed.add_field(name="🎬 Dicas/Vídeos", value=f"[Clique aqui]({video_link})", inline=False)
        embed.set_footer(text=f"Patch {self.patch} | Dados via Data Dragon")

        await interaction.followup.send(embed=embed, ephemeral=True)

    def cog_unload(self):
        self.bot.loop.create_task(self.session.close())

async def setup(bot):
    await bot.add_cog(Champion(bot))
