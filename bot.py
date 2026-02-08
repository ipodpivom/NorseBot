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
from flask import Flask, request

# --- КЛЮЧИ ---
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
HUGGING_FACE_KEY = os.environ.get("HUGGING_FACE_KEY")
YOUR_CHAT_ID = os.environ.get("YOUR_CHAT_ID")

# --- КОНФИГУРАЦИЯ ---
genai.configure(api_key=GEMINI_API_KEY)

# !!! ВРЕМЕННО: Ставим самую базовую модель, чтобы бот просто запустился !!!
# А в логах мы увидим, есть ли там Flash
model = genai.GenerativeModel('gemini-pro') 
bot = telebot.TeleBot(TELEGRAM_TOKEN)

API_URL = "https://router.huggingface.co/hf-inference/models/stabilityai/stable-diffusion-xl-base-1.0"
headers = {"Authorization": f"Bearer {HUGGING_FACE_KEY}"}

# --- ПРОМПТЫ ---
SYSTEM_PROMPT_TOPIC = "Ты — эрудированный знаток. Придумай ОДНУ тему для рассказа."
SYSTEM_PROMPT_TEXT = "Напиши короткий рассказ по теме."
SYSTEM_PROMPT_VOICE = "Напиши 1 предложение для вступления."
SYSTEM_PROMPT_IMAGE = "Epic scene describing: "

def clean_text(text):
    return text.replace("**", "").replace("__", "").replace("##", "").replace("* ", "- ")

def send_long_message(chat_id, text):
    if len(text) > 4000:
        for x in range(0, len(text), 4000):
            bot.send_message(chat_id, text[x:x+4000])
            time.sleep(1)
    else:
        bot.send_message(chat_id, text)

async def generate_voice_file(text, filename):
    communicate = edge_tts.Communicate(text, "ru-RU-DmitryNeural")
    await communicate.save(filename)

def process_topic():
    try:
        # 1. Тема
        response_topic = model.generate_content(SYSTEM_PROMPT_TOPIC)
        topic = response_topic.text.strip()
        bot.send_message(YOUR_CHAT_ID, f"✨ Тема: {topic}")

        # 2. Картинка (пока без нейро-промпта, чтобы проще было)
        response_img = requests.post(API_URL, headers=headers, json={"inputs": f"{SYSTEM_PROMPT_IMAGE} {topic}"})
        if response_img.status_code == 200:
            bot.send_photo(YOUR_CHAT_ID, response_img.content)

        # 3. Голос
        voice_text = model.generate_content(f"{SYSTEM_PROMPT_VOICE} Тема: {topic}").text
        filename = f"voice_{random.randint(1,999)}.mp3"
        asyncio.run(generate_voice_file(clean_text(voice_text), filename))
        with open(filename, 'rb') as audio:
            bot.send_voice(YOUR_CHAT_ID, audio)
        os.remove(filename)

        # 4. Текст
        story = model.generate_content(f"{SYSTEM_PROMPT_TEXT} Тема: {topic}").text
        send_long_message(YOUR_CHAT_ID, clean_text(story))

    except Exception as e:
        bot.send_message(YOUR_CHAT_ID, f"⚠️ Ошибка: {e}")
        print(f"Error: {e}")

@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(message.chat.id, "Жми /story")

@bot.message_handler(commands=['story'])
def story(message):
    bot.send_message(message.chat.id, "Начинаю...")
    process_topic()

# --- SERVER ---
server = Flask(__name__)
@server.route("/")
def webhook():
    return "OK", 200

def run_web_server():
    server.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))

if __name__ == "__main__":
    # --- ДИАГНОСТИКА МОДЕЛЕЙ ---
    print("🔍 СПИСОК ДОСТУПНЫХ МОДЕЛЕЙ:")
    try:
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                print(f"✅ {m.name}")
    except Exception as e:
        print(f"❌ Ошибка проверки моделей: {e}")
    # ---------------------------

    threading.Thread(target=run_web_server, daemon=True).start()
    print("🚀 Бот запущен!")
    bot.infinity_polling()
