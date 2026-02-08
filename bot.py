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
from datetime import datetime # Нужно для календаря

# --- КЛЮЧИ ---
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
HUGGING_FACE_KEY = os.environ.get("HUGGING_FACE_KEY")
YOUR_CHAT_ID = os.environ.get("YOUR_CHAT_ID")

# --- КОНФИГУРАЦИЯ ---
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-flash-latest') 
bot = telebot.TeleBot(TELEGRAM_TOKEN)

API_URL = "https://router.huggingface.co/hf-inference/models/stabilityai/stable-diffusion-xl-base-1.0"
headers = {"Authorization": f"Bearer {HUGGING_FACE_KEY}"}

# --- АТМОСФЕРНЫЕ СТАТУСЫ ---
VIKING_PHRASES_START = [
    "🍺 Скальд настраивает струны...",
    "🦅 Хугин и Мунин полетели за новостями...",
    "🔥 Руны брошены. Смотрим в бездну...",
    "⚡ Тор заносит молот...",
    "🌲 Иггдрасиль шепчет...",
    "🛡️ Хеймдалль трубит в рог...",
    "🕯️ Норны прядут нить судьбы..."
]

# --- ПРОМПТЫ (ТВОИ ЛЮБИМЫЕ) ---

# 1. Запасной генератор (если файл кончится)
SYSTEM_PROMPT_TOPIC_GEN = """
Ты — эрудированный знаток Скандинавской мифологии.
Придумай ОДНУ редкую, мистическую тему для рассказа.
Выведи ТОЛЬКО заголовок.
"""

# 2. Текст (Монументальный)
SYSTEM_PROMPT_TEXT = """
Ты — скальд. Напиши МОНУМЕНТАЛЬНЫЙ лонгрид (минимум 7000 знаков).
ПРАВИЛА ОФОРМЛЕНИЯ:
1. Используй ОБЫЧНЫЙ регистр. Предложения начинай с Заглавной буквы.
2. НЕ пиши весь текст КАПСОМ.
3. ЗАГОЛОВКИ разделов пиши КАПСОМ.
4. НЕ ИСПОЛЬЗУЙ жирный шрифт (**текст**).
5. Списки оформляй через дефис (-).
СТРУКТУРА:
1. ЭТИМОЛОГИЯ.
2. МИФ/ИСТОРИЯ (Самая большая, подробная часть с диалогами).
3. СИМВОЛИЗМ.
4. СВЯЗЬ С СОВРЕМЕННОСТЬЮ.
Тема:
"""

# 3. Голос (Коротко)
SYSTEM_PROMPT_VOICE = """
Напиши ОЧЕНЬ КОРОТКОЕ, атмосферное вступление к этой теме (максимум 3 предложения).
Стиль: старый мудрец рассказывает легенду у костра.
Текст должен быть на русском.
"""

SYSTEM_PROMPT_IMAGE = "Cinematic digital art, epic Norse mythology scene, dramatic lighting, highly detailed, 8k resolution, oil painting style. Topic: "

# --- ФУНКЦИИ ---
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

# --- НОВАЯ ЛОГИКА: ВЫБОР ПО ПОРЯДКУ ---
def get_topic():
    # 1. Пробуем взять из файла topics.txt
    if os.path.exists("topics.txt"):
        try:
            with open("topics.txt", "r", encoding="utf-8") as f:
                lines = [line.strip() for line in f if line.strip()]
            
            if lines:
                # Магия календаря: 
                # Берем номер дня в году (сегодня, например, 40-й день)
                # И берем соответствующую строчку.
                # Если список кончится, он начнет сначала (оператор %)
                day_of_year = datetime.now().timetuple().tm_yday
                index = (day_of_year) % len(lines)
                
                topic = lines[index]
                return topic, f"📜 Из свитков (Строка {index+1})"
        except Exception as e:
            print(f"Ошибка чтения файла: {e}")
    
    # 2. Если файла нет — генерируем AI
    response = model.generate_content(SYSTEM_PROMPT_TOPIC_GEN)
    return response.text.strip(), "🔮 Руны подсказали (AI)"

def process_topic():
    try:
        topic, source_msg = get_topic()
        
        status = random.choice(VIKING_PHRASES_START)
        bot.send_message(YOUR_CHAT_ID, f"{status}\n\n{source_msg}\nТема: {topic}")

        # Картинка
        try:
            img_prompt = model.generate_content(f"Describe this Norse myth for Stable Diffusion AI image generator. English only. Myth: {topic}").text
        except:
            img_prompt = SYSTEM_PROMPT_IMAGE + topic
            
        response_img = requests.post(API_URL, headers=headers, json={"inputs": img_prompt})
        if response_img.status_code == 200:
            bot.send_photo(YOUR_CHAT_ID, response_img.content)

        # Голос
        voice_text = clean_text(model.generate_content(f"{SYSTEM_PROMPT_VOICE} Тема: {topic}").text)
        filename = f"voice_{random.randint(1,9999)}.mp3"
        asyncio.run(generate_voice_file(voice_text, filename))
        with open(filename, 'rb') as audio:
            bot.send_voice(YOUR_CHAT_ID, audio)
        os.remove(filename)

        # Текст
        bot.send_chat_action(YOUR_CHAT_ID, 'typing')
        story = clean_text(model.generate_content(f"{SYSTEM_PROMPT_TEXT} {topic}").text)
        send_long_message(YOUR_CHAT_ID, story)

    except Exception as e:
        bot.send_message(YOUR_CHAT_ID, f"⚠️ Локи строит козни (Ошибка): {e}")
        print(f"Error: {e}")

# --- ОБРАБОТЧИКИ ---
@bot.message_handler(commands=['start'])
def start(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("📜 Расскажи Сагу"))
    bot.send_message(message.chat.id, "⚔️ Мои свитки полны историй. Нажми кнопку!", reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "📜 Расскажи Сагу")
def on_click(message):
    process_topic()

# --- WEB SERVER ---
server = Flask(__name__)
@server.route("/")
def webhook():
    return "Bot is running", 200

def run_web_server():
    server.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))

def schedule_loop():
    while True:
        time.sleep(86400)
        process_topic()

if __name__ == "__main__":
    threading.Thread(target=run_web_server, daemon=True).start()
    threading.Thread(target=schedule_loop, daemon=True).start()
    print("🚀 Бот запущен!")
    bot.infinity_polling()
