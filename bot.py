import os
import json
import random
import traceback
import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.environ.get("TELEGRAM_TOKEN", "8648169248")
OWNER_ID = int(os.environ.get("OWNER_ID", "0"))
DATA_FILE = "data.json"

blackjack_games = {}
pending_duels = {}  # chat_id -> {user_id, name, bet}

# ---------- PERSISTENCIA ----------
def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            data = json.load(f)
        balances = {int(k): v for k, v in data.get("balances", {}).items()}
        names = data.get("names", {})
        names = {int(k): v for k, v in names.items()}
        return balances, names
    return {}, {}

def save_data():
    with open(DATA_FILE, "w") as f:
        json.dump({"balances": balances, "names": names}, f)

balances, names = load_data()

# ---------- HELPERS ----------
def get_balance(user_id):
    if user_id not in balances:
        balances[user_id] = 100
        save_data()
    return balances[user_id]

def save_name(user):
    if user.username:
        names[user.id] = f"@{user.username}"
    elif user.first_name:
        names[user.id] = user.first_name
    else:
        names[user.id] = str(user.id)
    save_data()

def get_name(user_id):
    return names.get(user_id, str(user_id))

# ---------- MY ID ----------
async def myid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    save_name(user)
    await update.message.reply_text(f"🪪 Tu ID es: `{user.id}`", parse_mode="Markdown")

# ---------- START ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    save_name(user)
    balance = get_balance(user.id)
    await update.message.reply_text(f"Bienvenido 🎰\nTienes {balance} monedas 💰")

# ---------- BALANCE ----------
async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    save_name(user)
    bal = get_balance(user.id)
    await update.message.reply_text(f"💰 Balance: {bal}")

# ---------- SLOTS ----------
async def slots(update: Update, context: ContextTypes.DEFAULT_TYPE):
    save_name(update.effective_user)
    user = update.effective_user.id

    bet = 10
    if context.args:
        try:
            bet = int(context.args[0])
        except ValueError:
            await update.message.reply_text("❌ La apuesta debe ser un número. Ejemplo: /slots 20")
            return
        if bet <= 0:
            await update.message.reply_text("❌ La apuesta debe ser mayor a 0.")
            return

    if get_balance(user) < bet:
        await update.message.reply_text(f"No tienes suficiente dinero 😢 (Balance: {balances[user]})")
        return

    symbols = ["🍒", "🍋", "🔔", "⭐", "💎", "🃏"]
    roll = [random.choice(symbols) for _ in range(3)]

    if roll[0] == roll[1] == roll[2]:
        win = bet * 5
        balances[user] += win
        outcome = f"🎉 ¡JACKPOT! +{win} 💰"
    elif roll[0] == roll[1] or roll[1] == roll[2]:
        win = bet * 2
        balances[user] += win
        outcome = f"🙂 ¡Par! +{win} 💰"
    else:
        balances[user] -= bet
        outcome = f"😢 Perdiste -{bet} 💰"

    save_data()

    machine = (
        f"🎰  S L O T S  🎰\n"
        f"╔═════════════╗\n"
        f"║ {roll[0]}  {roll[1]}  {roll[2]} ║\n"
        f"╚═════════════╝\n"
        f"💵 Apuesta: {bet}\n\n"
        f"{outcome}\n"
        f"💰 Balance: {balances[user]}"
    )
    await update.message.reply_text(machine)

# ---------- BLACKJACK ----------
def draw_card():
    return random.randint(1, 11)

def total(hand):
    return sum(hand)

def fmt_cards(hand):
    return "  ".join(f"[{c}]" for c in hand)

def bj_table(player, dealer, hide_dealer=True):
    dealer_row = f"[{dealer[0]}] [?]" if hide_dealer else fmt_cards(dealer)
    return (
        f"🃏  B L A C K J A C K  🃏\n"
        f"┌─────────────────────┐\n"
        f"│ 🤖 DEALER: {dealer_row:<11}│\n"
        f"│                     │\n"
        f"│ 🙋 TÚ:    {fmt_cards(player):<12}│\n"
        f"│    Total: {total(player):<11}│\n"
        f"└─────────────────────┘"
    )

async def blackjack(update: Update, context: ContextTypes.DEFAULT_TYPE):
    save_name(update.effective_user)
    user = update.effective_user.id

    bet = 10
    if context.args:
        try:
            bet = int(context.args[0])
        except ValueError:
            await update.message.reply_text("❌ La apuesta debe ser un número. Ejemplo: /blackjack 50")
            return
        if bet <= 0:
            await update.message.reply_text("❌ La apuesta debe ser mayor a 0.")
            return

    if get_balance(user) < bet:
        await update.message.reply_text(f"No tienes suficiente dinero 😢 (Balance: {balances[user]})")
        return

    player = [draw_card(), draw_card()]
    dealer = [draw_card(), draw_card()]

    blackjack_games[user] = {"player": player, "dealer": dealer, "bet": bet}

    msg = (
        f"{bj_table(player, dealer, hide_dealer=True)}\n"
        f"💵 Apuesta: {bet}\n\n"
        f"👉 /hit — Pedir carta\n"
        f"✋ /stand — Plantarse"
    )
    await update.message.reply_text(msg)

async def hit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    save_name(update.effective_user)
    user = update.effective_user.id
    game = blackjack_games.get(user)

    if not game:
        await update.message.reply_text("No tienes partida activa")
        return

    game["player"].append(draw_card())
    bet = game["bet"]

    if total(game["player"]) > 21:
        balances[user] -= bet
        blackjack_games.pop(user)
        save_data()
        msg = (
            f"{bj_table(game['player'], game['dealer'], hide_dealer=False)}\n"
            f"💵 Apuesta: {bet}\n\n"
            f"💥 ¡Te pasaste! Perdiste -{bet} 💰\n"
            f"💰 Balance: {balances[user]}"
        )
    else:
        msg = (
            f"{bj_table(game['player'], game['dealer'], hide_dealer=True)}\n"
            f"💵 Apuesta: {bet}\n\n"
            f"👉 /hit — Pedir carta\n"
            f"✋ /stand — Plantarse"
        )
    await update.message.reply_text(msg)

async def stand(update: Update, context: ContextTypes.DEFAULT_TYPE):
    save_name(update.effective_user)
    user = update.effective_user.id
    game = blackjack_games.get(user)

    if not game:
        await update.message.reply_text("No tienes partida activa")
        return

    dealer = game["dealer"]
    while total(dealer) < 17:
        dealer.append(draw_card())

    bet = game["bet"]
    player_total = total(game["player"])
    dealer_total = total(dealer)

    if dealer_total > 21 or player_total > dealer_total:
        balances[user] += bet * 2
        outcome = f"🎉 ¡Ganaste! +{bet * 2} 💰"
    elif player_total < dealer_total:
        balances[user] -= bet
        outcome = f"😢 Perdiste -{bet} 💰"
    else:
        outcome = "🤝 ¡Empate!"

    blackjack_games.pop(user)
    save_data()

    dealer_row = fmt_cards(dealer)
    msg = (
        f"🃏  B L A C K J A C K  🃏\n"
        f"┌─────────────────────┐\n"
        f"│ 🤖 DEALER: {dealer_row:<11}│\n"
        f"│    Total: {dealer_total:<11}│\n"
        f"│                     │\n"
        f"│ 🙋 TÚ:    {fmt_cards(game['player']):<12}│\n"
        f"│    Total: {player_total:<11}│\n"
        f"└─────────────────────┘\n"
        f"💵 Apuesta: {bet}\n\n"
        f"{outcome}\n"
        f"💰 Balance: {balances[user]}"
    )
    await update.message.reply_text(msg)

# ---------- RULETA ----------
RED_NUMBERS = {1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36}

def get_color(n):
    if n == 0:
        return "🟢", "verde"
    return ("🔴", "rojo") if n in RED_NUMBERS else ("⚫", "negro")

async def ruleta(update: Update, context: ContextTypes.DEFAULT_TYPE):
    save_name(update.effective_user)
    user = update.effective_user.id

    if len(context.args) < 2:
        await update.message.reply_text(
            "Uso: /ruleta <apuesta> <tipo>\n\n"
            "Tipos de apuesta:\n"
            "  🔴 rojo / ⚫ negro  → x2\n"
            "  par / impar         → x2\n"
            "  1-12 / 13-24 / 25-36 → x3\n"
            "  0–36 (número exacto) → x36\n\n"
            "Ejemplo: /ruleta 50 rojo\n"
            "Ejemplo: /ruleta 20 17"
        )
        return

    try:
        bet = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ La apuesta debe ser un número.")
        return

    if bet <= 0:
        await update.message.reply_text("❌ La apuesta debe ser mayor a 0.")
        return

    if get_balance(user) < bet:
        await update.message.reply_text(f"No tienes suficiente dinero 😢 (Balance: {balances[user]})")
        return

    tipo = context.args[1].lower()
    numero = random.randint(0, 36)
    emoji, color = get_color(numero)
    es_par = numero != 0 and numero % 2 == 0

    win_mult = 0
    if tipo == "rojo" and color == "rojo":
        win_mult = 2
    elif tipo == "negro" and color == "negro":
        win_mult = 2
    elif tipo == "par" and es_par:
        win_mult = 2
    elif tipo == "impar" and numero != 0 and not es_par:
        win_mult = 2
    elif tipo == "1-12" and 1 <= numero <= 12:
        win_mult = 3
    elif tipo == "13-24" and 13 <= numero <= 24:
        win_mult = 3
    elif tipo == "25-36" and 25 <= numero <= 36:
        win_mult = 3
    else:
        try:
            num_apuesta = int(tipo)
            if 0 <= num_apuesta <= 36 and num_apuesta == numero:
                win_mult = 36
        except ValueError:
            await update.message.reply_text("❌ Tipo de apuesta no válido. Escribe /ruleta para ver las opciones.")
            return

    par_str = "Par" if es_par else ("Impar" if numero != 0 else "—")
    docena = "1-12" if 1 <= numero <= 12 else ("13-24" if 13 <= numero <= 24 else ("25-36" if 25 <= numero <= 36 else "—"))

    if win_mult > 0:
        ganancia = bet * win_mult
        balances[user] += ganancia - bet
        outcome = f"🎉 ¡Ganaste! +{ganancia - bet} 💰"
    else:
        balances[user] -= bet
        outcome = f"😢 Perdiste -{bet} 💰"

    save_data()

    await update.message.reply_text(
        f"🎡  R U L E T A  🎡\n"
        f"┌─────────────────────┐\n"
        f"│  Número:  {emoji} {numero:<10}│\n"
        f"│  Color:   {color:<11}│\n"
        f"│  Par/Imp: {par_str:<11}│\n"
        f"│  Docena:  {docena:<11}│\n"
        f"└─────────────────────┘\n"
        f"💵 Apuesta: {bet} → {tipo}\n\n"
        f"{outcome}\n"
        f"💰 Balance: {balances[user]}"
    )

# ---------- DUELO ----------
CARD_NAMES = {1: "A", 11: "J", 12: "Q", 13: "K"}

def draw_duel_card():
    val = random.randint(1, 13)
    return val, CARD_NAMES.get(val, str(val))

async def duel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    save_name(update.effective_user)
    user = update.effective_user
    chat_id = update.effective_chat.id

    if chat_id in pending_duels:
        challenger = pending_duels[chat_id]
        if challenger["user_id"] == user.id:
            await update.message.reply_text("⚔️ Ya tienes un duelo pendiente. Espera a que alguien lo acepte con /aceptar.")
        else:
            await update.message.reply_text(f"Ya hay un duelo abierto de {challenger['name']}. ¡Úsalo con /aceptar!")
        return

    if not context.args:
        await update.message.reply_text("Uso: /duel <cantidad>\nEjemplo: /duel 50")
        return

    try:
        bet = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ La cantidad debe ser un número.")
        return

    if bet <= 0:
        await update.message.reply_text("❌ La apuesta debe ser mayor a 0.")
        return

    if get_balance(user.id) < bet:
        await update.message.reply_text(f"No tienes suficiente dinero 😢 (Balance: {balances[user.id]})")
        return

    pending_duels[chat_id] = {"user_id": user.id, "name": get_name(user.id), "bet": bet}

    await update.message.reply_text(
        f"⚔️  D U E L O  ⚔️\n\n"
        f"{get_name(user.id)} lanza un reto de {bet} 💰\n\n"
        f"¿Quién se atreve? Usa /aceptar para enfrentarlo\n"
        f"(o /rechazar para cancelar el reto)"
    )

async def aceptar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    save_name(update.effective_user)
    user = update.effective_user
    chat_id = update.effective_chat.id

    if chat_id not in pending_duels:
        await update.message.reply_text("No hay ningún duelo pendiente. Crea uno con /duel <cantidad>")
        return

    duel_data = pending_duels[chat_id]

    if duel_data["user_id"] == user.id:
        await update.message.reply_text("No puedes aceptar tu propio duelo 😄")
        return

    bet = duel_data["bet"]
    challenger_id = duel_data["user_id"]
    challenger_name = duel_data["name"]
    rival_name = get_name(user.id)

    if get_balance(user.id) < bet:
        await update.message.reply_text(f"No tienes suficiente dinero para aceptar 😢 (Balance: {balances[user.id]})")
        return

    del pending_duels[chat_id]

    c_val, c_name = draw_duel_card()
    r_val, r_name = draw_duel_card()

    if c_val > r_val:
        balances[challenger_id] = get_balance(challenger_id) + bet
        balances[user.id] = get_balance(user.id) - bet
        outcome = f"🏆 ¡{challenger_name} gana! +{bet} 💰"
    elif r_val > c_val:
        balances[user.id] = get_balance(user.id) + bet
        balances[challenger_id] = get_balance(challenger_id) - bet
        outcome = f"🏆 ¡{rival_name} gana! +{bet} 💰"
    else:
        outcome = "🤝 ¡Empate! Nadie pierde nada."

    save_data()

    await update.message.reply_text(
        f"⚔️  D U E L O  ⚔️\n"
        f"┌─────────────────────┐\n"
        f"│ {challenger_name[:10]:<10} → [{c_name}]        │\n"
        f"│ {rival_name[:10]:<10} → [{r_name}]        │\n"
        f"└─────────────────────┘\n"
        f"💵 Apuesta: {bet}\n\n"
        f"{outcome}"
    )

async def rechazar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat_id = update.effective_chat.id

    if chat_id not in pending_duels:
        await update.message.reply_text("No hay ningún duelo pendiente.")
        return

    if pending_duels[chat_id]["user_id"] != user.id and user.id != OWNER_ID:
        await update.message.reply_text("Solo quien lanzó el reto puede cancelarlo.")
        return

    del pending_duels[chat_id]
    await update.message.reply_text("❌ Duelo cancelado.")

# ---------- RANKING ----------
async def ranking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not balances:
        await update.message.reply_text("No hay jugadores aún 🤷")
        return

    sorted_players = sorted(balances.items(), key=lambda x: x[1], reverse=True)

    lines = ["🏆 Ranking Global 🏆\n"]
    medals = ["🥇", "🥈", "🥉"]

    for i, (user_id, bal) in enumerate(sorted_players):
        medal = medals[i] if i < 3 else f"{i + 1}."
        name = get_name(user_id)
        lines.append(f"{medal} {name} — {bal} 💰")

    await update.message.reply_text("\n".join(lines))

# ---------- ADD BALANCE (solo owner) ----------
async def addbalance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user.id

    if user != OWNER_ID:
        await update.message.reply_text("⛔ No tienes permiso para usar este comando.")
        return

    if len(context.args) != 2:
        await update.message.reply_text("Uso: /addbalance <user_id> <cantidad>")
        return

    try:
        target_id = int(context.args[0])
        amount = int(context.args[1])
    except ValueError:
        await update.message.reply_text("❌ user_id y cantidad deben ser números.")
        return

    get_balance(target_id)
    balances[target_id] += amount
    save_data()
    await update.message.reply_text(
        f"✅ Se agregaron {amount} monedas al usuario {target_id}.\nNuevo balance: {balances[target_id]} 💰"
    )

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error("Exception while handling update:", exc_info=context.error)
    traceback.print_exc()

# ---------- MAIN ----------
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("myid", myid))
app.add_handler(CommandHandler("balance", balance))
app.add_handler(CommandHandler("slots", slots))
app.add_handler(CommandHandler("blackjack", blackjack))
app.add_handler(CommandHandler("hit", hit))
app.add_handler(CommandHandler("stand", stand))
app.add_handler(CommandHandler("ranking", ranking))
app.add_handler(CommandHandler("ruleta", ruleta))
app.add_handler(CommandHandler("duel", duel))
app.add_handler(CommandHandler("aceptar", aceptar))
app.add_handler(CommandHandler("rechazar", rechazar))
app.add_handler(CommandHandler("addbalance", addbalance))
app.add_error_handler(error_handler)

print("Bot corriendo...")
app.run_polling()