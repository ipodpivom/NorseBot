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

# --- БЕЗОПАСНОСТЬ: КЛЮЧИ БЕРУТСЯ ИЗ НАСТРОЕК СЕРВЕРА ---
# В этом коде нет твоих реальных токенов, поэтому его можно показывать в резюме.
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
HUGGING_FACE_KEY = os.environ.get("HUGGING_FACE_KEY")
YOUR_CHAT_ID = os.environ.get("YOUR_CHAT_ID")

# --- НАСТРОЙКИ ---
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')
bot = telebot.TeleBot(TELEGRAM_TOKEN)

API_URL = "https://router.huggingface.co/hf-inference/models/stabilityai/stable-diffusion-xl-base-1.0"
headers = {"Authorization": f"Bearer {HUGGING_FACE_KEY}"}

# --- ЛОГИКА БОТА ---
SYSTEM_PROMPT_TOPIC = "Ты — эрудированный знаток Скандинавской мифологии. Придумай ОДНУ редкую, мистическую тему для рассказа. Выведи ТОЛЬКО заголовок."
SYSTEM_PROMPT_TEXT = "Ты — скальд. Напиши атмосферный рассказ по этой теме (около 2000 знаков). Не используй Markdown жирный шрифт."
SYSTEM_PROMPT_VOICE = "Напиши очень короткое вступление (1-2 предложения) для озвучки, как будто старый викинг начинает рассказ."
SYSTEM_PROMPT_IMAGE = "Cinematic digital art, epic Norse mythology scene, dramatic lighting, 8k resolution. Topic: "

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
    # Используем голос 'DmitryNeural' - он звучит серьезно и качественно
    communicate = edge_tts.Communicate(text, "ru-RU-DmitryNeural")
    await communicate.save(filename)

def process_topic():
    try:
        # 1. Придумываем тему
        response_topic = model.generate_content(SYSTEM_PROMPT_TOPIC)
        topic = response_topic.text.strip()
        bot.send_message(YOUR_CHAT_ID, f"⚔️ Руны указали на тему: {topic}")

        # 2. Генерируем картинку
        img_prompt = SYSTEM_PROMPT_IMAGE + topic
        try:
            # Спрашиваем Gemini лучший промпт для картинки
            img_prompt = model.generate_content(f"Create a Stable Diffusion prompt for: {topic}. English only.").text
        except:
            pass # Если не вышло, используем базовый
            
        response_img = requests.post(API_URL, headers=headers, json={"inputs": img_prompt})
        if response_img.status_code == 200:
            bot.send_photo(YOUR_CHAT_ID, response_img.content)

        # 3. Генерируем Голос
        voice_text_raw = model.generate_content(f"{SYSTEM_PROMPT_VOICE} Тема: {topic}").text
        voice_text = clean_text(voice_text_raw)
        filename = f"voice_{random.randint(1,9999)}.mp3"
        
        asyncio.run(generate_voice_file(voice_text, filename))
        
        with open(filename, 'rb') as audio:
            bot.send_voice(YOUR_CHAT_ID, audio)
        os.remove(filename)

        # 4. Пишем Историю
        bot.send_chat_action(YOUR_CHAT_ID, 'typing')
        story_raw = model.generate_content(f"{SYSTEM_PROMPT_TEXT} Тема: {topic}").text
        story = clean_text(story_raw)
        send_long_message(YOUR_CHAT_ID, story)

    except Exception as e:
        bot.send_message(YOUR_CHAT_ID, f"⚠️ Сбой ритуала: {e}")
        print(f"Error: {e}")

# --- ОБРАБОТКА КОМАНД ---
@bot.message_handler(commands=['start'])
def start(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("📜 Расскажи историю"))
    bot.send_message(message.chat.id, "Слава Одину! Нажми кнопку, чтобы услышать сагу.", reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "📜 Расскажи историю")
def on_click(message):
    bot.send_message(message.chat.id, "⚡ Скальд настраивает струны...")
    process_topic()

# --- ВЕБ-СЕРВЕР (Требование Render) ---
server = Flask(__name__)

@server.route("/")
def webhook():
    return "NorseBot is Alive!", 200

def run_web_server():
    server.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))

def schedule_loop():
    while True:
        # Авто-пост раз в 24 часа
        time.sleep(86400)
        process_topic()

if __name__ == "__main__":
    # 1. Запуск веб-сервера (чтобы Render видел активность)
    t_server = threading.Thread(target=run_web_server)
    t_server.daemon = True
    t_server.start()

    # 2. Запуск таймера
    t_sched = threading.Thread(target=schedule_loop)
    t_sched.daemon = True
    t_sched.start()

    # 3. Запуск бота
    print("🚀 Бот запущен и готов к битве!")
    bot.infinity_polling()
