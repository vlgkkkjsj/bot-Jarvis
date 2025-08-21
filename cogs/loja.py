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
        tipo="Tipo do item: cargo, canal_texto ou canal_voz"
    )
    @app_commands.choices(tipo=[
        app_commands.Choice(name='Cargo Exclusivo', value='cargo'),
        app_commands.Choice(name='Canal de Texto', value='canal_texto'),
        app_commands.Choice(name='Canal de Voz', value='canal_voz')
    ])
    async def nwitem(self, interaction: discord.Interaction, product_name: str, description: str, price: int, tipo: app_commands.Choice[str]):
        db.set_item_shop(interaction.guild.id, tipo.value, product_name, description, price)
        await interaction.response.send_message(f"🛒 Item `{product_name}` do tipo `{tipo.name}` adicionado com sucesso à loja!", ephemeral=True)

    @app_commands.command(name='loja', description='Loja do servidor')
    @log_command(generic_title, generic_fields) 

    async def loja(self, interaction: discord.Interaction):
        xp = db.get_user_data(interaction.user.id, interaction.guild.id)[0]

        embed = discord.Embed(
            title="🛒 Loja do Servidor",
            description=f"XP atual de {interaction.user.display_name}: **+{xp}**\nAqui estão os itens disponíveis:",
            color=discord.Color.blurple()
        )
        embed.add_field(name="Cargo VIP – 100 XP", value="Acesso especial no servidor", inline=False)
        embed.add_field(name="Canal de Texto – 200 XP", value="Criação de canal exclusivo", inline=False)
        embed.add_field(name="Canal de Voz – 300 XP", value="Criação de canal de voz exclusivo", inline=False)
        embed.add_field(name="Ícone Personalizado – 400 XP", value="Ícone único para seu perfil", inline=False)

        await interaction.response.send_message(embed=embed, view=LojaView(), ephemeral=True)
        return True
class LojaSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="Cargo VIP", description="Acesso especial – 100 XP", value="cargo"),
            discord.SelectOption(label="Canal de Texto", description="Canal exclusivo – 200 XP", value="canal_texto"),
            discord.SelectOption(label="Canal de Voz", description="Canal de voz exclusivo – 300 XP", value="canal_voz"),
            discord.SelectOption(label="Ícone Personalizado", description="Ícone único – 400 XP", value="icone")
        ]
        super().__init__(placeholder="Selecione um item", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        try:
            selecionado = self.values[0]
            user = interaction.user
            guild = interaction.guild

            precos = {
                "cargo": 100,
                "canal_texto": 200,
                "canal_voz": 300,
                "icone": 400
            }

            preco = precos.get(selecionado)
            if preco is None:
                await interaction.response.send_message("❌ Item inválido.", ephemeral=True)
                return

            xp = db.get_user_data(user.id, guild.id)[0]
            if xp < preco:
                await interaction.response.send_message("❌ XP insuficiente para esta compra.", ephemeral=True)
                return

            db.update_xp(user.id, guild.id , xp - preco)

            if selecionado == "cargo":
                role = await guild.create_role(name="VIP")
                await user.add_roles(role)
                resultado = f"🎖️ Cargo `{role.name}` criado e atribuído a você!"

            elif selecionado == "canal_texto":
                overwrites = {
                    guild.default_role: discord.PermissionOverwrite(view_channel=False),
                    user: discord.PermissionOverwrite(view_channel=True)
                }
                canal = await guild.create_text_channel("vip-texto", overwrites=overwrites)
                resultado = f"📄 Canal de texto `{canal.name}` criado para você!"

            elif selecionado == "canal_voz":
                overwrites = {
                    guild.default_role: discord.PermissionOverwrite(view_channel=False),
                    user: discord.PermissionOverwrite(view_channel=True)
                }
                canal = await guild.create_voice_channel("vip-voz", overwrites=overwrites)
                resultado = f"🔊 Canal de voz `{canal.name}` criado para você!"

            elif selecionado == "icone":
                resultado = "🖼️ Ícone personalizado será enviado em breve (função simbólica)."

            else:
                resultado = "❓ Tipo de item não suportado."

            await interaction.response.send_message(f"✅ Compra realizada: **{selecionado}**\n{resultado}", ephemeral=True)
            await interaction.message.edit(view=None)

        except Exception as e:
            print(f"[Erro na LojaSelect] {e}")
            if not interaction.response.is_done():
                await interaction.response.send_message("❌ Ocorreu um erro interno ao processar sua compra.", ephemeral=True)

class LojaView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60)
        self.add_item(LojaSelect())

    @discord.ui.button(label="Cancelar", style=discord.ButtonStyle.danger)
    async def cancelar(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("❌ Operação cancelada.", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(Loja(bot))
