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
import cloudscraper
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

# Создаем хитрую заглушку, чтобы твой старый код продолжал работать без изменений!
# Инициализируем новый клиент Gemini
client = genai.Client(api_key=GEMINI_API_KEY)

# Создаем хитрую заглушку, чтобы твой старый код ниже работал без изменений
class ModelMock:
    def generate_content(self, prompt):
        class ResponseMock:
            def __init__(self, text):
                self.text = text
        res = client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
        return ResponseMock(res.text)

model = ModelMock()
bot = telebot.TeleBot(TELEGRAM_TOKEN)

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

RUNE_ACTION_PHRASES = [
    "🎲 Кости брошены на шкуру медведя...",
    "✋ Рука Одина тянется в мешок судеб...",
    "🌑 Камни шепчут во тьме...",
    "👁️ Гляди внимательно, воин, это твой знак...",
    "💨 Ветер перемен перевернул камень..."
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
SYSTEM_PROMPT_IMAGE = "Cinematic digital art, epic Norse mythology scene, dramatic lighting, 8k. Topic: "
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
    btn1 = types.KeyboardButton("📜 Расскажи Сагу")
    btn2 = types.KeyboardButton("ᛟ Вытянуть Руну") 
    btn3 = types.KeyboardButton("🔮 Спросить Одина")
    markup.add(btn1, btn2, btn3)
    return markup

def get_pollinations_url(prompt):
    encoded_prompt = urllib.parse.quote(prompt)
    seed = random.randint(1, 100000)
    return f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1024&height=1024&nologo=true&seed={seed}"

def download_image(url):
    try:
        print(f"⏳ Пробую пробить Cloudflare через cloudscraper...", flush=True)
        
        # Создаем "хитрый" клиент, который имитирует реальный Chrome
        scraper = cloudscraper.create_scraper(browser={
            'browser': 'chrome',
            'platform': 'windows',
            'desktop': True
        })
        
        resp = scraper.get(url, timeout=60)
        
        # Проверяем, что файл скачался и это не кусок текста с ошибкой
        if resp.status_code == 200 and len(resp.content) > 1000:
            print("✅ Защита пробита! Картинка у нас.", flush=True)
            return resp.content
        else:
            print(f"❌ Ошибка HTTP: {resp.status_code}. Ответ: {resp.text[:100]}", flush=True)
            
    except Exception as e:
        print(f"❌ Критическая ошибка скачивания: {e}", flush=True)
        
    return None

def generate_and_send_saga(target_chat_id=None):
    try:
        topic, src = get_topic()
        targets = [target_chat_id] if target_chat_id else subscribers
        
        try: img_p = model.generate_content(f"SD prompt for: {topic}").text
        except: img_p = SYSTEM_PROMPT_IMAGE + topic
        
        image_url = get_pollinations_url(img_p)
        img_data = download_image(image_url)

        v_text = clean_text(model.generate_content(f"{SYSTEM_PROMPT_VOICE} {topic}").text)
        fname = f"v_{random.randint(1,999)}.mp3"
        asyncio.run(generate_voice_file(v_text, fname))
        
        story = clean_text(model.generate_content(f"{SYSTEM_PROMPT_TEXT} {topic}").text)

        for chat_id in targets:
            try:
                bot.send_message(chat_id, f"{random.choice(START_PHRASES)}\n\n{src}\nТема: {topic}")
                
                # 🔥 МАГИЧЕСКОЕ ИСПРАВЛЕНИЕ ТУТ
                if img_data:
                    photo = io.BytesIO(img_data)
                    photo.name = 'image.jpg' # Телеграм теперь поймет, что это картинка!
                    bot.send_photo(chat_id, photo)
                else:
                    try:
                        bot.send_photo(chat_id, image_url)
                    except: pass
                
                with open(fname, 'rb') as a: bot.send_voice(chat_id, a)
                bot.send_chat_action(chat_id, 'typing')
                smart_split_and_send(chat_id, story)
            except Exception as e:
                print(f"Ошибка отправки юзеру: {e}")

        if os.path.exists(fname): os.remove(fname)

    except Exception as e: 
        print(f"CRITICAL ERROR SAGA: {e}")

def generate_and_send_rune(target_chat_id=None):
    try:
        if target_chat_id: 
            bot.send_message(target_chat_id, random.choice(RUNE_ACTION_PHRASES))
            bot.send_chat_action(target_chat_id, 'typing')

        rune = random.choice(RUNES)
        prompt = SYSTEM_PROMPT_RUNE.format(rune=rune)
        prediction = clean_text(model.generate_content(prompt).text)
        
        rune_name_eng = rune.split('(')[1].split(')')[0]
        img_prompt = f"Close up shot of an old dirty viking hand holding a dark runestone, glowing blue symbol of rune {rune_name_eng} carved on stone, cinematic lighting, photorealistic, 8k, bokeh background"
        
        image_url = get_pollinations_url(img_prompt)
        img_data = download_image(image_url)
        
        targets = [target_chat_id] if target_chat_id else subscribers
        
        for user_id in targets:
            try:
                if not target_chat_id:
                    bot.send_message(user_id, "🌅 Солнце встало. Твоя Руна Дня:")

                # 🔥 МАГИЧЕСКОЕ ИСПРАВЛЕНИЕ ТУТ
                if img_data:
                    photo = io.BytesIO(img_data)
                    photo.name = 'rune.jpg' # Принудительно говорим Телеграму, что это файл JPG
                    bot.send_photo(user_id, photo, caption=f"*{rune}*", parse_mode="Markdown")
                else:
                    try:
                        bot.send_photo(user_id, image_url, caption=f"*{rune}*", parse_mode="Markdown")
                    except:
                        bot.send_message(user_id, f"*{rune}*", parse_mode="Markdown")
                    
                bot.send_message(user_id, f"👁️ *Толкование:*\n\n{prediction}", parse_mode="Markdown")
            except Exception as e:
                print(f"Ошибка отправки руны: {e}")

    except Exception as e: 
        print(f"CRITICAL ERROR RUNE: {e}")

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

# Render автоматически выдает эту переменную окружения (например, https://norsebot.onrender.com)
WEBHOOK_URL = os.environ.get("RENDER_EXTERNAL_URL") 

# Сюда Telegram будет присылать сообщения
@server.route(f"/{TELEGRAM_TOKEN}", methods=['POST'])
def receive_update():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return "!", 200
    return "Not JSON", 403

# Заглушка для Render, чтобы он видел, что сайт работает
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
    # 1. Снимаем старые настройки (очищаем кэш Telegram)
    try: bot.remove_webhook()
    except: pass
    time.sleep(1)

    # 2. Устанавливаем Webhook, если мы на сервере Render
    if WEBHOOK_URL:
        bot.set_webhook(url=f"{WEBHOOK_URL}/{TELEGRAM_TOKEN}")
        print(f"✅ Вебхук успешно установлен на: {WEBHOOK_URL}")
    else:
        # Если ты запустишь бота у себя на компе, он по-прежнему будет работать через Polling
        print("⚠️ RENDER_EXTERNAL_URL не найден. Запускаю локальный Polling...")
        threading.Thread(target=bot.infinity_polling, daemon=True).start()

    # 3. Запускаем планировщик в фоне
    threading.Thread(target=scheduler, daemon=True).start()

    # 4. Запускаем сам веб-сервер (теперь он главный процесс)
    port = int(os.environ.get("PORT", 10000))
    server.run(host="0.0.0.0", port=port)
