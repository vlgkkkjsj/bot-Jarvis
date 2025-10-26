import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import random
import aiohttp
from datetime import datetime
from utils.logger import send_log
import db



class NomeUniaoModal(discord.ui.Modal):
    def __init__(self, autor: discord.Member, parceiro: discord.Member, view: "BotaoNomeCargo"):
        super().__init__(title=f"💞 Nome da união com {parceiro.display_name}")
        self.autor = autor
        self.parceiro = parceiro
        self.view_ref = view
        self.nome_cargo = discord.ui.TextInput(
            label="Nome do cargo que representará sua união",
            placeholder="Ex: Esposo(a) do(a) 💍",
            max_length=30,
            required=True
        )
        self.add_item(self.nome_cargo)

    async def on_submit(self, interaction: discord.Interaction):
        cargo_nome = self.nome_cargo.value.strip()
        role = await interaction.guild.create_role(
            name=cargo_nome,
            color=discord.Color.random(),
            mentionable=True,
            reason=f"União de {self.autor.mention} com {self.parceiro.mention}"
        )

        await self.autor.add_roles(role)
        await self.parceiro.add_roles(role)

        db.atualizar_cargo_casamento(self.autor.id, interaction.guild.id, role.id)
        db.atualizar_cargo_casamento(self.parceiro.id, interaction.guild.id, role.id)


        if self.view_ref and self.view_ref.message:
            self.view_ref.botao_personalizar.disabled = True
            await self.view_ref.message.edit(view=self.view_ref)

        await interaction.response.send_message(
            f"💖 Cargo **{role.name}** criado com sucesso! Vocês estão oficialmente unidos!", ephemeral=True
        )



class BotaoNomeCargo(discord.ui.View):
    def __init__(self, autor: discord.Member, parceiro: discord.Member):
        super().__init__(timeout=None)  
        self.autor = autor
        self.parceiro = parceiro
        self.message = None

        self.botao_personalizar = discord.ui.Button(
            label="💞 Personalizar nome do cargo da união",
            style=discord.ButtonStyle.primary,
            custom_id="personalizar_nome"
        )
        self.botao_personalizar.callback = self.abrir_modal
        self.add_item(self.botao_personalizar)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.autor.id:
            await interaction.response.send_message(
                "❌ Apenas quem fez o pedido pode personalizar o nome da união.", ephemeral=True
            )
            return False
        return True

    async def abrir_modal(self, interaction: discord.Interaction):
        await interaction.response.send_modal(NomeUniaoModal(self.autor, self.parceiro, self))


class PedidoCasamentoView(discord.ui.View):
    def __init__(self, autor: discord.Member, parceiro: discord.Member):
        super().__init__(timeout=180)
        self.autor = autor
        self.parceiro = parceiro
        self.evento = asyncio.Event()
        self.message = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.parceiro.id:
            await interaction.response.send_message("❌ Apenas o usuário convidado pode clicar.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Aceitar 💖", style=discord.ButtonStyle.success)
    async def aceitar(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.evento.set()
        embed_aceito = discord.Embed(
            title="💖 Pedido Aceito!",
            description=f"**{self.parceiro.mention}** aceitou o pedido! 💍",
            color=discord.Color.green()
        )
        await interaction.response.edit_message(embed=embed_aceito, view=None)

    @discord.ui.button(label="Recusar 💔", style=discord.ButtonStyle.danger)
    async def recusar(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(
            content=f"💔 **{self.parceiro.mention}** recusou o pedido de casamento.", embed=None, view=None
        )
        self.stop()



class DivorcioView(discord.ui.View):
    def __init__(self, autor: discord.Member, parceiro: discord.Member):
        super().__init__(timeout=180)
        self.autor = autor
        self.parceiro = parceiro
        self.confirmados = set()
        self.message = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id not in (self.autor.id, self.parceiro.id):
            await interaction.response.send_message("❌ Apenas os envolvidos podem clicar.", ephemeral=True)
            return False
        return True

    async def on_timeout(self):
        if self.message:
            await self.message.edit(content="⏳ Pedido de divórcio expirou.", view=None)

    @discord.ui.button(label="Confirmar 💔", style=discord.ButtonStyle.danger)
    async def confirmar(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id in self.confirmados:
            await interaction.response.send_message("⚠️ Você já confirmou.", ephemeral=True)
            return

        self.confirmados.add(interaction.user.id)
        embed = discord.Embed(
            title="💔 Pedido de Divórcio",
            description=f"**{self.autor.mention}** quer se divorciar de **{self.parceiro.mention}**.\n\n"
                        f"Confirmados: {', '.join([m.mention for m in [self.autor, self.parceiro] if m.id in self.confirmados])}",
            color=discord.Color.red()
        )
        await interaction.response.edit_message(embed=embed)

        if len(self.confirmados) == 2:
            dados_autor = db.obter_casamento(self.autor.id, interaction.guild.id)
            dados_parceiro = db.obter_casamento(self.parceiro.id, interaction.guild.id)

            cargo_id = dados_autor[1] if dados_autor and dados_autor[1] else (dados_parceiro[1] if dados_parceiro and dados_parceiro[1] else None)

            if cargo_id:
                role = interaction.guild.get_role(cargo_id)
                if role:
                    try:
                        await role.delete(reason="Divórcio 💔")
                    except discord.Forbidden:
                        await interaction.followup.send("⚠️ Não consegui excluir o cargo no servidor (permissões insuficientes).", ephemeral=True)

            db.deletar_casamento(self.autor.id, interaction.guild.id)
            db.deletar_casamento(self.parceiro.id, interaction.guild.id)
            db.remove_cargo_casal(cargo_id, interaction.guild.id)  

            embed_final = discord.Embed(
                title="💔 Divórcio Confirmado",
                description=f"**{self.autor.display_name}** e **{self.parceiro.display_name}** agora estão oficialmente divorciados.",
                color=discord.Color.red(),
                timestamp=datetime.now()
            )
            embed_final.add_field(name="👫 Ex-cônjuges", value=f"{self.autor.mention} & {self.parceiro.mention}", inline=False)
            await interaction.message.edit(embed=embed_final, view=None)
            for pessoa in (self.autor, self.parceiro):
                try:
                    await pessoa.send(embed=embed_final)
                except discord.Forbidden:
                    pass
            self.stop()

    @discord.ui.button(label="Cancelar 💞", style=discord.ButtonStyle.secondary)
    async def cancelar(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.message.edit(
            content=f"💞 **{self.autor.display_name}** e **{self.parceiro.display_name}** decidiram continuar juntos! ❤️",
            embed=None, view=None
        )
        self.stop()



async def parceiro_autocomplete(interaction: discord.Interaction, current: str):
    autor_id = interaction.user.id
    resultados = []
    parceiro_info = db.obter_casamento(autor_id, interaction.guild.id)
    if parceiro_info:
        parceiro_id = parceiro_info[0]
        parceiro = interaction.guild.get_member(parceiro_id)
        if parceiro and current.lower() in parceiro.display_name.lower():
            resultados.append(app_commands.Choice(name=parceiro.display_name, value=str(parceiro.id)))
    return resultados



class Social(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.subreddits = ["MemesBR"]


    @app_commands.command(name="casar", description="Peça alguém em casamento 💍")
    async def casar(self, interaction: discord.Interaction, usuario: discord.User):
        autor = interaction.user

        if usuario.bot or autor.id == usuario.id:
            await interaction.response.send_message("❌ Casamento inválido.", ephemeral=True)
            return

        if db.verificar_casado(autor.id, interaction.guild.id) or db.verificar_casado(usuario.id, interaction.guild.id):
            await interaction.response.send_message("💔 Um de vocês já está casado!", ephemeral=True)
            return

        embed = discord.Embed(
            title="💍 Pedido de Casamento",
            description=f"**{usuario.mention}**, você aceita se casar com **{autor.mention}**?",
            color=discord.Color.magenta()
        )
        view = PedidoCasamentoView(autor, usuario)
        await interaction.response.send_message(embed=embed, view=view)
        view.message = await interaction.original_response()

        try:
            await asyncio.wait_for(view.evento.wait(), timeout=60)
        except asyncio.TimeoutError:
            await interaction.followup.send("⏳ O pedido de casamento expirou.", ephemeral=True)
            return

        db.salvar_casamento(autor.id, usuario.id, interaction.guild.id)
        db.salvar_casamento(usuario.id, autor.id, interaction.guild.id)

        embed_casamento = discord.Embed(
            title="💍 Casamento Confirmado!",
            description=f"**{autor.mention}** e **{usuario.mention}** agora estão oficialmente casados! ❤️",
            color=discord.Color.purple(),
            timestamp=datetime.now()
        )
        embed_casamento.add_field(name="👫 Cônjuges", value=f"{autor.mention} & {usuario.mention}", inline=False)
        embed_casamento.set_footer(text="💞 Que a felicidade acompanhe vocês!")

        for pessoa in (autor, usuario):
            try:
                await pessoa.send(embed=embed_casamento)
            except discord.Forbidden:
                pass

        view_botao = BotaoNomeCargo(autor, usuario)
        mensagem_botao = await interaction.followup.send(embed=embed_casamento, view=view_botao)
        view_botao.message = mensagem_botao 

    @app_commands.command(name="divorciar", description="Peça o divórcio 😢")
    @app_commands.describe(parceiro="Escolha seu parceiro(a)")
    @app_commands.autocomplete(parceiro=parceiro_autocomplete)
    async def divorciar(self, interaction: discord.Interaction, parceiro: str):
        autor = interaction.user
        parceiro_id = int(parceiro)
        parceiro_member = interaction.guild.get_member(parceiro_id)

        if not parceiro_member:
            await interaction.response.send_message("❌ Não encontrei seu parceiro(a).", ephemeral=True)
            return

        parceiro_info = db.obter_casamento(autor.id, interaction.guild.id)
        if not parceiro_info or parceiro_info[0] != parceiro_id:
            await interaction.response.send_message("❌ Esse usuário não é seu parceiro(a) de casamento.", ephemeral=True)
            return

        view = DivorcioView(autor, parceiro_member)
        embed = discord.Embed(
            title="💔 Pedido de Divórcio",
            description=f"**{autor.mention}** quer se divorciar de **{parceiro_member.mention}**.\nAmbos precisam confirmar.",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed, view=view)
        view.message = await interaction.original_response()


    @app_commands.command(name="meme", description="Envia um meme aleatório de subreddits variados")
    async def meme(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)

        subreddit = random.choice(self.subreddits)
        url = f"https://meme-api.com/gimme/{subreddit}"

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as resp:
                    if resp.status != 200:
                        await interaction.followup.send(
                            f"❌ Não consegui buscar meme de `{subreddit}`. Tente novamente."
                        )
                        return
                    data = await resp.json()

            if not all(key in data for key in ["title", "postLink", "url", "subreddit"]):
                await interaction.followup.send("⚠️ Não encontrei um meme válido.")
                return

            embed = discord.Embed(
                title=data["title"],
                url=data["postLink"],
                color=discord.Color.random()
            )
            embed.set_image(url=data["url"])
            embed.set_footer(text=f"Subreddit: {data['subreddit']}")

            await interaction.followup.send(embed=embed)

        except asyncio.TimeoutError:
            await interaction.followup.send("⏳ A API demorou demais para responder.")
        except Exception as e:
            print(f"[ERROR] meme command falhou: {e}")
            await interaction.followup.send("⚠️ Ocorreu um erro ao tentar buscar um meme.")


async def setup(bot: commands.Bot):
    await bot.add_cog(Social(bot))
