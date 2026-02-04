import json
import logging
import os
import re
import urllib.error
import urllib.request
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
    parsed: Dict[str, str] = {}
    in_shipping_section = False
    in_order_section = False
    email_regex = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.IGNORECASE)
    phone_regex = re.compile(r"\+?\d[\d\s\-().]{5,}\d")
    quantity_regex = re.compile(r"\b\d+(?:[.,]\d+)?\s*(g|kg|mg|ml|l|pz|pezzi|x|oz)\b", re.IGNORECASE)
    currency_regex = re.compile(r"[$€]|eur|euro", re.IGNORECASE)
    address_keywords = (
        "via",
        "viale",
        "corso",
        "piazza",
        "vicolo",
        "strada",
        "piazzale",
        "punto di ritiro",
        "ritiro",
        "locker",
        "inpost",
    )
    payment_keywords = (
        "bonifico",
        "paypal",
        "contanti",
        "carta",
        "postepay",
        "ricarica",
        "revolut",
        "crypto",
        "bitcoin",
        "btc",
        "usdt",
    )

    def clean_unlabeled(value: str) -> str:
        return value.lstrip("•").strip()

    def looks_like_address(value: str) -> bool:
        lowered = value.lower()
        if any(keyword in lowered for keyword in address_keywords):
            return True
        return bool(re.search(r"\d", value))

    def looks_like_quantity(value: str) -> bool:
        if quantity_regex.search(value):
            return True
        return bool(re.fullmatch(r"\d+(?:[.,]\d+)?", value.strip()))

    def looks_like_payment(value: str) -> bool:
        lowered = value.lower()
        if any(keyword in lowered for keyword in payment_keywords):
            return True
        return bool(currency_regex.search(value))

    label_patterns = [
        (
            label,
            LABEL_MAP.get(normalize_label(label)),
            re.compile(rf"^\s*•?\s*{re.escape(label)}\s*:?\s*(.*)$", re.IGNORECASE),
        )
        for label in sorted(LABEL_MAP.keys(), key=len, reverse=True)
    ]
    lines = text.splitlines()
    for index, raw_line in enumerate(lines):
        line = raw_line.strip()
        if not line:
            continue
        if "informazioni spedizione" in line.lower():
            in_shipping_section = True
            in_order_section = False
            continue
        if "informazioni ordine" in line.lower():
            in_order_section = True
            in_shipping_section = False
            continue
        if "informazioni" in line.lower():
            continue
        if line.startswith("@") and "username_telegram" not in parsed:
            parsed["username_telegram"] = line
            continue
        for label, field_key, pattern in label_patterns:
            if not field_key:
                continue
            match = pattern.match(line)
            if not match:
                continue
            value = match.group(1).strip()
            if not value:
                for next_line in lines[index + 1 :]:
                    next_value = next_line.strip()
                    if not next_value or "informazioni" in next_value.lower():
                        continue
                    value = next_value
                    break
            if value:
                parsed[field_key] = value
            break
        else:
            if in_shipping_section:
                unlabeled_value = clean_unlabeled(line)
                if not unlabeled_value:
                    continue
                if "contatto" not in parsed and (
                    email_regex.search(unlabeled_value) or phone_regex.search(unlabeled_value)
                ):
                    parsed["contatto"] = unlabeled_value
                    continue
                if "indirizzo" not in parsed and looks_like_address(unlabeled_value):
                    parsed["indirizzo"] = unlabeled_value
                    continue
                if "nome_cognome" not in parsed:
                    parsed["nome_cognome"] = unlabeled_value
                continue
            if not in_order_section:
                continue
            unlabeled_value = clean_unlabeled(line)
            if not unlabeled_value:
                continue
            if "metodo_pagamento" not in parsed and looks_like_payment(unlabeled_value):
                parsed["metodo_pagamento"] = unlabeled_value
                continue
            if "quantita" not in parsed and looks_like_quantity(unlabeled_value):
                parsed["quantita"] = unlabeled_value
                continue
            if "prodotti" not in parsed:
                parsed["prodotti"] = unlabeled_value

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


def build_orders_list_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("Pronto", callback_data="ready_prompt")]]
    )


def extract_inpost_tracking_number(text: str) -> Optional[str]:
    match = re.fullmatch(r"\s*(\d{20,24})\s*", text)
    if not match:
        return None
    return match.group(1)


def fetch_inpost_tracking(tracking_number: str) -> Optional[Dict[str, str]]:
    url = f"https://api-shipx-pl.easypack24.net/v1/tracking/{tracking_number}"
    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            payload = json.load(response)
    except (urllib.error.URLError, json.JSONDecodeError):
        return None

    if not isinstance(payload, dict):
        return None
    details = payload.get("tracking_details") or []
    latest_detail = details[-1] if isinstance(details, list) and details else {}
    status = (
        payload.get("status")
        or latest_detail.get("status")
        or latest_detail.get("description")
        or "Stato non disponibile"
    )
    location = (
        latest_detail.get("location")
        or latest_detail.get("facility")
        or latest_detail.get("place")
        or payload.get("origin")
        or "Posizione non disponibile"
    )
    return {"status": status, "location": location}


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
    lines = []
    for order in orders:
        username = order.get("username_telegram") or order.get("sender") or "-"
        if username != "-" and not username.startswith("@"):
            username = f"@{username}"
        prodotti = order.get("prodotti", "-")
        quantita = order.get("quantita", "-")
        product_summary = prodotti if quantita == "-" else f"{prodotti} ({quantita})"
        ready_marker = " | ✅" if order.get("ready") else ""
        tracking_number = order.get("tracking_number")
        tracking_marker = f" | {tracking_number}" if tracking_number else ""
        lines.append(
            f"{order['id']}. {username} | {product_summary}{ready_marker}{tracking_marker}"
        )
    await update.message.reply_text("\n".join(lines), reply_markup=build_orders_list_keyboard())


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
    if query.data == "ready_prompt":
        context.user_data["awaiting_ready_order"] = True
        await query.message.reply_text("Inserisci il numero dell'ordine da segnare come pronto.")
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
    if context.user_data.pop("awaiting_tracking_number", False):
        order_id = context.user_data.pop("tracking_order_id", None)
        if not order_id:
            await update.message.reply_text("Ordine non trovato per il tracking.")
            return
        response = text.strip()
        if response.lower() in {"no", "n", "skip", "salta"}:
            await update.message.reply_text("Tracking saltato.")
            return
        data = load_orders()
        orders = data.get("orders", [])
        for order in orders:
            if str(order["id"]) == str(order_id):
                order["tracking_number"] = response
                save_orders(data)
                await update.message.reply_text(
                    f"✅ Tracking aggiunto all'ordine #{order_id}."
                )
                return
        await update.message.reply_text("Ordine non trovato.")
        return
    if context.user_data.pop("awaiting_ready_order", False):
        order_id = text.strip()
        if not order_id.isdigit():
            await update.message.reply_text("Inserisci un numero ordine valido.")
            return
        data = load_orders()
        orders = data.get("orders", [])
        for order in orders:
            if str(order["id"]) == order_id:
                order["ready"] = True
                save_orders(data)
                await update.message.reply_text(f"✅ Ordine #{order_id} segnato come pronto.")
                context.user_data["awaiting_tracking_number"] = True
                context.user_data["tracking_order_id"] = order_id
                await update.message.reply_text(
                    "Inserisci il numero di tracking (oppure rispondi No per saltare)."
                )
                return
        await update.message.reply_text("Ordine non trovato.")
        return
    tracking_number = extract_inpost_tracking_number(text)
    if tracking_number:
        info = fetch_inpost_tracking(tracking_number)
        if not info:
            await update.message.reply_text(
                "Non riesco a recuperare i dati InPost al momento. Riprova più tardi."
            )
            return
        await update.message.reply_text(
            "📦 InPost tracking:\n"
            f"• Numero: {tracking_number}\n"
            f"• Stato: {info['status']}\n"
            f"• Posizione: {info['location']}"
        )
        return
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
