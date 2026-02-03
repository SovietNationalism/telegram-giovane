import json
import logging
import os
import re
from datetime import datetime
from typing import Dict, Optional

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN non trovato!")

DATA_PATH = os.getenv("ORDERS_DATA_PATH", "orders.json")

ORDER_FIELDS = {
    "username_telegram": "Username Telegram",
    "prodotti": "Prodotto/i",
    "quantita": "Quantità",
    "metodo_pagamento": "Metodo di pagamento scelto",
    "nome_cognome": "Nome e Cognome",
    "contatto": "Num di Tel / Email",
    "indirizzo": "Indirizzo o punto di ritiro",
    "note": "Eventuali note o richieste speciali",
}

LABEL_MAP = {
    "username": "username_telegram",
    "username telegram": "username_telegram",
    "prodotto": "prodotti",
    "prodotto/i": "prodotti",
    "prodotti": "prodotti",
    "quantita": "quantita",
    "quantità": "quantita",
    "metodo di pagamento scelto": "metodo_pagamento",
    "metodo di pagamento": "metodo_pagamento",
    "nome e cognome": "nome_cognome",
    "num di tel / email": "contatto",
    "numero di tel / email": "contatto",
    "contatto": "contatto",
    "indirizzo o punto di ritiro": "indirizzo",
    "indirizzo": "indirizzo",
    "eventuali note o richieste speciali": "note",
    "note": "note",
}


def normalize_label(label: str) -> str:
    cleaned = label.strip().lower()
    cleaned = cleaned.replace("•", "").replace(":", "")
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned


def load_orders() -> Dict[str, dict]:
    if not os.path.exists(DATA_PATH):
        return {"next_id": 1, "orders": []}
    with open(DATA_PATH, "r", encoding="utf-8") as handle:
        return json.load(handle)


def save_orders(data: Dict[str, dict]) -> None:
    with open(DATA_PATH, "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)


def parse_order_message(text: str) -> Optional[Dict[str, str]]:
    if "INFORMAZIONI ORDINE" not in text.upper():
        return None

    parsed: Dict[str, str] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or "informazioni" in line.lower():
            continue
        if line.startswith("•"):
            line = line.lstrip("•").strip()
        if not line:
            continue

        match = re.match(r"(.+?)\s+(.+)", line)
        if not match:
            continue
        label, value = match.groups()
        normalized = normalize_label(label)
        field_key = LABEL_MAP.get(normalized)
        if field_key:
            parsed[field_key] = value.strip()

    if not parsed:
        return None
    return parsed


def format_order(order: Dict[str, str]) -> str:
    lines = [f"🧾 Ordine #{order['id']}"]
    for field_key, label in ORDER_FIELDS.items():
        value = order.get(field_key, "-")
        lines.append(f"• {label}: {value}")
    lines.append(f"📅 Inserito: {order['created_at']}")
    return "\n".join(lines)


def build_orders_keyboard(order_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("🗑️ Elimina", callback_data=f"delete:{order_id}")]]
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = (
        "Ciao! Inviami un messaggio con il form ordine compilato e lo salverò.\n\n"
        "Comandi disponibili:\n"
        "• /orders - mostra tutti gli ordini\n"
        "• /order <id> - mostra un ordine specifico\n"
        "• /edit_order <id> <campo> <valore> - modifica un campo\n"
        "• /delete_order <id> - elimina un ordine\n"
        "• /fields - elenco campi modificabili"
    )
    await update.message.reply_text(message)


async def list_orders(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    data = load_orders()
    orders = data.get("orders", [])
    if not orders:
        await update.message.reply_text("Nessun ordine salvato al momento.")
        return
    lines = [f"{order['id']}. {order.get('prodotti', '-')}" for order in orders]
    await update.message.reply_text("\n".join(lines))


async def show_order(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("Uso: /order <id>")
        return
    order_id = context.args[0]
    data = load_orders()
    order = next((item for item in data.get("orders", []) if str(item["id"]) == order_id), None)
    if not order:
        await update.message.reply_text("Ordine non trovato.")
        return
    await update.message.reply_text(format_order(order), reply_markup=build_orders_keyboard(order["id"]))


async def list_fields(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    lines = [f"{key}: {label}" for key, label in ORDER_FIELDS.items()]
    await update.message.reply_text("Campi modificabili:\n" + "\n".join(lines))


async def edit_order(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if len(context.args) < 3:
        await update.message.reply_text("Uso: /edit_order <id> <campo> <valore>")
        return
    order_id, field_key = context.args[0], context.args[1]
    if field_key not in ORDER_FIELDS:
        await update.message.reply_text("Campo non valido. Usa /fields per l'elenco.")
        return
    value = " ".join(context.args[2:]).strip()
    data = load_orders()
    orders = data.get("orders", [])
    for order in orders:
        if str(order["id"]) == order_id:
            order[field_key] = value
            save_orders(data)
            await update.message.reply_text("✅ Ordine aggiornato.\n\n" + format_order(order))
            return
    await update.message.reply_text("Ordine non trovato.")


async def delete_order(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("Uso: /delete_order <id>")
        return
    order_id = context.args[0]
    data = load_orders()
    orders = data.get("orders", [])
    new_orders = [order for order in orders if str(order["id"]) != order_id]
    if len(new_orders) == len(orders):
        await update.message.reply_text("Ordine non trovato.")
        return
    data["orders"] = new_orders
    save_orders(data)
    await update.message.reply_text("✅ Ordine eliminato.")


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    if not query.data:
        return
    action, order_id = query.data.split(":", 1)
    if action != "delete":
        return
    data = load_orders()
    orders = data.get("orders", [])
    new_orders = [order for order in orders if str(order["id"]) != order_id]
    if len(new_orders) == len(orders):
        await query.edit_message_text("Ordine non trovato.")
        return
    data["orders"] = new_orders
    save_orders(data)
    await query.edit_message_text("✅ Ordine eliminato.")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text or ""
    parsed = parse_order_message(text)
    if not parsed:
        return

    data = load_orders()
    order_id = data.get("next_id", 1)
    order = {
        "id": order_id,
        "created_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
        "raw_text": text,
        "sender": update.message.from_user.username or update.message.from_user.full_name,
    }
    order.update(parsed)
    data.setdefault("orders", []).append(order)
    data["next_id"] = order_id + 1
    save_orders(data)

    await update.message.reply_text(
        "✅ Ordine salvato!\n\n" + format_order(order),
        reply_markup=build_orders_keyboard(order_id),
    )


def main() -> None:
    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("orders", list_orders))
    application.add_handler(CommandHandler("order", show_order))
    application.add_handler(CommandHandler("fields", list_fields))
    application.add_handler(CommandHandler("edit_order", edit_order))
    application.add_handler(CommandHandler("delete_order", delete_order))
    application.add_handler(CallbackQueryHandler(handle_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    application.run_polling()


if __name__ == "__main__":
    main()
