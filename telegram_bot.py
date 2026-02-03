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
        with open('orders.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return []

def save_orders():
    with open('orders.json', 'w') as f:
        json.dump(orders, f, indent=2)

orders = load_orders()

def create_order_row(order):
    products = ', '.join([f"{p['qty']} {p['product']}" for p in order['products']])
    status = "✅✅" if order.get('pacco_pronto') and order.get('pacco_consegnato') else "✅❌" if order.get('pacco_pronto') else "❌❌"
    return f"{order['cliente']} | {products[:30]}... | {order['prezzo']}€ | {status}"

def parse_flexible_order(text):
    text_lower = text.lower()
    
    # Username
    username_match = re.search(r'@[\w]+', text)
    username = username_match.group(0) if username_match else "unknown"
    
    # Price
    price_match = re.search(r'(\d+(?:\.\d+)?)\s*€?', text_lower)
    price = price_match.group(1) + "€" if price_match else "??€"
    
    # Products grams
    gram_matches = re.findall(r'(\d+(?:\.\d+)?)\s*(g|grammi?|gr|ml)', text_lower)
    products = []
    for qty, unit in gram_matches:
        product_match = re.search(r'(filtrato|hash|dry|cali|og|lsd|oxy|filtered|drysift|spain)', text_lower)
        product_name = product_match.group(1) if product_match else 'unknown'
        products.append({'qty': f"{qty}{unit}", 'product': product_name})
    
    # Specific items
    specifics = {
        'dabwoods': re.findall(r'(\d*)\s*dabwoods?', text_lower),
        'packwoods': re.findall(r'(\d*)\s*packwoods?', text_lower),
        'backwoods': re.findall(r'(\d*)\s*backwoods?', text_lower),
        'lean': re.findall(r'(\d*)\s*lean', text_lower),
        'lsd': re.findall(r'(\d*)\s*lsd', text_lower),
        'oxy': re.findall(r'(\d*)\s*oxy', text_lower),
        'vape': re.findall(r'(\d*)\s*vape', text_lower),
        'pen': re.findall(r'(\d*)\s*pen', text_lower)
    }
    for item, qtys in specifics.items():
        for qty in qtys:
            products.append({'qty': qty or '1', 'product': item})
    
    # Name, phone, email, address
    name_match = re.search(r'([A-Z][a-z]+(?:\s[A-Z][a-z]+)+)', text)
    name = name_match.group(1) if name_match else ""
    
    phone_match = re.search(r'\d{3}\s?\d{3,7}\d{4}|\+39\d{9,10}', text)
    phone = phone_match.group(0) if phone_match else ""
    
    email_match = re.search(r'[\w\.-]+@[\w\.-]+', text)
    email = email_match.group(0) if email_match else ""
    
    address_match = re.search(r'(via|viale|corso|regione|locker|inpost).*?\d+', text, re.IGNORECASE)
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
    
    if not open_orders:
        text = "✅ **Nessun ordine aperto!**"
        keyboard = [[InlineKeyboardButton("➕ Nuovo", callback_data="add")]]
    else:
        per_page = 8
        total_pages = (len(open_orders) + per_page - 1) // per_page
        start_idx = page * per_page
        page_orders = open_orders[start_idx:start_idx + per_page]
        
        text = f"📋 **ORDINI APERTI** ({len(open_orders)}) - Pg {page+1}/{total_pages}\n\n"
        for i, order in enumerate(page_orders, start_idx+1):
            text += f"{i}. {create_order_row(order)}\n"
        
        keyboard = []
        if page > 0:
            keyboard.append(InlineKeyboardButton("⬅️", callback_data=f"p_{page-1}"))
        if page < total_pages - 1:
            keyboard.append(InlineKeyboardButton("➡️", callback_data=f"p_{page+1}"))
        keyboard.extend([
            [InlineKeyboardButton("➕ Nuovo", callback_data="add")],
            [InlineKeyboardButton("📊 Stats", callback_data="stats")]
        ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    else:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data.startswith("p_"):
        page = int(query.data[2:])
        await show_orders_page(query, context, page)
    elif query.data == "add":
        await query.edit_message_text(
            "📥 **Invia il messaggio dell'ordine**\n\n"
            "Rilevo automaticamente @username, prezzi €, grammi, nomi, indirizzi!",
            parse_mode='Markdown'
        )
        context.user_data['waiting_order'] = True
    elif query.data == "stats":
        total = len(orders)
        open_o = len([o for o in orders if not (o.get('pacco_pronto') and o.get('pacco_consegnato'))])
        revenue = sum(float(o['prezzo'].replace('€','')) for o in orders)
        text = f"📊 **Stats**\n\n• Totali: {total}\n• Aperti: {open_o}\n• Incasso: {revenue:.0f}€"
        await query.edit_message_text(text, parse_mode='Markdown')
    elif query.data.startswith("toggle_"):
        idx = int(query.data.split("_")[1])
        if 0 <= idx < len(orders):
            order = orders[idx]
            if not order.get('pacco_pronto'):
                order['pacco_pronto'] = True
            elif not order.get('pacco_consegnato'):
                order['pacco_consegnato'] = True
            save_orders()
        await show_orders_page(query, context, 0)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    
    if context.user_data.get('waiting_order'):
        parsed = parse_flexible_order(text)
        orders.append(parsed)
        save_orders()
        
        await update.message.reply_text(
            f"✅ **Aggiunto!**\n\n{create_order_row(parsed)}\n"
            f"**Note:** {parsed['note']}\n\n/start per lista",
            parse_mode='Markdown'
        )
        context.user_data['waiting_order'] = False
        return
    
    # Auto-detect order-like messages
    text_lower = text.lower()
    if any(x in text_lower for x in ['€', '@']) and any(x in text_lower for x in ['g', 'dabwood', 'lean', 'filtr']):
        parsed = parse_flexible_order(text)
        await update.message.reply_text(
            f"🤖 **Rilevato ordine:**\n{create_order_row(parsed)}\n\n"
            f"`SI` per aggiungere, `NO` per ignorare",
            parse_mode='Markdown'
        )
        context.user_data['pending_order'] = parsed

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling()

if __name__ == '__main__':
    main()
