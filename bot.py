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
LEONARDO_API_KEY = os.environ.get("LEONARDO_API_KEY")

# --- НАСТРОЙКИ ВРЕМЕНИ (UTC) ---
START_DATE = datetime(2026, 2, 10)  # Завтрашняя дата для старта с 1-й темы
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
generated_extra_topics = [] # Память для новых тем (антиплагиат)

subscribers = set()
if YOUR_CHAT_ID: subscribers.add(YOUR_CHAT_ID)

# --- ФРАЗЫ ---
WAIT_PHRASES = ["🦅 Хугин и Мунин полетели за историей...", "⏳ Норны сплетают нить, жди...", "🍺 Скальд наливает мёд поэзии..."]
START_PHRASES = ["⚔️ Руны легли верно!", "⚡ Тор ударил молотом!", "🐺 Фенрир завыл..."]
RUNE_ACTION_PHRASES = ["🎲 Кости брошены на шкуру медведя...", "✋ Рука Одина тянется...", "🌑 Камни шепчут во тьме..."]

# --- ПРОМПТЫ ---
SYSTEM_PROMPT_TEXT = """Ты — древний скальд. Напиши эпичную, атмосферную сагу (объем 8500 - 9000 знаков).
СТРОГИЕ ПРАВИЛА ОФОРМЛЕНИЯ:
1. НИКАКИХ служебных приписок в конце (не пиши количество символов!).
2. Текст должен быть разбит на короткие, удобные для чтения абзацы. Делай отступы (пустые строки) между смысловыми блоками.
3. Вступление пиши обычным текстом (не капсом!), атмосферно и загадочно.
4. Структура: Вступление -> 1. ЭТИМОЛОГИЯ -> 2. МИФ -> 3. СИМВОЛИЗМ. Заголовки разделов пиши ЗАГЛАВНЫМИ буквами с нумерацией.
5. Для перечислений используй обычный дефис "- ".
6. Цитаты богов/героев выделяй кавычками и пиши с новой строки.
7. Не используй символы разметки Markdown (*, #, _, **).
Тема: """
SYSTEM_PROMPT_VOICE = "Напиши атмосферное вступление (2-3 предложения) от лица старого викинга. На русском."
SYSTEM_PROMPT_ORACLE = "Ты — Один. Ответь мудро, кратко (4 предл.). СТРОГО НА РУССКОМ. Вопрос: "
SYSTEM_PROMPT_RUNE = "Ты — Шаман. Выпала Руна: {rune}. Дай краткое толкование. СТРОГО НА РУССКОМ."

# --- ФУНКЦИИ ---
def clean_text(text):
    # Мягкая очистка: убираем случайные остатки разметки, если ИИ вдруг ошибется
    return text.replace("**", "").replace("__", "").replace("##", "").replace("#", "").replace("*", "")

def smart_split_and_send(chat_id, text):
    chunk_size = 4000
    while text:
        if len(text) <= chunk_size:
            bot.send_message(chat_id, text)
            break
        split_at = text.rfind('\n', 0, chunk_size)
        if split_at == -1: split_at = chunk_size
        bot.send_message(chat_id, text[:split_at])
        text = text[split_at:].lstrip()
        time.sleep(1)

async def generate_voice_file(text, filename):
    communicate = edge_tts.Communicate(text, "ru-RU-DmitryNeural")
    await communicate.save(filename)

def get_topic():
    global generated_extra_topics
    try:
        with open('topics.txt', 'r', encoding='utf-8') as f:
            file_topics = [line.strip() for line in f if line.strip()]
    except Exception as e:
        print(f"❌ Ошибка чтения файла topics.txt: {e}")
        file_topics = []

    day_index = (datetime.now() - START_DATE).days

    if file_topics and day_index >= 0 and day_index < len(file_topics):
        topic = file_topics[day_index]
        return topic, "📜 Древние Свитки"
    else:
        print("⏳ Темы в файле закончились, придумываю новую уникальную...", flush=True)
        all_used_topics = file_topics + generated_extra_topics
        used_str = ", ".join(all_used_topics)
        
        prompt = f"Ты знаток мифов. Придумай ОДНУ редкую тему скандинавского фольклора. Только заголовок. Тема НЕ ДОЛЖНА быть похожа на эти: {used_str}"
        try:
            new_topic = model.generate_content(prompt).text.strip().replace('"', '').replace('.', '')
            if new_topic not in generated_extra_topics:
                generated_extra_topics.append(new_topic)
            return new_topic, "🔮 Руны AI (Новая Сага)"
        except Exception as e:
            print(f"❌ Ошибка генерации новой темы: {e}")
            return "Забытые боги Севера", "🔮 Запасная тема"

def get_main_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(types.KeyboardButton("📜 Расскажи Сагу"), types.KeyboardButton("ᛟ Вытянуть Руну"), types.KeyboardButton("🔮 Спросить Одина"))
    return markup

def get_ai_image_bytes(prompt, fallback_url):
    headers_req = {'User-Agent': 'Mozilla/5.0'}
    
    try:
        print("⏳ Шаг 1: Запрашиваю нейросеть через Leonardo.ai API...", flush=True)
        if not LEONARDO_API_KEY:
             raise ValueError("API-ключ Leonardo не найден в настройках.")

        url_generate = "https://cloud.leonardo.ai/api/rest/v1/generations"
        headers_leo = {
            "accept": "application/json",
            "content-type": "application/json",
            "authorization": f"Bearer {LEONARDO_API_KEY}"
        }
        
        payload = {"height": 512, "width": 512, "prompt": prompt, "num_images": 1}
        
        resp_gen = requests.post(url_generate, json=payload, headers=headers_leo, timeout=15)
        resp_gen.raise_for_status()
        generation_id = resp_gen.json().get("sdGenerationJob", {}).get("generationId")
        
        if generation_id:
             print("⏳ Шаг 2: Картинка рисуется, ожидаю результат...", flush=True)
             url_get = f"https://cloud.leonardo.ai/api/rest/v1/generations/{generation_id}"
             
             for _ in range(10): 
                 time.sleep(2)
                 res = requests.get(url_get, headers=headers_leo, timeout=10)
                 if res.status_code == 200:
                     data = res.json()
                     status = data.get("generations_by_pk", {}).get("status")
                     if status == "COMPLETE":
                         img_url = data["generations_by_pk"]["generated_images"][0]["url"]
                         img_resp = requests.get(img_url, headers=headers_req, timeout=20)
                         if img_resp.status_code == 200 and len(img_resp.content) > 1000:
                              print("✅ ИИ-картинка от Leonardo успешно скачана!", flush=True)
                              return img_resp.content
                         break 
             else:
                 print("⚠️ Превышено время ожидания готовности от Leonardo.", flush=True)
        else:
            print("⚠️ Leonardo не вернул ID генерации.", flush=True)

    except Exception as e:
        print(f"⚠️ План А (Leonardo) провалился: {e}", flush=True)

    try:
        print("⏳ Шаг 3: Качаю резервную картинку...", flush=True)
        resp = requests.get(fallback_url, headers=headers_req, timeout=10)
        if resp.status_code == 200:
            print("✅ Резервная картинка скачана!", flush=True)
            return resp.content
    except Exception as e:
        print(f"❌ Полный провал всех скачиваний: {e}", flush=True)
        
    return None

def generate_and_send_saga(target_chat_id=None):
    try:
        topic, src = get_topic()
        targets = [target_chat_id] if target_chat_id else subscribers
        
        try: 
            img_p = clean_text(model.generate_content(f"Translate to English, NO extra text: epic cinematic dark fantasy viking {topic}").text)
        except: 
            img_p = "epic viking norse mythology cinematic"
            
        fallback_url = f"https://placehold.co/800x800/1e293b/fbbf24.png?text=Viking+Saga"
        img_bytes = get_ai_image_bytes(img_p, fallback_url)

        v_text = clean_text(model.generate_content(f"{SYSTEM_PROMPT_VOICE} {topic}").text)
        fname = f"v_{random.randint(1,999)}.mp3"
        asyncio.run(generate_voice_file(v_text, fname))
        story = clean_text(model.generate_content(f"{SYSTEM_PROMPT_TEXT} {topic}").text)

        for chat_id in targets:
            try:
                bot.send_message(chat_id, f"{random.choice(START_PHRASES)}\n\n{src}\nТема: {topic}")
                
                if img_bytes:
                    photo = io.BytesIO(img_bytes)
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
        
        img_prompt = f"close up glowing magic rune stone {rune_name_eng} lying on dark earth, viking cinematic lighting 8k"
        fallback_url = RUNE_FALLBACKS[rune]
        img_bytes = get_ai_image_bytes(img_prompt, fallback_url)
        
        targets = [target_chat_id] if target_chat_id else subscribers
        for user_id in targets:
            try:
                if not target_chat_id: bot.send_message(user_id, "🌅 Солнце встало. Твоя Руна Дня:")

                if img_bytes:
                    photo = io.BytesIO(img_bytes)
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
        threading.Thread(target=bot.infinity_polling, daemon=True).start()

    threading.Thread(target=scheduler, daemon=True).start()
    port = int(os.environ.get("PORT", 10000))
    server.run(host="0.0.0.0", port=port)
