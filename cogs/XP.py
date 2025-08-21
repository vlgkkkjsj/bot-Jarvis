import discord
from discord.ext import commands
from discord import app_commands
import db
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


class XP(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name='getxp', description='Visualiza o XP, vitórias e derrotas de um usuário')
    @log_command(generic_title, generic_fields)
    @app_commands.describe(member='O usuário que você deseja consultar')
    async def getxp(self, interaction: discord.Interaction, member: discord.Member | None = None)->bool:
        member = member or interaction.user
        guild_id = interaction.guild.id
        db.ensure_user_exists(member.id, guild_id)
        data = db.get_user_data(member.id, guild_id)

        if not data:
            embed = discord.Embed(
                title="❌ Nenhum dado registrado",
                description="Usuário informado sem registros",
                color=discord.Color.red()
            )
            embed.set_thumbnail(url=interaction.client.user.avatar.url)
            embed.set_footer(text="developed by sbbones :)")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return False
        else:
            xp, vitorias, derrotas = data
            embed = discord.Embed(
                title=f"📊 Estatísticas de {member.display_name}",
                color=discord.Color.blurple()
            )
            embed.set_thumbnail(url=member.avatar.url if member.avatar else member.default_avatar.url)
            embed.add_field(name="✨ XP", value=f"{xp}", inline=True)
            embed.add_field(name="🏆 Vitórias", value=f"{vitorias}", inline=True)
            embed.add_field(name="💀 Derrotas", value=f"{derrotas}", inline=True)
            total = vitorias + derrotas
            winrate = f"{(vitorias / total * 100):.1f}%" if total > 0 else "N/A"
            embed.add_field(name="📈 Winrate", value=f"{winrate}", inline=False)
            embed.set_footer(text=f"Solicitado por {interaction.user.display_name}",
                             icon_url=interaction.user.avatar.url if interaction.user.avatar else interaction.user.default_avatar.url)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return True
    @app_commands.command(name='ranking', description='Top 10 usuários com mais XP')
    @log_command(generic_title, generic_fields) 

    async def ranking(self, interaction: discord.Interaction):
        guild_id = interaction.guild.id
        top = db.get_top_users(guild_id, limit=10)

        if not top:
            await interaction.response.send_message("📉 Nenhum dado de usuário encontrado.")
            return False

        embed = discord.Embed(
            title="🏆 Ranking de XP",
            description="Confira os **TOP 10 usuários** com mais experiência!",
            color=discord.Color.gold()
        )

        for i, (user_id, xp, vitorias, derrotas) in enumerate(top, start=1):
            user = self.bot.get_user(user_id) or await self.bot.fetch_user(user_id)
            medalha = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"🔹 #{i}"
            embed.add_field(
                name=f"{medalha} {user.name}",
                value=(f"✨ **XP:** {xp}\n🏆 **Vitórias:** {vitorias}\n💀 **Derrotas:** {derrotas}"),
                inline=False
            )

        embed.set_thumbnail(url=interaction.client.user.avatar.url if interaction.client.user.avatar else interaction.client.user.default_avatar.url)
        embed.set_footer(text="📊 Use /getxp para ver seus próprios dados")
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return True
    
    
async def setup(bot: commands.Bot):
    await bot.add_cog(XP(bot))
