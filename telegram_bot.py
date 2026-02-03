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
        return f"{order['cliente']} | --vuoto-- | {order['prezzo']}"
    
    products_str = ', '.join([f"{p['qty']} {p['product']}" for p in order['products'][:3]])
    if len(order['products']) > 3:
        products_str += f" +{len(order['products'])-3}"
    
    status = "✅✅" if order.get('pacco_pronto') and order.get('pacco_consegnato') else "✅❌" if order.get('pacco_pronto') else "❌❌"
    return f"{order['cliente']} | {products_str} | {order['prezzo']} | {status}"  # ✅ Rimossi € extra

def parse_flexible_order(text):
    text_lower = text.lower()
    products = []
    
    # Username
    username_match = re.search(r'@[a-zA-Z0-9_]+', text)
    username = username_match.group(0) if username_match else "unknown"
    
    # Price - ULTIMO € trovato
    price_matches = re.findall(r'(\d{1,4}(?:[.,]\d+)?)\s*€', text_lower)
    price = price_matches[-1].replace(',', '.') + "€" if price_matches else "??€"
    
    # Products - tutti i pattern
    product_patterns = [
        r'(\d+(?:[.,]\d+)?)\s*(g|gr)\s+([a-z\s]+?)(?=\s+\d|g|€|$)',
        r'(\d+(?:[.,]\d+)?)\s+([a-z]+?)(?:\s+g|\s*€|$)',
        r'(\d{2,})\s*(hash|frozen|dry|weed|filtrato|og|cali)',
    ]
    
    for pattern in product_patterns:
        matches = re.findall(pattern, text_lower, re.IGNORECASE)
        for match in matches:
            qty = match[0].replace(',', '.')
            if len(match) == 3:
                product_name = match[2].strip().split()[0]
            else:
                product_name = match[1]
            products.append({'qty': f"{qty}g", 'product': product_name.lower()})
    
    # Rimuovi duplicati
    seen = set()
    unique_products = []
    for p in products:
        key = f"{p['qty']}_{p['product']}"
        if key not in seen:
            seen.add(key)
            unique_products.append(p)
    products = unique_products[:6]
    
    # Name, phone, email, address
    name_match = re.search(r'([A-Z][a-z]+(?:\s[A-Z][a-z]+)+)', text)
    name = name_match.group(1) if name_match else ""
    
    phone_match = re.search(r'[\+]?[3][89]\d{8,10}', text)
    phone = phone_match.group(0) if phone_match else ""
    
    email_match = re.search(r'[\w\.-]+@[\w\.-]+', text)
    email = email_match.group(0) if email_match else ""
    
    address_match = re.search(r'(via|viale|corso|locker|inpost|tabacchino).*?\d+', text, re.IGNORECASE)
    address = address_match.group(0)[:80] if address_match else ""
    
    note = f"{name}, {phone}, {email}, {address}".strip(", ")
    
    return {
        'cliente': username,
        'products': products,
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
    text_lower = text.lower()  # ✅ ADD THIS LINE
    
    # Editing
    if context.user_data.get('editing_idx') is not None:
        idx = context.user_data['editing_idx']
        parsed = parse_flexible_order(text)
        orders[idx] = parsed
        save_orders()
        await update.message.reply_text(f"✅ Modificato!\n{create_order_row(parsed)}")
        context.user_data.pop('editing_idx')
        return

    # New order
    if context.user_data.get('waiting_order'):
        parsed = parse_flexible_order(text)
        orders.append(parsed)
        save_orders()
        preview = create_order_row(parsed)
        status = "✅✅" if parsed.get('pacco_pronto') and parsed.get('pacco_consegnato') else "✅❌" if parsed.get('pacco_pronto') else "❌❌"
        await update.message.reply_text(
            f"✅ **Aggiunto!**\n\n{preview}\n\nNote: {parsed['note']}\n\n/start",
            parse_mode='Markdown'
        )

    # Auto-detect order-like messages - PIÙ LARGHE
    order_keywords = ['g', 'gr', 'ordinare', 'weed', 'ordine', 'grammi', 'hash', 'frozen', 'dabwood', 'lean', 'filtr', 'og', 'cali', 'dry']  # ✅ Added 'dry'
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
