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
START_DATE = datetime(2026, 2, 8) 
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-flash-latest') 
bot = telebot.TeleBot(TELEGRAM_TOKEN)

API_URL = "https://router.huggingface.co/hf-inference/models/stabilityai/stable-diffusion-xl-base-1.0"
headers = {"Authorization": f"Bearer {HUGGING_FACE_KEY}"}

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
SYSTEM_PROMPT_TEXT = "Ты скальд. Напиши МОНУМЕНТАЛЬНЫЙ лонгрид (минимум 6000 знаков). Структура: 1. ЭТИМОЛОГИЯ, 2. МИФ, 3. СИМВОЛИЗМ, 4. СОВРЕМЕННОСТЬ. Не используй жирный шрифт. Тема: "
SYSTEM_PROMPT_VOICE = "Напиши атмосферное вступление (2-3 предложения) от лица старого викинга. На русском."
SYSTEM_PROMPT_IMAGE = "Cinematic digital art, epic Norse mythology scene, dramatic lighting, 8k. Topic: "

# 🔥 ИСПРАВЛЕННЫЙ ПРОМПТ ОРАКУЛА (РУССКИЙ ЯЗЫК)
SYSTEM_PROMPT_ORACLE = """
Ты — Один, Всеотец. 
Твоя задача: Ответить смертному мудро, кратко (максимум 4 предложения) и метафорично.
Используй образы рун, северной природы и богов. Не давай скучных советов.
ВАЖНО: ОТВЕЧАЙ СТРОГО НА РУССКОМ ЯЗЫКЕ.
Вопрос смертного: 
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

def process_topic():
    try:
        topic, src = get_topic()
        bot.send_message(YOUR_CHAT_ID, f"{random.choice(START_PHRASES)}\n\n{src}\nТема: {topic}")
        
        try: img_p = model.generate_content(f"SD prompt for: {topic}").text
        except: img_p = SYSTEM_PROMPT_IMAGE + topic
        resp = requests.post(API_URL, headers=headers, json={"inputs": img_p})
        if resp.status_code == 200: bot.send_photo(YOUR_CHAT_ID, resp.content)

        v_text = clean_text(model.generate_content(f"{SYSTEM_PROMPT_VOICE} {topic}").text)
        fname = f"v_{random.randint(1,99)}.mp3"
        asyncio.run(generate_voice_file(v_text, fname))
        with open(fname, 'rb') as a: bot.send_voice(YOUR_CHAT_ID, a)
        os.remove(fname)

        bot.send_chat_action(YOUR_CHAT_ID, 'typing')
        story = clean_text(model.generate_content(f"{SYSTEM_PROMPT_TEXT} {topic}").text)
        smart_split_and_send(YOUR_CHAT_ID, story)
    except Exception as e:
        bot.send_message(YOUR_CHAT_ID, f"⚠️ Ошибка: {e}")

def ask_odin_step(message):
    if message.text in ["📜 Расскажи Сагу", "🔮 Спросить Одина", "/start"]:
        bot.send_message(message.chat.id, "👁️ Ритуал прерван.", reply_markup=get_main_keyboard())
        return

    try:
        bot.send_chat_action(message.chat.id, 'typing')
        # Генерируем ответ (теперь точно на русском)
        answer = clean_text(model.generate_content(f"{SYSTEM_PROMPT_ORACLE} {message.text}").text)
        bot.reply_to(message, f"👁️ **Один говорит:**\n\n{answer}", parse_mode="Markdown", reply_markup=get_main_keyboard())
    except:
        bot.send_message(message.chat.id, "Туман скрыл ответ...", reply_markup=get_main_keyboard())

@bot.message_handler(commands=['start'])
def start(m):
    bot.send_message(m.chat.id, "⚔️ Чертоги открыты. Что ищешь?", reply_markup=get_main_keyboard())

@bot.message_handler(func=lambda m: m.text == "📜 Расскажи Сагу")
def on_saga_click(m):
    bot.send_message(m.chat.id, random.choice(WAIT_PHRASES))
    process_topic()

@bot.message_handler(func=lambda m: m.text == "🔮 Спросить Одина")
def on_oracle_click(m):
    msg = bot.send_message(m.chat.id, "👁️ Всеотец слушает. Задай свой вопрос...", reply_markup=types.ReplyKeyboardRemove())
    bot.register_next_step_handler(msg, ask_odin_step)

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
