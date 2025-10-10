import os
import sys
import logging
from typing import Dict, Optional

from telegram import (
    Update,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    MessageHandler,
    filters,
)
from telegram.error import BadRequest

# ─────────────────────────  CONFIG  ───────────────────────── #

BOT_TOKEN = os.getenv("BOT_TOKEN")

# External links provided by the client
CONTACT_URL = "https://t.me/GI0VANEBANDIT0"
REVIEWS_URL = "https://t.me/+x6I1LGcB_OY2MGQ0"

# Category channel URLs (leave empty "" if not yet available; the bot will show a placeholder)
CATEGORY_URLS: Dict[str, str] = {
    "cannabis": "",
    "psichedelici": "",
    "stimolanti": "",
    "sintetiche": "",
    "pharma": "",
    "cannabis_sintetica": "",
}

WELCOME_TEXT = (
    "✌️Bom dia tropa!🔥\n"
    "Il Giovane Bandito è pronto per portarti i prodotti della miglior qualità al minor prezzo possibile 🤝"
)

TOS_TEXT = (
    "effettuando un ordine accetti in automatico ai seguenti termini di servizio\n"
    "🫣\n"
    "unico contatto per effettuare ordini: @GI0VANEBANDIT0\n\n"
    "💰\n"
    "Unico metodo di pagamento accettato: crypto (solo BTC, LTC e XMR).\n"
    "In caso di pagamento inferiore a quanto concordato (causa distrazione, commissioni del wallet, valuta sbagliata etc.) sarà proporzionalmente ridotta la quantità di prodotto ordinato.\n\n"
    "Escrow accettato (solo conosciuti ed affidabili), spese di commissione a carico del cliente.\n\n"
    "📦\n"
    "Spedizione e stealth a scelta tra InPost, UPS e BRT sempre a 10€ (eccetto il caso in cui sia specificato nell'annuncio 'spedizione gratuita').\n\n"
    "☑️\n"
    "Reship del 100% in caso di pacco smarrito o bloccato per errori del vendor nelle spedizioni tramite corriere (BRT e UPS);\n"
    "Reship del 50% in caso di pacco smarrito o bloccato per errori del vendor nelle spedizioni tramite InPost;\n"
    "Reship del 100% in caso di pacco manomesso durante la spedizione e privo dei prodotti ordinati (dimostrabile sollo tramite video chiaro e ben visibile del momento del ritiro del pacco e successivamente della sua apertura).\n\n"
    "Refund del 50% in caso di pacco smarrito o bloccato per errori del vendor nelle spedizioni tramite corriere (BRT e UPS);\n"
    "Nessun refund in caso di pacco smarrito o bloccato per errori del vendor nelle spedizioni tramite InPost;\n"
    "Refund del 50% in caso di pacco manomesso durante la spedizione e privo dei prodotti ordinati (dimostrabile sollo tramite video chiaro e ben visibile del momento del ritiro del pacco e successivamente della sua apertura).\n\n"
    "Reship e refund erogati solo dopo piena certezza del pacco perso (tracking) o manomesso (video).\n\n"
    "🏷️\n"
    "Sconto di 10€ sull'ordine successivo se viene effettuata recensione onesta, ben curata e con fotografia."
)

# Inline categories as requested
CATEGORIES = [
    ("cannabis", "🍃 Cannabis"),
    ("psichedelici", "🎆 Psichedelici"),
    ("stimolanti", "🏃 Stimolanti"),
    ("sintetiche", "🥳 Sintetiche"),
    ("pharma", "💊 Pharma"),
    ("cannabis_sintetica", "🧪 Cannabis sintetica"),
]

# Optional note shown on the menu screen under the keyboard
MENU_NOTE = "🧪 Cannabis sintetica: 🤫 non rilevabile ai droga test"

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)
if not BOT_TOKEN:
    logger.critical("❌ BOT_TOKEN missing.")
    sys.exit(1)


# ─────────────────────────  BOT CLASS  ────────────────────── #

class BanditoBot:
    def __init__(self):
        # Track the last menu message per user to keep the chat tidy
        self.user_ids = set()

    # --------------- helpers --------------- #
    async def _delete_last_menu(self, context: ContextTypes.DEFAULT_TYPE, chat_id: int):
        msg_id = context.user_data.get("last_menu_msg_id")
        if msg_id:
            try:
                await context.bot.delete_message(chat_id=chat_id, message_id=msg_id)
            except BadRequest:
                pass
            context.user_data["last_menu_msg_id"] = None

    def _home_keyboard(self) -> InlineKeyboardMarkup:
        kb = [
            [InlineKeyboardButton("🛍️ Menù", callback_data="menu")],
            [InlineKeyboardButton("⭐️ Recensioni", url=REVIEWS_URL)],
            [InlineKeyboardButton("🔌 Contatto", url=CONTACT_URL)],
            [InlineKeyboardButton("📋 T.O.S", callback_data="tos")],
        ]
        return InlineKeyboardMarkup(kb)

    def _category_button(self, key: str, label: str) -> InlineKeyboardButton:
        url = (CATEGORY_URLS.get(key) or "").strip()
        if url:
            # Open the external channel directly if URL is configured
            return InlineKeyboardButton(label, url=url)
        # Otherwise, show a placeholder screen for the category
        return InlineKeyboardButton(label, callback_data=f"cat_{key}")

    def _menu_keyboard(self) -> InlineKeyboardMarkup:
        # Build rows with two buttons side-by-side
        rows = []
        row = []
        for key, label in CATEGORIES:
            row.append(self._category_button(key, label))
            if len(row) == 2:
                rows.append(row)
                row = []
        if row:
            rows.append(row)
        rows.append([InlineKeyboardButton("⬅️ Indietro", callback_data="back_to_home")])
        return InlineKeyboardMarkup(rows)

    async def _send_or_edit(self, update: Update, context: ContextTypes.DEFAULT_TYPE, text: str,
                            reply_markup: Optional[InlineKeyboardMarkup] = None,
                            parse_mode: Optional[str] = None):
        """
        Sends a new message and remembers its ID to delete on next navigation.
        """
        chat_id = update.effective_chat.id
        await self._delete_last_menu(context, chat_id)
        m = await context.bot.send_message(
            chat_id=chat_id, text=text, parse_mode=parse_mode, reply_markup=reply_markup
        )
        context.user_data["last_menu_msg_id"] = m.message_id

    # --------------- handlers --------------- #
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        self.user_ids.add(update.effective_user.id)
        await self._send_or_edit(
            update,
            context,
            text=WELCOME_TEXT,
            reply_markup=self._home_keyboard(),
        )

    async def button_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        q = update.callback_query
        d = q.data
        await q.answer()

        # Home navigation
        if d == "back_to_home":
            await self.start(update, context)
            return

        if d == "menu":
            await self._send_or_edit(
                update,
                context,
                text="Scegli un canale dal Menù:",
                reply_markup=self._menu_keyboard(),
            )
            # Optionally send the note as a separate message to avoid cluttering the keyboard message
            if MENU_NOTE:
                await context.bot.send_message(chat_id=update.effective_chat.id, text=MENU_NOTE)
            return

        if d == "tos":
            await self._send_or_edit(
                update,
                context,
                text=TOS_TEXT,
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("⬅️ Indietro", callback_data="back_to_home")]]
                ),
            )
            return

        # Category placeholder pages when URL is not set
        if d.startswith("cat_"):
            key = d.split("_", 1)[1]
            # Find label
            label = next((lbl for k, lbl in CATEGORIES if k == key), key)
            url = (CATEGORY_URLS.get(key) or "").strip()
            if url:
                # If URL was added at runtime, show direct-visit page
                kb = [[InlineKeyboardButton(f"Entra nel canale {label}", url=url)]]
            else:
                kb = [[InlineKeyboardButton("⬅️ Indietro", callback_data="menu")]]
            await self._send_or_edit(
                update,
                context,
                text=f"{label}\n\nApri il canale per vedere gli annunci." if url else f"{label}\n\nCanale non ancora configurato.",
                reply_markup=InlineKeyboardMarkup(kb),
            )
            return

    async def on_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        # Friendly fallback to /start
        t = (update.effective_message.text or "").strip().lower()
        if t in ("/start", "start"):
            await self.start(update, context)
            return
        await update.effective_message.reply_text("Usa /start per iniziare.")

# ──────────────────────────  MAIN  ────────────────────────── #

def main():
    logger.info("Avvio del bot...")
    try:
        app = Application.builder().token(BOT_TOKEN).build()
        bot = BanditoBot()

        app.add_handler(CommandHandler("start", bot.start))
        app.add_handler(CallbackQueryHandler(bot.button_handler))
        app.add_handler(MessageHandler(filters.ALL, bot.on_message))

        app.run_polling()
        logger.info("Bot terminato.")
    except Exception as e:
        logger.exception(f"❌ Errore critico: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
