import discord
from discord.ext import commands
from discord import app_commands
import functools
from utils.logger import send_log
from discord.ui import View, Button


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


class HelpView(View):
    def __init__(self, bot, user):
        super().__init__(timeout=180)
        self.bot = bot
        self.user = user

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user.id:
            await interaction.response.send_message(
                "❌ Apenas quem solicitou pode usar este painel.", ephemeral=True
            )
            return False
        return True


    async def update_embed(self, interaction: discord.Interaction, title: str, description: str, color: discord.Color):
        embed = discord.Embed(title=title, description=description, color=color)
        await interaction.response.edit_message(embed=embed, view=self)

  
    @discord.ui.button(label="🔧 Administração", style=discord.ButtonStyle.primary, custom_id="help_admin")
    async def admin_button(self, interaction: discord.Interaction, button: Button):
        desc = (
            "🛠️ **/setxp** — Define XP, vitórias e derrotas.\n"
            "🧹 **/clsdata** — Zera todos os dados.\n"
            "🔄 **/updata** — Atualiza todos os dados.\n"
            "❌ **/delxp** — Zera apenas o XP."
        )
        await self.update_embed(interaction, "🔧 Administração", desc, discord.Color.blue())

    @discord.ui.button(label="🛡️ Champion", style=discord.ButtonStyle.secondary, custom_id="help_champion")
    async def champion_button(self, interaction: discord.Interaction, button: Button):
        desc = "🎮 **/champion** — Escolhe um champion aleatório do LoL de acordo com a lane."
        await self.update_embed(interaction, "🛡️ Champion", desc, discord.Color.dark_blue())

    @discord.ui.button(label="💬 Interação", style=discord.ButtonStyle.success, custom_id="help_interacao")
    async def interacao_button(self, interaction: discord.Interaction, button: Button):
        desc = (
            "⏱️ 15 min em chat de voz = 15 XP\n"
            "💬 10 min em chat de texto = 10 XP\n"
            "👤 **/info** — Veja informações de um usuário do servidor\n"
            "🏅 **/givebadge** — Dar badge a um usuário (admin)\n"
            "❌ **/removebadge** — Remover badge de um usuário (admin)"
        )
        await self.update_embed(interaction, "💬 Interação", desc, discord.Color.green())

    @discord.ui.button(label="🛒 Loja", style=discord.ButtonStyle.primary, custom_id="help_loja")
    async def loja_button(self, interaction: discord.Interaction, button: Button):
        desc = (
            "🛍️ **/loja** — Abre a loja\n"
            "⚙️ **/cfg** — Configurações da compra do usuário\n"
            "🖌️ **/cfgname** — Configura o nome\n"
            "🎨 **/cfgcolor** — Configura a cor\n"
            "📞 **/cfgcall** — Configura a call\n"
            "🏷️ **/addtag** — Adiciona tag para alguém\n"
            "🆕 **/nvitem** — Adiciona novo item à loja personalizada"
        )
        await self.update_embed(interaction, "🛒 Loja", desc, discord.Color.gold())

    @discord.ui.button(label="⚖️ Moderação", style=discord.ButtonStyle.danger, custom_id="help_moderacao")
    async def moderacao_button(self, interaction: discord.Interaction, button: Button):
        desc = (
            "🔇 **/mute** — Muta um usuário\n"
            "⛔ **/ban** — Bane um usuário\n"
            "📜 **/punishments** — Mostra histórico de punições"
        )
        await self.update_embed(interaction, "⚖️ Moderação", desc, discord.Color.red())

    @discord.ui.button(label="🎶 Música", style=discord.ButtonStyle.secondary, custom_id="help_musica")
    async def musica_button(self, interaction: discord.Interaction, button: Button):
        desc = (
            "▶️ **/play** — Toca uma música\n"
            "⏯️ **/resume** — Continua a música pausada\n"
            "⏸️ **/pause** — Pausa a música\n"
            "🔁 **/loop** — Define loop\n"
            "📜 **/queue** — Mostra a fila\n"
            "⏭️ **/skip** — Pula a música atual\n"
            "🔀 **/shuffle** — Embaralha a fila"
        )
        await self.update_embed(interaction, "🎶 Música", desc, discord.Color.purple())

    @discord.ui.button(label="😂 Social", style=discord.ButtonStyle.success, custom_id="help_social")
    async def social_button(self, interaction: discord.Interaction, button: Button):
        desc = (
            "🖼️ **/meme** — Envia um meme aleatório\n"
            "💞 **/casar** — Pede um usuário em casamento\n"
            "💔 **/divorcio** — Pede divórcio"
        )
        await self.update_embed(interaction, "😂 Social", desc, discord.Color.orange())

    @discord.ui.button(label="🧠 Challenge", style=discord.ButtonStyle.primary, custom_id="help_challenge")
    async def challenge_button(self, interaction: discord.Interaction, button: Button):
        desc = (
            "🏁 **/challenge_start** — Cria um novo desafio (ADM)\n"
            "📋 **/entrar** — Entrar no desafio atual\n"
            "🚪 **/sair_time** — Sair do time atual\n"
            "❌ **/sair_desafio** — Sair completamente do desafio\n"
            "🎲 **/sortear_times** — Sorteia times do desafio (ADM)\n"
            "🕹️ **/ver_times** — Mostra todos os times e informações do desafio\n"
            "👥 **/participants** — Mostra todos os participantes do desafio (ADM)\n"
            "🏁 **/end_challenge** — Encerra o desafio ativo (ADM)"
        )
        await self.update_embed(interaction, "🧠 Challenge", desc, discord.Color.teal())

    @discord.ui.button(label="📊 XP", style=discord.ButtonStyle.secondary, custom_id="help_xp")
    async def xp_button(self, interaction: discord.Interaction, button: Button):
        desc = (
            "👤 **/getxp** — Veja seus dados de XP\n"
            "🏆 **/ranking** — Ranking dos 10 usuários com mais XP"
        )
        await self.update_embed(interaction, "📊 XP", desc, discord.Color.green())


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
            description="Clique nos botões abaixo para navegar entre as categorias de comandos.",
            color=discord.Color.from_rgb(88, 101, 242)
        )
        embed.set_thumbnail(url=self.bot.user.avatar.url if self.bot.user.avatar else None)
        view = HelpView(self.bot, interaction.user)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Misc(bot))
