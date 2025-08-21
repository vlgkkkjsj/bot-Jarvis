import discord
from discord.ext import commands
from discord import app_commands
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


class Misc(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    
    @app_commands.command(name="ola", description="Saudação simples")
    @log_command(generic_title, generic_fields) 

    async def ola(self, interaction: discord.Interaction):
        await interaction.response.send_message(f"Olá, {interaction.user.name} 👋", ephemeral=True)
        return True
        
    @app_commands.command(name="help", description="Exibe a lista de comandos do bot")
    @log_command(generic_title, generic_fields) 

    async def help(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="✨ Painel de Ajuda – JarvisBot",
            description=(
                "Bem-vindo ao painel de ajuda!\n"
                "Aqui estão todos os comandos disponíveis organizados por categoria.\n"
                "Use-os com responsabilidade ⚙️"
            ),
            color=discord.Color.from_rgb(88, 101, 242) 
        )

        embed.set_thumbnail(url=interaction.client.user.avatar.url if interaction.client.user.avatar else None)

        embed.add_field(
            name="🔧 Administração",
            value=(
                "🛠️ **/setxp** — Define XP, vitórias e derrotas de um usuário.\n"
                "🔄 **/upddata** — Atualiza todos os dados de um usuário.\n"
                "🧹 **/cleardata** — Zera todos os dados de um usuário.\n"
                "❌ **/delxp** — Zera apenas o XP de um usuário.\n"
                "🛒 **/nwitem** — Adiciona um novo item à loja."
            ),
            inline=False
        )

        embed.add_field(
            name="📊 Utilitários",
            value=(
                "👤 **/getxp** — Veja seus dados de XP, vitórias e derrotas.\n"
                "🏆 **/ranking** — Mostra o ranking dos 10 usuários com mais XP.\n"
                "💼 **/loja** — Exibe todos os itens disponíveis na loja."
            ),
            inline=False
        )

        embed.add_field(
            name="💬 Diversão",
            value=(
                "👋 **/ola** — Receba uma saudação amigável.\n"
                "💡 Mais comandos divertidos serão adicionados em breve!"
            ),
            inline=False
        )

        embed.set_footer(
            text=f"Solicitado por {interaction.user.display_name} • JarvisBot",
            icon_url=interaction.user.avatar.url if interaction.user.avatar else interaction.user.default_avatar.url
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)
        return True

async def setup(bot: commands.Bot):
    await bot.add_cog(Misc(bot))
