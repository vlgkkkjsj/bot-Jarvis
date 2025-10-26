import discord
from discord.ext import commands
from discord import app_commands
import db
import math
import functools
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


class XPView(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=60)
        self.bot = bot

    @discord.ui.button(label="🏆 Ver Ranking", style=discord.ButtonStyle.primary, emoji="📊")
    async def ranking_button(self, interaction: discord.Interaction, button: discord.ui.Button):
       cog: XP = self.bot.get_cog("XP")
       if cog:
           await cog.send_ranking(interaction)
       else:
           await interaction.response.send_message("⚠️ Ranking não disponível.", ephemeral=True)

class RankingView(discord.ui.View):
    def __init__(self, bot, interaction, data_func):
        super().__init__(timeout=60)
        self.bot = bot
        self.interaction = interaction
        self.data_func = data_func
        self.current_page = 0
        self.category = "xp"

        self.top_data = self.data_func(self.category)
        self.total_pages = math.ceil(len(self.top_data) / 10) or 1

    async def update_embed(self, interaction: discord.Interaction):
        start = self.current_page * 10
        end = start + 10
        page_data = self.top_data[start:end]
        guild = self.interaction.guild

        embed = discord.Embed(
            title=f"🏆 Ranking de {self.category.capitalize()}",
            description=f"Página {self.current_page + 1}/{self.total_pages}",
            color=discord.Color.gold()
        )

        for i, (user_id, xp, vitorias, derrotas) in enumerate(page_data, start=start + 1):
            try:
                user = guild.get_member(user_id) or await self.bot.fetch_user(user_id)
            except:
                continue

            medalha = (
                "🥇" if i == 1 else
                "🥈" if i == 2 else
                "🥉" if i == 3 else
                f"🔹 **#{i}**"
            )

            if self.category == "xp":
                valor = f"✨ **XP:** {xp}"
            elif self.category == "vitorias":
                valor = f"🏆 **Vitórias:** {vitorias}"
            else:
                valor = f"💀 **Derrotas:** {derrotas}"

            embed.add_field(
                name=f"{medalha} {user.display_name}",
                value=f"> {valor}",
                inline=False
            )

        if page_data:
            top1_user = guild.get_member(page_data[0][0]) or await self.bot.fetch_user(page_data[0][0])
            embed.set_thumbnail(url=top1_user.display_avatar.url)

        user_id = self.interaction.user.id
        for i, (uid, xp, v, d) in enumerate(self.top_data, start=1):
            if uid == user_id:
                stat = xp if self.category == "xp" else v if self.category == "vitorias" else d
                embed.set_footer(text=f"📍 Você está na posição #{i} ({self.category}: {stat})")
                break
        else:
            embed.set_footer(text="📍 Você ainda não entrou no ranking!")

        try:
            await interaction.response.edit_message(embed=embed, view=self)
        except discord.InteractionResponded:
            await interaction.edit_original_response(embed=embed, view=self)

    @discord.ui.button(label="◀️", style=discord.ButtonStyle.secondary)
    async def prev_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.interaction.user:
            return await interaction.response.send_message("⛔ Apenas quem usou o comando pode interagir.", ephemeral=True)
        if self.current_page > 0:
            self.current_page -= 1
            await self.update_embed(interaction)
        else:
            await interaction.response.defer()

    @discord.ui.button(label="▶️", style=discord.ButtonStyle.secondary)
    async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.interaction.user:
            return await interaction.response.send_message("⛔ Apenas quem usou o comando pode interagir.", ephemeral=True)
        if self.current_page < self.total_pages - 1:
            self.current_page += 1
            await self.update_embed(interaction)
        else:
            await interaction.response.defer()

    @discord.ui.button(label="XP", style=discord.ButtonStyle.primary)
    async def sort_xp(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.interaction.user:
            return await interaction.response.send_message("⛔ Apenas quem usou o comando pode interagir.", ephemeral=True)
        self.category = "xp"
        self.top_data = self.data_func("xp")
        self.current_page = 0
        self.total_pages = math.ceil(len(self.top_data) / 10) or 1
        await self.update_embed(interaction)

    @discord.ui.button(label="Vitórias", style=discord.ButtonStyle.success)
    async def sort_vitorias(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.interaction.user:
            return await interaction.response.send_message("⛔ Apenas quem usou o comando pode interagir.", ephemeral=True)
        self.category = "vitorias"
        self.top_data = self.data_func("vitorias")
        self.current_page = 0
        self.total_pages = math.ceil(len(self.top_data) / 10) or 1
        await self.update_embed(interaction)

    @discord.ui.button(label="Derrotas", style=discord.ButtonStyle.danger)
    async def sort_derrotas(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.interaction.user:
            return await interaction.response.send_message("⛔ Apenas quem usou o comando pode interagir.", ephemeral=True)
        self.category = "derrotas"
        self.top_data = self.data_func("derrotas")
        self.current_page = 0
        self.total_pages = math.ceil(len(self.top_data) / 10) or 1
        await self.update_embed(interaction)

class XP(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        
    @app_commands.command(name='getxp', description='Visualiza o XP, vitórias e derrotas de um usuário')
    @log_command(generic_title, generic_fields)
    @app_commands.describe(member='O usuário que você deseja consultar')
    async def getxp(self, interaction: discord.Interaction, member: discord.Member | None = None) -> bool:
        member = member or interaction.user
        guild_id = interaction.guild.id

        db.ensure_user_exists(member.id, guild_id)
        data = db.get_user_data(member.id, guild_id)

        if not data:
            embed = discord.Embed(
                title="❌ Nenhum dado encontrado",
                description=f"{member.mention} ainda não tem registros de XP.",
                color=discord.Color.red()
            )
            embed.set_thumbnail(url=interaction.client.user.display_avatar.url)
            embed.set_footer(text="Jogue e envie mensagens para ganhar XP!")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return False

        xp, vitorias, derrotas = data
        total = vitorias + derrotas
        winrate = f"{(vitorias / total * 100):.1f}%" if total > 0 else "N/A"

        level = int((xp / 100) ** 0.5)
        xp_next = (level + 1) ** 2 * 100
        xp_needed = xp_next - xp
        filled = int((xp / xp_next) * 10)
        bar = "█" * filled + "░" * (10 - filled)

        embed = discord.Embed(
            title=f"📊 Estatísticas de {member.display_name}",
            color=discord.Color.blurple()
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="🧬 Nível", value=f"**{level}**", inline=True)
        embed.add_field(name="✨ XP", value=f"{xp:,}", inline=True)
        embed.add_field(name="🏆 Vitórias", value=f"{vitorias}", inline=True)
        embed.add_field(name="💀 Derrotas", value=f"{derrotas}", inline=True)
        embed.add_field(name="📈 Winrate", value=winrate, inline=True)
        embed.add_field(name="⬆️ Próximo nível", value=f"{xp_needed} XP restantes", inline=False)
        embed.add_field(name="▰ Progresso", value=f"`{bar}`", inline=False)
        embed.set_footer(
            text=f"Solicitado por {interaction.user.display_name}",
            icon_url=interaction.user.display_avatar.url
        )
        view = XPView(self.bot)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        return True


    async def send_ranking(self, interaction: discord.Interaction):
        guild_id = interaction.guild.id

        def get_data(tipo):
            data = db.get_top_users(guild_id)
            if tipo == "xp":
                return sorted(data, key=lambda x: x[1], reverse=True)
            elif tipo == "vitorias":
                return sorted(data, key=lambda x: x[2], reverse=True)
            else:
                return sorted(data, key=lambda x: x[3], reverse=True)

        view = RankingView(self.bot, interaction, get_data)
        embed = discord.Embed(
            title="🏆 Ranking do Servidor",
            description="Carregando dados...",
            color=discord.Color.gold()
        )
        await interaction.response.send_message(embed=embed, view=view)
        await view.update_embed(interaction)

    @app_commands.command(name="ranking", description="Veja o ranking do servidor")
    async def ranking(self, interaction: discord.Interaction):
        await self.send_ranking(interaction)

async def setup(bot: commands.Bot):
    await bot.add_cog(XP(bot))