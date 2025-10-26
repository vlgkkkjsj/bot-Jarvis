import discord

async def send_log(ctx, title, fields):
    existing = discord.utils.get(ctx.guild.text_channels, name="logs-bot")
    if existing:
        log_channel = existing
    else:
        overwrites = {
            ctx.guild.default_role: discord.PermissionOverwrite(view_channel=False),
        }
        for role in ctx.guild.roles:
            if role.permissions.administrator:
                overwrites[role] = discord.PermissionOverwrite(view_channel=True, send_messages=False)
        log_channel = await ctx.guild.create_text_channel("logs-bot", overwrites=overwrites)

    embed = discord.Embed(title=title, color=discord.Color.blurple(), timestamp=ctx.created_at)
    for name, value in fields.items():
        embed.add_field(name=name, value=value, inline=False)
    embed.set_footer(text=f"Servidor: {ctx.guild.name}")
    await log_channel.send(embed=embed)

