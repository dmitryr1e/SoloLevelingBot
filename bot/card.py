"""Генерация карточки охотника — тёмная неоновая эстетика Solo Leveling."""
import io

import qrcode
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from bot import config, share

# Палитра: тёмный фон + синий неон + белый текст (+ красный для HP)
BG = (8, 11, 22)
PANEL = (13, 18, 34)
NEON = (56, 189, 248)        # неоново-голубой
NEON_DIM = (30, 90, 140)
GOLD = (250, 204, 21)        # золото для Монарха
GOLD_DIM = (150, 120, 20)
TEXT = (232, 240, 250)
TEXT_DIM = (120, 140, 170)
HP_RED = (248, 80, 96)

W, H = 800, 1240


def _make_qr(link: str, accent) -> Image.Image:
    """Неоновый QR-код с реф-ссылкой."""
    qr = qrcode.QRCode(border=1, box_size=4)
    qr.add_data(link)
    qr.make(fit=True)
    return qr.make_image(fill_color=accent, back_color=BG).convert("RGBA")


def _font(size: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(str(config.FONT_PATH), size)
    except OSError:
        return ImageFont.load_default(size)


def _neon_text(base: Image.Image, xy, text, font, fill=NEON, glow=NEON, anchor=None):
    """Текст со свечением: рисуем на слое, размываем, накладываем."""
    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.text(xy, text, font=font, fill=(*glow, 200), anchor=anchor)
    layer = layer.filter(ImageFilter.GaussianBlur(6))
    base.alpha_composite(layer)
    ImageDraw.Draw(base).text(xy, text, font=font, fill=fill, anchor=anchor)


def _bar(draw: ImageDraw.ImageDraw, x, y, w, h, ratio, color):
    ratio = max(0.0, min(1.0, ratio))
    draw.rounded_rectangle([x, y, x + w, y + h], radius=h // 2, fill=(20, 28, 48))
    if ratio > 0:
        draw.rounded_rectangle(
            [x, y, x + max(h, int(w * ratio)), y + h], radius=h // 2, fill=color
        )
    draw.rounded_rectangle([x, y, x + w, y + h], radius=h // 2, outline=NEON_DIM, width=2)


def render_card(user, hd: bool = False, premium: bool | None = None) -> bytes:
    if premium is None:
        premium = bool(user["is_premium"])
    # Тема: золото для Монарха, неон для остальных
    ACCENT = GOLD if premium else NEON
    ACCENT_DIM = GOLD_DIM if premium else NEON_DIM

    img = Image.new("RGBA", (W, H), BG)
    draw = ImageDraw.Draw(img)

    # Фоновая сетка
    for gx in range(0, W, 40):
        draw.line([(gx, 0), (gx, H)], fill=(14, 19, 34), width=1)
    for gy in range(0, H, 40):
        draw.line([(0, gy), (W, gy)], fill=(14, 19, 34), width=1)

    # Неоновая рамка
    frame_layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    fd = ImageDraw.Draw(frame_layer)
    fd.rounded_rectangle([16, 16, W - 16, H - 16], radius=24, outline=(*ACCENT, 180), width=4)
    img.alpha_composite(frame_layer.filter(ImageFilter.GaussianBlur(8)))
    draw.rounded_rectangle([16, 16, W - 16, H - 16], radius=24, outline=ACCENT, width=3)

    # Заголовок
    f_head = _font(26)
    draw.text((48, 52), "⟦ СИСТЕМА ⟧", font=f_head, fill=TEXT_DIM)
    title = "КАРТОЧКА МОНАРХА" if premium else "КАРТОЧКА ОХОТНИКА"
    draw.text((48, 88), title, font=_font(34), fill=TEXT)
    draw.line([(48, 140), (W - 48, 140)], fill=ACCENT_DIM, width=2)

    # Ранг — большая буква справа со свечением
    rank = config.rank_for_level(user["level"])
    _neon_text(img, (W - 130, 240), rank, _font(170), fill=ACCENT, glow=ACCENT, anchor="mm")
    draw.text((W - 130, 340), "РАНГ", font=_font(24), fill=TEXT_DIM, anchor="mm")

    # Имя и уровень
    name = (user["first_name"] or user["username"] or "ОХОТНИК").upper()[:16]
    draw.text((48, 180), name, font=_font(52), fill=TEXT)
    draw.text((48, 250), f"УРОВЕНЬ {user['level']}", font=_font(34), fill=ACCENT)

    xp_needed = config.xp_to_next(user["level"])
    draw.text((48, 300), f"ОПЫТ  {user['xp']} / {xp_needed}", font=_font(22), fill=TEXT_DIM)
    _bar(draw, 48, 332, 500, 18, user["xp"] / xp_needed, ACCENT)

    # HP
    y = 400
    hp_ratio = user["hp"] / user["max_hp"]
    hp_color = HP_RED if hp_ratio < 0.35 else ACCENT
    draw.text((48, y), f"HP  {user['hp']} / {user['max_hp']}", font=_font(26), fill=TEXT)
    _bar(draw, 48, y + 40, W - 96, 26, hp_ratio, hp_color)

    # Статы
    y = 520
    draw.text((48, y), "ХАРАКТЕРИСТИКИ", font=_font(24), fill=TEXT_DIM)
    y += 44
    max_stat = max(20, max(user[s] for s in config.STATS) + 5)
    for stat in config.STATS:
        value = user[stat]
        draw.text((48, y), config.STAT_FULL[stat].upper(), font=_font(24), fill=TEXT)
        draw.text((W - 48, y), str(value), font=_font(24), fill=ACCENT, anchor="ra")
        _bar(draw, 48, y + 34, W - 96, 14, value / max_stat, ACCENT)
        y += 78

    # Стрик
    y += 10
    draw.line([(48, y), (W - 48, y)], fill=ACCENT_DIM, width=2)
    y += 24
    draw.text((48, y), f"СЕРИЯ ДНЕЙ: {user['streak']}", font=_font(30), fill=TEXT)
    draw.text(
        (W - 48, y + 4),
        f"РЕКОРД {user['best_streak']}",
        font=_font(22),
        fill=TEXT_DIM,
        anchor="ra",
    )

    # QR-код с реф-ссылкой (внизу слева) + подпись.
    # Формат ссылки живёт в bot/share.py: его же разбирает handlers/common,
    # и расхождение дало бы QR, по которому вербовка не засчитывается.
    qr_img = _make_qr(share.ref_link(user["user_id"]), ACCENT)
    qr_size = 130
    qr_img = qr_img.resize((qr_size, qr_size), Image.NEAREST)
    qr_y = H - qr_size - 44
    img.alpha_composite(qr_img, (48, qr_y))
    draw.text((48 + qr_size + 20, qr_y + 24), "ПРИСОЕДИНЯЙСЯ К ОХОТЕ", font=_font(24), fill=TEXT)
    draw.text((48 + qr_size + 20, qr_y + 60), f"@{config.BOT_USERNAME}", font=_font(26), fill=ACCENT)
    footer = "SOLO LEVELING SYSTEM" + ("  //  МОНАРХ" if premium else "")
    draw.text((48 + qr_size + 20, qr_y + 98), footer, font=_font(18), fill=TEXT_DIM)

    if hd:
        img = img.resize((W * 2, H * 2), Image.LANCZOS)

    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="PNG")
    return buf.getvalue()
