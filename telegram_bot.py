import re
import logging
import json
import os
from datetime import datetime
from typing import List, Dict, Any
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN non trovato!")

orders: List[Dict[str, Any]] = []

def load_orders() -> List[Dict[str, Any]]:
    try:
        with open('orders.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return []

def save_orders():
    with open('orders.json', 'w', encoding='utf-8') as f:
        json.dump(orders, f, indent=2, ensure_ascii=False)

orders = load_orders()

# Product keywords mapping for better detection
PRODUCT_KEYWORDS = {
    'dabwoods': ['dabwoods', 'dab wood', 'dab'],
    'packwoods': ['packwoods', 'pack wood'],
    'backwoods': ['backwoods', 'back wood'],
    'lean': ['lean', 'thc lean', 'syrup', 'boccetta'],
    'lsd': ['lsd', 'cartoncino', 'cartoncini'],
    'oxy': ['oxy', 'ossicodone', '40mg'],
    'vape': ['vape', 'svapo'],
    'pen': ['pen', 'penna'],
    'filtrato': ['filtrato', 'filtered', '120u', '120 micron'],
    'hash': ['hash', 'drysift', 'dry sift'],
    'cali': ['cali', 'caliusa', 'calispain'],
    'og': ['og kush', 'og', 'kush'],
    'jungle': ['jungle boys', 'jungle'],
    'elements': ['elements', 'cartine elements'],
    'backwoods_pack': ['backwoods confezione', 'backwoods pacchetti'],
    'blunt': ['blunt wraps', 'blunt', 'wraps']
}

def parse_flexible_order(text: str) -> Dict[str, Any]:
    """Advanced AI-like parsing for ANY order format"""
    original_text = text
    text_lower = text.lower().replace(',', '').replace(';', '').replace('•', '-')
    
    parsed = {
        'cliente': 'unknown',
        'products': [],
        'prezzo': '??€',
        'note': '',
        'pacco_pronto': False,
        'pacco_consegnato': False,
        'data': datetime.now().isoformat(),
        'raw_text': original_text  # Keep original for editing
    }
    
    # 1. USERNAME (@username)
    username_match = re.search(r'@[\w\d_]{3,32}', text)
    if username_match:
        parsed['cliente'] = username_match.group(0)
    
    # 2. PRICE (most robust - numbers near €, euro, euri)
    price_patterns = [
        r'(\d+(?:\.\d{1,2})?)\s*€?',
        r'(\d+(?:\.\d{1,2})?)\s*(?:euro|euri)',
        r'totale\s*:?\s*(\d+(?:\.\d{1,2})?)'
    ]
    for pattern in price_patterns:
        price_match = re.search(pattern, text_lower)
        if price_match:
            parsed['prezzo'] = f"{price_match.group(1)}€"
            break
    
    # 3. PRODUCTS - GRAMS (most important)
    gram_patterns = [
        r'(\d+(?:\.\d+)?)\s*(?:g|gr|gramm[io])\s*(?:di\s+)?([a-z\s]+?)(?=\s*(?:€|\d+g|$))',
        r'(\d+(?:\.\d+)?)[ggr]?\s*([a-z\s]+?)(?=\s*(?:€|\d+g|$))',
        r'(\d+(?:\.\d+)?)\s*(?:grammi?|gr?\.)?\s*([a-z]+)'
    ]
    for pattern in gram_patterns:
        matches = re.finditer(pattern, text_lower)
        for match in matches:
            qty = match.group(1)
            product_hint = match.group(2).strip()
            
            # Match to known products
            product_name = 'unknown'
            for known, keywords in PRODUCT_KEYWORDS.items():
                if any(kw in product_hint for kw in keywords):
                    product_name = known
                    break
            
            parsed['products'].append({
                'qty': qty + 'g',
                'product': product_name,
                'raw': product_hint
            })
    
    # 4. SPECIFIC PRODUCTS (dabwoods, lean, etc.)
    for product_name, keywords in PRODUCT_KEYWORDS.items():
        for keyword in keywords:
            if keyword in text_lower:
                qty_matches = re.findall(r'(\d+)\s*' + re.escape(keyword), text_lower)
                qty = qty_matches[0] if qty_matches else '1'
                parsed['products'].append({
                    'qty': qty,
                    'product': product_name,
                    'raw': keyword
                })
                break  # One per product type
    
    # 5. SHIPPING INFO (name, phone, email, address)
    # Name (multiple words capitalized)
    name_candidates = re.findall(r'\b[A-Z][a-z]+(?:\s[A-Z][a-z]+){1,2}\b', text)
    if name_candidates:
        parsed['note'] += f"Nome: {name_candidates[0]} "
    
    # Phone (Italian numbers)
    phone_patterns = [
        r'(?:\+39|0039)?\s*3\d{2}\s?\d{6,7}',
        r'\d{10,11}',
        r'\(tel:\s*(\d+)\)'
    ]
    for pattern in phone_patterns:
        phone_match = re.search(pattern, text)
        if phone_match:
            parsed['note'] += f"Tel: {phone_match.group(0)} "
            break
    
    # Email
    email_match = re.search(r'[\w\.-]+@[\w\.-]+\.[a-z]{2,}', text)
    if email_match:
        parsed['note'] += f"Email: {email_match.group(0)} "
    
    # Address (via, viale, corso, locker, inpost + number)
    address_keywords = ['via ', 'viale ', 'corso ', 'regione ', 'locker ', 'inpost ', 'tabacchino ']
    for kw in address_keywords:
        if kw in text_lower:
            # Extract until end or next clear separator
            addr_start = text_lower.find(kw)
            addr_text = text[addr_start:addr_start+100].strip()
            parsed['note'] += f"Indirizzo: {addr_text} "
            break
    
    # Payment method
    payments = ['revolut', 'bonifico', 'paypal', 'bitnovo', 'carta']
    for p in payments:
        if p in text_lower:
            parsed['note'] += f"Pagamento: {p.title()} "
            break
    
    parsed['note'] = parsed['note'].strip(', ')
    
    return parsed

def create_order_row(order: Dict[str, Any]) -> str:
    if not order['products']:
        return f"{order['cliente']} | --vuoto-- | {order['prezzo']}€"
    
    products_str = ', '.join([f"{p['qty']} {p['product']}" for p in order['products'][:3]])
    if len(order['products']) > 3:
        products_str += f" +{len(order['products'])-3}"
    
    status = "✅✅" if order.get('pacco_pronto') and order.get('pacco_consegnato') else "✅❌" if order.get('pacco_pronto') else "❌❌"
    return f"{order['cliente']} | {products_str} | {order['prezzo']}€ | {status}"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await show_orders_page(update, context, page=0)

async def show_orders_page(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int = 0):
    open_orders = [o for o in orders if not (o.get('pacco_pronto') and o.get('pacco_consegnato'))]
    
    if not open_orders:
        text = "✅ **Nessun ordine aperto!**"
        keyboard = [[InlineKeyboardButton("➕ Nuovo ordine", callback_data="add")]]
    else:
        per_page = 7
        total_pages = (len(open_orders) + per_page - 1) // per_page
        start_idx = page * per_page
        page_orders = open_orders[start_idx:start_idx + per_page]
        
        text = f"📋 **ORDINI APERTI** ({len(open_orders)}) - Pagina {page+1}/{total_pages}\n\n"
        keyboard_rows = []
        
        for i, order in enumerate(page_orders, start_idx+1):
            text += f"{i}. {create_order_row(order)}\n"
            # Per-order buttons
            keyboard_rows.append([
                InlineKeyboardButton("✏️ Modifica", callback_data=f"edit_{open_orders.index(order)}"),
                InlineKeyboardButton("✅ Pronto", callback_data=f"ready_{open_orders.index(order)}")
            ])
        
        # Navigation
        nav_row = []
        if page > 0:
            nav_row.append(InlineKeyboardButton("⬅️ Prec", callback_data=f"p_{page-1}"))
        if page < total_pages - 1:
            nav_row.append(InlineKeyboardButton("Succ ➡️", callback_data=f"p_{page+1}"))
        if nav_row:
            keyboard_rows.append(nav_row)
        
        keyboard_rows.extend([
            [InlineKeyboardButton("➕ Nuovo", callback_data="add")],
            [InlineKeyboardButton("📊 Stats", callback_data="stats")]
        ])
        
        keyboard = InlineKeyboardMarkup(keyboard_rows)
    
    reply_markup = InlineKeyboardMarkup(keyboard_rows) if 'keyboard_rows' in locals() else InlineKeyboardMarkup(keyboard)
    
    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    else:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    if data.startswith("p_"):
        page = int(data[2:])
        await show_orders_page(query, context, page)
    
    elif data == "add":
        await query.edit_message_text(
            "📥 **Invia messaggio ordine**\n\n"
            "🧠 Parsing automatico rileva:\n"
            "• @username\n"
            "• Prezzi (€/euro)\n"
            "• Grammi (5g filtrato, 10g OG)\n"
            "• Dabwoods/lean/backwoods\n"
            "• Nomi/telefoni/email/indirizzi",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Lista", callback_data="list")]])
        )
        context.user_data['waiting_order'] = True
    
    elif data == "stats":
        total = len(orders)
        open_count = len([o for o in orders if not (o.get('pacco_pronto') and o.get('pacco_consegnato'))])
        revenue = sum(float(o['prezzo'].replace('€', '').replace(',', '.')) for o in orders if o['prezzo'] != '??€')
        
        # Product totals
        grams_total = sum(float(p['qty'].replace('g', '')) for o in orders for p in o['products'] if 'g' in p['qty'])
        
        text = f"""📊 **STATISTICHE COMPLETA**

**Ordini:** {total} totali | {open_count} aperti
**Incasso:** {revenue:.0f}€
**Grammi totali:** {grams_total:.1f}g

**Top prodotti:**
"""
        product_count = {}
        for order in orders:
            for p in order['products']:
                key = p['product']
                product_count[key] = product_count.get(key, 0) + 1
        
        for prod, count in sorted(product_count.items(), key=lambda x: x[1], reverse=True)[:5]:
            text += f"• {prod}: {count}x\n"
        
        keyboard = [[InlineKeyboardButton("🔙 Lista", callback_data="list")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    
    elif data == "list":
        await show_orders_page(query, context, 0)
    
    elif data.startswith("edit_"):
        order_idx = int(data.split("_")[1])
        if 0 <= order_idx < len(orders):
            order = orders[order_idx]
            text = f"✏️ **Modifica {order['cliente']}**\n\n"
            text += f"**Prodotti:** {', '.join([f'{p['qty']} {p['product']}' for p in order['products']])}\n"
            text += f"**Prezzo:** {order['prezzo']}\n"
            text += f"**Note:** {order['note']}\n\n"
            text += "Invia il testo CORRETTO dell'ordine:"
            
            keyboard = [[InlineKeyboardButton("❌ Elimina", callback_data=f"delete_{order_idx}")]]
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
            context.user_data['editing_order'] = order_idx
    
    elif data.startswith("delete_"):
        order_idx = int(data.split("_")[1])
        if 0 <= order_idx < len(orders):
            del orders[order_idx]
            save_orders()
        await show_orders_page(query, context, 0)
    
    elif data.startswith("ready_"):
        order_idx = int(data.split("_")[1])
        if 0 <= order_idx < len(orders):
            order = orders[order_idx]
            if not order.get('pacco_pronto'):
                order['pacco_pronto'] = True
            elif not order.get('pacco_consegnato'):
                order['pacco_consegnato'] = True
            save_orders()
        await show_orders_page(query, context, 0)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    
    # Editing mode
    if context.user_data.get('editing_order') is not None:
        order_idx = context.user_data['editing_order']
        parsed = parse_flexible_order(text)
        orders[order_idx] = parsed
        save_orders()
        
        await update.message.reply_text(
            f"✅ **Ordine {order_idx+1} modificato!**\n\n{create_order_row(parsed)}",
            parse_mode='Markdown'
        )
        context.user_data.pop('editing_order', None)
        return
    
    # New order mode
    if context.user_data.get('waiting_order'):
        parsed = parse_flexible_order(text)
        orders.append(parsed)
        save_orders()
        
        preview = create_order_row(parsed)
        await update.message.reply_text(
            f"✅ **Ordine aggiunto!**\n\n{preview}\n"
            f"**Note rilevate:** {parsed['note']}\n\n"
            f"/start per lista | Usa ✏️ per modifiche",
            parse_mode='Markdown'
        )
        context.user_data['waiting_order'] = False
        return
    
    # Auto-detect
    text_lower = text.lower()
    if ('€' in text_lower or 'euro' in text_lower) and any(kw in text_lower for kw in ['g', 'dabwood', 'lean', 'filtr', '@']):
        parsed = parse_flexible_order(text)
        await update.message.reply_text(
            f"🤖 **Auto-rilevato:**\n{create_order_row(parsed)}\n\n"
            f"`SI` = aggiungi | `NO` = ignora | Invia testo corretto",
            parse_mode='Markdown'
        )
        context.user_data['auto_confirm'] = True
        context.user_data['auto_parsed'] = parsed

def main():
    """Main bot runner"""
    application = Application.builder().token(BOT_TOKEN).build()

    # Handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Start bot
    print("🚀 Bot avviato!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
