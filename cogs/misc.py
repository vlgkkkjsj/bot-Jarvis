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
            description="Aqui estão todos os comandos disponíveis organizados por categoria. Use-os com responsabilidade ⚙️",
            color=discord.Color.from_rgb(88, 101, 242)
        )

        embed.set_thumbnail(url=self.bot.user.avatar.url if self.bot.user.avatar else None)

        embed.add_field(
            name="🔧 Administração",
            value=(
                "🛠️ **/setxp** — Define XP, vitórias e derrotas.\n"
                "🧹 **/clsdata** — Zera todos os dados.\n"
                "🔄 **/updata** — Atualiza todos os dados.\n"
                "❌ **/delxp** — Zera apenas o XP."
            ),
            inline=False
        )

        embed.add_field(
            name="🛡️ Champion",
            value="🎮 **/champion** — Escolhe um champion aleatório do LoL de acordo com a lane.",
            inline=False
        )

        embed.add_field(
            name="💬 Interação",
            value="⏱️ 15 min em chat de voz = 15 XP\n💬 10 min em chat de texto = 10 XP",
            inline=False
        )

        embed.add_field(
            name="🛒 Loja",
            value=(
                "🛍️ **/loja** — Abre a loja\n"
                "⚙️ **/cfg** — Configurações da compra do usuário\n"
                "🖌️ **/cfgname** — Configura o nome\n"
                "🎨 **/cfgcolor** — Configura a cor\n"
                "📞 **/cfgcall** — Configura a call\n"
                "🏷️ **/addtag** — Adiciona tag para alguém\n"
                "🆕 **/nvitem** — Adiciona novo item à loja personalizada"
            ),
            inline=False
        )

        embed.add_field(
            name="⚖️ Moderação",
            value="🔇 **/mute** — Muta um usuário\n⛔ **/ban** — Bane um usuário",
            inline=False
        )

        embed.add_field(
            name="🎶 Música",
            value=(
                "▶️ **/play** — Toca uma música\n"
                "⏯️ **/resume** — Continua a música pausada\n"
                "⏸️ **/pause** — Pausa a música\n"
                "🔁 **/loop** — Define loop\n"
                "📜 **/queue** — Mostra a fila\n"
                "⏭️ **/skip** — Pula a música atual\n"
                "🔀 **/shuffle** — Embaralha a fila"
            ),
            inline=False
        )

        embed.add_field(
            name="😂 Social",
            value="🖼️ **/meme** — Manda um meme aleatório",
            inline=False
        )

        embed.add_field(
            name="📊 XP",
            value="👤 **/getxp** — Veja seus dados de XP\n🏆 **/ranking** — Ranking dos 10 usuários com mais XP",
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
