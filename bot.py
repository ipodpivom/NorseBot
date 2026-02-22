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

# --- РЕЗЕРВНЫЙ СЛОВАРЬ (Надежный placehold.co) ---
RUNE_FALLBACKS = {
    "Феху (Fehu) - Богатство": "https://placehold.co/800x800/1e293b/fbbf24.png?text=Fehu",
    "Уруз (Uruz) - Сила": "https://placehold.co/800x800/1e293b/fbbf24.png?text=Uruz",
    "Турисаз (Thurisaz) - Врата": "https://placehold.co/800x800/1e293b/fbbf24.png?text=Thurisaz",
    "Ансуз (Ansuz) - Знание": "https://placehold.co/800x800/1e293b/fbbf24.png?text=Ansuz",
    "Райдо (Raidho) - Путь": "https://placehold.co/800x800/1e293b/fbbf24.png?text=Raidho",
    "Кеназ (Kenaz) - Огонь": "https://placehold.co/800x800/1e293b/fbbf24.png?text=Kenaz",
    "Гебо (Gebo) - Дар": "https://placehold.co/800x800/1e293b/fbbf24.png?text=Gebo",
    "Вуньо (Wunjo) - Радость": "https://placehold.co/800x800/1e293b/fbbf24.png?text=Wunjo",
    "Хагалаз (Hagalaz) - Разрушение": "https://placehold.co/800x800/1e293b/fbbf24.png?text=Hagalaz",
    "Наутиз (Nauthiz) - Нужда": "https://placehold.co/800x800/1e293b/fbbf24.png?text=Nauthiz",
    "Иса (Isa) - Лед": "https://placehold.co/800x800/1e293b/fbbf24.png?text=Isa",
    "Йера (Jera) - Урожай": "https://placehold.co/800x800/1e293b/fbbf24.png?text=Jera",
    "Эйваз (Eihwaz) - Защита": "https://placehold.co/800x800/1e293b/fbbf24.png?text=Eihwaz",
    "Перт (Perthro) - Тайна": "https://placehold.co/800x800/1e293b/fbbf24.png?text=Perthro",
    "Альгиз (Algiz) - Защита высших сил": "https://placehold.co/800x800/1e293b/fbbf24.png?text=Algiz",
    "Соулу (Sowilo) - Солнце": "https://placehold.co/800x800/1e293b/fbbf24.png?text=Sowilo",
    "Тейваз (Tiwaz) - Воин": "https://placehold.co/800x800/1e293b/fbbf24.png?text=Tiwaz",
    "Беркана (Berkana) - Рост": "https://placehold.co/800x800/1e293b/fbbf24.png?text=Berkana",
    "Эваз (Ehwaz) - Движение": "https://placehold.co/800x800/1e293b/fbbf24.png?text=Ehwaz",
    "Манназ (Mannaz) - Человек": "https://placehold.co/800x800/1e293b/fbbf24.png?text=Mannaz",
    "Лагуз (Laguz) - Интуиция": "https://placehold.co/800x800/1e293b/fbbf24.png?text=Laguz",
    "Ингуз (Inguz) - Плодородия": "https://placehold.co/800x800/1e293b/fbbf24.png?text=Inguz",
    "Отал (Othala) - Наследие": "https://placehold.co/800x800/1e293b/fbbf24.png?text=Othala",
    "Дагаз (Dagaz) - Прорыв": "https://placehold.co/800x800/1e293b/fbbf24.png?text=Dagaz"
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

# 🔥 3-СТУПЕНЧАТАЯ ЗАЩИТА СКАЧИВАНИЯ КАРТИНОК
def download_image_robust(ai_url, fallback_url):
    # Притворяемся настоящим браузером, чтобы нас не блокировали
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'image/avif,image/webp,image/apng,image/*,*/*;q=0.8'
    }

    # Шаг 1: Пытаемся скачать напрямую (самый быстрый и надежный путь)
    try:
        print("⏳ Шаг 1: Прямое скачивание ИИ-картинки...", flush=True)
        resp = requests.get(ai_url, headers=headers, timeout=25)
        if resp.status_code == 200 and len(resp.content) > 1000:
            print("✅ ИИ-картинка скачана напрямую!", flush=True)
            return resp.content
    except Exception as e:
        print(f"⚠️ Прямое скачивание не удалось: {e}", flush=True)

    # Шаг 2: Пробуем через новый прокси-сервер (если шаг 1 заблокирован)
    try:
        print("⏳ Шаг 2: Скачивание ИИ-картинки через прокси...", flush=True)
        proxy_url = f"https://api.codetabs.com/v1/proxy?quest={urllib.parse.quote(ai_url)}"
        resp = requests.get(proxy_url, headers=headers, timeout=30)
        if resp.status_code == 200 and len(resp.content) > 1000:
            print("✅ ИИ-картинка успешно пропущена через прокси!", flush=True)
            return resp.content
    except Exception as e:
        print(f"⚠️ Прокси не справился: {e}", flush=True)

    # Шаг 3: Используем нашу стильную заглушку (если ИИ совсем умер)
    try:
        print("⏳ Шаг 3: Качаю резервную картинку...", flush=True)
        resp = requests.get(fallback_url, headers=headers, timeout=10)
        if resp.status_code == 200:
            print("✅ Резервная картинка скачана!", flush=True)
            return resp.content
    except Exception as e:
        print(f"❌ Полный провал скачивания: {e}", flush=True)
        
    return None

def generate_and_send_saga(target_chat_id=None):
    try:
        topic, src = get_topic()
        targets = [target_chat_id] if target_chat_id else subscribers
        
        try: 
            img_p = clean_text(model.generate_content(f"Translate to English and give 3-4 keywords for image search, NO extra text: {topic}").text)
        except: 
            img_p = "epic viking norse mythology cinematic"
            
        ai_url = f"https://image.pollinations.ai/prompt/{urllib.parse.quote(img_p)}?width=1024&height=1024&nologo=true&seed={random.randint(1, 100000)}"
        fallback_url = f"https://loremflickr.com/800/800/viking,epic?random={random.randint(1, 10000)}"

        # Вызываем нашу железобетонную функцию скачивания
        img_data = download_image_robust(ai_url, fallback_url)

        v_text = clean_text(model.generate_content(f"{SYSTEM_PROMPT_VOICE} {topic}").text)
        fname = f"v_{random.randint(1,999)}.mp3"
        asyncio.run(generate_voice_file(v_text, fname))
        story = clean_text(model.generate_content(f"{SYSTEM_PROMPT_TEXT} {topic}").text)

        for chat_id in targets:
            try:
                bot.send_message(chat_id, f"{random.choice(START_PHRASES)}\n\n{src}\nТема: {topic}")
                
                if img_data:
                    photo = io.BytesIO(img_data)
                    photo.name = 'saga.jpg'
                    bot.send_photo(chat_id, photo)
                else:
                    bot.send_message(chat_id, "*(Картинка потерялась в тумане, но сага осталась...)*", parse_mode="Markdown")
                
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
        
        # Специальный короткий промпт для нейросети, чтобы она не путалась
        img_prompt = f"magic glowing rune stone {rune_name_eng} viking cinematic 8k"
        ai_url = f"https://image.pollinations.ai/prompt/{urllib.parse.quote(img_prompt)}?width=1024&height=1024&nologo=true&seed={random.randint(1, 100000)}"
        fallback_url = RUNE_FALLBACKS[rune]
        
        # Вызываем нашу железобетонную функцию скачивания
        img_data = download_image_robust(ai_url, fallback_url)
        
        targets = [target_chat_id] if target_chat_id else subscribers
        for user_id in targets:
            try:
                if not target_chat_id: bot.send_message(user_id, "🌅 Солнце встало. Твоя Руна Дня:")

                if img_data:
                    photo = io.BytesIO(img_data)
                    photo.name = 'rune.jpg'
                    bot.send_photo(user_id, photo, caption=f"*{rune}*", parse_mode="Markdown")
                else:
                    bot.send_message(user_id, f"*(Изображение утеряно в веках)*\n*{rune}*", parse_mode="Markdown")
                    
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
