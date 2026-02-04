import csv
import json
import logging
import os
import re
import tempfile
from datetime import date, datetime
from typing import Dict, Iterable, Optional, Tuple

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

DEFAULT_DATA_DIR = os.getenv("ORDERS_DATA_DIR", "data")
DATA_PATH = os.getenv("ORDERS_DATA_PATH", os.path.join(DEFAULT_DATA_DIR, "orders.json"))

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

REQUIRED_FIELDS = (
    "username_telegram",
    "prodotti",
    "quantita",
    "metodo_pagamento",
    "nome_cognome",
    "contatto",
    "indirizzo",
)

DATE_LINE_REGEX = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")

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
    data_dir = os.path.dirname(DATA_PATH)
    if data_dir:
        os.makedirs(data_dir, exist_ok=True)
    with open(DATA_PATH, "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)


def split_order_blocks(text: str) -> list[str]:
    parts = re.split(r"^\s*---\s*$", text, flags=re.MULTILINE)
    return [part.strip() for part in parts if part.strip()]


def parse_order_message(text: str) -> Tuple[Optional[Dict[str, str]], Optional[str]]:
    parsed: Dict[str, str] = {}
    date_override: Optional[str] = None
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
        date_match = DATE_LINE_REGEX.search(line)
        if date_match and date_override is None and line.replace(":", "").strip() == date_match.group(1):
            date_override = date_match.group(1)
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
        return None, date_override
    return parsed, date_override


def build_template_message() -> str:
    lines = ["Formato consigliato:"]
    for key, label in ORDER_FIELDS.items():
        lines.append(f"• {label}: ...")
    lines.append("• 2026-02-04 (opzionale per data ordine)")
    return "\n".join(lines)


def get_missing_fields(parsed: Dict[str, str]) -> list[str]:
    return [field for field in REQUIRED_FIELDS if not parsed.get(field)]


def parse_date(value: str) -> Optional[date]:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def parse_created_at(value: str) -> Optional[date]:
    for fmt in ("%Y-%m-%d %H:%M UTC", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


def extract_list_options(args: list[str]) -> Tuple[Optional[str], Optional[bool], Optional[date], Optional[date]]:
    query_parts: list[str] = []
    ready_filter: Optional[bool] = None
    from_date: Optional[date] = None
    to_date: Optional[date] = None
    index = 0
    while index < len(args):
        arg = args[index]
        if arg == "--ready":
            ready_filter = True
        elif arg == "--pending":
            ready_filter = False
        elif arg == "--from" and index + 1 < len(args):
            parsed = parse_date(args[index + 1])
            if parsed:
                from_date = parsed
            index += 1
        elif arg == "--to" and index + 1 < len(args):
            parsed = parse_date(args[index + 1])
            if parsed:
                to_date = parsed
            index += 1
        else:
            query_parts.append(arg)
        index += 1
    query = " ".join(query_parts).strip() or None
    return query, ready_filter, from_date, to_date


def filter_orders(
    orders: Iterable[Dict[str, str]],
    query: Optional[str],
    ready_filter: Optional[bool],
    from_date: Optional[date],
    to_date: Optional[date],
) -> list[Dict[str, str]]:
    filtered: list[Dict[str, str]] = []
    for order in orders:
        if ready_filter is not None and bool(order.get("ready")) != ready_filter:
            continue
        created_date = parse_created_at(order.get("created_at", ""))
        if from_date and created_date and created_date < from_date:
            continue
        if to_date and created_date and created_date > to_date:
            continue
        if query:
            lowered = query.lower()
            username = (order.get("username_telegram") or order.get("sender") or "").lower()
            prodotti = (order.get("prodotti") or "").lower()
            status = "ready" if order.get("ready") else "pending"
            if lowered not in username and lowered not in prodotti and lowered not in status:
                continue
        filtered.append(order)
    return filtered


def build_value_suggestions(field_key: str, orders: Iterable[Dict[str, str]], limit: int = 3) -> list[str]:
    seen = []
    for order in orders:
        value = order.get(field_key)
        if not value:
            continue
        if value in seen:
            continue
        seen.append(value)
        if len(seen) >= limit:
            break
    return seen


def format_order(order: Dict[str, str]) -> str:
    lines = [f"🧾 Ordine #{order['id']}"]
    for field_key, label in ORDER_FIELDS.items():
        value = order.get(field_key, "-")
        lines.append(f"• {label}: {value}")
    lines.append(f"📅 Inserito: {order['created_at']}")
    return "\n".join(lines)


def build_orders_keyboard(order_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✏️ Modifica", callback_data=f"edit_prompt:{order_id}"),
                InlineKeyboardButton("🗑️ Elimina", callback_data=f"delete:{order_id}"),
            ]
        ]
    )


def build_orders_list_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("Pronto", callback_data="ready_prompt")]]
    )


def build_edit_fields_keyboard(order_id: int) -> InlineKeyboardMarkup:
    rows = []
    for field_key, label in ORDER_FIELDS.items():
        rows.append([InlineKeyboardButton(label, callback_data=f"edit_field:{order_id}:{field_key}")])
    return InlineKeyboardMarkup(rows)


def build_missing_fields_keyboard(draft_id: int, missing_fields: list[str]) -> InlineKeyboardMarkup:
    rows = []
    for field_key in missing_fields:
        label = ORDER_FIELDS.get(field_key, field_key)
        rows.append([InlineKeyboardButton(label, callback_data=f"draft_field:{draft_id}:{field_key}")])
    return InlineKeyboardMarkup(rows)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = (
        "Ciao! Inviami un messaggio con il form ordine compilato e lo salverò.\n\n"
        "Comandi disponibili:\n"
        "• /orders [query] [--ready|--pending] [--from YYYY-MM-DD] [--to YYYY-MM-DD]\n"
        "• /order <id> - mostra un ordine specifico\n"
        "• /edit_order <id> <campo> <valore> - modifica un campo\n"
        "• /search <termine> - cerca per username, prodotto o stato\n"
        "• /delete_order <id> - elimina un ordine\n"
        "• /fields [termine] - elenco campi con suggerimenti\n"
        "• /export [--ready|--pending] [--from YYYY-MM-DD] [--to YYYY-MM-DD] - esporta CSV"
    )
    await update.message.reply_text(message)


async def list_orders(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    data = load_orders()
    orders = data.get("orders", [])
    query, ready_filter, from_date, to_date = extract_list_options(context.args)
    orders = filter_orders(orders, query, ready_filter, from_date, to_date)
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
        indirizzo = order.get("indirizzo", "-")
        nome_cognome = order.get("nome_cognome", "-")
        contatto = order.get("contatto", "-")
        ready_marker = " | ✅" if order.get("ready") else ""
        details_line = " | ".join([indirizzo, nome_cognome, contatto])
        lines.append(
            f"{order['id']}. {username} | {product_summary}{ready_marker}\n{details_line}"
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
    data = load_orders()
    query = " ".join(context.args).strip().lower() if context.args else None
    lines = []
    for key, label in ORDER_FIELDS.items():
        if query and query not in key.lower() and query not in label.lower():
            continue
        suggestions = build_value_suggestions(key, data.get("orders", []))
        suggestion_text = f" (es: {', '.join(suggestions)})" if suggestions else ""
        lines.append(f"{key}: {label}{suggestion_text}")
    if not lines:
        await update.message.reply_text("Nessun campo trovato. Usa /fields senza filtri.")
        return
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


async def export_orders(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    data = load_orders()
    query, ready_filter, from_date, to_date = extract_list_options(context.args)
    orders = filter_orders(data.get("orders", []), query, ready_filter, from_date, to_date)
    if not orders:
        await update.message.reply_text("Nessun ordine da esportare con questi filtri.")
        return
    headers = ["id", "created_at", "ready", "sender", *ORDER_FIELDS.keys(), "raw_text"]
    with tempfile.NamedTemporaryFile("w+", suffix=".csv", delete=False, encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers)
        writer.writeheader()
        for order in orders:
            row = {key: order.get(key, "") for key in headers}
            row["ready"] = "yes" if order.get("ready") else "no"
            writer.writerow(row)
        temp_path = handle.name
    try:
        await update.message.reply_document(document=open(temp_path, "rb"), filename="orders_export.csv")
    finally:
        os.remove(temp_path)


async def search_orders(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("Uso: /search <termine>")
        return
    await list_orders(update, context)


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    if not query.data:
        return
    if query.data == "ready_prompt":
        context.user_data["awaiting_ready_order"] = True
        await query.message.reply_text("Inserisci il numero dell'ordine da segnare come pronto.")
        return
    action, payload = query.data.split(":", 1)
    if action == "delete":
        order_id = payload
        data = load_orders()
        orders = data.get("orders", [])
        new_orders = [order for order in orders if str(order["id"]) != order_id]
        if len(new_orders) == len(orders):
            await query.edit_message_text("Ordine non trovato.")
            return
        data["orders"] = new_orders
        save_orders(data)
        await query.edit_message_text("✅ Ordine eliminato.")
        return
    if action == "edit_prompt":
        await query.message.reply_text("Seleziona il campo da modificare:", reply_markup=build_edit_fields_keyboard(int(payload)))
        return
    if action == "edit_field":
        order_id, field_key = payload.split(":", 1)
        context.user_data["awaiting_edit"] = {"order_id": order_id, "field": field_key}
        data = load_orders()
        suggestions = build_value_suggestions(field_key, data.get("orders", []))
        suggestion_text = f"\nSuggerimenti: {', '.join(suggestions)}" if suggestions else ""
        await query.message.reply_text(
            f"Inserisci il nuovo valore per {ORDER_FIELDS.get(field_key, field_key)}.{suggestion_text}"
        )
        return
    if action == "draft_field":
        draft_id, field_key = payload.split(":", 1)
        context.user_data["awaiting_draft"] = {"draft_id": draft_id, "field": field_key}
        await query.message.reply_text(
            f"Inserisci il valore mancante per {ORDER_FIELDS.get(field_key, field_key)}."
        )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text or ""
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
                return
        await update.message.reply_text("Ordine non trovato.")
        return
    awaiting_edit = context.user_data.pop("awaiting_edit", None)
    if awaiting_edit:
        order_id = awaiting_edit["order_id"]
        field_key = awaiting_edit["field"]
        value = text.strip()
        if not value:
            await update.message.reply_text("Valore non valido.")
            return
        data = load_orders()
        orders = data.get("orders", [])
        for order in orders:
            if str(order["id"]) == str(order_id):
                order[field_key] = value
                save_orders(data)
                await update.message.reply_text("✅ Ordine aggiornato.\n\n" + format_order(order))
                return
        await update.message.reply_text("Ordine non trovato.")
        return
    awaiting_draft = context.user_data.pop("awaiting_draft", None)
    if awaiting_draft:
        draft_id = awaiting_draft["draft_id"]
        field_key = awaiting_draft["field"]
        draft_orders = context.user_data.get("draft_orders", {})
        draft = draft_orders.get(draft_id)
        if not draft:
            await update.message.reply_text("Bozza non trovata. Reinvia il form.")
            return
        draft["parsed"][field_key] = text.strip()
        missing = get_missing_fields(draft["parsed"])
        if missing:
            await update.message.reply_text(
                "Mancano ancora:\n" + "\n".join(f"• {ORDER_FIELDS.get(key, key)}" for key in missing),
                reply_markup=build_missing_fields_keyboard(int(draft_id), missing),
            )
            return
        data = load_orders()
        order_id = data.get("next_id", 1)
        created_at = draft.get("created_at") or datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
        order = {
            "id": order_id,
            "created_at": created_at,
            "raw_text": draft["raw_text"],
            "sender": draft["sender"],
        }
        order.update(draft["parsed"])
        if draft.get("put_date"):
            order["put_date"] = draft["put_date"]
        data.setdefault("orders", []).append(order)
        data["next_id"] = order_id + 1
        save_orders(data)
        draft_orders.pop(draft_id, None)
        await update.message.reply_text(
            "✅ Ordine salvato!\n\n" + format_order(order),
            reply_markup=build_orders_keyboard(order["id"]),
        )
        return
    blocks = split_order_blocks(text)
    parsed_blocks = []
    for block in blocks:
        parsed, date_override = parse_order_message(block)
        if parsed:
            parsed_blocks.append((block, parsed, date_override))
    if not parsed_blocks:
        return

    data = load_orders()
    new_orders = []
    draft_orders = context.user_data.setdefault("draft_orders", {})
    draft_counter = context.user_data.get("draft_counter", 1)
    for block, parsed, date_override in parsed_blocks:
        missing = get_missing_fields(parsed)
        created_at = (
            f"{date_override} 00:00 UTC" if date_override else datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
        )
        if missing:
            draft_id = str(draft_counter)
            draft_counter += 1
            draft_orders[draft_id] = {
                "parsed": parsed,
                "raw_text": block,
                "sender": update.message.from_user.username or update.message.from_user.full_name,
                "created_at": created_at,
                "put_date": date_override,
            }
            await update.message.reply_text(
                "⚠️ Ordine incompleto. Mancano:\n"
                + "\n".join(f"• {ORDER_FIELDS.get(key, key)}" for key in missing)
                + "\n\n"
                + build_template_message(),
                reply_markup=build_missing_fields_keyboard(int(draft_id), missing),
            )
            continue
        order_id = data.get("next_id", 1)
        order = {
            "id": order_id,
            "created_at": created_at,
            "raw_text": block,
            "sender": update.message.from_user.username or update.message.from_user.full_name,
        }
        order.update(parsed)
        if date_override:
            order["put_date"] = date_override
        data.setdefault("orders", []).append(order)
        data["next_id"] = order_id + 1
        new_orders.append(order)
    context.user_data["draft_counter"] = draft_counter
    save_orders(data)

    if not new_orders:
        return

    if len(new_orders) == 1:
        order = new_orders[0]
        await update.message.reply_text(
            "✅ Ordine salvato!\n\n" + format_order(order),
            reply_markup=build_orders_keyboard(order["id"]),
        )
        return

    message = "✅ Ordini salvati!\n\n" + "\n\n".join(
        format_order(order) for order in new_orders
    )
    await update.message.reply_text(message)


def main() -> None:
    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("orders", list_orders))
    application.add_handler(CommandHandler("order", show_order))
    application.add_handler(CommandHandler("fields", list_fields))
    application.add_handler(CommandHandler("edit_order", edit_order))
    application.add_handler(CommandHandler("delete_order", delete_order))
    application.add_handler(CommandHandler("export", export_orders))
    application.add_handler(CommandHandler("search", search_orders))
    application.add_handler(CallbackQueryHandler(handle_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    application.run_polling()


if __name__ == "__main__":
    main()
