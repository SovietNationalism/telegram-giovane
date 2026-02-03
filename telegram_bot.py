import re
import logging
import json
import os
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN non trovato!")

orders = []

def load_orders():
    try:
        with open('orders.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return []

def save_orders():
    with open('orders.json', 'w', encoding='utf-8') as f:
        json.dump(orders, f, indent=2, ensure_ascii=False)

orders = load_orders()

def create_order_row(order):
    if not order['products']:
        return f"{order['cliente']} | --vuoto-- | {order['prezzo']}€"
    
    products_str = ', '.join([f"{p['qty']} {p['product']}" for p in order['products'][:3]])
    if len(order['products']) > 3:
        products_str += f" +{len(order['products'])-3}"
    
    status = "✅✅" if order.get('pacco_pronto') and order.get('pacco_consegnato') else "✅❌" if order.get('pacco_pronto') else "❌❌"
    return f"{order['cliente']} | {products_str} | {order['prezzo']}€ | {status}"

def parse_flexible_order(text):
    text_lower = text.lower()
    
    # Username
    username_match = re.search(r'@[\\w]+', text)
    username = username_match.group(0) if username_match else "unknown"
    
    # Price - AGGIORNATO
    price_match = re.search(r'(\d{1,4}(?:\.\d+)?)\s*€?', text_lower)
    price = price_match.group(1) + "€" if price_match else "??€"
    
    # Products grams MIGLIORATO - trova TUTTI i grammi
    gram_matches = re.findall(r'(\d+(?:\.\d+)?)\s*(g|gr|grammi?|frozen|hash)', text_lower, re.IGNORECASE)
    for qty, product_hint in gram_matches:
        product_name = product_hint.lower()
        if 'frozen' in product_name:
            product_name = 'frozen'
        elif 'hash' in product_name:
            product_name = 'hash'
        products.append({'qty': f"{qty}g", 'product': product_name})

    # Numeri grandi senza unità (190 hash → 190g hash)
    big_qty_matches = re.findall(r'(\d{2,})\s*(hash|frozen|weed|erba|calispain|dry|fumo|filtrato|og|cali)', text_lower)
    for qty, prod in big_qty_matches:
        products.append({'qty': f"{qty}g", 'product': prod})

    # Specific items (IL TUO CODICE FUNZIONANTE)
    specifics = {
        'dabwoods': re.findall(r'(\\d*)\\s*dabwoods?', text_lower),
        'packwoods': re.findall(r'(\\d*)\\s*packwoods?', text_lower),
        'backwoods': re.findall(r'(\\d*)\\s*backwoods?', text_lower),
        'lean': re.findall(r'(\\d*)\\s*lean', text_lower),
        'lsd': re.findall(r'(\\d*)\\s*lsd', text_lower),
        'oxy': re.findall(r'(\\d*)\\s*oxy', text_lower),
        'vape': re.findall(r'(\\d*)\\s*vape', text_lower),
        'pen': re.findall(r'(\\d*)\\s*pen', text_lower)
    }
    for item, qtys in specifics.items():
        for qty in qtys:
            if qty:  # Solo se trova quantità
                products.append({'qty': qty, 'product': item})
    
    # Name, phone, email, address (IL TUO CODICE FUNZIONANTE)
    name_match = re.search(r'([A-Z][a-z]+(?:\\s[A-Z][a-z]+)+)', text)
    name = name_match.group(1) if name_match else ""
    
    phone_match = re.search(r'(?:tel:)?\s*(\d{10,11})|3[89]\d{8}', text)
    phone = phone_match.group(0) if phone_match else ""
    
    email_match = re.search(r'[\\w\\.-]+@[\\w\\.-]+', text)
    email = email_match.group(0) if email_match else ""
    
    address_match = re.search(r'(via|viale|corso|regione|locker|inpost).*?\\d+', text, re.IGNORECASE)
    address = address_match.group(0)[:80] if address_match else ""
    
    note = f"{name}, {phone}, {email}, {address}".strip(", ")
    
    return {
        'cliente': username,
        'products': products[:6],
        'prezzo': price,
        'note': note,
        'pacco_pronto': False,
        'pacco_consegnato': False,
        'data': datetime.now().isoformat()
    }

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await show_orders_page(update, context, 0)

async def show_orders_page(update: Update, context: ContextTypes.DEFAULT_TYPE, page=0):
    open_orders = [o for o in orders if not (o.get('pacco_pronto') and o.get('pacco_consegnato'))]
    
    text = f"📋 **ORDINI APERTI** ({len(open_orders)})\n\n"
    keyboard = []
    
    if not open_orders:
        text += "✅ Nessun ordine aperto!"
        keyboard = [[InlineKeyboardButton("➕ Nuovo ordine", callback_data="add")]]
    else:
        per_page = 6
        total_pages = (len(open_orders) + per_page - 1) // per_page
        start_idx = page * per_page
        end_idx = min(start_idx + per_page, len(open_orders))
        
        for i in range(start_idx, end_idx):
            order = open_orders[i]
            text += f"{i+1}. {create_order_row(order)}\n"
            keyboard.append([
                InlineKeyboardButton("✏️ Modifica", callback_data=f"edit_{i}"),
                InlineKeyboardButton("✅ Pronto", callback_data=f"toggle_{i}")
            ])
        
        # Paginazione
        nav_row = []
        if page > 0:
            nav_row.append(InlineKeyboardButton("⬅️", callback_data=f"p_{page-1}"))
        if end_idx < len(open_orders):
            nav_row.append(InlineKeyboardButton("➡️", callback_data=f"p_{page+1}"))
        if nav_row:
            keyboard.append(nav_row)
        
        keyboard.extend([
            [InlineKeyboardButton("➕ Nuovo", callback_data="add")],
            [InlineKeyboardButton("📊 Stats", callback_data="stats")]
        ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    try:
        if update.callback_query:
            await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
        else:
            await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Errore pagina: {e}")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data.startswith("p_"):
        page = int(data[2:])
        await show_orders_page(query, context, page)
    elif data == "add":
        await query.edit_message_text(
            "📥 **Invia il messaggio dell'ordine**\n\n"
            "🧠 Parsing automatico rileva:\n"
            "• `@username`\n"
            "• Prezzi €\n"
            "• Grammi (5g filtrato)\n"
            "• Dabwoods/lean/backwoods\n"
            "• Nome/telefono/indirizzo",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Lista", callback_data="list")]])
        )
        context.user_data['waiting_order'] = True
    elif data == "stats":
        total = len(orders)
        open_count = len([o for o in orders if not (o.get('pacco_pronto') and o.get('pacco_consegnato'))])
        revenue = sum(float(o['prezzo'].replace('€','').replace(',','.')) for o in orders if o['prezzo'] != '??€')
        text = f"""📊 **STATISTICHE**

• Ordini totali: {total}
• Aperti: {open_count}
• Incasso: {revenue:,.0f}€"""
        await query.edit_message_text(text, parse_mode='Markdown')
    elif data == "list":
        await show_orders_page(query, context, 0)
    elif data.startswith("edit_"):
        idx = int(data.split("_")[1])
        if 0 <= idx < len(orders):
            order = orders[idx]
            text = f"✏️ **EDIT {order['cliente']}** | {create_order_row(order)}\n\n"
            text += "Invia il **NUOVO MESSAGGIO COMPLETO** per aggiornare tutto:"
            keyboard = [[InlineKeyboardButton("🗑 Elimina", callback_data=f"delete_{idx}")]]
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
            context.user_data['editing_idx'] = idx
    elif data.startswith("toggle_"):
        idx = int(data.split("_")[1])
        if 0 <= idx < len(orders):
            order = orders[idx]
            if not order.get('pacco_pronto'):
                order['pacco_pronto'] = True
            elif not order.get('pacco_consegnato'):
                order['pacco_consegnato'] = True
            save_orders()
        await show_orders_page(query, context, 0)
    elif data.startswith("delete_"):
        idx = int(data.split("_")[1])
        if 0 <= idx < len(orders):
            del orders[idx]
            save_orders()
        await show_orders_page(query, context, 0)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    
    # Editing
    if 'editing_idx' in context.user_data:
        idx = context.user_data['editing_idx']
        parsed = parse_flexible_order(text)
        orders[idx] = parsed
        save_orders()
        await update.message.reply_text(f"✅ Modificato!\n{create_order_row(parsed)}")
        context.user_data.pop('editing_idx')
        return

    # Editing - SOLO se in modalità editing
    if context.user_data.get('editing_idx') is not None:
        idx = context.user_data['editing_idx']
        new_parsed = parse_flexible_order(text)  # ← RILEGGE TUTTO
        orders[idx] = new_parsed
        save_orders()
        await update.message.reply_text(
            f"✅ **AGGIORNATO!**\n\n{create_order_row(new_parsed)}\n/start",
            parse_mode='Markdown'
        )
        context.user_data.pop('editing_idx')
        return
    
    # New order
    if context.user_data.get('waiting_order'):
        parsed = parse_flexible_order(text)
        orders.append(parsed)
        save_orders()
        preview = create_order_row(parsed)
        await update.message.reply_text(
            f"✅ **Aggiunto!**\n\n{preview}\n\nNote: {parsed['note']}\n\n/start",
            parse_mode='Markdown'
        )
        context.user_data['waiting_order'] = False
        return

    # Auto-detect order-like messages - PIÙ LARGHE
        order_keywords = ['g', 'gr', 'grammi', 'hash', 'frozen', 'dabwood', 'lean', 'filtr', 'og', 'cali']
        if '€' in text_lower and any(kw in text_lower for kw in order_keywords):
            parsed = parse_flexible_order(text)
            preview = create_order_row(parsed)
            await update.message.reply_text(
                f"🤖 **Rilevato ordine:**\n{preview}\n\n"
                f"`SI` per confermare\n"
                f"`NO` per ignorare\n"
                f"Oppure invia testo corretto",
                parse_mode='Markdown'
            )
            context.user_data['pending_order'] = parsed
            return

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("🚀 Bot avviato!")
    app.run_polling()

if __name__ == '__main__':
    main()
