import os
import json
import random
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

TOKEN = os.getenv("TOKEN")

# ---------- BASE DE DATOS ----------
def load_users():
    try:
        with open("users.json", "r") as f:
            return json.load(f)
    except:
        return {}

def save_users(users):
    with open("users.json", "w") as f:
        json.dump(users, f)

# ---------- /start ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    users = load_users()

    if user_id not in users:
        users[user_id] = {"balance": 100}
        save_users(users)
        await update.message.reply_text("🎰 Bienvenido, recibes $100 para empezar")
    else:
        await update.message.reply_text("Ya estás registrado 👀")

# ---------- /balance ----------
async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    users = load_users()

    if user_id in users:
        money = users[user_id]["balance"]
        await update.message.reply_text(f"💰 Tienes ${money}")
    else:
        await update.message.reply_text("Usa /start primero")

# ---------- /slot ----------
async def slot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    users = load_users()

    if user_id not in users:
        await update.message.reply_text("Usa /start primero")
        return

    try:
        bet = int(context.args[0])
    except:
        await update.message.reply_text("Ejemplo: /slot 50")
        return

    if bet <= 0 or bet > users[user_id]["balance"]:
        await update.message.reply_text("Apuesta inválida")
        return

    symbols = ["🍒","🍋","🍉","⭐","💎"]
    roll = [random.choice(symbols) for _ in range(3)]

    result = " | ".join(roll)

    if roll[0] == roll[1] == roll[2]:
        win = bet * 5
    elif len(set(roll)) == 2:
        win = bet * 2
    else:
        win = -bet

    users[user_id]["balance"] += win
    save_users(users)

    await update.message.reply_text(f"🎰 {result}\nResultado: {win}$")

# ---------- /blackjack ----------
def draw_card():
    return random.randint(1,11)

async def blackjack(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    users = load_users()

    if user_id not in users:
        await update.message.reply_text("Usa /start primero")
        return

    try:
        bet = int(context.args[0])
    except:
        await update.message.reply_text("Ejemplo: /blackjack 100")
        return

    if bet <= 0 or bet > users[user_id]["balance"]:
        await update.message.reply_text("Apuesta inválida")
        return

    player = draw_card() + draw_card()
    dealer = draw_card() + draw_card()

    if player > 21:
        win = -bet
    elif dealer > 21 or player > dealer:
        win = bet
    elif player == dealer:
        win = 0
    else:
        win = -bet

    users[user_id]["balance"] += win
    save_users(users)

    await update.message.reply_text(
        f"🃏 Tú: {player} | Dealer: {dealer}\nResultado: {win}$"
    )

# ---------- /ranking ----------
async def ranking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    users = load_users()

    sorted_users = sorted(users.items(), key=lambda x: x[1]["balance"], reverse=True)

    text = "🏆 Ranking:\n"

    for i, (user_id, data) in enumerate(sorted_users[:10]):
        text += f"{i+1}. ${data['balance']}\n"

    await update.message.reply_text(text)

# ---------- BOT ----------
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("balance", balance))
app.add_handler(CommandHandler("slot", slot))
app.add_handler(CommandHandler("blackjack", blackjack))
app.add_handler(CommandHandler("ranking", ranking))

app.run_polling()