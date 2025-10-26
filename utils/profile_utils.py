from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageFilter, ImageColor
import requests, io, numpy as np
import math

# 🎖️ BADGES
BADGE_EMOJIS = {
    "veteran": "🏆",
    "chatter": "💬",
    "caller": "🎧",
    "newbie": "🌱",
    "legend": "🌟"
}

BADGE_RULES = {
    "veteran": lambda xp, msgs, call: xp >= 2000,
    "chatter": lambda xp, msgs, call: msgs >= 1000,
    "caller": lambda xp, msgs, call: call >= 36000,
    "newbie": lambda xp, msgs, call: xp < 100,
    "legend": lambda xp, msgs, call: xp >= 10000
}


# 🏅 Verifica e adiciona badges automaticamente
def check_and_award_badges(db, user_id, guild_id, xp, messages, call_seconds):
    current = set(b['badge_key'] for b in db.get_user_badges(user_id , guild_id))
    new = []
    for key, rule in BADGE_RULES.items():
        if rule(xp, messages , call_seconds) and key not in current:
            db.add_user_badge(user_id, guild_id , key)
            new.append(key)
    return new


# 🔍 Retorna badges do usuário
def get_badges(db, user_id, guild_id):
    user_badges = db.get_user_badges(user_id, guild_id)
    return [b["badge_key"] for b in user_badges]


# 🧩 Renderiza badges como texto
def render_badges(badges: list) -> str:
    result = []
    for b in badges:
        emoji = BADGE_EMOJIS.get(b, "")
        name = b.capitalize() 
        result.append(f"{emoji} {name}")
    return "   ".join(result) if result else "Nenhuma"


# 📜 Texto do perfil (para embed)
def generate_profile_text(xp, messages, call_seconds, vitorias, derrotas):
    h, r = divmod(call_seconds, 3600)
    m, s = divmod(r, 60)
    call_time_str = f"{h}h {m}m {s}s"
    return (f"✨ XP: {xp}\n"
            f"💬 Mensagens: {messages}\n"
            f"🕒 Tempo em call: {call_time_str}\n"
            f"🏆 Vitórias: {vitorias} | 💀 Derrotas: {derrotas}")


# 🎨 Geração do perfil com visual moderno
def generate_profile_image(member, xp, messages, call_seconds, vitorias, derrotas, badges):
    W, H = 900, 300
    base = Image.new("RGBA", (W, H), (0, 0, 0, 0))

    # --- GRADIENTE DE FUNDO (DIAGONAL) ---
    def diagonal_gradient(size, color1, color2):
        w, h = size
        grad = np.zeros((h, w, 4), dtype=np.uint8)
        for y in range(h):
            for x in range(w):
                t = (x + y) / (w + h)
                r = int(color1[0]*(1-t) + color2[0]*t)
                g = int(color1[1]*(1-t) + color2[1]*t)
                b = int(color1[2]*(1-t) + color2[2]*t)
                grad[y, x] = (r, g, b, 255)
        return Image.fromarray(grad, "RGBA")

    grad = diagonal_gradient((W, H), (25, 25, 45), (75, 85, 130))
    base = Image.alpha_composite(base, grad)

    # --- AVATAR COM SOMBRA E BORDA ---
    try:
        avatar_bytes = requests.get(member.display_avatar.url, timeout=5).content
        avatar = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA").resize((200, 200))
    except:
        avatar = Image.new("RGBA", (200, 200), (120, 120, 120, 255))

    mask = Image.new("L", (200, 200), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, 200, 200), fill=255)
    avatar = ImageOps.fit(avatar, (200, 200))

    # sombra suave atrás do avatar
    shadow = avatar.copy().convert("RGBA").filter(ImageFilter.GaussianBlur(10))
    shadow_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    shadow_layer.paste(shadow, (45, 55), mask)
    base = Image.alpha_composite(base, shadow_layer)

    # avatar e borda
    avatar_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    avatar_layer.paste(avatar, (40, 50), mask)
    border = Image.new("RGBA", (210, 210), (0, 0, 0, 0))
    ImageDraw.Draw(border).ellipse((0,0,210,210), outline=(100,180,255,255), width=8)
    avatar_layer.paste(border, (35, 45), border)
    base = Image.alpha_composite(base, avatar_layer)

    # --- FONTES ---
    try:
        font_bold = ImageFont.truetype("DejaVuSans-Bold.ttf", 32)
        font = ImageFont.truetype("DejaVuSans.ttf", 18)
        font_small = ImageFont.truetype("DejaVuSans.ttf", 14)
    except:
        font_bold = ImageFont.load_default()
        font = ImageFont.load_default()
        font_small = ImageFont.load_default()

    draw = ImageDraw.Draw(base)

    # --- TEXTOS ---
    draw.text((270, 50), member.display_name, font=font_bold, fill=(255,255,255))
    draw.text((270, 90), f"✨ XP: {xp}", font=font, fill=(180,200,255))
    draw.text((270, 115), f"💬 Mensagens: {messages}", font=font, fill=(200,255,200))
    draw.text((270, 140), f"🕒 Tempo em call: {call_seconds//3600}h {(call_seconds//60)%60}m", font=font, fill=(255,220,200))
    draw.text((270, 165), f"🏆 Vitórias: {vitorias} | 💀 Derrotas: {derrotas}", font=font, fill=(255,200,200))

    # --- BARRA DE XP COM GRADIENTE ---
    level_data = calculate_level(xp)
    bar_x, bar_y, bar_w, bar_h = 270, 200, 580, 30
    pct = level_data["progress"]

    draw.rounded_rectangle([bar_x, bar_y, bar_x+bar_w, bar_y+bar_h], radius=15, fill=(40,40,60))

    def draw_gradient_bar(draw, x, y, w, h, pct):
        start = ImageColor.getrgb("#4facfe")
        end = ImageColor.getrgb("#00f2fe")
        for i in range(int(w * pct)):
            ratio = i / w
            r = int(start[0]*(1-ratio) + end[0]*ratio)
            g = int(start[1]*(1-ratio) + end[1]*ratio)
            b = int(start[2]*(1-ratio) + end[2]*ratio)
            draw.line([(x+i, y), (x+i, y+h)], fill=(r,g,b), width=1)
    draw_gradient_bar(draw, bar_x, bar_y, bar_w, bar_h, pct)

    draw.text((bar_x, bar_y - 25), f"Nível {level_data['level']} ({int(pct*100)}%)", font=font, fill=(255,255,255))
    draw.text((bar_x + bar_w - 180, bar_y + 35),
              f"{level_data['xp_into_level']}/{level_data['next_level_xp']} XP",
              font=font_small, fill=(200,200,200))

    # --- BADGES ---
    badge_x, badge_y = 270, 250
    for badge in badges:
        emoji = BADGE_EMOJIS.get(badge, "")
        name = badge.capitalize()
        draw.text((badge_x, badge_y), f"{emoji} {name}", font=font, fill=(120,200,255))
        badge_x += 140  

    # --- BORDA EXTERNA ---
    draw.rectangle([0,0,W-1,H-1], outline=(255,255,255,60), width=2)

    # --- FINALIZAÇÃO ---
    buffer = io.BytesIO()
    base.save(buffer, "PNG")
    buffer.seek(0)
    return buffer


# ⚙️ Sistema de nível
def calculate_level(xp: int):
    level = 0
    xp_needed = 500
    remaining_xp = xp
    while remaining_xp >= xp_needed:
        remaining_xp -= xp_needed
        level += 1
        xp_needed = 500 + (level * 100) 
    next_level_xp = xp_needed
    xp_into_level = remaining_xp
    xp_to_next = next_level_xp - xp_into_level
    progress_pct = (xp_into_level / next_level_xp) if next_level_xp > 0 else 0
    return {
        "level": level,
        "xp_into_level": xp_into_level,
        "xp_to_next": xp_to_next,
        "next_level_xp": next_level_xp,
        "progress": progress_pct
    }
