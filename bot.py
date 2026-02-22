import telebot
from telebot import types
from google import genai
import os
import time
import requests
import threading
import random
import asyncio
import edge_tts
import urllib.parse
import io
from flask import Flask, request
from datetime import datetime

# --- КЛЮЧИ ---
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
YOUR_CHAT_ID = os.environ.get("YOUR_CHAT_ID")

# --- НАСТРОЙКИ ВРЕМЕНИ (UTC) ---
START_DATE = datetime(2026, 2, 8) 
TIME_RUNE_UTC = 4  # 6:00 Киев
TIME_SAGA_UTC = 7  # 9:00 Киев

client = genai.Client(api_key=GEMINI_API_KEY)

class ModelMock:
    def generate_content(self, prompt):
        class ResponseMock:
            def __init__(self, text):
                self.text = text
        res = client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
        return ResponseMock(res.text)

model = ModelMock()
bot = telebot.TeleBot(TELEGRAM_TOKEN)

# --- РЕЗЕРВНЫЙ СЛОВАРЬ ---
RUNE_FALLBACKS = {
    "Феху (Fehu) - Богатство": "https://fakeimg.pl/800x800/1e293b/fbbf24/?text=Fehu&font=museo",
    "Уруз (Uruz) - Сила": "https://fakeimg.pl/800x800/1e293b/fbbf24/?text=Uruz&font=museo",
    "Турисаз (Thurisaz) - Врата": "https://fakeimg.pl/800x800/1e293b/fbbf24/?text=Thurisaz&font=museo",
    "Ансуз (Ansuz) - Знание": "https://fakeimg.pl/800x800/1e293b/fbbf24/?text=Ansuz&font=museo",
    "Райдо (Raidho) - Путь": "https://fakeimg.pl/800x800/1e293b/fbbf24/?text=Raidho&font=museo",
    "Кеназ (Kenaz) - Огонь": "https://fakeimg.pl/800x800/1e293b/fbbf24/?text=Kenaz&font=museo",
    "Гебо (Gebo) - Дар": "https://fakeimg.pl/800x800/1e293b/fbbf24/?text=Gebo&font=museo",
    "Вуньо (Wunjo) - Радость": "https://fakeimg.pl/800x800/1e293b/fbbf24/?text=Wunjo&font=museo",
    "Хагалаз (Hagalaz) - Разрушение": "https://fakeimg.pl/800x800/1e293b/fbbf24/?text=Hagalaz&font=museo",
    "Наутиз (Nauthiz) - Нужда": "https://fakeimg.pl/800x800/1e293b/fbbf24/?text=Nauthiz&font=museo",
    "Иса (Isa) - Лед": "https://fakeimg.pl/800x800/1e293b/fbbf24/?text=Isa&font=museo",
    "Йера (Jera) - Урожай": "https://fakeimg.pl/800x800/1e293b/fbbf24/?text=Jera&font=museo",
    "Эйваз (Eihwaz) - Защита": "https://fakeimg.pl/800x800/1e293b/fbbf24/?text=Eihwaz&font=museo",
    "Перт (Perthro) - Тайна": "https://fakeimg.pl/800x800/1e293b/fbbf24/?text=Perthro&font=museo",
    "Альгиз (Algiz) - Защита высших сил": "https://fakeimg.pl/800x800/1e293b/fbbf24/?text=Algiz&font=museo",
    "Соулу (Sowilo) - Солнце": "https://fakeimg.pl/800x800/1e293b/fbbf24/?text=Sowilo&font=museo",
    "Тейваз (Tiwaz) - Воин": "https://fakeimg.pl/800x800/1e293b/fbbf24/?text=Tiwaz&font=museo",
    "Беркана (Berkana) - Рост": "https://fakeimg.pl/800x800/1e293b/fbbf24/?text=Berkana&font=museo",
    "Эваз (Ehwaz) - Движение": "https://fakeimg.pl/800x800/1e293b/fbbf24/?text=Ehwaz&font=museo",
    "Манназ (Mannaz) - Человек": "https://fakeimg.pl/800x800/1e293b/fbbf24/?text=Mannaz&font=museo",
    "Лагуз (Laguz) - Интуиция": "https://fakeimg.pl/800x800/1e293b/fbbf24/?text=Laguz&font=museo",
    "Ингуз (Inguz) - Плодородия": "https://fakeimg.pl/800x800/1e293b/fbbf24/?text=Inguz&font=museo",
    "Отал (Othala) - Наследие": "https://fakeimg.pl/800x800/1e293b/fbbf24/?text=Othala&font=museo",
    "Дагаз (Dagaz) - Прорыв": "https://fakeimg.pl/800x800/1e293b/fbbf24/?text=Dagaz&font=museo"
}
RUNES = list(RUNE_FALLBACKS.keys())

subscribers = set()
if YOUR_CHAT_ID: subscribers.add(YOUR_CHAT_ID)

# --- ФРАЗЫ ---
WAIT_PHRASES = [
    "🦅 Хугин и Мунин полетели за историей...",
    "⏳ Норны сплетают нить, жди...",
    "🍺 Скальд наливает мёд поэзии...",
    "🌲 Шепот ветвей Иггдрасиля..."
]

START_PHRASES = [
    "⚔️ Руны легли верно!",
    "⚡ Тор ударил молотом!",
    "📜 Сдуваю пыль со свитков...",
    "🐺 Фенрир завыл..."
]

RUNE_ACTION_PHRASES = [
    "🎲 Кости брошены на шкуру медведя...",
    "✋ Рука Одина тянется в мешок судеб...",
    "🌑 Камни шепчут во тьме...",
    "👁️ Гляди внимательно, воин, это твой знак..."
]

# --- ПРОМПТЫ ---
SYSTEM_PROMPT_TOPIC_GEN = "Ты знаток мифов. Придумай одну редкую тему скандинавского фольклора. Только заголовок."
SYSTEM_PROMPT_TEXT = """
Ты — древний скальд. Напиши МОНУМЕНТАЛЬНЫЙ лонгрид (объем 8000-9000 знаков).
Пиши МАКСИМАЛЬНО ПОДРОБНО, с диалогами.
СТРУКТУРА: 1. ЭТИМОЛОГИЯ, 2. МИФ (Детально), 3. СИМВОЛИЗМ, 4. СОВРЕМЕННОСТЬ.
Не используй жирный шрифт. Тема: 
"""
SYSTEM_PROMPT_VOICE = "Напиши атмосферное вступление (2-3 предложения) от лица старого викинга. На русском."
SYSTEM_PROMPT_ORACLE = "Ты — Один. Ответь смертному мудро, кратко (4 предл.), метафорично. СТРОГО НА РУССКОМ. Вопрос: "
SYSTEM_PROMPT_RUNE = "Ты — Шаман. Выпала Руна: {rune}. Дай краткое (3-4 предл.) толкование. СТРОГО НА РУССКОМ."

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

def get_main_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(types.KeyboardButton("📜 Расскажи Сагу"), types.KeyboardButton("ᛟ Вытянуть Руну"), types.KeyboardButton("🔮 Спросить Одина"))
    return markup

def get_ai_image_url(prompt):
    encoded_prompt = urllib.parse.quote(prompt)
    seed = random.randint(1, 1000000)
    return f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1024&height=1024&nologo=true&seed={seed}"

# 🔥 НОВАЯ ФУНКЦИЯ: Скачивает картинку в память Render перед отправкой
def download_and_send(chat_id, main_url, fallback_url, caption=None):
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    
    try:
        print("⏳ Render скачивает ИИ-картинку себе в память...", flush=True)
        resp = requests.get(main_url, headers=headers, timeout=20)
        if resp.status_code == 200 and len(resp.content) > 1000:
            photo = io.BytesIO(resp.content)
            photo.name = 'ai_image.jpg'
            if caption:
                bot.send_photo(chat_id, photo, caption=caption, parse_mode="Markdown")
            else:
                bot.send_photo(chat_id, photo)
            print("✅ Файл картинки успешно передан в Телеграм!", flush=True)
            return True
    except Exception as e:
        print(f"⚠️ ИИ-генератор не ответил: {e}", flush=True)

    try:
        print("⏳ Скачиваю резервную картинку в память...", flush=True)
        resp = requests.get(fallback_url, headers=headers, timeout=10)
        if resp.status_code == 200:
            photo = io.BytesIO(resp.content)
            photo.name = 'fallback.jpg'
            if caption:
                bot.send_photo(chat_id, photo, caption=caption, parse_mode="Markdown")
            else:
                bot.send_photo(chat_id, photo)
            print("✅ Резервный файл отправлен!", flush=True)
            return True
    except Exception as e:
        print(f"❌ Полный провал скачивания: {e}", flush=True)
        
    # Если сломалось вообще всё (даже резерв)
    if caption:
        bot.send_message(chat_id, f"*(Изображение утеряно в веках)*\n{caption}", parse_mode="Markdown")
    else:
        bot.send_message(chat_id, "*(Картинка потерялась в тумане, но сага осталась...)*", parse_mode="Markdown")
    return False

def generate_and_send_saga(target_chat_id=None):
    try:
        topic, src = get_topic()
        targets = [target_chat_id] if target_chat_id else subscribers
        
        try: 
            img_p = clean_text(model.generate_content(f"Translate to English and give 3-4 keywords for image search, NO extra text: {topic}").text)
        except: 
            img_p = "epic viking norse mythology cinematic"
            
        ai_url = get_ai_image_url(img_p)
        fallback_url = f"https://loremflickr.com/800/800/viking,mythology?random={random.randint(1, 10000)}"

        v_text = clean_text(model.generate_content(f"{SYSTEM_PROMPT_VOICE} {topic}").text)
        fname = f"v_{random.randint(1,999)}.mp3"
        asyncio.run(generate_voice_file(v_text, fname))
        story = clean_text(model.generate_content(f"{SYSTEM_PROMPT_TEXT} {topic}").text)

        for chat_id in targets:
            try:
                bot.send_message(chat_id, f"{random.choice(START_PHRASES)}\n\n{src}\nТема: {topic}")
                
                # Вызываем нашу новую безопасную функцию отправки фото
                download_and_send(chat_id, ai_url, fallback_url)
                
                with open(fname, 'rb') as a: bot.send_voice(chat_id, a)
                bot.send_chat_action(chat_id, 'typing')
                smart_split_and_send(chat_id, story)
            except Exception as e:
                print(f"❌ Ошибка отправки Саги: {e}", flush=True)

        if os.path.exists(fname): os.remove(fname)
    except Exception as e: 
        print(f"❌ CRITICAL ERROR SAGA: {e}", flush=True)

def generate_and_send_rune(target_chat_id=None):
    try:
        if target_chat_id: 
            bot.send_message(target_chat_id, random.choice(RUNE_ACTION_PHRASES))
            bot.send_chat_action(target_chat_id, 'typing')

        rune = random.choice(RUNES)
        prompt = SYSTEM_PROMPT_RUNE.format(rune=rune)
        prediction = clean_text(model.generate_content(prompt).text)
        rune_name_eng = rune.split('(')[1].split(')')[0]
        
        img_prompt = f"magic glowing rune stone {rune_name_eng} viking cinematic 8k"
        ai_url = get_ai_image_url(img_prompt)
        fallback_url = RUNE_FALLBACKS[rune]
        
        targets = [target_chat_id] if target_chat_id else subscribers
        for user_id in targets:
            try:
                if not target_chat_id: bot.send_message(user_id, "🌅 Солнце встало. Твоя Руна Дня:")

                # Вызываем нашу новую безопасную функцию отправки фото
                download_and_send(user_id, ai_url, fallback_url, caption=f"*{rune}*")
                    
                bot.send_message(user_id, f"👁️ *Толкование:*\n\n{prediction}", parse_mode="Markdown")
            except Exception as e:
                print(f"❌ Ошибка отправки Руны: {e}", flush=True)
    except Exception as e: 
        print(f"❌ CRITICAL ERROR RUNE: {e}", flush=True)

def ask_odin_step(message):
    if message.text in ["📜 Расскажи Сагу", "🔮 Спросить Одина", "ᛟ Вытянуть Руну", "/start"]:
        bot.send_message(message.chat.id, "👁️ Ритуал прерван.", reply_markup=get_main_keyboard())
        return
    try:
        bot.send_chat_action(message.chat.id, 'typing')
        answer = clean_text(model.generate_content(f"{SYSTEM_PROMPT_ORACLE} {message.text}").text)
        bot.reply_to(message, f"👁️ *Один говорит:*\n\n{answer}", parse_mode="Markdown", reply_markup=get_main_keyboard())
    except:
        bot.send_message(message.chat.id, "Туман скрыл ответ...", reply_markup=get_main_keyboard())

# --- ОБРАБОТЧИКИ ---
@bot.message_handler(commands=['start'])
def start(m):
    subscribers.add(str(m.chat.id))
    bot.send_message(m.chat.id, "⚔️ Чертоги открыты.", reply_markup=get_main_keyboard())

@bot.message_handler(func=lambda m: m.text == "📜 Расскажи Сагу")
def on_saga_click(m):
    bot.send_message(m.chat.id, random.choice(WAIT_PHRASES))
    threading.Thread(target=generate_and_send_saga, args=(m.chat.id,)).start()

@bot.message_handler(func=lambda m: m.text == "ᛟ Вытянуть Руну")
def on_rune_click(m):
    threading.Thread(target=generate_and_send_rune, args=(m.chat.id,)).start()

@bot.message_handler(func=lambda m: m.text == "🔮 Спросить Одина")
def on_oracle_click(m):
    msg = bot.send_message(m.chat.id, "👁️ Всеотец слушает. Задай свой вопрос...", reply_markup=types.ReplyKeyboardRemove())
    bot.register_next_step_handler(msg, ask_odin_step)

# --- SERVER & SCHEDULER ---
server = Flask(__name__)
WEBHOOK_URL = os.environ.get("RENDER_EXTERNAL_URL") 

@server.route(f"/{TELEGRAM_TOKEN}", methods=['POST'])
def receive_update():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return "!", 200
    return "Not JSON", 403

@server.route("/")
def index():
    return "Сервис работает! 🛡️ Webhook активен.", 200

def scheduler():
    while True:
        now = datetime.now()
        if now.hour == TIME_RUNE_UTC and now.minute == 0:
            generate_and_send_rune() 
            time.sleep(61)
        elif now.hour == TIME_SAGA_UTC and now.minute == 0:
            generate_and_send_saga() 
            time.sleep(61)  
        time.sleep(30)

if __name__ == "__main__":
    try: bot.remove_webhook()
    except: pass
    time.sleep(1)

    if WEBHOOK_URL:
        bot.set_webhook(url=f"{WEBHOOK_URL}/{TELEGRAM_TOKEN}")
        print(f"✅ Вебхук успешно установлен на: {WEBHOOK_URL}")
    else:
        print("⚠️ RENDER_EXTERNAL_URL не найден. Запускаю локальный Polling...")
        threading.Thread(target=bot.infinity_polling, daemon=True).start()

    threading.Thread(target=scheduler, daemon=True).start()
    port = int(os.environ.get("PORT", 10000))
    server.run(host="0.0.0.0", port=port)
