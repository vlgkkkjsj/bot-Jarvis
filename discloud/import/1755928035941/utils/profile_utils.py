from PIL import Image, ImageDraw, ImageFont, ImageOps
import requests, io

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


def check_and_award_badges(db, user_id, guild_id, xp, messages, call_seconds):
    current = set(b['badge_key'] for b in db.get_user_badges(user_id , guild_id))
    new = []
    for key, rule in BADGE_RULES.items():
        if rule(xp, messages , call_seconds) and key not in current:
            db.add_user_badge(user_id, guild_id , key)
            new.append(key)
    return new

def get_badges(db, user_id, guild_id):
    user_badges = db.get_user_badges(user_id, guild_id)
    return [b["badge_key"] for b in user_badges]

def render_badges(badges: list) -> str:

    result = []
    for b in badges:
        emoji = BADGE_EMOJIS.get(b, "")
        name = b.capitalize() 
        result.append(f"{emoji} {name}")
    return "   ".join(result) if result else "Nenhuma"

def generate_profile_text(xp, messages, call_seconds, vitorias, derrotas):
    h, r = divmod(call_seconds, 3600)
    m, s = divmod(r, 60)
    call_time_str = f"{h}h {m}m {s}s"
    return (f"✨ XP: {xp}\n"
            f"💬 Mensagens: {messages}\n"
            f"🕒 Tempo em call: {call_time_str}\n"
            f"🏆 Vitórias: {vitorias} | 💀 Derrotas: {derrotas}")


def generate_profile_image(member, xp, messages, call_seconds, vitorias, derrotas, badges):
    W, H = 900, 300
    base = Image.new("RGBA", (W, H), (30, 30, 40, 255))

    grad = Image.new("RGBA", (W, H), 0)
    grad_draw = ImageDraw.Draw(grad)
    for x in range(W):
        r = int(30 + (x / W) * 40)
        g = int(30 + (x / W) * 50)
        b = int(40 + (x / W) * 60)
        grad_draw.line([(x, 0), (x, H)], fill=(r, g, b, 255))
    base = Image.alpha_composite(base, grad)

    draw = ImageDraw.Draw(base)

    try:
        avatar_bytes = requests.get(member.display_avatar.url, timeout=5).content
        avatar = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA").resize((200, 200))
    except:
        avatar = Image.new("RGBA", (200, 200), (100, 100, 100, 255))
    mask = Image.new("L", (200, 200), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, 200, 200), fill=255)
    avatar = ImageOps.fit(avatar, (200, 200))
    base.paste(avatar, (40, 50), mask)

    border = Image.new("RGBA", (210, 210), (0, 0, 0, 0))
    border_draw = ImageDraw.Draw(border)
    border_draw.ellipse((0,0,210,210), outline=(50,150,255,200), width=8)
    base.alpha_composite(border, (35, 45))

    try:
        font_bold = ImageFont.truetype("DejaVuSans-Bold.ttf", 32)
        font = ImageFont.truetype("DejaVuSans.ttf", 18)
    except:
        font_bold = ImageFont.load_default()
        font = ImageFont.load_default()

    draw.text((270, 50), member.display_name, font=font_bold, fill=(255,255,255))

    draw.text((270, 90), f"XP: {xp}", font=font, fill=(180,200,255))
    draw.text((270, 115), f"Mensagens: {messages}", font=font, fill=(200,255,200))
    draw.text((270, 140), f"Tempo em call: {call_seconds//3600}h {(call_seconds//60)%60}m", font=font, fill=(255,220,200))
    draw.text((270, 165), f"Vitórias: {vitorias} | Derrotas: {derrotas}", font=font, fill=(255,200,200))

    level_data = calculate_level(xp)
    bar_x, bar_y, bar_w, bar_h = 270, 200, 580, 30
    pct = level_data["progress"]
    draw.rounded_rectangle([bar_x, bar_y, bar_x+bar_w, bar_y+bar_h], radius=15, fill=(50,50,60))
    draw.rounded_rectangle([bar_x, bar_y, bar_x+int(bar_w*pct*bar_w), bar_y+bar_h], radius=15, fill=(100,200,255))
    
    draw.text(
        (bar_x + bar_w - 200, bar_y - 25),
        f"Lvl {level_data['level']}  ({int(pct*100)}%)",
        font=font,
        fill=(255,255,255)
    )
    draw.text(
        (bar_x + bar_w - 150, bar_y + 35),
        f"{level_data['xp_into_level']}/{level_data['next_level_xp']} XP",
        font=font,
        fill=(200,200,200)
    )
    
    badge_x, badge_y = 270, 250
    for badge in badges:
        emoji = BADGE_EMOJIS.get(badge, "")
        name = badge.capitalize()
        draw.text((badge_x, badge_y), f"{emoji} {name}", font=font, fill=(100,200,255))
        badge_x += 150  

    draw.rectangle([0,0,W-1,H-1], outline=(255,255,255,50), width=2)

    buffer = io.BytesIO()
    base.save(buffer, "PNG")
    buffer.seek(0)
    return buffer

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
