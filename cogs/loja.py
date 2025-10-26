import re
import asyncio
import functools
import time
from typing import Optional
from datetime import datetime
from discord.utils import find, format_dt

import discord
from discord.ext import commands, tasks
from discord import app_commands
from discord.ui import View, Button, Modal, Select, TextInput

import db
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

async def safe_delete(channel: discord.TextChannel, delay: int = 60, reason: str = None):
    await asyncio.sleep(delay)
    try:
        await channel.delete(reason=reason)
    except Exception:
        pass


class NickModal(discord.ui.Modal, title="✏️ Alterar Apelido"):
    def __init__(self, user: discord.Member, canal_temp_id: Optional[int]):
        super().__init__(timeout=None)
        self.user = user
        self.canal_temp_id = canal_temp_id
        self.nick = TextInput(
            label="Novo apelido no servidor",
            placeholder="Digite o novo apelido aqui",
            required=True,
            max_length=32
        )
        self.add_item(self.nick)

    async def on_submit(self, interaction: discord.Interaction):
        novo_nick = self.nick.value.strip()
        membro = self.user
        guild = interaction.guild
        bot_member = guild.me

        if not guild.me.guild_permissions.manage_nicknames:
            return await interaction.response.send_message(
                "⛔ Eu não tenho permissão **Gerenciar apelidos** neste servidor.",
                ephemeral=True
            )

        if bot_member.top_role <= membro.top_role:
            return await interaction.response.send_message(
                "⚠️ Meu cargo está **abaixo do seu** na hierarquia. "
                "Coloque meu cargo acima do seu e tente de novo.",
                ephemeral=True
            )

        try:
            before_nick = membro.nick
            await membro.edit(nick=novo_nick, reason=f"Alteração de apelido pela loja - solicitada por {membro}")
            after_nick = membro.nick

            if after_nick != novo_nick:
                await guild._state.http.edit_member(guild.id, membro.id, nick=novo_nick, reason="Forçado (fallback API)")

            embed = discord.Embed(
                title="✅ Compra confirmada",
                description=f"Você comprou **apelido**!\n\n✅ O apelido de {membro.mention} foi alterado para **{novo_nick}**!",
                color=discord.Color.green()
            )

            try:
                await interaction.response.send_message(embed=embed, view=FecharView(), ephemeral=True)
            except Exception:
                await interaction.followup.send(embed=embed, ephemeral=True)

            if self.canal_temp_id:
                canal_temp = guild.get_channel(self.canal_temp_id)
                if canal_temp:
                    asyncio.create_task(safe_delete(canal_temp, delay=60, reason="Conversa de compra encerrada"))

            print(f"[INFO] Nick antes: {before_nick} → depois: {novo_nick}")

        except Exception as e:
            await interaction.response.send_message(f"❌ Erro ao alterar apelido: {e}", ephemeral=True)


class ConfirmarCompraView(discord.ui.View):
    def __init__(self, user, item, preco, selecionado, canal_temp: discord.TextChannel):
        super().__init__(timeout=None)
        self.user = user
        self.item = item
        self.preco = preco
        self.selecionado = selecionado
        self.canal_temp = canal_temp

    @discord.ui.button(label="✅ Confirmar", style=discord.ButtonStyle.success)
    async def confirmar(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.user:
            return await interaction.response.send_message("❌ Apenas você pode confirmar esta compra.", ephemeral=True)

        guild = interaction.guild

        xp = db.get_user_data(self.user.id, guild.id)[0]
        if xp < self.preco:
            return await interaction.response.send_message("❌ XP insuficiente.", ephemeral=True)

        novo_xp = max(0, xp - self.preco)
        db.update_xp(self.user.id, guild.id, novo_xp)

        if self.selecionado == "nick":
            try:
                await interaction.response.send_modal(NickModal(self.user, self.canal_temp.id if self.canal_temp else None))
            except Exception as e:
                try:
                    await interaction.response.send_message(f"❌ Erro ao abrir modal de nick: {e}", ephemeral=True)
                except Exception:
                    pass
            return

        await interaction.response.defer(thinking=True, ephemeral=True)
        resultado = ""

        if self.selecionado == "cargo":
            role_id, call_id = db.get_vip_role(self.user.id, guild.id) or (None, None)
            role = guild.get_role(role_id) if role_id else None
            canal = guild.get_channel(call_id) if call_id else None

            if not role:
                role = await guild.create_role(name=f"VIP-{self.user.display_name}")
                await self.user.add_roles(role)
                db.save_vip_role(self.user.id, guild.id, role.id)
                resultado = f"🎖️ Cargo `{role.name}` criado e atribuído!\n"
            else:
                await self.user.add_roles(role)
                resultado = f"🎖️ Você já tinha o cargo `{role.name}`, foi atribuído novamente!\n"

            if not canal:
                overwrites = {
                    guild.default_role: discord.PermissionOverwrite(view_channel=False),
                    self.user: discord.PermissionOverwrite(view_channel=True),
                    role: discord.PermissionOverwrite(view_channel=True, connect=True, speak=True)
                }
                canal = await guild.create_voice_channel(f"voz-{self.user.name}", overwrites=overwrites)
                db.update_vip_call(self.user.id, guild.id, canal.id)
                resultado += f"🔊 Canal de voz `{canal.name}` criado para você!\n"
            else:
                resultado += f"🔊 Você já tinha um canal de voz VIP: `{canal.name}`!\n"

            embed = discord.Embed(
                title="✅ Compra confirmada",
                description=f"Você comprou **{self.item}**!\n\n{resultado}",
                color=discord.Color.green()
            )

            try:
                await interaction.edit_original_response(embed=embed, view=FecharView())
            except Exception:
                await interaction.followup.send(embed=embed, ephemeral=True, view=FecharView())

            try:
                embed_cfg = discord.Embed(
                    title="⚙️ Suas Configurações VIP",
                    description=(
                        "Aqui estão as opções do seu cargo VIP.\n"
                        "Use os botões abaixo para **personalizar** seu VIP:\n"
                        "- 🎨 Alterar cor\n"
                        "- 📛 Renomear cargo\n"
                        "- 📞 Renomear call VIP\n"
                        "- 🏷️ Dar VIP para outro usuário\n"
                        "- ❌ Remover VIP de alguém\n"
                    ),
                    color=role.color
                )
                embed_cfg.add_field(name="📛 Cargo", value=role.mention, inline=True)
                embed_cfg.add_field(name="🎨 Cor", value=str(role.color), inline=True)
                embed_cfg.add_field(name="📞 Call VIP", value=canal.mention if canal else "Nenhuma", inline=False)

                # Cria view igual ao /cfg
                view = discord.ui.View()
                btn_rename = discord.ui.Button(label="Renomear Cargo", style=discord.ButtonStyle.primary)
                btn_color = discord.ui.Button(label="Mudar Cor", style=discord.ButtonStyle.success)
                btn_call = discord.ui.Button(label="Renomear Call", style=discord.ButtonStyle.secondary)
                btn_addtag = discord.ui.Button(label="Dar VIP", style=discord.ButtonStyle.secondary)
                btn_removetag = discord.ui.Button(label="Remover VIP", style=discord.ButtonStyle.danger)

                async def callback_rename(i: discord.Interaction):
                    await i.response.send_modal(RenameVipModal(role))

                async def callback_color(i: discord.Interaction):
                    await i.response.send_modal(CfgColor(role))

                async def callback_call(i: discord.Interaction):
                    await i.response.send_modal(CfgCall(guild, role))

                async def callback_addtag(i: discord.Interaction):
                    await i.response.send_modal(AddTagModal(role))

                async def callback_removetag(i: discord.Interaction):
                    await i.response.send_modal(RemoveTagModal(role))

                btn_rename.callback = callback_rename
                btn_color.callback = callback_color
                btn_call.callback = callback_call
                btn_addtag.callback = callback_addtag
                btn_removetag.callback = callback_removetag

                view.add_item(btn_rename)
                view.add_item(btn_color)
                view.add_item(btn_call)
                view.add_item(btn_addtag)
                view.add_item(btn_removetag)


                if self.canal_temp:
                    await self.canal_temp.send(content=f"{self.user.mention}", embed=embed_cfg, view=view)

            except Exception as e:
                print(f"[ERRO - Exibir CFG VIP] {e}")

            return


        if self.selecionado == "boost_xp":
            multiplier = 1.5
            duration = 24 * 60 * 60

            db.set_boost_xp(self.user.id, guild.id, multiplier, duration)


            role_name = "⚡ BoostXP"
            role = discord.utils.get(guild.roles, name=role_name)


            if not role:
                try:
                    role = await guild.create_role(
                        name=role_name,
                        color=discord.Color.gold(),
                        reason="Cargo global de Boost XP criado automaticamente"
                    )
                    if guild.me and guild.me.top_role:
                        await role.edit(position=max(0, guild.me.top_role.position - 1))
                except Exception as e:
                    print(f"[ERRO] Não foi possível criar o cargo BoostXP: {e}")
                    role = None


            if role:
                try:
                    await self.user.add_roles(role, reason="Boost XP ativado")
                except Exception as e:
                    print(f"[ERRO] Não foi possível atribuir o cargo BoostXP: {e}")


            asyncio.create_task(self._schedule_boost_end(interaction.client, self.user, guild, duration, role_name="⚡ BoostXP"))

            expires_at = int(time.time()) + duration
            rel = format_dt(datetime.fromtimestamp(expires_at), style="R")
            abs_time = format_dt(datetime.fromtimestamp(expires_at), style="f")

            embed = discord.Embed(
                title="⚡ Boost de XP Ativado!",
                description=(
                    f"**Usuário:** {self.user.mention}\n"
                    f"**Multiplicador:** x{multiplier}\n"
                    f"**Término:** {rel} (até {abs_time})\n\n"
                    "Seu boost começou agora! Você ganhará **50% a mais de XP** durante esse tempo."
                ),
                color=discord.Color.gold()
            )

            await interaction.edit_original_response(embed=embed, view=FecharView())
            if self.canal_temp:
                asyncio.create_task(safe_delete(self.canal_temp, delay=300, reason="Conversa de compra encerrada (boost aplicado)"))
            return

 
    @discord.ui.button(label="❌ Cancelar", style=discord.ButtonStyle.danger)
    async def cancelar(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.user:
            return await interaction.response.send_message("❌ Apenas você pode cancelar.", ephemeral=True)

        try:
            await interaction.message.edit(content="❌ Compra cancelada.", embed=None, view=None)
        except Exception:
            pass

        try:
            if self.canal_temp:
                asyncio.create_task(safe_delete(self.canal_temp, delay=300, reason="Compra cancelada pelo usuário"))

        except Exception:
            pass
        


    async def _schedule_boost_end(self, bot, user: discord.Member, guild: discord.Guild, delay: int, role_name: str = "⚡ BoostXP"):
        await asyncio.sleep(delay)

        try:
            db.remove_boost(user.id, guild.id)
        except Exception:
            pass

        member = guild.get_member(user.id)
        if not member:
            return

        role = discord.utils.get(guild.roles, name=role_name)
        if role and role in member.roles:
            try:
                await member.remove_roles(role, reason="Boost expirado")
            except Exception as e:
                print(f"[ERRO] Falha ao remover cargo BoostXP: {e}")

        try:
            await user.send("⏰ Seu **Boost de XP** terminou! ⚡")
        except Exception:
            pass

class FecharView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🗑️ Fechar conversa", style=discord.ButtonStyle.secondary)
    async def fechar(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            await interaction.channel.delete(reason="Conversa de compra encerrada")
        except Exception:
            pass


class LojaSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="Cargo VIP", description="Acesso especial – 500 XP", value="cargo"),
            discord.SelectOption(label="⚡ Boost de XP", description="+50% XP por 24h – 300 XP", value="boost_xp"),
            discord.SelectOption(label="✏️ Alterar Apelido", description="Mude seu nick – 100 XP", value="nick"),
        ]
        super().__init__(placeholder="Selecione um item", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        try:
            selecionado = self.values[0]
            user, guild = interaction.user, interaction.guild

            precos = {"cargo": 500, "boost_xp": 300, "nick": 100}
            preco = precos.get(selecionado)
            if preco is None:
                return await interaction.response.send_message("❌ Item inválido.", ephemeral=True)

            xp = db.get_user_data(user.id, guild.id)[0]
            if xp < preco:
                return await interaction.response.send_message("❌ XP insuficiente.", ephemeral=True)

            overwrites = {
                guild.default_role: discord.PermissionOverwrite(view_channel=False),
                user: discord.PermissionOverwrite(view_channel=True),
                guild.me: discord.PermissionOverwrite(view_channel=True)
            }
            canal_temp = await guild.create_text_channel(f"vip-{user.name}", overwrites=overwrites)

            embed = discord.Embed(
                title="🛒 Confirmação de compra",
                description=(
                    f"Você está prestes a comprar **{selecionado}**!\n\n"
                    f"Preço: **{preco} XP**\n"
                    "Confirme abaixo para prosseguir."
                ),
                color=discord.Color.blurple()
            )
            await canal_temp.send(
                content=f"{user.mention}",
                embed=embed,
                view=ConfirmarCompraView(user, selecionado, preco, selecionado, canal_temp)
            )

            for child in self.view.children:
                child.disabled = True
            try:
                await interaction.response.edit_message(view=self.view)
            except Exception:
                pass

        except Exception as e:
            print(f"[Erro na LojaSelect] {e}")
            if not interaction.response.is_done():
                await interaction.response.send_message("❌ Ocorreu um erro interno.", ephemeral=True)


class LojaView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60)
        self.add_item(LojaSelect())

    @discord.ui.button(label="Cancelar", style=discord.ButtonStyle.danger)
    async def cancelar(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("❌ Operação cancelada.", ephemeral=True)



class RenameVipModal(discord.ui.Modal, title="Renomeia o cargo VIP"):
    def __init__(self, role: discord.Role):
        super().__init__(timeout=None)
        self.role = role
        self.rename = TextInput(
            label="Novo nome do cargo",
            placeholder="Insira o novo nome do cargo",
            required=True,
            max_length=32
        )
        self.add_item(self.rename)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            await self.role.edit(name=self.rename.value)
            await interaction.response.send_message(f"✅ Cargo renomeado para **{self.rename.value}**!", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Erro ao renomear o cargo: {e}", ephemeral=True)


class CfgCall(discord.ui.Modal, title="📞 Configurar Call VIP"):
    def __init__(self, guild: discord.Guild, role: discord.Role):
        super().__init__()
        self.guild = guild
        self.role = role
        self.call_name = TextInput(
            label="Nome da sua call VIP",
            placeholder="Sala do(a) " + role.name,
            required=True,
            max_length=32
        )
        self.add_item(self.call_name)

    async def on_submit(self, interaction: discord.Interaction):
        role_id, call_id = db.get_vip_role(interaction.user.id, self.guild.id)
        channel = self.guild.get_channel(call_id) if call_id else None

        if channel:
            await channel.edit(name=f"{self.call_name.value}")
            await interaction.response.send_message(f"✏️ Call VIP renomeada para {channel.mention}", ephemeral=True)
        else:
            overwrites = {
                self.guild.default_role: discord.PermissionOverwrite(connect=False),
                self.role: discord.PermissionOverwrite(connect=True, speak=True)
            }
            channel = await self.guild.create_voice_channel(name=f"🔒 {self.call_name.value}", overwrites=overwrites)
            db.update_vip_call(interaction.user.id, self.guild.id, channel.id)
            await interaction.response.send_message(f"✅ Nova call VIP criada: {channel.mention}", ephemeral=True)


class AddTagModal(discord.ui.Modal, title="🏷️ Dar VIP para outro usuário"):
    def __init__(self, role: discord.Role):
        super().__init__()
        self.role = role
        self.user_input = TextInput(
            label="ID do usuário, menção, nome ou apelido",
            placeholder="@usuario, ID ou nome/apelido",
            required=True
        )
        self.add_item(self.user_input)

    async def on_submit(self, interaction: discord.Interaction):
        guild = interaction.guild
        raw = self.user_input.value.strip()
        member = None

        try:
            match = re.match(r"<@!?(\d+)>", raw)
            if match:
                user_id = int(match.group(1))
                member = guild.get_member(user_id)
            elif raw.isdigit():
                user_id = int(raw)
                member = guild.get_member(user_id)
            else:
                member = find(lambda m: raw.lower() in m.name.lower() or raw.lower() in m.display_name.lower(), guild.members)
        except Exception as e:
            await interaction.response.send_message(f"⚠️ Erro ao processar entrada: `{e}`.", ephemeral=True)
            return

        if not member:
            await interaction.response.send_message("❌ Usuário não encontrado.", ephemeral=True)
            return

        try:
            await member.add_roles(self.role)
            await interaction.response.send_message(f"✅ Cargo `{self.role.name}` dado a {member.mention}!", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message("⛔ Não tenho permissão para atribuir este cargo.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"⚠️ Erro: `{e}`", ephemeral=True)


class RemoveTagModal(discord.ui.Modal, title="❌ Remove o cargo VIP de outro usuário"):
    def __init__(self, role: discord.Role):
        super().__init__()
        self.role = role
        self.user_input = TextInput(label="ID do usuário ou menção", placeholder="@usuario ou ID", required=True)
        self.add_item(self.user_input)

    async def on_submit(self, interaction: discord.Interaction):
        guild = interaction.guild
        raw = self.user_input.value.strip()
        match = re.match(r"<@!?(\d+)>", raw)
        try:
            user_id = int(match.group(1)) if match else int(raw)
        except Exception:
            await interaction.response.send_message("❌ Entrada inválida.", ephemeral=True)
            return

        member = guild.get_member(user_id)
        if not member:
            await interaction.response.send_message("❌ Usuário não encontrado.", ephemeral=True)
            return
        if self.role not in member.roles:
            await interaction.response.send_message(f"❌ {member.mention} não possui o cargo `{self.role.name}`.", ephemeral=True)
            return

        await member.remove_roles(self.role)
        await interaction.response.send_message(f"✅ Cargo `{self.role.name}` removido de {member.mention}!", ephemeral=True)


class CfgColor(discord.ui.Modal, title="🎨 Alterar cor do cargo VIP"):
    def __init__(self, role: discord.Role):
        super().__init__()
        self.role = role
        self.color_input = TextInput(label="Nova cor em HEX", placeholder="#5865F2", required=True, max_length=7)
        self.add_item(self.color_input)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            new_color = discord.Color(int(self.color_input.value.lstrip("#"), 16))
            await self.role.edit(color=new_color)
            await interaction.response.send_message(f"✅ Cor do cargo alterada para `{self.color_input.value}`!", ephemeral=True)
        except ValueError:
            await interaction.response.send_message("❌ Código inválido. Use formato HEX (ex: `#ff0000`).", ephemeral=True)



class Loja(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        self.boost_checker.start()

    def cog_unload(self):
        self.boost_checker.cancel()

    @tasks.loop(minutes=1)
    async def boost_checker(self):


        try:
            expired = []
            if hasattr(db, "get_boosts_expired"):
                expired = db.get_boosts_expired()
            else:
                return 
            for user_id, guild_id in expired:
                try:
                    db.remove_boost(user_id, guild_id)
                except Exception:
                    pass

                guild = self.bot.get_guild(guild_id)
                if not guild:
                    continue
                member = guild.get_member(user_id)
                if not member:
                    continue
                try:
                    for r in list(member.roles):
                        if r.name.startswith("⚡ BoostXP"):
                            try:
                                await member.remove_roles(r, reason="Boost expirado")
                                try:
                                    await r.delete(reason="Boost expirado")
                                except Exception:
                                    pass
                            except Exception:
                                pass
                except Exception:
                    pass

                try:
                    await member.send("⏰ Seu **Boost de XP** terminou! Esperamos que tenha aproveitado o bônus. ⚡")
                except Exception:
                    pass
        except Exception:
            pass

    # comandos
    @app_commands.command(name='nwitem', description='Adiciona um novo item à loja')
    @log_command(generic_title, generic_fields)
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(
        product_name="Nome do produto",
        description="Descrição do item",
        price="Preço em XP",
        tipo="Tipo do item: cargo, canal_voz, boost_xp ou nick"
    )
    @app_commands.choices(tipo=[
        app_commands.Choice(name='Cargo Exclusivo', value='cargo'),
        app_commands.Choice(name='Boost de XP', value='boost_xp'),
        app_commands.Choice(name='Alterar Apelido', value='nick'),
    ])
    async def nwitem(self, interaction: discord.Interaction, product_name: str, description: str, price: int, tipo: app_commands.Choice[str]):
        db.set_item_shop(interaction.guild.id, tipo.value, product_name, description, price)
        await interaction.response.send_message(f"🛒 Item `{product_name}` adicionado com sucesso!", ephemeral=True)

    @app_commands.command(name='loja', description='Loja do servidor')
    @log_command(generic_title, generic_fields)
    async def loja(self, interaction: discord.Interaction):
        xp = db.get_user_data(interaction.user.id, interaction.guild.id)[0]
        embed = discord.Embed(
            title="🛒 Loja do Servidor",
            description=f"XP atual de {interaction.user.display_name}: **{xp}**\nSelecione um item:",
            color=discord.Color.blurple()
        )
        await interaction.response.send_message(embed=embed, view=LojaView(), ephemeral=True)

    @app_commands.command(name="cfg", description="Mostra as configurações atuais do seu cargo VIP")
    async def cfg(self, interaction: discord.Interaction):
        member = interaction.user
        result = db.get_vip_role(member.id, interaction.guild.id)
        if not result:
            await interaction.response.send_message("❌ Você não possui um cargo VIP configurado.", ephemeral=True)
            return

        role_id, call_id = result
        role = interaction.guild.get_role(role_id)
        if not role:
            await interaction.response.send_message("❌ Você não possui um cargo VIP configurado ou o cargo foi deletado.", ephemeral=True)
            return

        embed = discord.Embed(title="⚙️ Suas Configurações VIP", color=role.color)
        embed.add_field(name="🎨 Cor do cargo", value=str(role.color), inline=False)
        embed.add_field(name="📛 Nome do cargo", value=role.name, inline=False)

        view = discord.ui.View()
        btn_rename = discord.ui.Button(label="Renomear Cargo ", style=discord.ButtonStyle.primary)
        btn_color = discord.ui.Button(label="Muda Cor", style=discord.ButtonStyle.success)
        btn_call = discord.ui.Button(label="Renomeia Call", style=discord.ButtonStyle.secondary)
        btn_addtag = discord.ui.Button(label="Seta Tag", style=discord.ButtonStyle.secondary)
        btn_removetag = discord.ui.Button(label="Remover VIP", style=discord.ButtonStyle.danger)

        async def callback_rename(i: discord.Interaction):
            await i.response.send_modal(RenameVipModal(role))

        async def callback_color(i: discord.Interaction):
            await i.response.send_modal(CfgColor(role))

        async def callback_call(i: discord.Interaction):
            await i.response.send_modal(CfgCall(interaction.guild, role))

        async def callback_addtag(i: discord.Interaction):
            await i.response.send_modal(AddTagModal(role))

        async def callback_removetag(i: discord.Interaction):
            await i.response.send_modal(RemoveTagModal(role))

        btn_rename.callback = callback_rename
        btn_color.callback = callback_color
        btn_call.callback = callback_call
        btn_addtag.callback = callback_addtag
        btn_removetag.callback = callback_removetag

        view.add_item(btn_rename)
        view.add_item(btn_color)
        view.add_item(btn_call)
        view.add_item(btn_addtag)
        view.add_item(btn_removetag)

        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Loja(bot))
