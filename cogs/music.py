import os
import shutil
import asyncio
import random
from collections import deque

import discord
from discord.ext import commands
from discord import app_commands
import yt_dlp

SONG_QUEUES = {}
PRELOADED_SOURCES = {}
LOOP_MODE = {}
AUTO_DISCONNECT = 60
PRELOAD_LIMIT = 3 

FFMPEG_PATH = shutil.which("ffmpeg") or shutil.which("ffmpeg.exe")
if not FFMPEG_PATH:
    candidate = os.path.join(os.getcwd(), "bin", "ffmpeg.exe")
    if os.path.isfile(candidate):
        FFMPEG_PATH = candidate
    else:
        FFMPEG_PATH = "ffmpeg"
        print("Aviso: ffmpeg não encontrado automaticamente.")

ffmpeg_options = {
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 -nostdin -hide_banner -loglevel error",
    "options": "-vn -bufsize 2M -rtbufsize 1G -threads 4"
}


class Music(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.disconnect_tasks = {}
        self.current_track = {}
        self.play_locks = {}
        self.track_cache = {}  

    async def _extract_info(self, query, ydl_opts=None):
        if ydl_opts is None:
            ydl_opts = {
                "format": "bestaudio/best",
                "noplaylist": True,
                "quiet": True,
                "no_warnings": True,
                "http_headers": {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0 Safari/537.36"
                }
            }
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, lambda: yt_dlp.YoutubeDL(ydl_opts).extract_info(query, download=False))

    async def resolve_track(self, track):
        url = track.get("url")
        if url in self.track_cache:
            return self.track_cache[url]

        try:
            info = await self._extract_info(url)
            stream_url = info.get("url") or (info.get("formats")[0].get("url") if info.get("formats") else None)
            if stream_url:
                self.track_cache[url] = stream_url
            return stream_url
        except Exception as e:
            print(f"[Resolve] Erro ao resolver {track.get('title', '???')} : {e}")
            return None

    async def get_ffmpeg_source(self, audio_url: str) -> discord.FFmpegOpusAudio:
        return discord.FFmpegOpusAudio(audio_url, **ffmpeg_options, executable=FFMPEG_PATH)

    async def preload_audio(self, guild_id, track):
        try:
            stream_url = await self.resolve_track(track)
            if stream_url:
                loop = asyncio.get_running_loop()
                source = await loop.run_in_executor(
                    None,
                    lambda: discord.FFmpegOpusAudio(stream_url, **ffmpeg_options, executable=FFMPEG_PATH)
                )
                PRELOADED_SOURCES.setdefault(guild_id, deque()).append((track, source))
        except Exception as e:
            print(f"[Pré-carregamento] Erro: {e}")

    async def send_now_playing(self, channel, track):
        title = track.get("title", "Sem título")
        url = track.get("webpage_url")
        thumbnail = track.get("thumbnail")
        duration = track.get("duration")
        duration_str = f"{duration//60}:{duration%60:02d}" if duration else "Desconhecida"

        embed = discord.Embed(
            title="🎶 Tocando agora",
            description=f"[**{title}**]({url})" if url else title,
            color=discord.Color.purple()
        )
        embed.add_field(name="⏱️ Duração", value=duration_str, inline=True)
        embed.add_field(name="🎧 Pedido por", value=track.get("requested_by", "Desconhecido"), inline=True)
        if thumbnail:
            embed.set_thumbnail(url=thumbnail)
        embed.set_footer(text="JarvisBot • Powered by yt-dlp + FFmpeg")
        await channel.send(embed=embed)

    async def _play_next(self, guild, channel):
        guild_id = str(guild.id)
        if guild_id not in self.play_locks:
            self.play_locks[guild_id] = asyncio.Lock()

        async with self.play_locks[guild_id]:
            queue = SONG_QUEUES.get(guild_id, deque())
            voice_client = guild.voice_client

            if not queue and LOOP_MODE.get(guild_id) != "song":
                if guild_id in self.disconnect_tasks:
                    self.disconnect_tasks[guild_id].cancel()
                self.disconnect_tasks[guild_id] = asyncio.create_task(self._auto_disconnect(voice_client, guild_id))
                return

            if LOOP_MODE.get(guild_id) == "song" and self.current_track.get(guild_id):
                track = self.current_track[guild_id]
            else:
                if not queue:
                    return
                track = queue.popleft()
                self.current_track[guild_id] = track
                if LOOP_MODE.get(guild_id) == "queue":
                    queue.append(track)

            source = None
            if PRELOADED_SOURCES.get(guild_id):
                try:
                    t, source = PRELOADED_SOURCES[guild_id].popleft()
                    if t["url"] != track["url"]:  
                        source = None
                except IndexError:
                    source = None

            if not source:
                stream_url = await self.resolve_track(track)
                if not stream_url:
                    await channel.send("❌ Erro: não foi possível obter o stream da música.")
                    return
                source = await self.get_ffmpeg_source(stream_url)

            def after_play(error):
                if error:
                    print(f"Erro ao tocar {track.get('title')}: {error}")
                fut = asyncio.run_coroutine_threadsafe(self._play_next(guild, channel), self.bot.loop)
                try:
                    fut.result()
                except Exception as e:
                    print(f"[after_play] Erro ao agendar próxima música: {e}")

            voice_client.play(source, after=after_play)
            await self.send_now_playing(channel, track)

            for next_track in list(queue)[:PRELOAD_LIMIT]:
                
                asyncio.create_task(self.preload_audio(guild_id, next_track))

    async def _auto_disconnect(self, voice_client, guild_id):
        await asyncio.sleep(AUTO_DISCONNECT)
        if voice_client and not voice_client.is_playing():
            try:
                await voice_client.disconnect()
            except Exception:
                pass
            SONG_QUEUES[guild_id] = deque()
            PRELOADED_SOURCES[guild_id] = deque()

    @commands.hybrid_command(name="play", description="Toca uma música")
    async def play(self, ctx: commands.Context, *, search: str):
        await ctx.defer()
        if not ctx.author.voice or not ctx.author.voice.channel:
            return await ctx.send("❌ Você precisa estar em um canal de voz!")

        vc_channel = ctx.author.voice.channel
        voice_client = ctx.guild.voice_client
        if voice_client is None:
            voice_client = await vc_channel.connect()
        elif vc_channel != voice_client.channel:
            await voice_client.move_to(vc_channel)

        query = search if any(s in search for s in ["spotify.com", "soundcloud.com", "youtube.com"]) else "ytsearch1:" + search

        try:
            results = await self._extract_info(query, {"format": "bestaudio/best", "noplaylist": True})
        except Exception as e:
            return await ctx.send(f"❌ Erro ao buscar: {e}")

        track = results["entries"][0] if "entries" in results else results
        track["requested_by"] = ctx.author.mention

        guild_id = str(ctx.guild.id)
        if SONG_QUEUES.get(guild_id) is None:
            SONG_QUEUES[guild_id] = deque()
            PRELOADED_SOURCES[guild_id] = deque()
            LOOP_MODE[guild_id] = "none"
            self.play_locks[guild_id] = asyncio.Lock()

        SONG_QUEUES[guild_id].append(track)
        asyncio.create_task(self.preload_audio(guild_id, track))

        if voice_client.is_playing() or voice_client.is_paused():
            embed = discord.Embed(
                title="➕ Adicionado à Fila",
                description=f"**[{track.get('title')}]({track.get('webpage_url')})**",
                color=discord.Color.green()
            )
            embed.set_thumbnail(url=track.get("thumbnail"))
            await ctx.send(embed=embed)
        else:
            await self._play_next(ctx.guild, ctx.channel)

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if member.bot:
            return
        vc = member.guild.voice_client
        if vc and vc.channel and len(vc.channel.members) == 1:
            await vc.disconnect()

    @commands.hybrid_command(name="skip", description="Pula a música atual")
    async def skip(self, ctx: commands.Context):
        vc = ctx.guild.voice_client
        guild_id = str(ctx.guild.id)
        if vc and vc.is_playing():
            vc.stop()  
            track = self.current_track.get(guild_id)
            embed = discord.Embed(
                title="⏭ Música Pulada",
                description=f"**[{track.get('title','Sem título')}]({track.get('webpage_url','')})**" if track else "Música atual pulada",
                color=discord.Color.orange()
            )
            await ctx.send(embed=embed)
        else:
            await ctx.send("❌ Nenhuma música tocando.")

    @commands.hybrid_command(name="pause", description="Pausa a música atual")
    async def pause(self, ctx: commands.Context):
        vc = ctx.guild.voice_client
        guild_id = str(ctx.guild.id)
        track = self.current_track.get(guild_id)
        if vc and vc.is_playing():
            vc.pause()
            embed = discord.Embed(
                title="⏸ Música Pausada",
                description=f"**[{track.get('title','Sem título')}]({track.get('webpage_url','')})**" if track else "Música pausada",
                color=discord.Color.red()
            )
            embed.set_thumbnail(url=track.get("thumbnail") if track else None)
            await ctx.send(embed=embed)
        else:
            await ctx.send("❌ Nenhuma música para pausar.")

    @commands.hybrid_command(name="resume", description="Continua a música pausada")
    async def resume(self, ctx: commands.Context):
        vc = ctx.guild.voice_client
        guild_id = str(ctx.guild.id)
        track = self.current_track.get(guild_id)
        if vc and vc.is_paused():
            vc.resume()
            embed = discord.Embed(
                title="▶️ Música Retomada",
                description=f"**[{track.get('title','Sem título')}]({track.get('webpage_url','')})**" if track else "Música retomada",
                color=discord.Color.green()
            )
            embed.set_thumbnail(url=track.get("thumbnail") if track else None)
            await ctx.send(embed=embed)
        else:
            await ctx.send("❌ Nenhuma música pausada.")

    @commands.hybrid_command(name="queue", description="Mostra a fila de músicas")
    async def queue(self, ctx: commands.Context):
        guild_id = str(ctx.guild.id)
        queue = SONG_QUEUES.get(guild_id, deque())
        if not queue:
            return await ctx.send("❌ A fila está vazia.")

        pages = [list(queue)[i:i+10] for i in range(0, len(queue), 10)]
        page = 0

        def make_embed(p):
            embed = discord.Embed(
                title=f"📜 Fila de músicas ({len(queue)} no total)",
                description="",
                color=discord.Color.green()
            )
            for i, song in enumerate(p, start=1 + page * 10):
                embed.description += f"**{i}.** [{song.get('title','Sem título')}]({song.get('webpage_url','')})\n"
            embed.set_footer(text=f"Página {page+1}/{len(pages)}")
            return embed

        msg = await ctx.send(embed=make_embed(pages[page]))
        if len(pages) > 1:
            await msg.add_reaction("⬅️")
            await msg.add_reaction("➡️")

            def check(reaction, user):
                return user == ctx.author and str(reaction.emoji) in ["⬅️", "➡️"]

            while True:
                try:
                    reaction, user = await self.bot.wait_for("reaction_add", timeout=30.0, check=check)
                    if str(reaction.emoji) == "➡️" and page < len(pages)-1:
                        page += 1
                        await msg.edit(embed=make_embed(pages[page]))
                    elif str(reaction.emoji) == "⬅️" and page > 0:
                        page -= 1
                        await msg.edit(embed=make_embed(pages[page]))
                    await msg.remove_reaction(reaction, user)
                except asyncio.TimeoutError:
                    break

    @commands.hybrid_command(name="shuffle", description="Embaralha a fila")
    async def shuffle(self, ctx: commands.Context):
        guild_id = str(ctx.guild.id)
        queue = SONG_QUEUES.get(guild_id, deque())
        if not queue:
            return await ctx.send("❌ A fila está vazia.")
        temp = list(queue)
        random.shuffle(temp)
        SONG_QUEUES[guild_id] = deque(temp)
        embed = discord.Embed(
            title="🔀 Fila Embaralhada",
            description="As músicas foram embaralhadas com sucesso.",
            color=discord.Color.blue()
        )
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="loop", description="Define o loop da música ou fila")
    @app_commands.describe(mode="Modo de loop: none, song, queue", track_number="Número da música na fila para colocar em loop (opcional)")
    async def loop(self, ctx: commands.Context, mode: str, track_number: int = None):
        guild_id = str(ctx.guild.id)
        queue = list(SONG_QUEUES.get(guild_id, deque()))
        mode = mode.lower()
        if mode not in ["none", "song", "queue"]:
            return await ctx.send("❌ Modos válidos: `none`, `song`, `queue`")

        if track_number is not None:
            if not queue or track_number < 1 or track_number > len(queue):
                return await ctx.send("❌ Número inválido de música na fila.")
            self.current_track[guild_id] = queue[track_number - 1]
            mode = "song"

        LOOP_MODE[guild_id] = mode
        if mode == "song" and self.current_track.get(guild_id):
            track_title = self.current_track[guild_id].get("title", "Sem título")
            await ctx.send(f"🔁 Música **{track_title}** em loop.")
        else:
            await ctx.send(f"🔁 Loop definido para: `{mode}`")


async def setup(bot: commands.Bot):
    await bot.add_cog(Music(bot))
