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
from datetime import datetime

# --- КЛЮЧИ ---
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
HUGGING_FACE_KEY = os.environ.get("HUGGING_FACE_KEY")
YOUR_CHAT_ID = os.environ.get("YOUR_CHAT_ID")

# --- НАСТРОЙКИ ---
# 📅 ВАЖНО: Дата начала отсчета (год, месяц, день). 
# Сегодняшний день будет №0 (первая строка файла).
START_DATE = datetime(2026, 2, 8) 

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-flash-latest') 
bot = telebot.TeleBot(TELEGRAM_TOKEN)

API_URL = "https://router.huggingface.co/hf-inference/models/stabilityai/stable-diffusion-xl-base-1.0"
headers = {"Authorization": f"Bearer {HUGGING_FACE_KEY}"}

# --- ПРОМПТЫ ---
SYSTEM_PROMPT_TOPIC_GEN = "Ты — знаток мифов. Придумай одну редкую тему скандинавского фольклора. Только заголовок."

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

SYSTEM_PROMPT_VOICE = """
Напиши ОЧЕНЬ КОРОТКОЕ, атмосферное вступление к этой теме (максимум 3 предложения).
Стиль: старый мудрец рассказывает легенду у костра.
Текст должен быть на русском.
"""

SYSTEM_PROMPT_IMAGE = "Cinematic digital art, epic Norse mythology scene, dramatic lighting, highly detailed, 8k resolution, oil painting style. Topic: "

# --- ФУНКЦИИ ---
def clean_text(text):
    return text.replace("**", "").replace("__", "").replace("##", "").replace("* ", "- ")

# 🧠 Умная нарезка текста (чтобы не рвать слова)
def smart_split_and_send(chat_id, text):
    chunk_size = 4000
    while text:
        if len(text) <= chunk_size:
            bot.send_message(chat_id, text)
            break
        
        # Ищем ближайший перенос строки или пробел перед лимитом
        split_at = text.rfind('\n', 0, chunk_size)
        if split_at == -1:
            split_at = text.rfind(' ', 0, chunk_size)
        
        if split_at == -1: # Если совсем нет пробелов (редко), режем жестко
            split_at = chunk_size
            
        chunk = text[:split_at]
        bot.send_message(chat_id, chunk)
        
        # Убираем отправленное + перенос строки
        text = text[split_at:].lstrip()
        time.sleep(1) # Даем Телеграму выдохнуть

async def generate_voice_file(text, filename):
    communicate = edge_tts.Communicate(text, "ru-RU-DmitryNeural")
    await communicate.save(filename)

def get_topic():
    # 1. Считаем дни от даты запуска
    now = datetime.now()
    delta = now - START_DATE
    day_index = delta.days 
    
    # Если вдруг дата запуска в будущем (ошибка настройки), ставим 0
    if day_index < 0: day_index = 0

    if os.path.exists("topics.txt"):
        try:
            with open("topics.txt", "r", encoding="utf-8") as f:
                lines = [line.strip() for line in f if line.strip()]
            
            if lines:
                # Берем тему по порядку. Если список кончился — идем по кругу.
                real_index = day_index % len(lines)
                topic = lines[real_index]
                return topic, f"📜 Свиток №{real_index + 1} (из {len(lines)})"
        except Exception as e:
            print(f"Ошибка файла: {e}")
    
    # Если файла нет
    response = model.generate_content(SYSTEM_PROMPT_TOPIC_GEN)
    return response.text.strip(), "🔮 Руны AI"

def process_topic():
    try:
        topic, source_msg = get_topic()
        
        # 1. Приветствие (без картинки пока)
        bot.send_message(YOUR_CHAT_ID, f"🔥 Ритуал начат...\n\n{source_msg}\nТема: {topic}")

        # 2. Картинка (Gemini улучшает промпт)
        try:
            img_prompt = model.generate_content(f"Describe this Norse myth for Stable Diffusion AI image generator. English only. Myth: {topic}").text
        except:
            img_prompt = SYSTEM_PROMPT_IMAGE + topic
            
        response_img = requests.post(API_URL, headers=headers, json={"inputs": img_prompt})
        if response_img.status_code == 200:
            bot.send_photo(YOUR_CHAT_ID, response_img.content)

        # 3. Голос
        voice_text = clean_text(model.generate_content(f"{SYSTEM_PROMPT_VOICE} Тема: {topic}").text)
        filename = f"voice_{random.randint(1,9999)}.mp3"
        asyncio.run(generate_voice_file(voice_text, filename))
        with open(filename, 'rb') as audio:
            bot.send_voice(YOUR_CHAT_ID, audio)
        os.remove(filename)

        # 4. Текст (Умная отправка)
        bot.send_chat_action(YOUR_CHAT_ID, 'typing')
        story = clean_text(model.generate_content(f"{SYSTEM_PROMPT_TEXT} {topic}").text)
        smart_split_and_send(YOUR_CHAT_ID, story)

    except Exception as e:
        bot.send_message(YOUR_CHAT_ID, f"⚠️ Ошибка скальда: {e}")
        print(f"Error: {e}")

# --- ОБРАБОТЧИКИ ---
@bot.message_handler(commands=['start'])
def start(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    # Кнопка одна, чтобы не путаться
    markup.add(types.KeyboardButton("📜 Расскажи Сагу"))
    bot.send_message(message.chat.id, "⚔️ Добро пожаловать в Вальхаллу знаний.", reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "📜 Расскажи Сагу")
def on_click(message):
    # Защита от спама кнопкой (простая)
    bot.send_message(message.chat.id, "⏳ Секунду...")
    process_topic()

# --- WEB SERVER ---
server = Flask(__name__)
@server.route("/")
def webhook():
    return "OK", 200

def run_web_server():
    server.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))

def schedule_loop():
    while True:
        # Авто-пост раз в 24 часа
        time.sleep(86400)
        process_topic()

if __name__ == "__main__":
    # 🧹 ЧИСТКА: Удаляем старые вебхуки, чтобы не было конфликтов 409
    try:
        bot.remove_webhook()
        time.sleep(1)
    except:
        pass

    threading.Thread(target=run_web_server, daemon=True).start()
    threading.Thread(target=schedule_loop, daemon=True).start()
    
    print("🚀 Бот перезапущен и очищен!")
    bot.infinity_polling()
