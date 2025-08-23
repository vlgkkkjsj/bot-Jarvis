import discord
from discord.ext import commands
from discord import app_commands
import asyncio



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



class ConfirmMuteView(discord.ui.View):

    def __init__(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        duration: int,
        tipo: str,
        prova: discord.Attachment,
        apply_callback 
    ):
        super().__init__(timeout=30)
        self.interaction = interaction
        self.member = member
        self.duration = duration
        self.tipo = tipo
        self.prova = prova
        self.apply_callback = apply_callback

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user != self.interaction.user:
            await interaction.response.send_message("❌ Apenas quem iniciou o comando pode usar estes botões.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="✅ Confirmar", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, _: discord.ui.Button):
        final_embed = await self.apply_callback()
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(content=None, embed=final_embed, view=self)
        self.stop()

    @discord.ui.button(label="❌ Cancelar", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, _: discord.ui.Button):
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(content="❌ Mute cancelado.", view=self)
        self.stop()

    async def on_timeout(self) -> None:
        for child in self.children:
            child.disabled = True
        if self.interaction.response.is_done():

            try:
                await self.interaction.edit_original_response(view=self)
            except discord.HTTPException:
                pass


class ConfirmBanView(discord.ui.View):

    def __init__(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        reason: str,
        prova: discord.Attachment,
        apply_callback  
    ):
        super().__init__(timeout=30)
        self.interaction = interaction
        self.member = member
        self.reason = reason
        self.prova = prova
        self.apply_callback = apply_callback

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user != self.interaction.user:
            await interaction.response.send_message("❌ Apenas quem iniciou o comando pode usar estes botões.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="✅ Confirmar", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, _: discord.ui.Button):
        final_embed = await self.apply_callback()
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(content=None, embed=final_embed, view=self)
        self.stop()

    @discord.ui.button(label="❌ Cancelar", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, _: discord.ui.Button):
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(content="❌ Banimento cancelado.", view=self)
        self.stop()

    async def on_timeout(self) -> None:
        for child in self.children:
            child.disabled = True
        if self.interaction.response.is_done():
            try:
                await self.interaction.edit_original_response(view=self)
            except discord.HTTPException:
                pass



class Moderation(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def type_autocomplete(self, interaction: discord.Interaction, current: str):
        options = ["chat", "call"]
        return [app_commands.Choice(name=o.capitalize(), value=o) for o in options if current.lower() in o]

    @app_commands.command(name='mute', description='Muta um usuário (chat ou voz) com confirmação e DM.')
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
        duration: int | None = 10,
        tipo: str = "chat",
        prova: discord.Attachment | None = None
    ):
        if member == interaction.user:
            return await interaction.response.send_message("❌ Você não pode se mutar.", ephemeral=True)

        if member.top_role >= interaction.user.top_role and interaction.user != interaction.guild.owner:
            return await interaction.response.send_message("❌ Você não pode mutar alguém com cargo igual ou maior que o seu.", ephemeral=True)

        if member.top_role >= interaction.guild.me.top_role:
            return await interaction.response.send_message("❌ Não posso interagir com alguém com cargo igual ou maior que o meu.", ephemeral=True)

        if duration is None or duration <= 0:
            duration = 10

        if not _is_media(prova):
            return await interaction.response.send_message("❌ O arquivo enviado precisa ser **imagem** ou **vídeo**.", ephemeral=True)

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
        if prova.content_type.startswith("image/"):
            confirm.set_image(url=prova.url)
        else:
            confirm.add_field(name="📎 Prova", value=f"[Abrir vídeo]({prova.url})", inline=False)

        async def aplicar_mute() -> discord.Embed:
            dm = discord.Embed(
                title="🔇 Você foi mutado",
                description=f"Você recebeu um mute no servidor **{interaction.guild.name}**.",
                color=discord.Color.orange()
            )
            dm.add_field(name="⏱ Duração", value=f"{duration} minutos", inline=False)
            dm.add_field(name="🔨 Tipo", value=tipo.capitalize(), inline=False)
            if prova.content_type.startswith("image/"):
                dm.set_image(url=prova.url)
            else:
                dm.add_field(name="📎 Prova", value=f"[Abrir arquivo]({prova.url})", inline=False)
            await _safe_dm(member, dm)

            if tipo == "chat":
                role = discord.utils.get(interaction.guild.roles, name="Mutado")
                if not role:
                    role = await interaction.guild.create_role(name="Mutado", reason="Cargo de mute (chat)")
                    for ch in interaction.guild.channels:
                        try:
                            await ch.set_permissions(role, send_messages=False, speak=False)
                        except Exception:
                            pass
                await member.add_roles(role, reason=f"Mute de chat por {duration} min")

                async def remover_mute_chat():
                    await asyncio.sleep(duration * 60)
                    try:
                        if role in member.roles:
                            await member.remove_roles(role, reason="Mute expirado")
                        # DM de desmute
                        un = discord.Embed(
                            title="🔊 Você foi desmutado",
                            description=f"Seu mute no servidor **{interaction.guild.name}** foi retirado.",
                            color=discord.Color.green()
                        )
                        await _safe_dm(member, un)
                    except Exception:
                        pass

                asyncio.create_task(remover_mute_chat())

                done = discord.Embed(
                    title="🔇 Mute Aplicado",
                    description=f"🔇 {member.mention} mutado **no chat** por **{duration} min**.",
                    color=discord.Color.orange()
                )
                if prova.content_type.startswith("image/"):
                    done.set_image(url=prova.url)
                else:
                    done.add_field(name="📎 Prova", value=f"[Abrir arquivo]({prova.url})", inline=False)
                return done

            else:
                # Mute de voz
                if not member.voice:
                    done = discord.Embed(
                        title="⚠️ Ação não aplicada",
                        description=f"{member.mention} não está em um canal de voz.",
                        color=discord.Color.yellow()
                    )
                    return done
                role = discord.utils.get(interaction.guild.roles, name="Mutado")
                if not role:
                    role = await interaction.guild.create_role(name="Mutado", reason="Cargo de mute (voz)")
                    for ch in interaction.guild.channels:
                        if isinstance(ch, discord.VoiceChannel):
                            try:
                                await ch.set_permissions(role, speak=False)
                            except Exception:
                                pass
                if role not in member.roles:
                    await member.add_roles(role, reason=f"Mute de voz por {duration} min")
                                    
                await member.edit(mute=True, reason=f"Mute de voz por {duration} min")

                async def remover_mute_voz():
                    await asyncio.sleep(duration * 60)
                    try:
                        if member.guild and member.voice and member.voice.mute:
                            await member.edit(mute=False, reason="Mute expirado")
                        un = discord.Embed(
                            title="🔊 Você foi desmutado",
                            description=f"Seu mute no servidor **{interaction.guild.name}** foi retirado.",
                            color=discord.Color.green()
                        )
                        await _safe_dm(member, un)
                    except Exception:
                        pass

                asyncio.create_task(remover_mute_voz())

                done = discord.Embed(
                    title="🔇 Mute Aplicado",
                    description=f"🔈 {member.mention} mutado **na voz** por **{duration} min**.",
                    color=discord.Color.orange()
                )
                if prova.content_type.startswith("image/"):
                    done.set_image(url=prova.url)
                else:
                    done.add_field(name="📎 Prova", value=f"[Abrir arquivo]({prova.url})", inline=False)
                return done

        view = ConfirmMuteView(interaction, member, duration, tipo, prova, aplicar_mute)
        await interaction.response.send_message(embed=confirm, view=view, ephemeral=True)

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

        view = ConfirmBanView(interaction, member, reason, prova, aplicar_ban)
        await interaction.response.send_message(embed=confirm, view=view, ephemeral=True)



async def setup(bot: commands.Bot):
    await bot.add_cog(Moderation(bot))
