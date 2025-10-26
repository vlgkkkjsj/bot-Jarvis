import discord
from discord.ext import commands, tasks
from discord import app_commands, ui
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


class SetXPModal(ui.Modal, title="Definir XP e Estatísticas"):
    def __init__(self, member: discord.Member, triggering_interaction: discord.Interaction):
        super().__init__()
        self.member = member
        self.triggering_interaction = triggering_interaction

        self.xp = ui.TextInput(label="XP", placeholder="Ex: 1200", required=True)
        self.vitorias = ui.TextInput(label="Vitórias", placeholder="Ex: 10", required=True)
        self.derrotas = ui.TextInput(label="Derrotas", placeholder="Ex: 3", required=True)

        self.add_item(self.xp)
        self.add_item(self.vitorias)
        self.add_item(self.derrotas)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            xp = int(self.xp.value)
            vitorias = int(self.vitorias.value)
            derrotas = int(self.derrotas.value)

            if any(n < 0 for n in [xp, vitorias, derrotas]):
                embed = discord.Embed(
                    title="❌ Erro nos dados fornecidos",
                    description="Nenhum dos valores pode ser negativo.",
                    color=discord.Color.red()
                )
                return await interaction.response.send_message(embed=embed, ephemeral=True)

            db.set_user_data(self.member.id, interaction.guild.id, xp, vitorias, derrotas)

            embed = discord.Embed(
                title="✅ Dados cadastrados",
                description=f"Estatísticas de {self.member.mention} atualizadas com sucesso!",
                color=discord.Color.green()
            )
            embed.add_field(name="✨ XP", value=str(xp))
            embed.add_field(name="🏆 Vitórias", value=str(vitorias))
            embed.add_field(name="💀 Derrotas", value=str(derrotas))
            embed.set_thumbnail(url=self.member.display_avatar.url)
            embed.set_footer(text=f"Solicitado por {interaction.user}", icon_url=interaction.user.display_avatar.url)

            await interaction.response.send_message(embed=embed, ephemeral=True)

            await send_log(interaction, "📊 XP Atualizado via Modal", {
                "👤 Usuário": f"{interaction.user} ({interaction.user.id})",
                "🎯 Alvo": f"{self.member} ({self.member.id})",
                "XP": str(xp),
                "Vitórias": str(vitorias),
                "Derrotas": str(derrotas)
            })

        except ValueError:
            await interaction.response.send_message("❌ Os valores devem ser números inteiros.", ephemeral=True)



class SilentUserSelect(ui.UserSelect):
    async def callback(self, interaction: discord.Interaction):

        await interaction.response.defer()

        if hasattr(self, "view") and isinstance(self.view, MemberSelectView):
            self.view.selected_member = self.values[0]
            self.view.confirm_button.disabled = False
            try:
                await interaction.edit_original_response(view=self.view)
            except Exception:
                pass


class MemberSelectView(ui.View):
    def __init__(self, on_confirm_callback, timeout: int = 60):
 
        super().__init__(timeout=timeout)
        self.on_confirm_callback = on_confirm_callback
        self.selected_member: discord.Member | None = None


        self.member_select = SilentUserSelect(placeholder="Selecione um membro", min_values=1, max_values=1)
        self.add_item(self.member_select)


        self.confirm_button = ui.Button(label="Confirmar", style=discord.ButtonStyle.green, disabled=True)
        self.confirm_button.callback = self._confirm_callback
        self.add_item(self.confirm_button)

    async def _confirm_callback(self, interaction: discord.Interaction):

        if not self.selected_member:
            return await interaction.response.send_message("❌ Selecione um membro primeiro.", ephemeral=True)

        await self.on_confirm_callback(interaction, self.selected_member)
        self.stop()



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


    @app_commands.command(name="setxp", description="Define o XP, vitórias e derrotas de um membro (via modal)")
    @app_commands.checks.has_permissions(administrator=True)
    async def setxp(self, interaction: discord.Interaction):

        
        async def on_confirm(inter: discord.Interaction, member: discord.Member):

            await inter.response.send_modal(SetXPModal(member, inter))

        view = MemberSelectView(on_confirm)
        await interaction.response.send_message("Selecione o membro para editar:", view=view, ephemeral=True)

    @setxp.error
    async def setxp_error(self, interaction: discord.Interaction, error):
        if isinstance(error, app_commands.errors.MissingPermissions):
            await interaction.response.send_message("❌ Você não tem permissão para isso.", ephemeral=True)
        else:
            await interaction.response.send_message(f"Erro desconhecido: {error}", ephemeral=True)

    @app_commands.command(name='clsdata', description='Reseta todos os dados de um membro')
    @app_commands.checks.has_permissions(administrator=True)
    async def clear_data(self, interaction: discord.Interaction):


        async def confirmar(inter: discord.Interaction, member: discord.Member):
            await inter.response.defer(ephemeral=True)
            db.clear_user_data(member.id, inter.guild.id)

            embed = discord.Embed(
                title="🧹 Dados Resetados",
                description=f"Todas as estatísticas de {member.mention} foram zeradas com sucesso!",
                color=discord.Color.orange()
            )
            embed.set_thumbnail(url=member.display_avatar.url)
            embed.set_footer(text=f"Solicitado por {inter.user.display_name}", icon_url=inter.user.display_avatar.url)
            await inter.followup.send(embed=embed, ephemeral=True)


            await send_log(inter, "🧹 Dados Resetados", {
                "👤 Usuário": f"{inter.user} ({inter.user.id})",
                "🎯 Alvo": f"{member} ({member.id})"
            })

        view = MemberSelectView(confirmar)
        await interaction.response.send_message("Selecione um membro para resetar os dados:", view=view, ephemeral=True)

    @app_commands.command(name='updata', description="Atualiza todos os dados de um membro")
    @app_commands.checks.has_permissions(administrator=True)
    async def update_user_data(self, interaction: discord.Interaction):

        
        async def confirmar(inter: discord.Interaction, member: discord.Member):

            await inter.response.send_modal(SetXPModal(member, inter))

        view = MemberSelectView(confirmar)
        await interaction.response.send_message("Selecione um membro para atualizar os dados:", view=view, ephemeral=True)

    @app_commands.command(name='delxp', description='Zera apenas o XP de um usuário')
    @app_commands.checks.has_permissions(administrator=True)
    async def delxp(self, interaction: discord.Interaction):

        async def confirmar(inter: discord.Interaction, member: discord.Member):
            await inter.response.defer(ephemeral=True)
            db.reset_user_xp(member.id, inter.guild.id)

            embed = discord.Embed(
                title="💤 XP Resetado",
                description=f"O XP de {member.mention} foi zerado com sucesso!",
                color=discord.Color.red()
            )
            embed.set_thumbnail(url=member.display_avatar.url)
            embed.set_footer(text=f"Solicitado por {inter.user.display_name}", icon_url=inter.user.display_avatar.url)
            await inter.followup.send(embed=embed, ephemeral=True)

            await send_log(inter, "💤 XP Resetado", {
                "👤 Usuário": f"{inter.user} ({inter.user.id})",
                "🎯 Alvo": f"{member} ({member.id})"
            })

        view = MemberSelectView(confirmar)
        await interaction.response.send_message("Selecione um membro para zerar o XP:", view=view, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Admin(bot))
