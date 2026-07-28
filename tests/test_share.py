"""Вирусность (спринт Б, п. 14): реф-ссылка, кнопка «Поделиться», share-тексты.

Проверяем три класса дефектов, которые не поймают ни ruff, ни типы:
1) ссылка ведёт не туда или ломается кодированием — вербовка молча не
   засчитывается, а охотник об этом не узнает;
2) share-текст персональный, значит кнопка обязана нести реф-параметр
   именно того, кто делится, — иначе пользователь дарит вербовку чужому;
3) кнопка появляется в моменты гордости (веха, ранг), а не в каждом
   сообщении — иначе диалог превращается в шум.
"""
from urllib.parse import parse_qs, urlparse

from bot import config, game, keyboards, render, share, texts
from bot.handlers.card import cmd_card
from bot.handlers.social import cmd_ref

# ---------- ссылка и URL шеринга ----------

def test_ref_link_matches_deep_link_parser():
    """Главный регресс: ссылку разбирает handlers/common._parse_ref.

    Если формат разъедется, регистрация по ссылке пройдёт, но referrer
    не определится — бонусы не начислятся, и ошибка будет невидимой.
    """
    from bot.handlers.common import _parse_ref

    link = share.ref_link(777)
    payload = parse_qs(urlparse(link).query)["start"][0]

    assert config.BOT_USERNAME in link
    assert _parse_ref(payload) == 777


def test_share_url_carries_encoded_text_and_ref_link():
    text = "Ранг A & уровень 45\nПрисоединяйся"
    url = share.share_url(42, text)
    query = parse_qs(urlparse(url).query)

    # parse_qs декодирует обратно: значит кодирование было корректным и «&»
    # внутри текста не оторвал остаток в отдельный параметр
    assert query["url"] == [share.ref_link(42)]
    assert query["text"] == [text]
    assert url.startswith("https://t.me/share/url?")


def test_share_url_encodes_ampersand_and_newlines():
    """Незакодированный «&» обрезал бы текст на первом же символе."""
    url = share.share_url(1, "a&b\nc")

    assert "a&b" not in url.split("text=")[1]
    assert "%26" in url and "%0A" in url


def test_card_text_uses_real_rank_for_level():
    class FakeUser(dict):
        pass

    user = FakeUser(level=45, streak=12)
    text = share.card_text(user)

    assert config.rank_for_level(45) in text
    assert "12" in text


def test_share_texts_have_no_html():
    """SHARE_* уходят в чат друга как обычный текст — теги отобразились бы как есть."""
    for template in (texts.SHARE_CARD, texts.SHARE_MILESTONE, texts.SHARE_RANK):
        assert "<" not in template and ">" not in template


# ---------- клавиатуры ----------

def test_share_button_is_url_button_not_callback():
    """switch_inline_query/callback здесь не годятся: нужен штатный шеринг Telegram."""
    button = keyboards.share_button(5, "текст")

    assert button.callback_data is None
    assert button.url == share.share_url(5, "текст")


def test_message_markup_combines_upsell_and_share():
    """У сообщения одна reply_markup: две клавиатуры собрать нельзя, вторая затрёт первую."""
    kb = keyboards.message_markup(
        upsell_key=config.UPSELL_FREEZE, share_for=(9, "текст")
    )

    assert len(kb.inline_keyboard) == 2
    assert kb.inline_keyboard[0][0].callback_data == "buy:freeze"
    assert kb.inline_keyboard[1][0].text == keyboards.SHARE_LABEL


def test_message_markup_without_anything_is_none():
    assert keyboards.message_markup() is None
    assert keyboards.message_markup(upsell_key=None, share_for=None) is None


# ---------- share-тексты из рендера ----------

def test_milestone_message_offers_share_and_no_upsell():
    events = game.DayEvents(
        new_day=True,
        quests_issued=4,
        streak=7,
        milestone=(7, 100, 1),
        hp=100,
        max_hp=100,
    )

    milestone = [m for m in render.render_day_messages(events) if m.share]

    assert len(milestone) == 1
    assert "7" in milestone[0].share
    # Веха — момент гордости, продавать тут нечего
    assert milestone[0].upsell is None


def test_rank_up_carries_share_but_level_up_does_not():
    """Уровни растут постоянно; кнопка на каждом — шум. Ранг меняется 6 раз за игру."""
    result = game.XpResult(levels_gained=[(10, "СИЛ", 1)], rank_up="D")

    messages = render.render_xp_messages(result)

    assert messages[0].share is None
    assert messages[1].share is not None and "D" in messages[1].share


def test_painful_messages_carry_no_share():
    """Делиться смертью и сгоревшей серией никто не будет — предлагать неуместно."""
    events = game.DayEvents(
        new_day=True,
        quests_issued=4,
        missed=3,
        damage=24,
        died=True,
        death_level=4,
        hp=50,
        max_hp=100,
    )

    assert all(m.share is None for m in render.render_day_messages(events))


def test_render_xp_result_still_returns_plain_texts():
    """Старый строковый API сохранён — на него опирается существующий код."""
    result = game.XpResult(levels_gained=[(11, "ИНТ", 2)], rank_up="C")

    plain = render.render_xp_result(result)

    assert all(isinstance(t, str) for t in plain)
    assert plain == [m.text for m in render.render_xp_messages(result)]


# ---------- хендлеры ----------

class FakeMessage:
    """Минимум, который нужен /card и /ref: from_user.id, answer, answer_photo."""

    def __init__(self, user_id: int = 1):
        self.from_user = type("U", (), {"id": user_id})()
        self.answers: list[tuple[str, object]] = []
        self.photos: list[tuple[str, object]] = []

    async def answer(self, text: str, reply_markup=None, **kwargs) -> None:
        self.answers.append((text, reply_markup))

    async def answer_photo(self, photo, caption: str = "", reply_markup=None, **kwargs):
        self.photos.append((caption, reply_markup))


async def test_card_caption_has_ref_link_and_share_button(user):
    """Пересланную карточку читают с телефона — QR с того же экрана не отсканировать."""
    message = FakeMessage()

    await cmd_card(message)

    caption, markup = message.photos[0]
    assert share.ref_link(1) in caption
    assert markup.inline_keyboard[0][0].url == share.share_url(
        1, share.card_text(await _reload(1))
    )


async def test_ref_command_has_share_button(user):
    message = FakeMessage()

    await cmd_ref(message)

    _, markup = message.answers[0]
    button = markup.inline_keyboard[0][0]

    assert button.text == keyboards.SHARE_LABEL
    # Ссылка внутри url-параметра закодирована, поэтому сверяем через разбор
    assert parse_qs(urlparse(button.url).query)["url"] == [share.ref_link(1)]


async def _reload(user_id: int):
    from bot import db

    return await db.get_user(user_id)
