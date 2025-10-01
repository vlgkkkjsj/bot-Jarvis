import re
import asyncio
import functools
from typing import Optional

import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import View, Button, Modal, Select

import db
from utils.logger import send_log


# ==============================
# 🔹 DECORATORS E HELPERS
# ==============================
def log_command(title_getter, fields_getter):
    """Decorator para logar comandos executados."""
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

        await interaction.response.defer(thinking=True, ephemeral=True)

        guild = interaction.guild
        xp = db.get_user_data(self.user.id, guild.id)[0]

        if xp < self.preco:
            return await interaction.followup.send("❌ XP insuficiente.", ephemeral=True)

        novo_xp = max(0, xp - self.preco)
        db.update_xp(self.user.id, guild.id, novo_xp)
        resultado = ""

        if self.selecionado == "cargo":
            role_id, call_id = db.get_vip_role(self.user.id, guild.id) or (None, None)

            role = guild.get_role(role_id) if role_id else None
            canal = guild.get_channel(call_id) if call_id else None

            if not role:
                role = await guild.create_role(name=f"VIP-{self.user.display_name}")
                await self.user.add_roles(role)
                db.save_vip_role(self.user.id, guild.id, role.id)
                resultado += f"🎖️ Cargo `{role.name}` criado e atribuído!\n"
            else:
                await self.user.add_roles(role)
                resultado += f"🎖️ Você já tinha o cargo `{role.name}`, foi atribuído novamente!\n"

            if not canal:
                overwrites = {
                    guild.default_role: discord.PermissionOverwrite(view_channel=False),
                    self.user: discord.PermissionOverwrite(view_channel=True),
                    role: discord.PermissionOverwrite(view_channel=True, connect=True, speak=True)
                }
                canal = await guild.create_voice_channel(f"voz-{self.user.name}", overwrites=overwrites)
                db.update_vip_call(self.user.id, guild.id, canal.id)
                resultado += f"🔊 Canal de voz `{canal.name}` criado para você!"
            else:
                resultado += f"🔊 Você já tinha um canal de voz VIP: `{canal.name}`!"

        elif self.selecionado == "boost_xp":
            db.set_boost_xp(self.user.id, guild.id, 1.5, 24 * 60 * 60)
            resultado = "⚡ Boost de XP aplicado por 24h!"

        elif self.selecionado == "nick":
            return await interaction.followup.send("✏️ Digite seu novo apelido no canal privado criado.", ephemeral=True)

        else:
            resultado = "❓ Tipo de item não suportado."

        embed = discord.Embed(
            title="✅ Compra confirmada",
            description=f"Você comprou **{self.item}**!\n\n{resultado}",
            color=discord.Color.green()
        )
        await interaction.edit_original_response(embed=embed, view=FecharView())

    @discord.ui.button(label="❌ Cancelar", style=discord.ButtonStyle.danger)
    async def cancelar(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.user:
            return await interaction.response.send_message("❌ Apenas você pode cancelar.", ephemeral=True)

        await interaction.message.edit(content="❌ Compra cancelada.", embed=None, view=None)
        await self.canal_temp.delete(reason="Compra cancelada pelo usuário")


class FecharView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None) 

    @discord.ui.button(label="🗑️ Fechar conversa", style=discord.ButtonStyle.secondary)
    async def fechar(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.channel.delete(reason="Conversa de compra encerrada")

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

            precos = {"cargo": 500, "canal_voz": 390, "boost_xp": 300, "nick": 100}
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
            canal_temp = await guild.create_text_channel(f"compra-{user.name}", overwrites=overwrites)

            embed = discord.Embed(
                title="🛒 Confirmação de compra",
                description=(
                    f"Você comprou **{selecionado}**!\n"
                    "Use os comandos abaixo para configurar seu VIP:\n"
                    "- `/cfg` → Visualizar configurações atuais\n"
                    "- `/cfgname` → Alterar nome do cargo\n"
                    "- `/cfgcolor` → Alterar cor do cargo\n"
                    "- `/cfgcall` → Alterar capacidade da call\n"
                    "- `/addtag` → Dar seu cargo VIP a outro usuário"
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
            except (discord.InteractionResponded, discord.NotFound):
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


class RenameVipModal(discord.ui.Modal, title = "Renomeia o cargo VIP"):
    def __init__(self, role: discord.Role):
        super().__init__(timeout=None)
        self.role = role
        
        self.rename = discord.ui.TextInput(
            label="Novo nome do cargo",
            placeholder="Insira o novo nome do cargo",
            required=True,
            max_length=32  
        )
        self.add_item(self.rename)

    async def  on_submit(self, interaction: discord.Interaction):
        try:
            await self.role.edit(name=self.rename.value)
            await interaction.response.send_message(
                f"✅ Cargo renomeado para **{self.rename.value}**!",
                ephemeral=True                
            )
        except Exception as e:
            await interaction.response.send_message(
                f"❌ Erro ao renomear o cargo: {e}",
                ephemeral=True                
            )

class CfgCall(discord.ui.Modal, title="📞 Configurar Call VIP"):
    def __init__(self, guild: discord.Guild, role: discord.Role):
        super().__init__()
        self.guild = guild
        self.role = role

        self.call_name = discord.ui.TextInput(
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
            await channel.edit(name=f" {self.call_name.value}")
            await interaction.response.send_message(
                f"✏️ Call VIP renomeada para {channel.mention}", ephemeral=True
            )
        else:
            overwrites = {
                self.guild.default_role: discord.PermissionOverwrite(connect=False),
                self.role: discord.PermissionOverwrite(connect=True, speak=True)
            }
            channel = await self.guild.create_voice_channel(
                name=f"🔒 {self.call_name.value}", overwrites=overwrites
            )
            db.update_vip_call(interaction.user.id, self.guild.id, channel.id)
            await interaction.response.send_message(
                f"✅ Nova call VIP criada: {channel.mention}", ephemeral=True
            )

class AddTagModal(discord.ui.Modal, title="🏷️ Dar VIP para outro usuário"):
    def __init__(self, role: discord.Role):
        super().__init__()
        self.role = role

        self.user_input = discord.ui.TextInput(
            label="ID do usuário ou menção",
            placeholder="@usuario ou ID",
            required=True
        )
        self.add_item(self.user_input)

    async def on_submit(self, interaction: discord.Interaction):
        guild = interaction.guild
        raw = self.user_input.value.strip()
        
        match = re.match(r"<@!?(\d+)>", raw)
        user_id = int(match.group(1)) if match else int(raw)
        member = guild.get_member(user_id)
        if not member:
            await interaction.response.send_message("❌ Usuário não encontrado.", ephemeral=True)
            return
        await member.add_roles(self.role)
        await interaction.response.send_message(f"✅ Cargo `{self.role.name}` dado a {member.mention}!", ephemeral=True)
      
class RemoveTagModal(discord.ui.Modal, title="❌ Remove o cargo VIP de outro usuário"):
    def __init__(self, role: discord.Role):
        super().__init__()
        self.role = role

        self.user_input = discord.ui.TextInput(
            label="ID do usuário ou menção",
            placeholder="@usuario ou ID",
            required=True
        )
        self.add_item(self.user_input)

    async def on_submit(self, interaction: discord.Interaction):
        guild = interaction.guild
        raw = self.user_input.value.strip()

        match = re.match(r"<@!?(\d+)>", raw)
        user_id = int(match.group(1)) if match else int(raw)
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

        self.color_input = discord.ui.TextInput(
            label="Nova cor em HEX",
            placeholder="#5865F2",
            required=True,
            max_length=7
        )
        self.add_item(self.color_input)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            new_color = discord.Color(int(self.color_input.value.lstrip("#"), 16))
            await self.role.edit(color=new_color)
            await interaction.response.send_message(
                f"✅ Cor do cargo alterada para `{self.color_input.value}`!", ephemeral=True
            )
        except ValueError:
            await interaction.response.send_message(
                "❌ Código inválido. Use formato HEX (ex: `#ff0000`).", ephemeral=True
            )
    
class Loja(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

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

    
# CFG
    @app_commands.command(name="cfg", description="Mostra as configurações atuais do seu cargo VIP")
    async def cfg(self, interaction: discord.Interaction):
        member = interaction.user

        result = db.get_vip_role(member.id, interaction.guild.id)
        if not result:
            await interaction.response.send_message(
                "❌ Você não possui um cargo VIP configurado.", ephemeral=True
            )
            return

        role_id, call_id = result  
        role = interaction.guild.get_role(role_id)

        if not role:
            await interaction.response.send_message(
                "❌ Você não possui um cargo VIP configurado ou o cargo foi deletado.", ephemeral=True
            )
            return

        embed = discord.Embed(
            title="⚙️ Suas Configurações VIP",
            color=role.color
        )
        embed.add_field(name="🎨 Cor do cargo", value=str(role.color), inline=False)
        embed.add_field(name="📛 Nome do cargo", value=role.name, inline=False)

        view = discord.ui.View()

        btn_rename = discord.ui.Button(label="Renomear Cargo ", style=discord.ButtonStyle.primary)
        btn_color  = discord.ui.Button(label="Muda Cor", style=discord.ButtonStyle.success)
        btn_call   = discord.ui.Button(label="Renomeia Call", style=discord.ButtonStyle.secondary)
        btn_addtag = discord.ui.Button(label="Seta Tag", style=discord.ButtonStyle.secondary)
        btn_removetag = discord.ui.Button(label="Remover VIP", style=discord.ButtonStyle.danger)  # NOVO

        
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
