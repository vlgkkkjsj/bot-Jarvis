import discord
from discord.ext import commands, tasks
from discord import app_commands
import db
from utils.logger import send_log
import functools

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

class Admin(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.sync_all_members.start()  

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        total = 0
        for member in guild.members:
            if not member.bot:
                await self.register_member(member)
                total += 1
        print(f"[INFO] Verificação inicial concluída para o servidor {guild.name}. {total} membros cadastrados.")

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        if not member.bot:
            await self.register_member(member)

    async def register_member(self, member: discord.Member):
        try:
            db.ensure_user_exists(member.id, member.guild.id)
            print(f"[INFO] Usuário {member} registrado automaticamente.")

            canal_log = discord.utils.get(member.guild.text_channels, name="bot-logs")
            if canal_log:
                embed = discord.Embed(
                    title="✅ Novo usuário cadastrado",
                    description=f"{member.mention} foi registrado automaticamente.",
                    color=discord.Color.green()
                )
                await canal_log.send(embed=embed)
        except Exception as e:
            print(f"[ERRO] Falha ao registrar {member}: {e}")

    @tasks.loop(hours=1)
    async def sync_all_members(self):
        for guild in self.bot.guilds:
            total = 0
            for member in guild.members:
                if not member.bot:
                    db.ensure_user_exists(member.id, guild.id)
                    total += 1
            print(f"[SYNC] {total} membros verificados/cadastrados no servidor {guild.name}.")

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        try:
            db.delete_user(member.id, member.guild.id)
            print(f"[INFO] Usuário {member} removido do DB (saiu de {member.guild.name}).")

            canal_log = discord.utils.get(member.guild.text_channels, name="bot-logs")
            if canal_log:
                embed = discord.Embed(
                    title="❌ Usuário removido",
                    description=f"{member.mention} saiu e seus dados foram excluídos.",
                    color=discord.Color.red()
                )
                await canal_log.send(embed=embed)

        except Exception as e:
            print(f"[ERRO] Falha ao remover {member}: {e}")

    @app_commands.command(name="setxp", description="Define o XP, vitórias e derrotas de um membro")
    @log_command(generic_title, generic_fields)
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(
        member="Membro a ser alterado",
        xp="Quantidade de XP",
        vitorias="Quantidade de vitórias",
        derrotas="Quantidade de derrotas"
    )
    async def setxp(self, interaction: discord.Interaction, member: discord.Member, xp: int, vitorias: int, derrotas: int):
        await interaction.response.defer(ephemeral=True)

        if any(n < 0 for n in [xp, vitorias, derrotas]):
            embed = discord.Embed(
                title="❌ Erro nos dados fornecidos",
                description="Nenhum dos valores pode ser negativo.",
                color=discord.Color.red()
            )
            embed.set_thumbnail(url=member.display_avatar.url)
            await interaction.followup.send(embed=embed, ephemeral=True)
            return False

        db.set_user_data(member.id, interaction.guild.id, xp, vitorias, derrotas)
        embed = discord.Embed(
            title="✅ Dados cadastrados",
            description=f'Dados de {member.mention} cadastrados com sucesso!',
            color=discord.Color.green()
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(text=f"Solicitado por {interaction.user}", icon_url=interaction.user.display_avatar.url)
        await interaction.followup.send(embed=embed, ephemeral=True, delete_after=5)
        return True

    @setxp.error
    async def setxp_error(self, interaction: discord.Interaction, error):
        if isinstance(error, app_commands.errors.MissingPermissions):
            await interaction.response.send_message("❌ Você não tem permissão para isso.", ephemeral=True)
        else:
            await interaction.response.send_message(f"Erro desconhecido: {error}", ephemeral=True)

    @app_commands.command(name='clsdata', description='Reseta todos os dados de um membro')
    @app_commands.checks.has_permissions(administrator=True)
    @log_command(generic_title, generic_fields)
    @app_commands.describe(member="Membro a ser resetado")
    async def clear_data(self, interaction: discord.Interaction, member: discord.Member):
        await interaction.response.defer(ephemeral=True)
        guild_id = interaction.guild.id
        db.clear_user_data(member.id, guild_id)

        embed = discord.Embed(
            title="🧹 Dados Resetados",
            description=f"Todas as estatísticas de {member.mention} foram zeradas com sucesso!",
            color=discord.Color.orange()
        )
        embed.set_thumbnail(url=interaction.client.user.avatar.url)
        embed.set_footer(
            text=f"Solicitado por {interaction.user.display_name}",
            icon_url=interaction.user.avatar.url if interaction.user.avatar else interaction.user.default_avatar.url
        )
        await interaction.followup.send(embed=embed, ephemeral=True)
        return True

    @app_commands.command(name='updata', description="Atualiza todos os dados de um membro")
    @app_commands.checks.has_permissions(administrator=True)
    @log_command(generic_title, generic_fields)
    @app_commands.describe(
        member="Membro a ser alterado",
        xp="Quantidade de XP",
        vitorias="Quantidade de vitórias",
        derrotas="Quantidade de derrotas"
    )
    async def update_user_data(self, interaction: discord.Interaction, member: discord.Member, xp: int, vitorias: int, derrotas: int):
        await interaction.response.defer(ephemeral=True)

        if any(n < 0 for n in [xp, vitorias, derrotas]):
            embed = discord.Embed(
                title="❌ Erro nos dados fornecidos",
                description="Nenhum dos valores pode ser negativo.",
                color=discord.Color.red()
            )
            embed.set_thumbnail(url=member.display_avatar.url)
            await interaction.followup.send(embed=embed, ephemeral=True)
            return False

        guild_id = interaction.guild.id
        db.update_user_data(member.id, guild_id, xp, vitorias, derrotas)

        total = vitorias + derrotas
        winrate = f"{(vitorias / total * 100):.1f}%" if total > 0 else "N/A"

        embed = discord.Embed(
            title="🧹 Dados Atualizados",
            description=f"Estatísticas de {member.mention} foram atualizadas com sucesso!",
            color=discord.Color.orange()
        )
        embed.set_thumbnail(url=interaction.client.user.avatar.url)
        embed.add_field(name="✨ XP", value=f"{xp}", inline=True)
        embed.add_field(name="🏆 Vitórias", value=f"{vitorias}", inline=True)
        embed.add_field(name="💀 Derrotas", value=f"{derrotas}", inline=True)
        embed.add_field(name="📈 Winrate", value=f"{winrate}", inline=False)
        embed.set_footer(
            text=f"Solicitado por {interaction.user.display_name}",
            icon_url=interaction.user.avatar.url if interaction.user.avatar else interaction.user.default_avatar.url
        )

        await interaction.followup.send(embed=embed, ephemeral=True)
        return True

    @app_commands.command(name='delxp', description='Zera apenas o XP de um usuário')
    @log_command(generic_title, generic_fields)
    @app_commands.describe(member="Membro a ter o XP zerado")
    async def delxp(self, interaction: discord.Interaction, member: discord.Member):
        await interaction.response.defer(ephemeral=True)
        db.reset_user_xp(member.id, interaction.guild.id)
        await interaction.followup.send(f'XP de {member.mention} foi zerado com sucesso.', ephemeral=True)
        return True

async def setup(bot: commands.Bot):
    await bot.add_cog(Admin(bot))

