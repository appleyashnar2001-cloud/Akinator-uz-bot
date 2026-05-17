import os
import threading
from flask import Flask
import telebot
from telebot import types
import akinator
from deep_translator import GoogleTranslator

# Render uchun Web Server (Bot 24/7 yoniq turishi uchun)
app = Flask('')

@app.route('/')
def home():
    return "Akinator Bot Yoniq!"

def run_server():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

# Botni sozlash
TOKEN = os.environ.get("BOT_TOKEN")
bot = telebot.TeleBot(TOKEN)

# Tarjimon funksiyasi (Inglizchadan O'zbekchaga va teskari)
def to_uzbek(text):
    try:
        return GoogleTranslator(source='en', target='uz').translate(text)
    except:
        return text

# Foydalanuvchilar o'yin poygasi (Sessiyalarni saqlash uchun)
user_games = {}

# Akinator javob tugmalari
def get_akinator_keyboard():
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("Ha ✅", callback_data="aki_0"),
        types.InlineKeyboardButton("Yo'q ❌", callback_data="aki_1"),
        types.InlineKeyboardButton("Bilmayman 🤷‍♂️", callback_data="aki_2"),
        types.InlineKeyboardButton("Ehtimol bor 🤔", callback_data="aki_3"),
        types.InlineKeyboardButton("Ehtimol yo'q 🧐", callback_data="aki_4"),
        types.InlineKeyboardButton("⬅️ Orqaga (O'chirish)", callback_data="aki_back")
    )
    return markup

# /start buyrug'i
@bot.message_handler(commands=['start'])
def start_cmd(message):
    welcome_text = (
        "🔮 **Xush kelibsiz! Men Akinatorman!**\n\n"
        "Siz bitta real yoki xayoliy personajni (masalan: Alisher Navoiy, Ronaldo, o'zingiz yoki biror multfilm qahramonini) o'ylang. "
        "Men sizga savollar beraman va uni topishga harakat qilaman!\n\n"
        "Tayyor bo'lsangiz, pastdagi tugmani bosing 👇"
    )
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("🔮 O'yinni boshlash")
    bot.send_message(message.chat.id, welcome_text, parse_mode="Markdown", reply_markup=markup)

# O'yinni boshlash matni kelganda
@bot.message_handler(func=lambda m: m.text == "🔮 O'yinni boshlash")
def start_game(message):
    user_id = message.from_user.id
    bot.send_message(message.chat.id, "🧠 Akinator miyasini ishga tushirmoqda, biroz kuting...")
    
    try:
        # Yangi Akinator o'yinini boshlash
        aki = akinator.Akinator()
        q = aki.start_game(language="en") # inglizcha boshlaymiz, keyin tarjima qilamiz
        
        # Foydalanuvchi sessiyasini saqlash
        user_games[user_id] = aki
        
        # Savolni o'zbekchaga o'girish
        uz_question = to_uzbek(q)
        
        bot.send_message(
            message.chat.id, 
            f"❓ **1-savol:**\n\n{uz_question}", 
            parse_mode="Markdown", 
            reply_markup=get_akinator_keyboard()
        )
    except Exception as e:
        bot.send_message(message.chat.id, "❌ O'yinni boshlashda xatolik yuz berdi. Qaytadan urinib ko'ring.")

# Akinator tugmalari bosilganda (Callback query)
@bot.callback_query_handler(func=lambda call: call.data.startswith("aki_"))
def process_akinator(call):
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    message_id = call.message.message_id
    
    # Agar foydalanuvchi o'yinni boshlamagan bo'lsa
    if user_id not in user_games:
        bot.answer_callback_query(call.id, "Iltimos, o'yinni qaytadan boshlang!", show_alert=True)
        return

    aki = user_games[user_id]
    action = call.data.split("_")[1]

    try:
        bot.answer_callback_query(call.id, "O'ylanmoqda... 🤔")

        # Orqaga qaytish bosilganda
        if action == "back":
            try:
                q = aki.back()
                uz_question = to_uzbek(q)
                bot.edit_message_text(
                    chat_id=chat_id, message_id=message_id,
                    text=f"❓ **Savolga qaytdik:**\n\n{uz_question}",
                    parse_mode="Markdown", reply_markup=get_akinator_keyboard()
                )
            except akinator.CantGoBackAnyFurther:
                bot.answer_callback_query(call.id, "Bundan ortiq orqaga qaytib bo'lmaydi!", show_alert=True)
            return

        # Aks holda javobni yuborish va keyingi savolga o'tish
        # Akinator 80% dan yuqori aniqlikda javob topsa, o'yinni to'xtatadi
        if aki.progression <= 80:
            q = aki.answer(int(action))
            uz_question = to_uzbek(q)
            
            bot.edit_message_text(
                chat_id=chat_id, message_id=message_id,
                text=f"❓ **Keyingi savol:**\n\n{uz_question}",
                parse_mode="Markdown", reply_markup=get_akinator_keyboard()
            )
        else:
            # Personajni taxmin qilish qismi
            aki.win()
            guess = aki.first_guess
            
            uz_name = to_uzbek(guess['name'])
            uz_desc = to_uzbek(guess['description'])
            
            result_text = (
                "🎉 **Men topdim!**\n\n"
                f"👤 **Siz o'ylagan personaj:** {uz_name}\n"
                f"📝 **Ta'rif:** {uz_desc}\n\n"
                "Rasm yuklanmoqda..."
            )
            bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=result_text, parse_mode="Markdown")
            
            # Personaj rasmini yuborish
            try:
                bot.send_photo(chat_id, guess['absolute_picture_path'], caption=f"Ushbu personajmidi: {uz_name}? ✨")
            except:
                bot.send_message(chat_id, f"Rasm yuklab bo'lmadi, lekin siz o'ylagan odam: **{uz_name}** edi! 🥷", parse_mode="Markdown")
            
            # Sessiyani tozalash
            del user_games[user_id]

    except Exception as e:
        bot.send_message(chat_id, "😔 O'yin davomida texnik uzilish bo'ldi. Qaytadan urinib ko'ring.")
        if user_id in user_games:
            del user_games[user_id]

if __name__ == "__main__":
    t = threading.Thread(target=run_server)
    t.start()
    print("Akinator bot ishga tushdi...")
    bot.infinity_polling()
