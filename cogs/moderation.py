import discord
from discord.ext import commands
from discord import app_commands
from typing import Callable, Awaitable
import asyncio
import db



def _is_media(att: discord.Attachment | None) -> bool:
    return bool(
        att
        and att.content_type
        and (att.content_type.startswith("image/") or att.content_type.startswith("video/"))
    )


async def _safe_dm(member: discord.Member, embed: discord.Embed) -> None:
    try:
        await member.send(embed=embed)
    except discord.Forbidden:
        pass
    except discord.HTTPException:
        pass

async def _safe_dm(member: discord.Member, embed: discord.Embed):
    try:
        await member.send(embed=embed)
    except (discord.Forbidden, discord.HTTPException):
        pass

class ConfirmActionView(discord.ui.View):
    def __init__(
        self,
        interaction: discord.Interaction,
        apply_callback: Callable[[], Awaitable[discord.Embed]],
        *,
        confirm_label: str = "✅ Confirmar",
        cancel_label: str = "❌ Cancelar",
        cancel_message: str = "Ação cancelada.",
        timeout_message: str = "Tempo esgotado, operação cancelada.",
        timeout: int = 30
    ):
        super().__init__(timeout=timeout)
        self.interaction = interaction
        self.apply_callback = apply_callback
        self.confirm_label = confirm_label
        self.cancel_label = cancel_label
        self.cancel_message = cancel_message
        self.timeout_message = timeout_message
        self.result_embed: discord.Embed | None = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user != self.interaction.user:
            await interaction.response.send_message(
                "❌ Apenas quem iniciou o comando pode usar estes botões.", ephemeral=True
            )
            return False
        return True

    async def _disable_all_buttons(self):
        for child in self.children:
            child.disabled = True
        try:
            if not self.interaction.response.is_done():
                await self.interaction.response.edit_message(view=self)
            else:
                await self.interaction.edit_original_response(view=self)
        except discord.HTTPException:
            pass

    @discord.ui.button(label="✅ Confirmar", style=discord.ButtonStyle.success)
    async def confirm_button(self, interaction: discord.Interaction, button: discord.ui.Button):

        await self._disable_all_buttons()
        try:
            self.result_embed = await self.apply_callback()

            if not interaction.response.is_done():
                await interaction.response.edit_message(embed=self.result_embed, view=self)
            else:
                await interaction.followup.send(embed=self.result_embed, ephemeral=True)
        except Exception as e:
            content = f"❌ Ocorreu um erro: {e}"
            if not interaction.response.is_done():
                await interaction.response.edit_message(content=content, embed=None, view=self)
            else:
                await interaction.followup.send(content=content, ephemeral=True)
        finally:
            self.stop()

    @discord.ui.button(label="❌ Cancelar", style=discord.ButtonStyle.secondary)
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._disable_all_buttons()
        try:
            if not interaction.response.is_done():
                await interaction.response.edit_message(content=self.cancel_message, embed=None, view=self)
            else:
                await interaction.followup.send(content=self.cancel_message, ephemeral=True)
        finally:
            self.stop()

    async def on_timeout(self) -> None:
        await self._disable_all_buttons()
        try:
            if not self.interaction.response.is_done():
                await self.interaction.edit_original_response(content=self.timeout_message, view=self)
            else:
                await self.interaction.followup.send(content=self.timeout_message, ephemeral=True)
        except Exception:
            pass
        
class Moderation(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.log_channel_name = "logs-punições"
        
    async def get_or_create_log_channel(self, guild: discord.Guild)-> discord.TextChannel:
        
        channel = discord.utils.get(guild.text_channels, name = self.log_channel_name)
        if channel:
            return channel
        
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
        }
        for role in guild.roles:
            if role.permissions.administrator or role.permissions.kick_members or role.permissions.manage_guild:
                overwrites[role] = discord.PermissionOverwrite(view_channel=True, send_messages=False)

        channel = await guild.create_text_channel(self.log_channel_name, overwrites=overwrites, reason="Canal de logs de punições")
        return channel            

    async def type_autocomplete(self, interaction: discord.Interaction, current: str):
        options = ["chat", "call"]
        return [app_commands.Choice(name=o.capitalize(), value=o) for o in options if current.lower() in o]

    @app_commands.command(name='mute',description='Muta um usuário (chat ou voz) com confirmação e DM.')
    @app_commands.describe(
        member="Usuário a ser mutado",
        duration="Duração em minutos (padrão: 10)",
        tipo="Tipo de mute: chat ou call",
        prova="Imagem ou vídeo contendo provas"
    )
    @app_commands.autocomplete(tipo=type_autocomplete)
    @app_commands.checks.has_permissions(manage_roles=True, mute_members=True)
    async def mute(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        prova: discord.Attachment, 
        duration: int | None = 10,
        tipo: str = "chat",
    ):
        if member == interaction.user:
            return await interaction.response.send_message("❌ Você não pode se mutar.", ephemeral=True)

        if member.top_role >= interaction.user.top_role and interaction.user != interaction.guild.owner:
            return await interaction.response.send_message(
                "❌ Você não pode mutar alguém com cargo igual ou maior que o seu.", ephemeral=True
            )

        if member.top_role >= interaction.guild.me.top_role:
            return await interaction.response.send_message(
                "❌ Não posso interagir com alguém com cargo igual ou maior que o meu.", ephemeral=True
            )

        if duration is None or duration <= 0:
            duration = 10

        if prova and not _is_media(prova):
            return await interaction.response.send_message(
                "❌ O arquivo enviado precisa ser **imagem** ou **vídeo**.", ephemeral=True
            )

        tipo = tipo.lower()
        if tipo not in ("chat", "call"):
            return await interaction.response.send_message("❌ Tipo inválido. Use `chat` ou `call`.", ephemeral=True)

        confirm = discord.Embed(
            title="🔇 Confirmar Mute",
            description=f"Tem certeza que deseja mutar **{member}**?",
            color=discord.Color.orange()
        )
        confirm.add_field(name="⏱ Duração", value=f"{duration} minutos", inline=False)
        confirm.add_field(name="🔨 Tipo", value=tipo.capitalize(), inline=False)
        confirm.add_field(name="👤 Usuário", value=f"{member} ({member.id})", inline=False)
        if prova:
            if prova.content_type.startswith("image/"):
                confirm.set_image(url=prova.url)
            else:
                confirm.add_field(name="📎 Prova", value=f"[Abrir arquivo]({prova.url})", inline=False)

        async def aplicar_mute() -> discord.Embed:

            dm = discord.Embed(
                title="🔇 Você foi mutado",
                description=f"Você recebeu um mute no servidor **{interaction.guild.name}**.",
                color=discord.Color.orange()
            )
            dm.add_field(name="⏱ Duração", value=f"{duration} minutos", inline=False)
            dm.add_field(name="🔨 Tipo", value=tipo.capitalize(), inline=False)
            dm.add_field(name="🔨 Staff", value=f"{interaction.user} ({interaction.user.id})", inline=False)
            if prova:
                if prova.content_type.startswith("image/"):
                    dm.set_image(url=prova.url)
                else:
                    dm.add_field(name="📎 Prova", value=f"[Abrir arquivo]({prova.url})", inline=False)
            await _safe_dm(member, dm)

            role = discord.utils.get(interaction.guild.roles, name="Mutado")
            if not role:
                role = await interaction.guild.create_role(name="Mutado", reason="Cargo de mute")
                for ch in interaction.guild.channels:
                    try:
                        perms = {}
                        if isinstance(ch, discord.TextChannel):
                            perms = {"send_messages": False}
                        elif isinstance(ch, discord.VoiceChannel):
                            perms = {"speak": False}
                        await ch.set_permissions(role, **perms)
                    except Exception:
                        pass

            if tipo == "chat":
                await member.add_roles(role, reason=f"Mute de chat por {duration} min")
                asyncio.create_task(self.remover_mute_chat(interaction.guild, member, role, duration))
            else:
                if not member.voice:
                    return discord.Embed(
                        title="⚠️ Ação não aplicada",
                        description=f"{member.mention} não está em um canal de voz.",
                        color=discord.Color.yellow()
                    )
                if role not in member.roles:
                    await member.add_roles(role, reason=f"Mute de voz por {duration} min")
                await member.edit(mute=True, reason=f"Mute de voz por {duration} min")
                asyncio.create_task(self.remover_mute_voz(member, role, duration, tipo))

            db.add_punishment(
                member.id, interaction.guild.id, interaction.user.id,
                f"mute-{tipo}", duration, prova.url if prova else None
            )

            log_channel = await self.get_or_create_log_channel(interaction.guild)
            log = discord.Embed(title="🔇 Mute Aplicado", color=discord.Color.orange())
            log.add_field(name="👤 Usuário", value=f"{member} ({member.id})")
            log.add_field(name="Staff", value=f"{interaction.user}")
            log.add_field(name="⏱ Duração", value=f"{duration} minutos")
            log.add_field(name="📅 Data", value=discord.utils.format_dt(discord.utils.utcnow(), style='F'))
            if prova:
                if prova.content_type.startswith("image/"):
                    log.set_image(url=prova.url)
                else:
                    log.add_field(name="📎 Prova", value=f"[Abrir arquivo]({prova.url})")
            await log_channel.send(embed=log)

            done = discord.Embed(
                title="🔇 Mute Aplicado",
                description=f"{member.mention} mutado por {duration} min.",
                color=discord.Color.orange()
            )
            done.add_field(name="Staff", value=f"{interaction.user}")
            if prova:
                if prova.content_type.startswith("image/"):
                    done.set_image(url=prova.url)
                else:
                    done.add_field(name="📎 Prova", value=f"[Abrir arquivo]({prova.url})")
            return done

        view = ConfirmActionView(interaction, aplicar_mute)
        await interaction.response.send_message(embed=confirm, view=view, ephemeral=True)


    async def remover_mute_chat(self, guild, member, role, duration):
        await asyncio.sleep(duration * 60)
        try:
            member = await guild.fetch_member(member.id)
            if role in member.roles:
                await member.remove_roles(role, reason="Mute expirado")

            un = discord.Embed(
                title="🔊 Você foi desmutado",
                description=f"Seu mute no servidor **{guild.name}** foi retirado.",
                color=discord.Color.green()
            )
            await _safe_dm(member, un)
        except Exception as e:
            print(f"Erro ao remover mute chat: {e}")
            
            
    async def remover_mute_voz(self, member, role, duration, tipo):
        await asyncio.sleep(duration * 60)
        try:
            if role in member.roles:
                await member.remove_roles(role, reason="Mute expirado")
            if tipo == "call" and member.voice:
                await member.edit(mute=False, reason="Mute expirado")
            un = discord.Embed(
                title="🔊 Você foi desmutado",
                description=f"Seu mute no servidor foi retirado.",
                color=discord.Color.green()
            )
            await _safe_dm(member, un)
        except Exception:
            pass

    @app_commands.command(name="ban", description="Bane um usuário com confirmação e DM (prova obrigatória: imagem/vídeo).")
    @app_commands.describe(
        member="Usuário a ser banido",
        reason="Motivo do banimento",
        prova="Imagem ou vídeo contendo provas"
    )
    @app_commands.checks.has_permissions(ban_members=True)
    async def ban(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        reason: str,
        prova: discord.Attachment
    ):
        if member == interaction.user:
            return await interaction.response.send_message("❌ Você não pode se banir.", ephemeral=True)

        if member.top_role >= interaction.user.top_role and interaction.user != interaction.guild.owner:
            return await interaction.response.send_message("❌ Você não pode banir alguém com cargo igual ou maior que o seu.", ephemeral=True)

        if member.top_role >= interaction.guild.me.top_role:
            return await interaction.response.send_message("❌ Não posso interagir com alguém com cargo igual ou maior que o meu.", ephemeral=True)

        if not _is_media(prova):
            return await interaction.response.send_message("❌ O arquivo enviado precisa ser **imagem** ou **vídeo**.", ephemeral=True)

        confirm = discord.Embed(
            title="🚫 Confirmar Banimento",
            description=f"Tem certeza que deseja banir **{member}**?",
            color=discord.Color.red()
        )
        confirm.add_field(name="👤 Usuário", value=f"{member} ({member.id})", inline=False)
        confirm.add_field(name="📝 Motivo", value=reason, inline=False)
        confirm.add_field(name="🔨 Staff", value=f"{interaction.user} ({interaction.user.id})", inline=False)
        if prova.content_type.startswith("image/"):
            confirm.set_image(url=prova.url)
        else:
            confirm.add_field(name="📎 Prova", value=f"[Abrir vídeo]({prova.url})", inline=False)

        async def aplicar_ban() -> discord.Embed:
            dm = discord.Embed(
                title="🚫 Você foi banido",
                description=f"Você foi banido do servidor **{interaction.guild.name}**.",
                color=discord.Color.red()
            )
            dm.add_field(name="📝 Motivo", value=reason, inline=False)
            if prova.content_type.startswith("image/"):
                dm.set_image(url=prova.url)
            else:
                dm.add_field(name="📎 Prova", value=f"[Abrir arquivo]({prova.url})", inline=False)
            await _safe_dm(member, dm)

            await member.ban(reason=reason)
            db.add_punishment(member.id, interaction.guild.id, interaction.user.id, "ban", None, prova.url)
            log_channel = await self.get_or_create_log_channel(interaction.guild)

            log = discord.Embed(title="🚫 Banimento Registrado", color=discord.Color.red())
            log.add_field(name="👤 Usuário", value=f"{member} ({member.id})")
            log.add_field(name="Staff", value=f"{interaction.user}")
            log.add_field(name="📝 Motivo", value=reason)
            log.add_field(name="📅 Data", value=discord.utils.format_dt(discord.utils.utcnow(), style='F'))
            if prova.content_type.startswith("image/"):
                log.set_image(url=prova.url)
            else:
                log.add_field(name="📎 Prova", value=f"[Abrir arquivo]({prova.url})")
            await log_channel.send(embed=log)

            done = discord.Embed(
                title="🚫 Usuário Banido",
                color=discord.Color.red()
            )
            done.add_field(name="👤 Usuário", value=f"{member} ({member.id})", inline=False)
            done.add_field(name="📝 Motivo", value=reason, inline=False)
            done.add_field(name="🔨 Staff", value=f"{interaction.user} ({interaction.user.id})", inline=False)
            if prova.content_type.startswith("image/"):
                done.set_image(url=prova.url)
            else:
                done.add_field(name="📎 Prova", value=f"[Abrir arquivo]({prova.url})", inline=False)
            return done

        view = ConfirmActionView(interaction, aplicar_ban)
        await interaction.response.send_message(embed=confirm, view=view, ephemeral=True)

    @app_commands.command(name="punishments", description="Mostra o histórico de punições de um usuário.")
    @app_commands.describe(user="Usuário para ver o histórico")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def punishments(self, interaction: discord.Interaction, user: discord.Member):
        punishments = db.get_punishments(user.id, interaction.guild.id)
        if not punishments:
            return await interaction.response.send_message(f"✅ {user.mention} não possui punições registradas.", ephemeral=True)

        embed = discord.Embed(title=f"📜 Histórico de punições — {user}", color=discord.Color.blurple())
        embed.set_thumbnail(url=user.display_avatar.url)

        for i, p in enumerate(punishments[:10], start=1):
            staff_id = p[0]   
            tipo = p[1]      
            duracao = p[2]    
            data = p[3]       
            prova = p[4]     

            duracao_text = f"{duracao} min" if duracao else "Permanente"

            field_value = f"👮 **Staff:** <@{staff_id}>\n⏱ **Duração:** {duracao_text}\n📅 **Data:** {data[:19].replace('T', ' ')}"

            if prova:
                if any(prova.lower().endswith(ext) for ext in (".png", ".jpg", ".jpeg", ".gif", ".webp")):
                    embed.set_image(url=prova)
                else:
                    field_value += f"\n📎 **Prova:** [Abrir arquivo]({prova})"
            else:
                field_value += "\n📎 **Prova:** Nenhuma"

            embed.add_field(name=f"#{i} — {tipo.capitalize()}", value=field_value, inline=False)

        embed.set_footer(text=f"Total de punições: {db.count_punishments(user.id, interaction.guild.id)}")
        await interaction.response.send_message(embed=embed, ephemeral=True)
        
async def setup(bot: commands.Bot):
    await bot.add_cog(Moderation(bot))
