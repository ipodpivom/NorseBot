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

# --- НАСТРОЙКИ ---
START_DATE = datetime(2026, 2, 8) # Дата начала отсчета списка
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-flash-latest') 
bot = telebot.TeleBot(TELEGRAM_TOKEN)

API_URL = "https://router.huggingface.co/hf-inference/models/stabilityai/stable-diffusion-xl-base-1.0"
headers = {"Authorization": f"Bearer {HUGGING_FACE_KEY}"}

# --- АТМОСФЕРНЫЕ ФРАЗЫ ---
WAIT_PHRASES = [
    "🦅 Хугин и Мунин уже полетели за этой историей...",
    "⏳ Норны сплетают нить судьбы, жди...",
    "🍺 Скальд наливает мёд поэзии...",
    "🌲 Слушаю шепот ветвей Иггдрасиля...",
    "🔥 Раздуваю угли в очаге знаний...",
    "👁️ Один вглядывается в колодец Мимира..."
]

START_PHRASES = [
    "⚔️ Руны легли верно!",
    "⚡ Тор ударил молотом — слушай!",
    "📜 Сдуваю вековую пыль со свитков...",
    "🐺 Фенрир завыл, предвещая великий рассказ...",
    "🌊 Драккар причалил к берегам памяти...",
    "🛡️ Хеймдалль протрубил в Гьяллархорн!"
]

# --- ПРОМПТЫ ---
SYSTEM_PROMPT_TOPIC_GEN = "Ты знаток мифов. Придумай одну редкую тему скандинавского фольклора. Только заголовок."
SYSTEM_PROMPT_TEXT = "Ты скальд. Напиши МОНУМЕНТАЛЬНЫЙ лонгрид (минимум 7000 знаков). Структура: 1. ЭТИМОЛОГИЯ, 2. МИФ, 3. СИМВОЛИЗМ, 4. СОВРЕМЕННОСТЬ. Не используй жирный шрифт. Тема: "
SYSTEM_PROMPT_VOICE = "Напиши атмосферное вступление (2-3 предложения) от лица старого викинга. На русском."
SYSTEM_PROMPT_IMAGE = "Cinematic digital art, epic Norse mythology scene, dramatic lighting, 8k. Topic: "

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
    # Считаем дни от запуска
    day_index = (datetime.now() - START_DATE).days
    if day_index < 0: day_index = 0
    
    if os.path.exists("topics.txt"):
        try:
            with open("topics.txt", "r", encoding="utf-8") as f:
                lines = [l.strip() for l in f if l.strip()]
            if lines: 
                # Берем тему по порядку
                return lines[day_index % len(lines)], f"📜 Свиток №{day_index % len(lines) + 1}"
        except: pass
    
    return model.generate_content(SYSTEM_PROMPT_TOPIC_GEN).text.strip(), "🔮 Руны AI"

def process_topic():
    try:
        topic, src = get_topic()
        
        # Случайная фраза начала
        start_msg = random.choice(START_PHRASES)
        bot.send_message(YOUR_CHAT_ID, f"{start_msg}\n\n{src}\nТема: {topic}")
        
        # Картинка
        try: img_p = model.generate_content(f"SD prompt for: {topic}").text
        except: img_p = SYSTEM_PROMPT_IMAGE + topic
        resp = requests.post(API_URL, headers=headers, json={"inputs": img_p})
        if resp.status_code == 200: bot.send_photo(YOUR_CHAT_ID, resp.content)

        # Голос
        v_text = clean_text(model.generate_content(f"{SYSTEM_PROMPT_VOICE} {topic}").text)
        fname = f"v_{random.randint(1,99)}.mp3"
        asyncio.run(generate_voice_file(v_text, fname))
        with open(fname, 'rb') as a: bot.send_voice(YOUR_CHAT_ID, a)
        os.remove(fname)

        # Текст
        bot.send_chat_action(YOUR_CHAT_ID, 'typing')
        story = clean_text(model.generate_content(f"{SYSTEM_PROMPT_TEXT} {topic}").text)
        smart_split_and_send(YOUR_CHAT_ID, story)
        
    except Exception as e:
        bot.send_message(YOUR_CHAT_ID, f"⚠️ Локи строит козни (Ошибка): {e}")

# --- ОБРАБОТЧИКИ ---
@bot.message_handler(commands=['start'])
def start(m):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(types.KeyboardButton("📜 Расскажи Сагу"))
    bot.send_message(m.chat.id, "⚔️ Добро пожаловать, путник.", reply_markup=kb)

@bot.message_handler(func=lambda m: m.text == "📜 Расскажи Сагу")
def on_click(m):
    # Случайная фраза ожидания
    wait_msg = random.choice(WAIT_PHRASES)
    bot.send_message(m.chat.id, wait_msg)
    process_topic()

# --- SERVER ---
server = Flask(__name__)
@server.route("/")
def webhook(): return "OK", 200

def run_server(): server.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
def scheduler():
    while True:
        time.sleep(86400)
        process_topic()

if __name__ == "__main__":
    try: bot.remove_webhook()
    except: pass
    threading.Thread(target=run_server, daemon=True).start()
    threading.Thread(target=scheduler, daemon=True).start()
    bot.infinity_polling()
