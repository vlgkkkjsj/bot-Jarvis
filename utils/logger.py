import discord
import traceback
from datetime import datetime

_log_cache = {}
_cooldowns = {}
LOG_COOLDOWN = 2  

LOG_STYLES = {
    "info": {"color": discord.Color.blurple(), "emoji": "ℹ️"},
    "warning": {"color": discord.Color.gold(), "emoji": "⚠️"},
    "error": {"color": discord.Color.red(), "emoji": "❌"},
    "success": {"color": discord.Color.green(), "emoji": "✅"},
    "command": {"color": discord.Color.teal(), "emoji": "💬"},
    "message_delete": {"color": discord.Color.dark_red(), "emoji": "🗑️"},
    "message_edit": {"color": discord.Color.orange(), "emoji": "✏️"},
}


async def get_log_channel(guild: discord.Guild) -> discord.TextChannel | None:
    if not guild:
        return None
    if guild.id in _log_cache:
        return _log_cache[guild.id]

    existing = discord.utils.get(guild.text_channels, name="logs-bot")
    if existing:
        _log_cache[guild.id] = existing
        return existing

    overwrites = {guild.default_role: discord.PermissionOverwrite(view_channel=False)}
    for role in guild.roles:
        if role.permissions.administrator:
            overwrites[role] = discord.PermissionOverwrite(view_channel=True, send_messages=False)

    try:
        channel = await guild.create_text_channel("logs-bot", overwrites=overwrites)
        _log_cache[guild.id] = channel
        return channel
    except Exception as e:
        print(f"[LOGGER] ❌ Falha ao criar canal de logs em {guild.name}: {e}")
        return None


def is_on_cooldown(guild_id: int) -> bool:
    last = _cooldowns.get(guild_id, 0)
    now = datetime.utcnow().timestamp()
    return (now - last) < LOG_COOLDOWN

def set_cooldown(guild_id: int):
    _cooldowns[guild_id] = datetime.utcnow().timestamp()


async def send_log(ctx_or_interaction, title: str, fields: dict, log_type: str = "info"):
    try:
        guild = getattr(ctx_or_interaction, "guild", None)
        user = getattr(ctx_or_interaction, "user", getattr(ctx_or_interaction, "author", None))
        if not guild:
            return
        if is_on_cooldown(guild.id):
            return

        channel = await get_log_channel(guild)
        if not channel:
            return

        style = LOG_STYLES.get(log_type, LOG_STYLES["info"])

        embed = discord.Embed(
            title=f"{style['emoji']} {title}",
            color=style['color'],
            timestamp=datetime.utcnow()
        )

        for name, value in fields.items():
            embed.add_field(name=name, value=value, inline=False)

        if user:
            embed.set_thumbnail(url=user.display_avatar.url)

        embed.set_footer(text=f"Servidor: {guild.name} | Usuário: {user}", icon_url=user.display_avatar.url if user else None)

        await channel.send(embed=embed)
        set_cooldown(guild.id)

    except Exception as e:
        print(f"[LOGGER] Falha ao enviar log: {e}")
        traceback.print_exc()


async def log_command(ctx_or_interaction, success=True):
    guild = getattr(ctx_or_interaction, "guild", None)
    if not guild:
        return

    status = "success" if success else "error"
    user = getattr(ctx_or_interaction, "user", getattr(ctx_or_interaction, "author", None))
    channel = getattr(ctx_or_interaction, "channel", None)
    command = getattr(
        getattr(ctx_or_interaction, "command", None),
        "name",
        getattr(getattr(ctx_or_interaction, "command", None), "qualified_name", "desconhecido")
    )

    fields = {
        "👤 Usuário": f"{user} ({user.id})" if user else "Desconhecido",
        "💬 Comando": f"/{command}",
        "📍 Canal": channel.mention if channel else "DM"
    }

    await send_log(ctx_or_interaction, f"Comando executado: /{command}", fields, log_type=status)


async def log_error(ctx_or_interaction, error: Exception):
    guild = getattr(ctx_or_interaction, "guild", None)
    if not guild:
        return

    tb = "".join(traceback.format_exception(type(error), error, error.__traceback__))[-1800:]
    fields = {
        "🧠 Tipo": type(error).__name__,
        "📜 Erro": f"```py\n{str(error)}\n```",
        "📂 Traceback": f"```py\n{tb}\n```",
    }

    await send_log(ctx_or_interaction, "Erro detectado no bot", fields, log_type="error")


async def log_message_edit(before: discord.Message, after: discord.Message):
    if before.author.bot or not before.guild or before.content == after.content:
        return

    diff = {
        "✏️ Antes": (before.content[:1020] + "...") if len(before.content) > 1020 else before.content or "*vazio*",
        "🆕 Depois": (after.content[:1020] + "...") if len(after.content) > 1020 else after.content or "*vazio*",
        "📍 Canal": before.channel.mention
    }

    await send_log(before, f"Mensagem editada por {before.author}", diff, log_type="message_edit")


async def log_message_delete(message: discord.Message):
    if message.author.bot or not message.guild:
        return

    fields = {
        "🗑️ Conteúdo": (message.content[:1020] + "...") if len(message.content) > 1020 else message.content or "*vazio*",
        "📍 Canal": message.channel.mention
    }

    await send_log(message, f"Mensagem deletada por {message.author}", fields, log_type="message_delete")
