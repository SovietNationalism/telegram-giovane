import logging
import json
import asyncio
import os  # <-- AGGIUNTO
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Your bot token from environment variable
BOT_TOKEN = os.getenv("BOT_TOKEN")  # <-- CAMBIATO QUI

if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN non trovato! Imposta env var BOT_TOKEN")

# Resto del codice identico...
# In-memory storage (use SQLite/PostgreSQL for production)
orders = []

def load_orders():
    """Load orders from JSON file or return empty list"""
    try:
        with open('orders.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return []

def save_orders():
    """Save orders to JSON file"""
    with open('orders.json', 'w') as f:
        json.dump(orders, f, indent=2)

orders = load_orders()

def create_order_row(order):
    """Format single order as compact string"""
    products = ', '.join([f"{p['qty']} {p['product']}" for p in order['products']])
    status = "✅✅" if order['pacco_pronto'] and order['pacco_consegnato'] else "✅❌" if order['pacco_pronto'] else "❌❌"
    return f"{order['cliente']} | {products} | {order['prezzo']}€ | {status}"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show main menu with pagination"""
    await show_orders_page(update, context, page=0)

async def show_orders_page(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int = 0):
    """Show paginated orders list"""
    # Filter open orders first? Change to orders[:] for all
    open_orders = [o for o in orders if not (o.get('pacco_pronto', False) and o.get('pacco_consegnato', False))]
    
    if not open_orders:
        text = "✅ **Nessun ordine aperto!** ✅\nTutti completati."
        keyboard = [[InlineKeyboardButton("📥 Nuovo ordine", callback_data="add_order")]]
    else:
        # Pagination: 10 orders per page
        per_page = 10
        total_pages = (len(open_orders) + per_page - 1) // per_page
        start_idx = page * per_page
        end_idx = start_idx + per_page
        page_orders = open_orders[start_idx:end_idx]
        
        text = f"📋 **ORDINI APERTI** ({len(open_orders)} totali) - Pagina {page+1}/{total_pages}\n\n"
        for i, order in enumerate(page_orders, start_idx+1):
            text += f"{i}. {create_order_row(order)}\n"
        
        # Navigation buttons
        keyboard = []
        if page > 0:
            keyboard.append(InlineKeyboardButton("⬅️ Prec", callback_data=f"page_{page-1}"))
        if page < total_pages - 1:
            keyboard.append(InlineKeyboardButton("Succ ➡️", callback_data=f"page_{page+1}"))
        keyboard.append([InlineKeyboardButton("📥 Nuovo ordine", callback_data="add_order")])
        keyboard.append([InlineKeyboardButton("📊 Stats", callback_data="stats")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    if data.startswith("page_"):
        page = int(data.split("_")[1])
        await show_orders_page(query, context, page)
    elif data == "add_order":
        await query.edit_message_text(
            "📥 **Aggiungi nuovo ordine**\n\n"
            "Invia formato:\n"
            "`@username | 5g filtrato, 3 dabwoods | 120€ | nome, tel, indirizzo, pagamento`\n\n"
            "Es: `@user1 | 10g dry, 2 lean | 85€ | Mario Rossi, 3331234567, Via Roma 1 Milano, Revolut`",
            parse_mode='Markdown'
        )
        # Set waiting state for next message
        context.user_data['waiting_order'] = True
    elif data == "stats":
        total_orders = len(orders)
        open_orders = len([o for o in orders if not (o.get('pacco_pronto', False) and o.get('pacco_consegnato', False))])
        total_revenue = sum(float(o['prezzo'].replace('€', '')) for o in orders)
        
        text = f"📊 **STATISTICHE**\n\n" \
               f"• Ordini totali: {total_orders}\n" \
               f"• Aperti: {open_orders}\n" \
               f"• Incasso totale: {total_revenue:.0f}€\n" \
               f"• Media ordine: {total_revenue/total_orders:.0f}€"
        
        keyboard = [[InlineKeyboardButton("🔙 Lista ordini", callback_data="list")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    elif data == "list":
        await show_orders_page(query, context, 0)
    elif data.startswith("toggle_"):
        order_id = int(data.split("_")[1])
        order = orders[order_id]
        if order_id < len(orders):
            # Toggle pacco_pronto / pacco_consegnato
            if not order.get('pacco_pronto', False):
                order['pacco_pronto'] = True
            elif not order.get('pacco_consegnato', False):
                order['pacco_consegnato'] = True
            else:
                order['pacco_consegnato'] = False  # Reset if both done
            
            save_orders()
            await show_orders_page(query, context, 0)
    elif data.startswith("detail_"):
        order_id = int(data.split("_")[1])
        if order_id < len(orders):
            order = orders[order_id]
            text = f"📋 **Dettaglio {order['cliente']}**\n\n" + "\n".join([f"• {p['qty']} {p['product']}" for p in order['products']]) + f"\n\nPrezzo: {order['prezzo']}\nNote: {order.get('note', 'N/A')}"
            keyboard = [
                [InlineKeyboardButton("✅ Pronto", callback_data=f"toggle_{order_id}")],
                [InlineKeyboardButton("🔙 Lista", callback_data="list")]
            ]
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Parse new order from text message"""
    if context.user_data.get('waiting_order'):
        text = update.message.text
        try:
            # Simple parsing: @username | prodotti | prezzo | note spedizione
            parts = text.split('|')
            if len(parts) >= 3:
                cliente = parts[0].strip()
                products_str = parts[1].strip()
                prezzo = parts[2].strip()
                
                # Parse products
                products = []
                for item in products_str.split(','):
                    item = item.strip()
                    if 'g' in item or 'ml' in item:
                        qty, product = item.rsplit(' ', 1)
                        products.append({'qty': qty, 'product': product})
                    else:
                        products.append({'qty': item, 'product': 'unknown'})
                
                # Note = rest of message
                note = '|'.join(parts[3:]).strip() if len(parts) > 3 else ""
                
                new_order = {
                    'cliente': cliente,
                    'products': products,
                    'prezzo': prezzo,
                    'note': note,
                    'pacco_pronto': False,
                    'pacco_consegnato': False,
                    'data': datetime.now().isoformat()
                }
                
                orders.append(new_order)
                save_orders()
                
                await update.message.reply_text(
                    f"✅ **Ordine aggiunto!**\n\n{create_order_row(new_order)}\n\n"
                    "Usa /start per vedere la lista.",
                    parse_mode='Markdown'
                )
            else:
                await update.message.reply_text("❌ Formato non valido. Riprova.")
        except Exception as e:
            logger.error(f"Parse error: {e}")
            await update.message.reply_text("❌ Errore parsing. Usa il formato esatto.")
        
        context.user_data['waiting_order'] = False
        return

def main():
    """Start the bot"""
    app = Application.builder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    app.run_polling()

if __name__ == '__main__':
    main()
