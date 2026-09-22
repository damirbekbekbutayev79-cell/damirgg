"""Qiziqish va xarakter bo'yicha do'st topuvchi Telegram bot.

Stack: Python 3.10+, aiogram 3.x, SQLite (standart kutubxona).
Ishga tushirish:
    pip install -r requirements.txt
    export BOT_TOKEN="123456:ABC..."     # Windows: set BOT_TOKEN=...
    python bot.py
"""
import asyncio
import json
import logging
import os
import re
import sqlite3

from aiogram import BaseMiddleware, Bot, Dispatcher, F, Router
from aiogram.exceptions import TelegramAPIError, TelegramUnauthorizedError
from aiogram.filters import CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)

from questions import QUESTIONS

# --------------------------------------------------------------------------
# Sozlamalar
# --------------------------------------------------------------------------
def _load_env():
    """bot.py yonidagi .env faylidan KEY=VALUE qatorlarini o'qiydi."""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip("\"'"))


_load_env()
TOKEN = os.getenv("BOT_TOKEN", "")
DB_PATH = os.getenv("DB_PATH", "bot.db")
MAX_PICK = 6      # bitta savolda ko'pi bilan nechta variant
MAX_EDITS = 5     # profilni o'zgartirish limiti
TOP_N = 10        # top ro'yxat uzunligi
LANGS = ("uz", "en", "ru")

# Profil maydonlari (bazadagi ustun nomlari, so'raladigan tartibda)
STEPS = [
    "first_name", "last_name", "patronymic", "age",
    "region", "phone", "username",
]

# --------------------------------------------------------------------------
# Matnlar (uz, en, ru)
# --------------------------------------------------------------------------
T = {
    "welcome": (
        "👋 Botga xush kelibsiz!\nIltimos, profilingizni kiriting.",
        "👋 Welcome to the bot!\nPlease fill in your profile.",
        "👋 Добро пожаловать в бот!\nПожалуйста, заполните свой профиль.",
    ),
    "ask_first_name": ("Ismingizni kiriting:", "Enter your first name:", "Введите ваше имя:"),
    "ask_last_name": ("Familiyangizni kiriting:", "Enter your last name:", "Введите вашу фамилию:"),
    "ask_patronymic": (
        "Sharifingizni kiriting (otangizning ismi):",
        "Enter your patronymic (father's name):",
        "Введите ваше отчество:",
    ),
    "ask_age": ("Yoshingizni kiriting:", "Enter your age:", "Введите ваш возраст:"),
    "ask_region": (
        "Viloyatingizni kiriting (masalan: Samarqand viloyati):",
        "Enter your region (e.g. Samarkand region):",
        "Введите вашу область (например: Самаркандская область):",
    ),
    "ask_phone": (
        "Telefon raqamingizni yuboring: pastdagi tugmani bosing yoki +998901234567 ko'rinishida yozing.",
        "Send your phone number: tap the button below or type it like +998901234567.",
        "Отправьте номер телефона: нажмите кнопку ниже или напишите в виде +998901234567.",
    ),
    "ask_username": (
        "Telegram username'ingizni kiriting (masalan: @username):",
        "Enter your Telegram username (e.g. @username):",
        "Введите ваш Telegram username (например: @username):",
    ),
    "btn_phone": ("📱 Raqamni yuborish", "📱 Share number", "📱 Отправить номер"),
    "skip": ("⏭ O'tkazib yuborish", "⏭ Skip", "⏭ Пропустить"),
    "btn_cancel": ("✖️ Bekor qilish", "✖️ Cancel", "✖️ Отмена"),
    "bad_name": (
        "❌ Faqat harflardan iborat, 2–40 belgili matn kiriting.",
        "❌ Enter 2–40 characters, letters only.",
        "❌ Введите 2–40 символов, только буквы.",
    ),
    "bad_age": (
        "❌ Yoshni 12 dan 99 gacha raqam bilan kiriting.",
        "❌ Enter your age as a number from 12 to 99.",
        "❌ Введите возраст числом от 12 до 99.",
    ),
    "bad_place": (
        "❌ 2–60 belgidan iborat matn kiriting.",
        "❌ Enter text of 2–60 characters.",
        "❌ Введите текст длиной 2–60 символов.",
    ),
    "bad_phone": (
        "❌ Telefon raqami noto'g'ri. Tugmani bosing yoki +998901234567 shaklida yozing. Faqat o'zingizning raqamingizni yuborish mumkin.",
        "❌ Invalid phone number. Tap the button or type it like +998901234567. Only your own number is accepted.",
        "❌ Неверный номер. Нажмите кнопку или напишите в виде +998901234567. Принимается только ваш номер.",
    ),
    "bad_username": (
        "❌ Username noto'g'ri (5–32 belgi: lotin harflari, raqamlar va _).",
        "❌ Invalid username (5–32 characters: Latin letters, digits and _).",
        "❌ Неверный username (5–32 символа: латиница, цифры и _).",
    ),
    "reg_done": ("✅ Profil saqlandi! Bosh menyu:", "✅ Profile saved! Main menu:", "✅ Профиль сохранён! Главное меню:"),
    "m_search": ("🔍 Dost qidirish", "🔍 Find friends", "🔍 Поиск друзей"),
    "m_friends": ("👥 Do'stlar ro'yxati", "👥 My friends", "👥 Список друзей"),
    "m_matches": ("💞 Sizga mos do'stlar", "💞 Your matches", "💞 Подходящие вам друзья"),
    "m_profile": ("👤 Profil", "👤 Profile", "👤 Профиль"),
    "m_lang": ("🌐 Tilni o'zgartirish", "🌐 Change language", "🌐 Сменить язык"),
    "lang_changed": (
        "✅ Til o'zgartirildi.",
        "✅ Language changed.",
        "✅ Язык изменён.",
    ),
    "menu_hint": ("Menyudan foydalaning 👇", "Please use the menu 👇", "Пользуйтесь меню 👇"),
    "not_reg": (
        "Botdan foydalanish uchun /start bosib ro'yxatdan o'ting.",
        "Press /start and register to use the bot.",
        "Нажмите /start и зарегистрируйтесь, чтобы пользоваться ботом.",
    ),
    "test_intro": (
        "📝 Anonim test: {total} ta savol. Har bir savolda ko'pi bilan {m} ta variant tanlashingiz mumkin (kamroq ham bo'ladi). Javoblaringizni boshqalar ko'rmaydi — faqat mos kelish foizi ko'rsatiladi.",
        "📝 Anonymous test: {total} questions. Choose at most {m} options per question (fewer is fine). Nobody sees your answers — only the match percentage is shown.",
        "📝 Анонимный тест: {total} вопросов. В каждом можно выбрать не более {m} вариантов (можно меньше). Ваши ответы никто не увидит — показывается только процент совпадения.",
    ),
    "q_head": (
        "Savol {n}/{total}\n\n{q}\n\nTanlandi: {c}/{m}",
        "Question {n}/{total}\n\n{q}\n\nSelected: {c}/{m}",
        "Вопрос {n}/{total}\n\n{q}\n\nВыбрано: {c}/{m}",
    ),
    "btn_next": ("Keyingi savol ➡️", "Next question ➡️", "Следующий вопрос ➡️"),
    "btn_finish": ("✅ Testni yakunlash", "✅ Finish test", "✅ Завершить тест"),
    "max_pick": (
        "Ko'pi bilan {m} ta variant tanlash mumkin!",
        "You can select at most {m} options!",
        "Можно выбрать не более {m} вариантов!",
    ),
    "need_pick": (
        "Kamida 1 ta variant tanlang yoki savolni o'tkazib yuboring.",
        "Select at least 1 option or skip the question.",
        "Выберите хотя бы 1 вариант или пропустите вопрос.",
    ),
    "test_empty": (
        "Kamida bitta savolga javob bering.",
        "Answer at least one question.",
        "Ответьте хотя бы на один вопрос.",
    ),
    "test_saved": ("✅ Test yakunlandi!", "✅ Test completed!", "✅ Тест завершён!"),
    "matches_title": (
        "💞 Sizga eng mos {n} ta inson:\n",
        "💞 Your top {n} matches:\n",
        "💞 Ваши {n} самых подходящих людей:\n",
    ),
    "no_test": (
        "Avval testni yeching: «🔍 Dost qidirish» tugmasini bosing.",
        "Take the test first: tap «🔍 Find friends».",
        "Сначала пройдите тест: нажмите «🔍 Поиск друзей».",
    ),
    "no_matches": (
        "Hozircha mos foydalanuvchilar topilmadi. Keyinroq qayta urinib ko'ring.",
        "No matching users yet. Please try again later.",
        "Подходящих пользователей пока нет. Попробуйте позже.",
    ),
    "friends_title": ("👥 Do'stlaringiz:", "👥 Your friends:", "👥 Ваши друзья:"),
    "no_friends": ("Hozircha do'stlaringiz yo'q.", "You have no friends yet.", "У вас пока нет друзей."),
    "req_sent": (
        "✅ So'rov yuborildi. Ikkinchi tomon tasdiqlagandan keyin do'st bo'lasiz.",
        "✅ Request sent. You will become friends once the other person accepts.",
        "✅ Запрос отправлен. Вы станете друзьями, когда другой человек его примет.",
    ),
    "req_wait": (
        "⏳ So'rov allaqachon yuborilgan, javobni kuting.",
        "⏳ Request already sent, please wait for a reply.",
        "⏳ Запрос уже отправлен, ожидайте ответа.",
    ),
    "req_friends": ("✅ Siz allaqachon do'stsiz.", "✅ You are already friends.", "✅ Вы уже друзья."),
    "req_declined": (
        "❌ Bu foydalanuvchi so'rovingizni rad etgan.",
        "❌ This user declined your request.",
        "❌ Этот пользователь отклонил ваш запрос.",
    ),
    "req_failed": (
        "Foydalanuvchiga xabar yuborib bo'lmadi. Keyinroq urinib ko'ring.",
        "Could not message this user. Please try later.",
        "Не удалось отправить сообщение пользователю. Попробуйте позже.",
    ),
    "req_in": (
        "🤝 {name}, {age} ({loc}) siz bilan do'stlashmoqchi.\nMoslik: {pct}",
        "🤝 {name}, {age} ({loc}) wants to be your friend.\nMatch: {pct}",
        "🤝 {name}, {age} ({loc}) хочет с вами подружиться.\nСовпадение: {pct}",
    ),
    "btn_accept": ("✅ Qabul qilish", "✅ Accept", "✅ Принять"),
    "btn_decline": ("❌ Rad etish", "❌ Decline", "❌ Отклонить"),
    "req_accepted_me": (
        "✅ Endi siz {name} bilan do'stsiz!",
        "✅ You are now friends with {name}!",
        "✅ Теперь вы друзья с {name}!",
    ),
    "req_accepted_other": (
        "🎉 {name} so'rovingizni qabul qildi! Ma'lumotlari «Do'stlar ro'yxati»da.",
        "🎉 {name} accepted your request! Details are in «My friends».",
        "🎉 {name} принял(а) ваш запрос! Контакты — в «Списке друзей».",
    ),
    "req_declined_me": ("So'rov rad etildi.", "Request declined.", "Запрос отклонён."),
    "profile_title": ("👤 Sizning profilingiz", "👤 Your profile", "👤 Ваш профиль"),
    "btn_edit": ("✏️ Ma'lumotni o'zgartirish", "✏️ Edit info", "✏️ Изменить данные"),
    "edit_left": (
        "✏️ Sizda {n} ta o'zgartirish imkoniyati qoldi (jami {total} ta). Har bir o'zgartirish 1 ta imkoniyatni sarflaydi.\nQaysi ma'lumotni o'zgartirasiz?",
        "✏️ You have {n} edits left (out of {total}). Each change uses 1 edit.\nWhich field do you want to change?",
        "✏️ У вас осталось {n} изменений (из {total}). Каждое изменение расходует 1 попытку.\nКакое поле изменить?",
    ),
    "edit_none": (
        "Kechirasiz, o'zgartirish imkoniyatlari tugagan.",
        "Sorry, you have used all your edits.",
        "К сожалению, лимит изменений исчерпан.",
    ),
    "edit_done": (
        "✅ Saqlandi. Qolgan o'zgartirish imkoniyati: {n}",
        "✅ Saved. Edits remaining: {n}",
        "✅ Сохранено. Осталось изменений: {n}",
    ),
    "f_first_name": ("Ism", "First name", "Имя"),
    "f_last_name": ("Familiya", "Last name", "Фамилия"),
    "f_patronymic": ("Sharif", "Patronymic", "Отчество"),
    "f_age": ("Yosh", "Age", "Возраст"),
    "f_region": ("Viloyat", "Region", "Область"),
    "f_phone": ("Telefon", "Phone", "Телефон"),
    "f_username": ("Username", "Username", "Username"),
    "interests_title": ("🎯 Qiziqishlari", "🎯 Interests", "🎯 Интересы"),
    "no_interests": (
        "Hali test yechilmagan.",
        "Test not completed yet.",
        "Тест ещё не пройден.",
    ),
    "btn_view": ("🔎 Profil", "🔎 Profile", "🔎 Профиль"),
}

LANG_PROMPT = "Tilni tanlang / Choose a language / Выберите язык:"
NOT_REG_ALL = (
    "Botdan foydalanish uchun /start bosing.\n"
    "Press /start to use the bot.\n"
    "Нажмите /start, чтобы пользоваться ботом."
)


def t(lang: str, key: str, **kw) -> str:
    s = T[key][LANGS.index(lang)]
    return s.format(**kw) if kw else s


def all_t(key: str) -> list:
    return list(T[key])


# --------------------------------------------------------------------------
# Baza
# --------------------------------------------------------------------------
db = sqlite3.connect(DB_PATH, check_same_thread=False)
db.row_factory = sqlite3.Row
db.executescript(
    """
CREATE TABLE IF NOT EXISTS users(
    tg_id INTEGER PRIMARY KEY,
    lang TEXT DEFAULT 'uz',
    first_name TEXT, last_name TEXT, patronymic TEXT, age INTEGER,
    region TEXT, phone TEXT, username TEXT,
    registered INTEGER DEFAULT 0,
    edits_used INTEGER DEFAULT 0,
    answers TEXT,                 -- {"savol_indeksi": [variant indekslari]}
    test_done INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS friendships(
    requester INTEGER, target INTEGER,
    status TEXT,                  -- pending | accepted | rejected
    PRIMARY KEY(requester, target)
);
"""
)


def q1(sql, args=()):
    return db.execute(sql, args).fetchone()


def qa(sql, args=()):
    return db.execute(sql, args).fetchall()


def ex(sql, args=()):
    db.execute(sql, args)
    db.commit()


def get_user(uid):
    return q1("SELECT * FROM users WHERE tg_id=?", (uid,))


def is_reg(uid) -> bool:
    u = get_user(uid)
    return bool(u and u["registered"])


def L(uid) -> str:
    u = get_user(uid)
    return u["lang"] if u and u["lang"] in LANGS else "uz"


def set_lang(uid, lang):
    ex(
        "INSERT INTO users(tg_id, lang) VALUES(?, ?) "
        "ON CONFLICT(tg_id) DO UPDATE SET lang=excluded.lang",
        (uid, lang),
    )


def save_profile(uid, reg: dict):
    sets = ", ".join(f"{f}=?" for f in STEPS)
    ex(f"UPDATE users SET {sets}, registered=1 WHERE tg_id=?", [reg[f] for f in STEPS] + [uid])


def fullname(u) -> str:
    return f"{u['first_name']} {u['last_name']}"


def loc(u) -> str:
    return u["region"] or "—"


def interests_text(lang, answers_json):
    """Foydalanuvchi test javoblariga qarab qiziqishlar ro'yxatini matn qilib beradi
    (boshqa foydalanuvchilarga ko'rsatish uchun ochiq ma'lumot)."""
    if not answers_json:
        return None
    i = LANGS.index(lang)
    try:
        ans = json.loads(answers_json)
    except (TypeError, ValueError):
        return None
    lines = []
    for qi_str in sorted(ans, key=int):
        opts = ans[qi_str]
        qi = int(qi_str)
        if not opts or not (0 <= qi < len(QUESTIONS)):
            continue
        q = QUESTIONS[qi]
        labels = [q["o"][k][i] for k in opts if 0 <= k < len(q["o"])]
        if labels:
            lines.append(f"• {q['q'][i]}: {', '.join(labels)}")
    return "\n".join(lines) if lines else None


# --------------------------------------------------------------------------
# Tekshiruv (validatsiya)
# --------------------------------------------------------------------------
NAME_RE = re.compile(r"[^\W\d_](?:[^\W\d_]|[ '’ʻʼ`\-]){1,39}")
USER_RE = re.compile(r"[A-Za-z][A-Za-z0-9_]{4,31}")
BAD_KEY = {
    "first_name": "bad_name", "last_name": "bad_name", "patronymic": "bad_name",
    "age": "bad_age", "region": "bad_place", "phone": "bad_phone", "username": "bad_username",
}


def parse(field: str, m: Message):
    """(ok, qiymat) qaytaradi."""
    text = (m.text or "").strip()
    if field in ("first_name", "last_name", "patronymic"):
        return (True, text) if NAME_RE.fullmatch(text) else (False, None)
    if field == "age":
        if text.isdigit() and 12 <= int(text) <= 99:
            return True, int(text)
        return False, None
    if field == "region":
        return (True, text) if 2 <= len(text) <= 60 else (False, None)
    if field == "phone":
        if m.contact:
            # soxta raqamlarga qarshi: faqat o'z kontakti qabul qilinadi
            if m.contact.user_id != m.from_user.id:
                return False, None
            raw = m.contact.phone_number
        else:
            raw = text
        d = re.sub(r"[\s\-()]", "", raw or "")
        if not re.fullmatch(r"\+?\d{9,15}", d):
            return False, None
        digits = d.lstrip("+")
        if len(digits) == 9:
            digits = "998" + digits
        return True, "+" + digits
    if field == "username":
        name = text.lstrip("@")
        return (True, name) if USER_RE.fullmatch(name) else (False, None)
    return False, None


# --------------------------------------------------------------------------
# Klaviaturalar
# --------------------------------------------------------------------------
def menu_kb(lang):
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=t(lang, "m_search")), KeyboardButton(text=t(lang, "m_friends"))],
            [KeyboardButton(text=t(lang, "m_matches")), KeyboardButton(text=t(lang, "m_profile"))],
            [KeyboardButton(text=t(lang, "m_lang"))],
        ],
        resize_keyboard=True,
    )


def lang_kb(prefix="lang"):
    return InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(text="🇺🇿 O'zbekcha", callback_data=f"{prefix}:uz"),
            InlineKeyboardButton(text="🇬🇧 English", callback_data=f"{prefix}:en"),
            InlineKeyboardButton(text="🇷🇺 Русский", callback_data=f"{prefix}:ru"),
        ]]
    )


def field_kb(lang, field, editing=False):
    rows = []
    if field == "phone":
        rows.append([KeyboardButton(text=t(lang, "btn_phone"), request_contact=True)])
    if editing:
        rows.append([KeyboardButton(text=t(lang, "btn_cancel"))])
    if rows:
        return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)
    return None if editing else ReplyKeyboardRemove()


# --------------------------------------------------------------------------
# FSM
# --------------------------------------------------------------------------
class Reg(StatesGroup):
    lang = State()
    field = State()


class Test(StatesGroup):
    q = State()


class Edit(StatesGroup):
    value = State()


router = Router()
MENU_STATES = StateFilter(None, Test.q, Edit.value)


# --------------------------------------------------------------------------
# Ro'yxatdan o'tmaganlarni to'sish
# --------------------------------------------------------------------------
class RegGuard(BaseMiddleware):
    async def __call__(self, handler, event, data):
        user = data.get("event_from_user")
        if user is None or data.get("raw_state") is not None or is_reg(user.id):
            return await handler(event, data)
        if isinstance(event, Message) and (event.text or "").startswith("/start"):
            return await handler(event, data)
        row = get_user(user.id)
        text = t(row["lang"], "not_reg") if row and row["lang"] in LANGS else NOT_REG_ALL
        if isinstance(event, Message):
            await event.answer(text)
        elif isinstance(event, CallbackQuery):
            await event.answer(text, show_alert=True)


# --------------------------------------------------------------------------
# /start, til tanlash, ro'yxatdan o'tish
# --------------------------------------------------------------------------
@router.message(CommandStart())
async def h_start(m: Message, state: FSMContext):
    await state.clear()
    uid = m.from_user.id
    if is_reg(uid):
        # Ro'yxatdan o'tgan foydalanuvchi — ma'lumotlari saqlanib, to'g'ridan-to'g'ri asosiy panel
        lang = L(uid)
        await m.answer(t(lang, "menu_hint"), reply_markup=menu_kb(lang))
        return
    await state.set_state(Reg.lang)            # ro'yxatdan o'tmagan bo'lsa — boshidan boshlanadi
    await m.answer("👋", reply_markup=ReplyKeyboardRemove())
    await m.answer(LANG_PROMPT, reply_markup=lang_kb())


@router.message(Reg.lang)
async def h_lang_text(m: Message):
    await m.answer(LANG_PROMPT, reply_markup=lang_kb())


@router.callback_query(Reg.lang, F.data.startswith("lang:"))
async def h_lang(c: CallbackQuery, state: FSMContext):
    lang = c.data.split(":")[1]
    if lang not in LANGS:
        await c.answer()
        return
    set_lang(c.from_user.id, lang)
    await state.set_state(Reg.field)
    await state.update_data(step=0, reg={})
    try:
        await c.message.edit_reply_markup(reply_markup=None)
    except TelegramAPIError:
        pass
    await c.message.answer(t(lang, "welcome"))
    await c.message.answer(t(lang, "ask_" + STEPS[0]), reply_markup=field_kb(lang, STEPS[0]))
    await c.answer()


@router.message(Reg.field)
async def h_reg_field(m: Message, state: FSMContext):
    uid = m.from_user.id
    lang = L(uid)
    d = await state.get_data()
    step, reg = d["step"], d["reg"]
    field = STEPS[step]
    ok, val = parse(field, m)
    if not ok:
        await m.answer(t(lang, BAD_KEY[field]))
        return
    reg[field] = val
    step += 1
    if step < len(STEPS):
        await state.update_data(step=step, reg=reg)
        await m.answer(t(lang, "ask_" + STEPS[step]), reply_markup=field_kb(lang, STEPS[step]))
    else:
        save_profile(uid, reg)               # faqat oxirida yoziladi
        await state.clear()
        await m.answer(t(lang, "reg_done"), reply_markup=menu_kb(lang))


# --------------------------------------------------------------------------
# 4 — Profil va o'zgartirish (5 martagacha)
# --------------------------------------------------------------------------
def profile_text(lang, u) -> str:
    lines = [t(lang, "profile_title"), ""]
    for f in STEPS:
        v = u[f]
        if f == "username" and v:
            v = "@" + v
        lines.append(f"{t(lang, 'f_' + f)}: {v if v not in (None, '') else '—'}")
    it = interests_text(lang, u["answers"])
    lines += ["", t(lang, "interests_title") + ":", it or t(lang, "no_interests")]
    return "\n".join(lines)


async def send_profile(m: Message, uid: int):
    lang = L(uid)
    kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=t(lang, "btn_edit"), callback_data="edit")]]
    )
    await m.answer(profile_text(lang, get_user(uid)), reply_markup=kb)


@router.message(MENU_STATES, F.text.in_(all_t("m_profile")))
async def h_profile(m: Message, state: FSMContext):
    await state.clear()
    await send_profile(m, m.from_user.id)


@router.message(MENU_STATES, F.text.in_(all_t("m_lang")))
async def h_menu_lang(m: Message, state: FSMContext):
    await state.clear()
    await m.answer(LANG_PROMPT, reply_markup=lang_kb(prefix="clang"))


@router.callback_query(F.data.startswith("clang:"))
async def h_change_lang(c: CallbackQuery):
    lang = c.data.split(":")[1]
    if lang not in LANGS:
        await c.answer()
        return
    set_lang(c.from_user.id, lang)
    try:
        await c.message.edit_reply_markup(reply_markup=None)
    except TelegramAPIError:
        pass
    await c.message.answer(t(lang, "lang_changed"))
    await c.message.answer(t(lang, "menu_hint"), reply_markup=menu_kb(lang))
    await c.answer()


@router.callback_query(F.data == "edit")
async def h_edit(c: CallbackQuery):
    uid = c.from_user.id
    lang = L(uid)
    left = MAX_EDITS - get_user(uid)["edits_used"]
    if left <= 0:
        await c.answer(t(lang, "edit_none"), show_alert=True)
        return
    rows, row = [], []
    for f in STEPS:
        row.append(InlineKeyboardButton(text=t(lang, "f_" + f), callback_data="ef:" + f))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    await c.message.answer(
        t(lang, "edit_left", n=left, total=MAX_EDITS),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
    )
    await c.answer()


@router.callback_query(F.data.startswith("ef:"))
async def h_edit_field(c: CallbackQuery, state: FSMContext):
    uid = c.from_user.id
    lang = L(uid)
    field = c.data[3:]
    if field not in STEPS:
        await c.answer()
        return
    if MAX_EDITS - get_user(uid)["edits_used"] <= 0:
        await c.answer(t(lang, "edit_none"), show_alert=True)
        return
    await state.clear()
    await state.set_state(Edit.value)
    await state.update_data(field=field)
    await c.message.answer(t(lang, "ask_" + field), reply_markup=field_kb(lang, field, editing=True))
    await c.answer()


@router.message(Edit.value, F.text.in_(all_t("btn_cancel")))
async def h_edit_cancel(m: Message, state: FSMContext):
    await state.clear()
    await m.answer(t(L(m.from_user.id), "menu_hint"), reply_markup=menu_kb(L(m.from_user.id)))


@router.message(Edit.value)
async def h_edit_value(m: Message, state: FSMContext):
    uid = m.from_user.id
    lang = L(uid)
    field = (await state.get_data()).get("field")
    if field not in STEPS:
        await state.clear()
        return
    if MAX_EDITS - get_user(uid)["edits_used"] <= 0:
        await state.clear()
        await m.answer(t(lang, "edit_none"), reply_markup=menu_kb(lang))
        return
    ok, val = parse(field, m)
    if not ok:
        await m.answer(t(lang, BAD_KEY[field]))
        return
    ex(f"UPDATE users SET {field}=?, edits_used=edits_used+1 WHERE tg_id=?", (val, uid))
    await state.clear()
    left = MAX_EDITS - get_user(uid)["edits_used"]
    await m.answer(t(lang, "edit_done", n=left), reply_markup=menu_kb(lang))
    await send_profile(m, uid)


# --------------------------------------------------------------------------
# 1 — Dost qidirish (anonim test)
# --------------------------------------------------------------------------
def render(lang, qi, sel):
    i = LANGS.index(lang)
    q = QUESTIONS[qi]
    text = t(lang, "q_head", n=qi + 1, total=len(QUESTIONS), q=q["q"][i], c=len(sel), m=MAX_PICK)
    rows = []
    for k, o in enumerate(q["o"]):
        rows.append([InlineKeyboardButton(
            text=("✅ " if k in sel else "⬜ ") + o[i], callback_data=f"opt:{k}")])
    skip = InlineKeyboardButton(text=t(lang, "skip"), callback_data="skip")
    if qi == len(QUESTIONS) - 1:
        rows.append([skip, InlineKeyboardButton(text=t(lang, "btn_finish"), callback_data="fin")])
    else:
        rows.append([InlineKeyboardButton(text=t(lang, "btn_next"), callback_data="next"), skip])
    return text, InlineKeyboardMarkup(inline_keyboard=rows)


@router.message(MENU_STATES, F.text.in_(all_t("m_search")))
async def h_search(m: Message, state: FSMContext):
    lang = L(m.from_user.id)
    await state.clear()
    await state.set_state(Test.q)
    await state.update_data(qi=0, ans={}, sel=[])
    await m.answer(t(lang, "test_intro", total=len(QUESTIONS), m=MAX_PICK))
    text, kb = render(lang, 0, [])
    await m.answer(text, reply_markup=kb)


@router.callback_query(Test.q, F.data.startswith("opt:"))
async def h_toggle(c: CallbackQuery, state: FSMContext):
    lang = L(c.from_user.id)
    d = await state.get_data()
    qi, sel = d["qi"], list(d["sel"])
    try:
        k = int(c.data[4:])
    except ValueError:
        await c.answer()
        return
    if not 0 <= k < len(QUESTIONS[qi]["o"]):
        await c.answer()
        return
    if k in sel:
        sel.remove(k)
    elif len(sel) >= MAX_PICK:                # 6 tadan ko'p taqiqlangan
        await c.answer(t(lang, "max_pick", m=MAX_PICK), show_alert=True)
        return
    else:
        sel.append(k)
    await state.update_data(sel=sel)
    text, kb = render(lang, qi, sel)
    try:
        await c.message.edit_text(text, reply_markup=kb)
    except TelegramAPIError:
        pass
    await c.answer()


async def advance(c: CallbackQuery, state: FSMContext, save: bool):
    lang = L(c.from_user.id)
    d = await state.get_data()
    qi, ans, sel = d["qi"], d["ans"], d["sel"]
    if save:
        ans[str(qi)] = sorted(sel)
    if qi + 1 >= len(QUESTIONS):
        await finish(c, state, ans)
        return
    await state.update_data(qi=qi + 1, ans=ans, sel=[])
    text, kb = render(lang, qi + 1, [])
    await c.message.edit_text(text, reply_markup=kb)
    await c.answer()


@router.callback_query(Test.q, F.data == "next")
async def h_next(c: CallbackQuery, state: FSMContext):
    if not (await state.get_data())["sel"]:
        await c.answer(t(L(c.from_user.id), "need_pick"), show_alert=True)
        return
    await advance(c, state, save=True)


@router.callback_query(Test.q, F.data == "skip")
async def h_skip(c: CallbackQuery, state: FSMContext):
    await advance(c, state, save=False)


@router.callback_query(Test.q, F.data == "fin")
async def h_fin(c: CallbackQuery, state: FSMContext):
    d = await state.get_data()
    ans = d["ans"]
    if d["sel"]:
        ans[str(d["qi"])] = sorted(d["sel"])
    await finish(c, state, ans)


async def finish(c: CallbackQuery, state: FSMContext, ans: dict):
    uid = c.from_user.id
    lang = L(uid)
    if not ans:
        await c.answer(t(lang, "test_empty"), show_alert=True)
        return
    ex("UPDATE users SET answers=?, test_done=1 WHERE tg_id=?", (json.dumps(ans), uid))
    await state.clear()
    try:
        await c.message.edit_text(t(lang, "test_saved"))
    except TelegramAPIError:
        pass
    await c.answer()
    await send_matches(c.message, uid, lang)


# --------------------------------------------------------------------------
# Moslikni hisoblash va 3 — top 10
# --------------------------------------------------------------------------
def similarity(a: dict, b: dict):
    """Ikkalasi ham javob bergan savollar bo'yicha o'rtacha Jaccard (0..1)."""
    scores = []
    for k, sa in a.items():
        sb = b.get(k)
        if not sa or not sb:
            continue
        A, B = set(sa), set(sb)
        scores.append(len(A & B) / len(A | B))
    return sum(scores) / len(scores) if scores else None


def pct_between(a, b) -> str:
    ua, ub = get_user(a), get_user(b)
    if ua and ub and ua["answers"] and ub["answers"]:
        s = similarity(json.loads(ua["answers"]), json.loads(ub["answers"]))
        if s is not None:
            return f"{round(s * 100)}%"
    return "—"


def top_matches(uid):
    me = get_user(uid)
    if not me or not me["test_done"] or not me["answers"]:
        return None
    mine = json.loads(me["answers"])
    out = []
    for u in qa("SELECT * FROM users WHERE registered=1 AND test_done=1 AND tg_id!=?", (uid,)):
        s = similarity(mine, json.loads(u["answers"]))
        if s is not None:
            out.append((u, round(s * 100)))
    out.sort(key=lambda x: -x[1])
    return out[:TOP_N]


def friend_state(me, other):
    r = q1("SELECT status FROM friendships WHERE requester=? AND target=?", (me, other))
    if r:
        return {"accepted": "friends", "pending": "sent", "rejected": "declined"}[r["status"]]
    r = q1("SELECT status FROM friendships WHERE requester=? AND target=?", (other, me))
    if r:
        return {"accepted": "friends", "pending": "received", "rejected": "i_declined"}[r["status"]]
    return None


async def send_matches(msg: Message, uid: int, lang: str):
    res = top_matches(uid)
    if res is None:
        await msg.answer(t(lang, "no_test"))
        return
    if not res:
        await msg.answer(t(lang, "no_matches"))
        return
    lines = [t(lang, "matches_title", n=len(res))]
    rows = []
    for i, (u, pct) in enumerate(res, 1):
        short = f"{u['first_name']} {u['last_name'][:1]}."
        lines.append(f"{i}. {short}, {u['age']} — {loc(u)} — {pct}%")
        st = friend_state(uid, u["tg_id"])
        icon = "✅" if st == "friends" else "⏳" if st == "sent" else "🤝"
        rows.append([
            InlineKeyboardButton(
                text=f"{icon} {i}. {short} — {pct}%", callback_data=f"fr:{u['tg_id']}"),
            InlineKeyboardButton(text=t(lang, "btn_view"), callback_data=f"view:{u['tg_id']}"),
        ])
    await msg.answer("\n".join(lines), reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))


@router.message(MENU_STATES, F.text.in_(all_t("m_matches")))
async def h_matches(m: Message, state: FSMContext):
    await state.clear()
    await send_matches(m, m.from_user.id, L(m.from_user.id))


# --------------------------------------------------------------------------
# Do'stlashish (ikki tomonlama tasdiq — soxta do'stlar bo'lmasligi uchun)
# --------------------------------------------------------------------------
async def notify(bot: Bot, uid: int, key: str, **kw):
    try:
        await bot.send_message(uid, t(L(uid), key, **kw))
    except TelegramAPIError:
        pass


@router.callback_query(F.data.startswith("view:"))
async def h_view(c: CallbackQuery):
    """Do'st bo'lmagan foydalanuvchining ochiq profili: ism, yosh, viloyat, qiziqishlar.
    Telefon va username faqat do'st bo'lgandan keyin (do'stlar ro'yxatida) ko'rinadi."""
    lang = L(c.from_user.id)
    try:
        other = int(c.data[5:])
    except ValueError:
        await c.answer()
        return
    u = get_user(other)
    if not u or not u["registered"]:
        await c.answer()
        return
    it = interests_text(lang, u["answers"])
    text = (
        f"👤 {fullname(u)}, {u['age']}\n📍 {loc(u)}\n\n"
        f"{t(lang, 'interests_title')}:\n{it or t(lang, 'no_interests')}"
    )
    await c.message.answer(text)
    await c.answer()


@router.callback_query(F.data.startswith("fr:"))
async def h_friend(c: CallbackQuery, bot: Bot):
    me = c.from_user.id
    lang = L(me)
    try:
        other = int(c.data[3:])
    except ValueError:
        await c.answer()
        return
    target = get_user(other)
    if other == me or not target or not target["registered"]:
        await c.answer()
        return
    st = friend_state(me, other)
    if st == "friends":
        await c.answer(t(lang, "req_friends"), show_alert=True)
        return
    if st == "sent":
        await c.answer(t(lang, "req_wait"), show_alert=True)
        return
    if st == "declined":
        await c.answer(t(lang, "req_declined"), show_alert=True)
        return
    if st == "received":                      # ikkalasi ham xohlagan — darhol tasdiqlanadi
        ex("UPDATE friendships SET status='accepted' WHERE requester=? AND target=?", (other, me))
        await c.answer(t(lang, "req_accepted_me", name=fullname(target)), show_alert=True)
        await notify(bot, other, "req_accepted_other", name=fullname(get_user(me)))
        return
    if st == "i_declined":                    # men rad etgan edim, endi o'zim so'rayapman
        ex("DELETE FROM friendships WHERE requester=? AND target=?", (other, me))

    ex("INSERT INTO friendships(requester, target, status) VALUES(?, ?, 'pending')", (me, other))
    me_u = get_user(me)
    tl = target["lang"] if target["lang"] in LANGS else "uz"
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=t(tl, "btn_accept"), callback_data=f"acc:{me}"),
        InlineKeyboardButton(text=t(tl, "btn_decline"), callback_data=f"dec:{me}"),
    ]])
    req_text = t(tl, "req_in", name=fullname(me_u), age=me_u["age"], loc=loc(me_u),
                 pct=pct_between(me, other))
    it = interests_text(tl, me_u["answers"])
    if it:
        req_text += f"\n\n{t(tl, 'interests_title')}:\n{it}"
    try:
        await bot.send_message(other, req_text, reply_markup=kb)
    except TelegramAPIError:
        ex("DELETE FROM friendships WHERE requester=? AND target=?", (me, other))
        await c.answer(t(lang, "req_failed"), show_alert=True)
        return
    await c.answer(t(lang, "req_sent"), show_alert=True)


@router.callback_query(F.data.startswith("acc:") | F.data.startswith("dec:"))
async def h_answer_request(c: CallbackQuery, bot: Bot):
    me = c.from_user.id
    lang = L(me)
    act, sid = c.data.split(":")
    other = int(sid)
    # faqat haqiqiy, kutilayotgan so'rov bo'yicha (callback soxtalashtirib bo'lmaydi)
    r = q1("SELECT 1 FROM friendships WHERE requester=? AND target=? AND status='pending'", (other, me))
    if not r:
        await c.answer()
        return
    other_u = get_user(other)
    if act == "acc":
        ex("UPDATE friendships SET status='accepted' WHERE requester=? AND target=?", (other, me))
        text = t(lang, "req_accepted_me", name=fullname(other_u))
        await notify(bot, other, "req_accepted_other", name=fullname(get_user(me)))
    else:
        ex("UPDATE friendships SET status='rejected' WHERE requester=? AND target=?", (other, me))
        text = t(lang, "req_declined_me")
    try:
        await c.message.edit_text(text)
    except TelegramAPIError:
        pass
    await c.answer()


# --------------------------------------------------------------------------
# 2 — Do'stlar ro'yxati
# --------------------------------------------------------------------------
@router.message(MENU_STATES, F.text.in_(all_t("m_friends")))
async def h_friends(m: Message, state: FSMContext):
    await state.clear()
    uid = m.from_user.id
    lang = L(uid)
    rows = qa(
        """SELECT u.* FROM friendships f
           JOIN users u ON u.tg_id = CASE WHEN f.requester=? THEN f.target ELSE f.requester END
           WHERE f.status='accepted' AND (f.requester=? OR f.target=?)""",
        (uid, uid, uid),
    )
    if not rows:
        await m.answer(t(lang, "no_friends"))
        return
    text = t(lang, "friends_title")
    for u in rows:
        block = (
            f"👤 {fullname(u)}, {u['age']}\n📍 {loc(u)}\n"
            f"📞 {u['phone']}\n✈️ @{u['username']}"
        )
        it = interests_text(lang, u["answers"])
        if it:
            block += f"\n{t(lang, 'interests_title')}:\n{it}"
        if len(text) + len(block) > 3800:      # Telegram limiti (4096)
            await m.answer(text)
            text = ""
        text += "\n\n" + block
    await m.answer(text)


# --------------------------------------------------------------------------
# Qolgan xabarlar
# --------------------------------------------------------------------------
@router.message(StateFilter(None))
async def h_fallback(m: Message):
    lang = L(m.from_user.id)
    await m.answer(t(lang, "menu_hint"), reply_markup=menu_kb(lang))


@router.callback_query()
async def h_cb_fallback(c: CallbackQuery):
    await c.answer()


# --------------------------------------------------------------------------
async def main():
    if not TOKEN:
        raise SystemExit("BOT_TOKEN topilmadi: .env faylini bot.py yoniga qo'ying (ichida BOT_TOKEN=... bo'lsin).")
    logging.basicConfig(level=logging.INFO)
    bot = Bot(token=TOKEN)
    print("Telegram'ga ulanmoqda...", flush=True)
    try:
        me = await asyncio.wait_for(bot.get_me(), timeout=30)
    except TelegramUnauthorizedError:
        raise SystemExit(
            "❌ Token noto'g'ri yoki bekor qilingan (revoke). "
            "@BotFather'dan yangi token oling va .env dagi BOT_TOKEN ni almashtiring."
        )
    except Exception as e:
        raise SystemExit(
            f"❌ Telegram'ga ulanib bo'lmadi: {type(e).__name__}: {e}\n"
            "Internet yoki Telegram bloklanganini tekshiring (VPN yoqib ko'ring)."
        )
    print(f"✅ Bot ishlayapti: @{me.username}. Telegram'da shu botga /start yozing. To'xtatish: Ctrl+C", flush=True)
    dp = Dispatcher(storage=MemoryStorage())
    dp.message.outer_middleware(RegGuard())
    dp.callback_query.outer_middleware(RegGuard())
    dp.include_router(router)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
