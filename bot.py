import telebot
from telebot import types
import google.generativeai as genai
import os
import time
import requests
import threading
import random
import asyncio
import edge_tts
from flask import Flask
from datetime import datetime

# --- КЛЮЧИ ---
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
HUGGING_FACE_KEY = os.environ.get("HUGGING_FACE_KEY")
YOUR_CHAT_ID = os.environ.get("YOUR_CHAT_ID")

# --- НАСТРОЙКИ ВРЕМЕНИ (UTC) ---
START_DATE = datetime(2026, 2, 8) 

# Киев зимой = UTC+2.
# Чтобы было 6:00 утра по Киеву -> ставим 4
TIME_RUNE_UTC = 4 
# Чтобы было 9:00 утра по Киеву -> ставим 7
TIME_SAGA_UTC = 7

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-flash-latest') 
bot = telebot.TeleBot(TELEGRAM_TOKEN)

API_URL = "https://router.huggingface.co/hf-inference/models/stabilityai/stable-diffusion-xl-base-1.0"
headers = {"Authorization": f"Bearer {HUGGING_FACE_KEY}"}

# --- СПИСОК РУН ---
RUNES = [
    "Феху (Fehu) - Богатство", "Уруз (Uruz) - Сила", "Турисаз (Thurisaz) - Врата", 
    "Ансуз (Ansuz) - Знание", "Райдо (Raidho) - Путь", "Кеназ (Kenaz) - Огонь",
    "Гебо (Gebo) - Дар", "Вуньо (Wunjo) - Радость", "Хагалаз (Hagalaz) - Разрушение",
    "Наутиз (Nauthiz) - Нужда", "Иса (Isa) - Лед", "Йера (Jera) - Урожай",
    "Эйваз (Eihwaz) - Защита", "Перт (Perthro) - Тайна", "Альгиз (Algiz) - Защита высших сил",
    "Соулу (Sowilo) - Солнце", "Тейваз (Tiwaz) - Воин", "Беркана (Berkana) - Рост",
    "Эваз (Ehwaz) - Движение", "Манназ (Mannaz) - Человек", "Лагуз (Laguz) - Интуиция",
    "Ингуз (Inguz) - Плодородия", "Отал (Othala) - Наследие", "Дагаз (Dagaz) - Прорыв"
]

subscribers = set()
if YOUR_CHAT_ID:
    subscribers.add(YOUR_CHAT_ID)

# --- ФРАЗЫ ---
WAIT_PHRASES = [
    "🦅 Хугин и Мунин полетели за историей...",
    "⏳ Норны сплетают нить, жди...",
    "🍺 Скальд наливает мёд поэзии...",
    "🌲 Шепот ветвей Иггдрасиля...",
    "🔥 Раздуваю угли знаний..."
]

START_PHRASES = [
    "⚔️ Руны легли верно!",
    "⚡ Тор ударил молотом!",
    "📜 Сдуваю пыль со свитков...",
    "🐺 Фенрир завыл..."
]

# --- ПРОМПТЫ ---
SYSTEM_PROMPT_TOPIC_GEN = "Ты знаток мифов. Придумай одну редкую тему скандинавского фольклора. Только заголовок."

SYSTEM_PROMPT_TEXT = """
Ты — древний скальд. Напиши МОНУМЕНТАЛЬНЫЙ лонгрид (объем 8000-9000 знаков).
Пиши МАКСИМАЛЬНО ПОДРОБНО, с диалогами, описаниями природы и чувств героев.
СТРУКТУРА:
1. ЭТИМОЛОГИЯ.
2. МИФ/ИСТОРИЯ (Детальный пересказ).
3. СИМВОЛИЗМ.
4. СВЯЗЬ С СОВРЕМЕННОСТЬЮ.
Не используй жирный шрифт. Тема: 
"""

SYSTEM_PROMPT_VOICE = "Напиши атмосферное вступление (2-3 предложения) от лица старого викинга. На русском."
SYSTEM_PROMPT_IMAGE = "Cinematic digital art, epic Norse mythology scene, dramatic lighting, 8k. Topic: "
SYSTEM_PROMPT_ORACLE = "Ты — Один. Ответь смертному мудро, кратко (4 предл.), метафорично. СТРОГО НА РУССКОМ. Вопрос: "

SYSTEM_PROMPT_RUNE = """
Ты — Один. Твоя рука вытянула Руну Дня.
Руна: {rune}.
Дай краткое (3-4 предложения), мистическое, но полезное напутствие на этот день.
Что эта руна предвещает? О чем предупреждает?
Отвечай СТРОГО НА РУССКОМ ЯЗЫКЕ.
"""

# --- ФУНКЦИИ ---
def clean_text(text):
    return text.replace("**", "").replace("__", "").replace("##", "").replace("* ", "- ")

def smart_split_and_send(chat_id, text):
    chunk_size = 4000
    while text:
        if len(text) <= chunk_size:
            bot.send_message(chat_id, text)
            break
        split_at = text.rfind('\n', 0, chunk_size)
        if split_at == -1: split_at = text.rfind(' ', 0, chunk_size)
        if split_at == -1: split_at = chunk_size
        bot.send_message(chat_id, text[:split_at])
        text = text[split_at:].lstrip()
        time.sleep(1)

async def generate_voice_file(text, filename):
    communicate = edge_tts.Communicate(text, "ru-RU-DmitryNeural")
    await communicate.save(filename)

def get_topic():
    day_index = (datetime.now() - START_DATE).days
    if day_index < 0: day_index = 0
    if os.path.exists("topics.txt"):
        try:
            with open("topics.txt", "r", encoding="utf-8") as f:
                lines = [l.strip() for l in f if l.strip()]
            if lines: return lines[day_index % len(lines)], f"📜 Свиток №{day_index % len(lines) + 1}"
        except: pass
    return model.generate_content(SYSTEM_PROMPT_TOPIC_GEN).text.strip(), "🔮 Руны AI"

# --- ОБРАБОТЧИКИ ---
def get_main_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    btn1 = types.KeyboardButton("📜 Расскажи Сагу")
    btn2 = types.KeyboardButton("🔮 Спросить Одина")
    markup.add(btn1, btn2)
    return markup

# Функция для генерации саги (используется и кнопкой, и рассылкой)
def generate_and_send_saga(target_chat_id=None):
    try:
        topic, src = get_topic()
        
        # Если чат не указан, шлем всем подписчикам (рассылка)
        targets = [target_chat_id] if target_chat_id else subscribers
        
        # Генерируем контент ОДИН раз
        try: img_p = model.generate_content(f"SD prompt for: {topic}").text
        except: img_p = SYSTEM_PROMPT_IMAGE + topic
        resp_img = requests.post(API_URL, headers=headers, json={"inputs": img_p})
        
        v_text = clean_text(model.generate_content(f"{SYSTEM_PROMPT_VOICE} {topic}").text)
        fname = f"v_{random.randint(1,999)}.mp3"
        asyncio.run(generate_voice_file(v_text, fname))
        
        story = clean_text(model.generate_content(f"{SYSTEM_PROMPT_TEXT} {topic}").text)

        # Рассылаем всем
        for chat_id in targets:
            try:
                bot.send_message(chat_id, f"{random.choice(START_PHRASES)}\n\n{src}\nТема: {topic}")
                if resp_img.status_code == 200: 
                    bot.send_photo(chat_id, resp_img.content)
                
                with open(fname, 'rb') as a: 
                    bot.send_voice(chat_id, a)
                
                bot.send_chat_action(chat_id, 'typing')
                smart_split_and_send(chat_id, story)
            except Exception as e:
                print(f"Ошибка отправки {chat_id}: {e}")

        if os.path.exists(fname): os.remove(fname)

    except Exception as e:
        print(f"Глобальная ошибка саги: {e}")

def ask_odin_step(message):
    if message.text in ["📜 Расскажи Сагу", "🔮 Спросить Одина", "/start", "/subscribe"]:
        bot.send_message(message.chat.id, "👁️ Ритуал прерван.", reply_markup=get_main_keyboard())
        return
    try:
        bot.send_chat_action(message.chat.id, 'typing')
        answer = clean_text(model.generate_content(f"{SYSTEM_PROMPT_ORACLE} {message.text}").text)
        bot.reply_to(message, f"👁️ **Один говорит:**\n\n{answer}", parse_mode="Markdown", reply_markup=get_main_keyboard())
    except:
        bot.send_message(message.chat.id, "Туман скрыл ответ...", reply_markup=get_main_keyboard())

# --- УТРЕННЯЯ РАССЫЛКА РУН ---
def send_morning_rune():
    print("☀️ Рассылка Рун...")
    try:
        rune = random.choice(RUNES)
        prompt = SYSTEM_PROMPT_RUNE.format(rune=rune)
        prediction = clean_text(model.generate_content(prompt).text)
        
        img_prompt = f"Mystical glowing Norse rune symbol {rune.split(' ')[0]} carved on dark stone, magical blue energy, cinematic lighting, 8k"
        resp = requests.post(API_URL, headers=headers, json={"inputs": img_prompt})
        
        for user_id in subscribers:
            try:
                bot.send_message(user_id, f"🌅 **Руна Дня:** {rune}", parse_mode="Markdown")
                if resp.status_code == 200:
                    bot.send_photo(user_id, resp.content)
                bot.send_message(user_id, f"👁️ **Слово Одина:**\n\n{prediction}", parse_mode="Markdown")
            except: pass
    except Exception as e:
        print(f"Ошибка рун: {e}")

@bot.message_handler(commands=['start'])
def start(m):
    subscribers.add(str(m.chat.id))
    bot.send_message(m.chat.id, "⚔️ Чертоги открыты. Жди Руну в 6:00 и Сагу в 9:00.", reply_markup=get_main_keyboard())

@bot.message_handler(commands=['subscribe'])
def subscribe(m):
    subscribers.add(str(m.chat.id))
    bot.send_message(m.chat.id, "🔔 Подписка оформлена.")

@bot.message_handler(func=lambda m: m.text == "📜 Расскажи Сагу")
def on_saga_click(m):
    bot.send_message(m.chat.id, random.choice(WAIT_PHRASES))
    # Запускаем в отдельном потоке, чтобы бот не вис
    threading.Thread(target=generate_and_send_saga, args=(m.chat.id,)).start()

@bot.message_handler(func=lambda m: m.text == "🔮 Спросить Одина")
def on_oracle_click(m):
    msg = bot.send_message(m.chat.id, "👁️ Всеотец слушает. Задай свой вопрос...", reply_markup=types.ReplyKeyboardRemove())
    bot.register_next_step_handler(msg, ask_odin_step)

# --- SERVER & SCHEDULER ---
server = Flask(__name__)
@server.route("/")
def webhook(): return "OK", 200

def run_server(): server.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))

def scheduler():
    while True:
        now = datetime.now()
        
        # 1. РУНЫ (06:00 Киев -> 04:00 UTC)
        if now.hour == TIME_RUNE_UTC and now.minute == 0:
            send_morning_rune()
            time.sleep(61)
            
        # 2. ИСТОРИЯ (09:00 Киев -> 07:00 UTC)
        elif now.hour == TIME_SAGA_UTC and now.minute == 0:
            print("📜 Рассылка Саги...")
            generate_and_send_saga() # Без аргументов = всем подписчикам
            time.sleep(61)
            
        time.sleep(30)

if __name__ == "__main__":
    try: bot.remove_webhook()
    except: pass
    threading.Thread(target=run_server, daemon=True).start()
    threading.Thread(target=scheduler, daemon=True).start()
    bot.infinity_polling()
