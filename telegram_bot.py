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

def parse_flexible_order(text):
    """Parse ANY order format automatically"""
    text = text.lower()
    
    # Extract username (@username pattern)
    username_match = re.search(r'@[\w]+', text)
    username = username_match.group(0) if username_match else "unknown"
    
    # Extract price (€ numbers)
    price_match = re.search(r'(\d+(?:\.\d+)?)\s*€?', text)
    price = price_match.group(1) + "€" if price_match else "??€"
    
    # Extract products (grams, dabwoods, lean, etc.)
    products = []
    
    # Grams pattern: 5g, 10 g, 20g filtrato, etc.
    gram_matches = re.findall(r'(\d+(?:\.\d+)?)\s*(g|grammi?|gr|ml)', text)
    for qty, unit in gram_matches:
        product = re.search(r'(filtrato|hash|dry|cali|og|lsd|oxy|filtered|drysift)', text)
        product_name = product.group(1) if product else 'unknown'
        products.append({'qty': f"{qty}{unit}", 'product': product_name})
    
    # Specific products: dabwoods, packwoods, backwoods, lean, etc.
    specific = []
    for item in ['dabwoods', 'packwoods', 'backwoods', 'lean', 'lsd', 'oxy', 'vape', 'pen']:
        if item in text:
            qty_match = re.search(rf'(\d+)\s*{item}', text)
            qty = qty_match.group(1) if qty_match else '1'
            products.append({'qty': qty, 'product': item})
    
    # Cartine/elements/backwoods packs
    if any(word in text for word in ['cartine', 'elements', 'backwoods', 'blunt']):
        qty_match = re.search(r'(\d+)\s*(cartine|elements|backwoods|blunt)', text)
        if qty_match:
            products.append({'qty': qty_match.group(1), 'product': qty_match.group(2)})
    
    # Shipping info (names, emails, phones, addresses)
    name_match = re.search(r'([A-Z][a-z]+\s+[A-Z][a-z]+)', text)
    name = name_match.group(1) if name_match else "unknown"
    
    phone_match = re.search(r'(\d{3}\s?\d{3,7}\d{4})|(\+39\d{9,10})', text)
    phone = phone_match.group(0) if phone_match else ""
    
    email_match = re.search(r'[\w\.-]+@[\w\.-]+', text)
    email = email_match.group(0) if email_match else ""
    
    # Address keywords
    address_match = re.search(r'(via|viale|corso|regione|locker|inpost|tabacchino).*?(?:\d+,\s*)?\d+', text, re.IGNORECASE | re.DOTALL)
    address = address_match.group(0)[:100] if address_match else ""
    
    note = f"{name}, {phone}, {email}, {address}".strip(", ")
    
    return {
        'cliente': username,
        'products': products[:5],  # Limit to avoid spam
        'prezzo': price,
        'note': note,
        'pacco_pronto': False,
        'pacco_consegnato': False,
        'data': datetime.now().isoformat()
    }

# ... (load_orders, save_orders, create_order_row, show_orders_page IDENTICI dal codice precedente)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Parse ANY message format automatically"""
    if context.user_data.get('waiting_order', False):
        text = update.message.text
        
        parsed = parse_flexible_order(text)
        
        orders.append(parsed)
        save_orders()
        
        preview = create_order_row(parsed)
        await update.message.reply_text(
            f"✅ **Ordine estratto automaticamente!**\n\n"
            f"{preview}\n\n"
            f"**Note rilevate:** {parsed['note']}\n\n"
            f"✅ Corretto? Usa /start per lista.",
            parse_mode='Markdown'
        )
        context.user_data['waiting_order'] = False
        return
    
    # Auto-parse if looks like order (contains € or @username + grams)
    text = update.message.text.lower()
    if '€' in text or ('@' in text and any(g in text for g in ['g', 'dabwoods', 'lean'])):
        await update.message.reply_text(
            "🤖 Rilevato ordine! Confermo parsing...\n"
            "Rispondi SI per aggiungere, NO per ignorare."
        )
        context.user_data['auto_parse'] = parse_flexible_order(update.message.text)
        return

async def confirm_auto_parse(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get('auto_parse'):
        if 'si' in update.message.text.lower():
            parsed = context.user_data['auto_parse']
            orders.append(parsed)
            save_orders()
            await update.message.reply_text(f"✅ Aggiunto!\n{create_order_row(parsed)}")
        context.user_data.pop('auto_parse', None)

# Main app setup (IDENTICO)
def main():
    app = Application.builder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    app.run_polling()

if __name__ == '__main__':
    main()
