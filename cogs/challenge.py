import discord
from discord.ext import commands, tasks
from discord import app_commands
from discord.ui import View, Modal, TextInput, Button
from datetime import datetime
import random
import asyncio
import db

COOLDOWN_SECONDS = 10



class CreateChallengeModal(Modal, title="🧠 Criar Novo Desafio"):
    nome = TextInput(label="Nome do Desafio", placeholder="Ex: Hackathon de Bots", required=True)
    tema = TextInput(label="Tema", placeholder="Ex: Automação, IA, Games...", required=True)
    tecnologias = TextInput(label="Tecnologias", placeholder="Ex: Python, JS, etc", required=True)
    periodo = TextInput(label="Período (dd/mm/yyyy - dd/mm/yyyy)", placeholder="Ex: 24/10/2025 - 26/10/2025", required=True)
    descricao = TextInput(label="Descrição do Desafio", style=discord.TextStyle.paragraph, required=True)

    async def on_submit(self, interaction: discord.Interaction):
        guild_id = interaction.guild.id
        try:
            inicio_str, fim_str = [s.strip() for s in self.periodo.value.split("-")]
            start_date = datetime.strptime(inicio_str, "%d/%m/%Y")
            end_date = datetime.strptime(fim_str, "%d/%m/%Y")
        except ValueError:
            return await interaction.response.send_message("❌ Formato inválido! Use **dd/mm/yyyy - dd/mm/yyyy**", ephemeral=True)

        db.create_challenge(
            guild_id,
            self.nome.value,
            self.tema.value,
            self.tecnologias.value,
            start_date.isoformat(),
            end_date.isoformat(),
            self.descricao.value,
        )

        embed = discord.Embed(
            title=f"🏁 Novo Desafio: {self.nome.value}",
            description=self.descricao.value,
            color=discord.Color.blurple(),
            timestamp=datetime.utcnow()
        )
        embed.add_field(name="🎯 Tema", value=self.tema.value, inline=False)
        embed.add_field(name="🧰 Tecnologias", value=self.tecnologias.value, inline=False)
        embed.add_field(name="📅 Período", value=self.periodo.value)
        embed.set_footer(text="Use /entrar para participar!")

        view = JoinChallengeView()
        await interaction.response.send_message("✅ Desafio criado com sucesso!", ephemeral=True)
        await interaction.channel.send(embed=embed, view=view)


class JoinChallengeModal(Modal, title="📋 Entrar no Desafio"):
    confirm = TextInput(label="Digite SIM para confirmar", required=True)

    async def on_submit(self, interaction: discord.Interaction):
        guild_id = interaction.guild.id
        challenge = db.get_active_challenge(guild_id)
        if not challenge:
            return await interaction.response.send_message("Nenhum desafio ativo!", ephemeral=True)
        challenge_id = challenge[0]

        if self.confirm.value.strip().lower() != "sim":
            return await interaction.response.send_message("Participação cancelada.", ephemeral=True)

        success = db.add_participant(guild_id, interaction.user.id)
        if not success:
            return await interaction.response.send_message("Você já está participando deste desafio!", ephemeral=True)

        participantes = db.get_participants(guild_id, challenge_id)
        embed = discord.Embed(
            title="🎉 Participação confirmada!",
            description=f"👥 Participantes atuais: {len(participantes)}",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)



class ConfirmChallengeView(View):
    def __init__(self, author: discord.Member):
        super().__init__(timeout=60)
        self.author = author

    @discord.ui.select(
        placeholder="Deseja criar um novo desafio?",
        options=[
            discord.SelectOption(label="Sim", value="yes", emoji="✅"),
            discord.SelectOption(label="Não", value="no", emoji="❌")
        ]
    )
    async def select_callback(self, interaction: discord.Interaction, select: discord.ui.Select):
        if interaction.user != self.author:
            return await interaction.response.send_message("Somente quem iniciou pode confirmar.", ephemeral=True)
        if select.values[0] == "yes":
            await interaction.response.send_modal(CreateChallengeModal())
        else:
            await interaction.response.send_message("Criação cancelada.", ephemeral=True)


class JoinChallengeView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Entrar no Desafio", style=discord.ButtonStyle.success)
    async def join_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(JoinChallengeModal())



class UpdateTeamsView(View):
    def __init__(self, cog, guild_id):
        super().__init__(timeout=None)
        self.cog = cog
        self.guild_id = guild_id

    @discord.ui.button(label="🔄 Atualizar Times", style=discord.ButtonStyle.primary, custom_id="refresh_teams")
    async def refresh(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.show_teams(interaction, self.guild_id, refresh=True)



class ParticipantsView(View):
    def __init__(self, cog, guild_id, participants, page=0):
        super().__init__(timeout=None)
        self.cog = cog
        self.guild_id = guild_id
        self.participants = participants
        self.page = page
        self.per_page = 5

    def get_page_data(self):
        start = self.page * self.per_page
        end = start + self.per_page
        return self.participants[start:end]

    @discord.ui.button(label="⬅️", style=discord.ButtonStyle.secondary)
    async def previous(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.page > 0:
            self.page -= 1
            await self.cog.show_participants(interaction, self.guild_id, self.participants, self.page)
        else:
            await interaction.response.defer(ephemeral=True)

    @discord.ui.button(label="🔄 Atualizar Participantes", style=discord.ButtonStyle.primary)
    async def refresh(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.show_participants(interaction, self.guild_id, None, self.page, refresh=True)

    @discord.ui.button(label="➡️", style=discord.ButtonStyle.secondary)
    async def next(self, interaction: discord.Interaction, button: discord.ui.Button):
        if (self.page + 1) * self.per_page < len(self.participants):
            self.page += 1
            await self.cog.show_participants(interaction, self.guild_id, self.participants, self.page)
        else:
            await interaction.response.defer(ephemeral=True)



class Challenge(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.challenge_timer.start()
        self.last_sort = {}
        self.last_view = {}

    @app_commands.command(name="challenge_start", description="Cria um novo desafio (ADM)")
    @commands.has_permissions(administrator=True)
    async def challenge_start(self, interaction: discord.Interaction):
        view = ConfirmChallengeView(interaction.user)
        await interaction.response.send_message("Deseja criar um novo desafio?", view=view, ephemeral=True)

    @app_commands.command(name="entrar", description="Entrar no desafio atual")
    async def entrar(self, interaction: discord.Interaction):
        await interaction.response.send_modal(JoinChallengeModal())

    @app_commands.command(name="sair_time", description="Sair do time atual")
    async def sair_time(self, interaction: discord.Interaction):
        guild_id = interaction.guild.id
        try:
            db.remove_participant_from_team(guild_id, interaction.user.id)
            await interaction.response.send_message("🚪 Você saiu do seu time.", ephemeral=True)
        except Exception as e:
            print(f"[DB ERROR sair_time] {e}")
            await interaction.response.send_message("❌ Erro ao sair do time (ver logs).", ephemeral=True)

    @app_commands.command(name="sair_desafio", description="Sair completamente do desafio atual")
    async def sair_desafio(self, interaction: discord.Interaction):
        guild_id = interaction.guild.id
        try:
            db.remove_participant_from_team(guild_id, interaction.user.id)
            db.remove_participant(guild_id, interaction.user.id)
            await interaction.response.send_message("✅ Você saiu do desafio e do time.", ephemeral=True)
        except Exception as e:
            print(f"[DB ERROR sair_desafio] {e}")
            await interaction.response.send_message("❌ Erro ao sair do desafio.", ephemeral=True)

    @app_commands.command(name="sortear_times", description="Sorteia times do desafio (ADM)")
    @commands.has_permissions(administrator=True)
    async def sortear_times(self, interaction: discord.Interaction, num_times: int = 2):
        guild_id = interaction.guild.id
        now = datetime.utcnow().timestamp()
        if self.last_sort.get(guild_id) and now - self.last_sort[guild_id] < COOLDOWN_SECONDS:
            return await interaction.response.send_message(
                f"⏳ Aguarde {COOLDOWN_SECONDS}s antes de sortear novamente.", ephemeral=True
            )
        self.last_sort[guild_id] = now

        challenge = db.get_active_challenge(guild_id)
        if not challenge:
            return await interaction.response.send_message("Nenhum desafio ativo!", ephemeral=True)

        challenge_id = challenge[0]
        teams = db.create_teams_for_challenge(guild_id, challenge_id, num_times)
        if not teams:
            return await interaction.response.send_message("Não há participantes suficientes!", ephemeral=True)

        linguagens = [
            "Python", "JavaScript", "C++", "Rust", "Go", "C#", "Java", "TypeScript",
            "Kotlin", "Swift", "Ruby", "Perl", "Dart", "Lua", "Haskell", "Elixir",
            "PHP", "R", "Scala", "Clojure"
        ]
        random.shuffle(linguagens)

        embed = discord.Embed(
            title=f"🎲 Times Sorteados — {challenge[2]}",
            description="✨ Aqui estão os times formados para o desafio atual!",
            color=discord.Color.gold(),
            timestamp=datetime.utcnow()
        )
        embed.set_footer(text=f"Servidor: {interaction.guild.name}", icon_url=interaction.guild.icon.url if interaction.guild.icon else None)

        for i, team in enumerate(teams):
            nome_time = linguagens[i % len(linguagens)]
            membros = [
                interaction.guild.get_member(uid).mention if interaction.guild.get_member(uid)
                else f"<@{uid}>"
                for uid in team["members"]
            ]
            membros_texto = "\n".join(membros) if membros else "*Sem membros*"
            embed.add_field(
                name=f"💻 Time **{nome_time}**",
                value=f"{membros_texto}",
                inline=True  
            )

        if len(teams) % 2 != 0:
            embed.add_field(name="\u200b", value="\u200b", inline=True)

        await interaction.response.send_message(embed=embed)


    @app_commands.command(name="end_challenge", description="Encerra o desafio ativo (ADM)")
    @commands.has_permissions(administrator=True)
    async def end_challenge(self, interaction: discord.Interaction):
        guild_id = interaction.guild.id
        challenge = db.get_active_challenge(guild_id)
        if not challenge:
            return await interaction.response.send_message("Nenhum desafio ativo para encerrar.", ephemeral=True)
        try:
            db.end_active_challenge(guild_id)
            await interaction.response.send_message("✅ Desafio encerrado com sucesso!", ephemeral=False)
        except Exception as e:
            print(f"[DB ERROR] end_active_challenge: {e}")
            await interaction.response.send_message("❌ Erro ao encerrar o desafio (ver logs).", ephemeral=True)


    async def show_teams(self, interaction, guild_id, refresh=False):
        challenge = db.get_active_challenge(guild_id)
        if not challenge:
            return await interaction.response.send_message("❌ Nenhum desafio ativo encontrado.", ephemeral=True)

        challenge_id = challenge[0]
        teams = db.get_teams(guild_id, challenge_id)
        if not teams:
            return await interaction.response.send_message("⚠️ Nenhum time foi sorteado ainda!", ephemeral=True)

        start = datetime.fromisoformat(challenge[5]).strftime("%d/%m/%Y")
        end = datetime.fromisoformat(challenge[6]).strftime("%d/%m/%Y")

        embed = discord.Embed(
            title=f"🏁 {challenge[2]}",
            description=f"🧠 **{challenge[3]}**\n\n{challenge[7]}",
            color=discord.Color.blurple(),
            timestamp=datetime.utcnow()
        )
        embed.add_field(name="🎯 Tema", value=challenge[3], inline=False)
        embed.add_field(name="🧰 Tecnologias", value=challenge[4], inline=False)
        embed.add_field(name="📅 Período", value=f"{start} → {end}", inline=False)
        embed.add_field(name="👥 Times Formados", value="═══════════════════════", inline=False)

        for team in teams:
            membros = [
                interaction.guild.get_member(uid).mention if interaction.guild.get_member(uid)
                else f"<@{uid}>"
                for uid in team["members"]
            ]
            membros_texto = "\n".join(membros) if membros else "*Sem membros no momento*"
            embed.add_field(name=f"💻 **{team['team_name']}**", value=membros_texto, inline=True)

        if len(teams) % 2 != 0:
            embed.add_field(name="\u200b", value="\u200b", inline=True)

        view = UpdateTeamsView(self, guild_id)
        if refresh:
            await interaction.response.edit_message(embed=embed, view=view)
        else:
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)



    @app_commands.command(name="ver_times", description="Mostra todos os times e informações do desafio")
    async def ver_times(self, interaction: discord.Interaction):
        await self.show_teams(interaction, interaction.guild.id)


    async def show_participants(self, interaction, guild_id, participants=None, page=0, refresh=False):
        challenge = db.get_active_challenge(guild_id)
        if not challenge:
            return await interaction.response.send_message("❌ Nenhum desafio ativo encontrado.", ephemeral=True)

        challenge_id = challenge[0]
        if participants is None:
            participants = db.get_participants(guild_id, challenge_id)

        page_size = 5
        start = page * page_size
        end = start + page_size
        page_participants = participants[start:end]

        mentions = [
            interaction.guild.get_member(uid).mention if interaction.guild.get_member(uid)
            else f"<@{uid}>"
            for uid in page_participants
        ]

        embed = discord.Embed(
            title=f"👥 Participantes do Desafio — Página {page + 1}/{(len(participants) - 1)//page_size + 1}",
            description="\n".join(mentions) if mentions else "*Sem participantes ainda.*",
            color=discord.Color.teal(),
            timestamp=datetime.utcnow()
        )
        embed.set_footer(text=f"Total: {len(participants)} participantes")

        view = ParticipantsView(self, guild_id, participants, page)
        if refresh:
            await interaction.response.edit_message(embed=embed, view=view)
        else:
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @app_commands.command(name="participants", description="Mostra todos os participantes do desafio (ADM)")
    @commands.has_permissions(administrator=True)
    async def participants(self, interaction: discord.Interaction):
        await self.show_participants(interaction, interaction.guild.id)


    @tasks.loop(minutes=1)
    async def challenge_timer(self):
        await self.bot.wait_until_ready()
        for guild in self.bot.guilds:
            challenge = db.get_active_challenge(guild.id)
            if not challenge:
                continue
            start_time = datetime.fromisoformat(challenge[5])
            end_time = datetime.fromisoformat(challenge[6])
            now = datetime.utcnow()
            canal = guild.system_channel or next((c for c in guild.text_channels if c.permissions_for(guild.me).send_messages), None)
            if not canal:
                continue
            if now >= end_time:
                db.end_active_challenge(guild.id)
                await canal.send("🏁 **O desafio acabou!** Espero que tenham se divertido!")
            elif abs((now - start_time).total_seconds()) < 60:
                await canal.send("🚀 **O desafio começou!** Boa sorte a todos!")

    @challenge_timer.before_loop
    async def before_timer(self):
        await self.bot.wait_until_ready()


async def setup(bot):
    await bot.add_cog(Challenge(bot))
