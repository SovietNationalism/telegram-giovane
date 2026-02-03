import re
import logging
import json
import os
from datetime import datetime
from typing import List, Dict, Any
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# Logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Configurazione bot
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN non trovato!")

# Ordini in memoria (in produzione usa DB/SQlite)
orders: List[Dict[str, Any]] = []


def load_orders() -> List[Dict[str, Any]]:
    """Carica ordini da JSON o ritorna lista vuota"""
    try:
        with open('orders.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return []


def save_orders():
    """Salva ordini in JSON"""
    with open('orders.json', 'w', encoding='utf-8') as f:
        json.dump(orders, f, indent=2, ensure_ascii=False)


# Carica ordini all’avvio
orders = load_orders()


# Mappa prodotti per riconoscimento intelligente
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
    """Rileva ordine da QUALUNQUE formato di messaggio"""
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
        'raw_text': original_text  # Per modifica dopo
    }

    # 1. Username @username
    username_match = re.search(r'@[\w\d_]{3,32}', text)
    if username_match:
        parsed['cliente'] = username_match.group(0)

    # 2. Prezzi (€, euro, euri, totale)
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

    # 3. Grammi (5g filtrato, 20g OG, 30g dry, ecc.)
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
            # Associa a prodotto noto
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

    # 4. Prodotti specifici (dabwoods, lean, backwoods, ecc.)
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
                break  # 1 volta per prodotto

    # 5. Info spedizione (nome, tel, email, indirizzo, pagamento)
    # Nome: 2-3 parole iniziali maiuscole
    name_candidates = re.findall(r'\b[A-Z][a-z]+(?:\s[A-Z][a-z]+){1,2}\b', text)
    if name_candidates:
        parsed['note'] += f"Nome: {name_candidates[0]} "

    # Telefono italiano (3xx senza prefisso o con +39/0039)
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

    # Indirizzo (via, viale, corso, locker, inpost, tabacchino)
    address_keywords = ['via ', 'viale ', 'corso ', 'regione ', 'locker ', 'inpost ', 'tabacchino ']
    for kw in address_keywords:
        if kw in text_lower:
            addr_start = text_lower.find(kw)
            addr_text = text[addr_start:addr_start+100].strip()
            parsed['note'] += f"Indirizzo: {addr_text} "
            break

    # Metodo di pagamento
    payments = ['revolut', 'bonifico', 'paypal', 'bitnovo', 'carta']
    for p in payments:
        if p in text_lower:
            parsed['note'] += f"Pagamento: {p.title()} "
            break

    parsed['note'] = parsed['note'].strip(', ')
    return parsed


def create_order_row(order: Dict[str, Any]) -> str:
    """Riga compatta ordine per la lista"""
    if not order['products']:
        return f"{order['cliente']} | --vuoto-- | {order['prezzo']}€"

    products_str = ', '.join([f"{p['qty']} {p['product']}" for p in order['products'][:3]])
    if len(order['products']) > 3:
        products_str += f" +{len(order['products'])-3}"

    status = "✅✅" if order.get('pacco_pronto') and order.get('pacco_consegnato') \
        else "✅❌" if order.get('pacco_pronto') \
        else "❌❌"
    return f"{order['cliente']} | {products_str} | {order['prezzo']}€ | {status}"


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /start: mostra ordini aperti"""
    await show_orders_page(update, context, 0)


async def show_orders_page(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int = 0):
    """Mostra ordini aperti con paginazione (max 6 per pagina)"""
    open_orders = [o for o in orders
                   if not (o.get('pacco_pronto') and o.get('pacco_consegnato'))]

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
                InlineKeyboardButton("✅ Pronto/consegn.", callback_data=f"ready_{i}")
            ])

        # Barra di navigazione
        nav_row = []
        if page > 0:
            nav_row.append(InlineKeyboardButton("⬅️ Precedente", callback_data=f"p_{page-1}"))
        if end_idx < len(open_orders):
            nav_row.append(InlineKeyboardButton("Successivo ➡️", callback_data=f"p_{page+1}"))
        if nav_row:
            keyboard.append(nav_row)

        # Bottom buttons
        keyboard.extend([
            [InlineKeyboardButton("➕ Nuovo ordine", callback_data="add")],
            [InlineKeyboardButton("📊 Statistiche", callback_data="stats")]
        ])

    reply_markup = InlineKeyboardMarkup(keyboard)
    try:
        if update.callback_query:
            await update.callback_query.edit_message_text(
                text, reply_markup=reply_markup, parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Error show_orders_page: {e}")
        await update.effective_message.reply_text(text)


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Callback inline: paginazione, edit, toggle, stats, ecc."""
    query = update.callback_query
    await query.answer()
    data = query.data

    if data.startswith("p_"):  # Pagina
        page = int(data[2:])
        await show_orders_page(query, context, page)

    elif data == "add":  # Nuovo ordine (auto‑detect)
        await query.edit_message_text(
            "📥 **Invia il messaggio dell'ordine**\n\n"
            "🧠 Parsing automatico rileva:\n"
            "• `@username`\n"
            "• Prezzi (€ / euro)\n"
            "• Grammi (5g filtrato, 10g OG)\n"
            "• Dabwoods / lean / backwoods\n"
            "• Nome / telefono / email / indirizzo\n\n"
            "Basta il tuo solito formato.",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Lista ordini", callback_data="list")]])
        )
        context.user_data['waiting_order'] = True

    elif data == "stats":  # Statistiche
        total = len(orders)
        open_count = len([o for o in orders if not (o.get('pacco_pronto') and o.get('pacco_consegnato'))])
        revenue = sum(
            float(o['prezzo'].replace('€', '').replace(',', '.'))
            for o in orders if o['prezzo'] and not o['prezzo'].startswith('??')
        )
        grams_total = sum(
            float(p['qty'].replace('g', '').replace('ml', ''))
            for o in orders
            for p in o['products']
            if p['qty'].endswith('g')
        )

        text = f"""📊 **STATISTICHE GENERALI**

• Ordini totali: {total}
• Ordini aperti: {open_count}
• Incasso totale: {revenue:,.0f} €
• Grammi venduti: {grams_total:.1f} g

**Top 5 prodotti:**\n"""

        product_count = {}
        for o in orders:
            for p in o['products']:
                product_count[p['product']] = product_count.get(p['product'], 0) + 1

        for prod, cnt in sorted(product_count.items(), key=lambda x: x[1], reverse=True)[:5]:
            text += f"• {prod}: {cnt}x\n"

        keyboard = [[InlineKeyboardButton("🔙 Lista ordini", callback_data="list")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

    elif data == "list":  # Torna a lista
        await show_orders_page(query, context, 0)

    elif data.startswith("edit_"):  # Modifica ordine
        idx = int(data.split("_")[1])
        if 0 <= idx < len(orders):
            order = orders[idx]
            text = f"✏️ **Modifica {order['cliente']}**\n\n"
            text += f"• Prodotti: {', '.join([f'{p['qty']} {p['product']}' for p in order['products']])}\n"
            text += f"• Prezzo: {order['prezzo']}\n"
            text += f"• Note: {order['note']}\n\n"
            text += "Rispondi con il testo corretto dell'ordine:"

            keyboard = [
                [InlineKeyboardButton("🗑 Elimina ordine", callback_data=f"delete_{idx}")]
            ]
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
            context.user_data['editing_order'] = idx

    elif data.startswith("delete_"):  # Elimina ordine
        idx = int(data.split("_")[1])
        if 0 <= idx < len(orders):
            del orders[idx]
            save_orders()
        await show_orders_page(query, context, 0)

    elif data.startswith("ready_"):  # Toggle ready → delivered
        idx = int(data.split("_")[1])
        if 0 <= idx < len(orders):
            order = orders[idx]
            if not order.get('pacco_pronto'):
                order['pacco_pronto'] = True
            elif not order.get('pacco_consegnato'):
                order['pacco_consegnato'] = True
            save_orders()
        await show_orders_page(query, context, 0)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Gestisce messaggi: parsing automatico, editing, nuovo ordine"""
    text = update.message.text

    # 1. Modifica ordine in corso
    if context.user_data.get('editing_order') is not None:
        order_idx = context.user_data['editing_order']
        parsed = parse_flexible_order(text)
        if 0 <= order_idx < len(orders):
            orders[order_idx] = parsed
            save_orders()
            await update.message.reply_text(
                f"✅ **Ordine {order_idx+1} modificato!**\n\n{create_order_row(parsed)}",
                parse_mode='Markdown'
            )
        context.user_data.pop('editing_order', None)
        return

    # 2. Nuovo ordine (da /start -> “➕ Nuovo ordine”)
    if context.user_data.get('waiting_order'):
        parsed = parse_flexible_order(text)
        orders.append(parsed)
        save_orders()
        preview = create_order_row(parsed)
        note_preview = f"\n📝 Note: {parsed['note']}" if parsed['note'] else ""
        await update.message.reply_text(
            f"✅ **Ordine aggiunto a Schedule One!**\n\n"
            f"{preview}{note_preview}\n\n"
            f"Usa ✏️ nella lista per modificare. /start per vedere ordini.",
            parse_mode='Markdown'
        )
        context.user_data['waiting_order'] = False
        return

    # 3. Auto‑detect su messaggi che sembrano ordini
    text_lower = text.lower()
    if ('€' in text_lower or 'euro' in text_lower) and any(
        kw in text_lower for kw in ['g', 'dabwood', 'lean', 'filtr', '@', 'pag']
    ):
        parsed = parse_flexible_order(text)
        await update.message.reply_text(
            "🤖 **Rilevato ordine in corso…**\n\n"
            f"{create_order_row(parsed)}\n\n"
            "• Rispondi `SI` per aggiungere l'ordine.\n"
            "• Rispondi `NO` per ignorare.\n"
            "• Oppure invia il testo corretto per modificare direttamente.",
            parse_mode='Markdown'
        )
        context.user_data['auto_confirm'] = True
       
