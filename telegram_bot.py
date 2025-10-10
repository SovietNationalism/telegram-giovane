import os, sys, logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes
)
from telegram.error import BadRequest

# ─────────────────────────  CONFIG  ───────────────────────── #

BOT_TOKEN         = os.getenv("BOT_TOKEN")
ADMIN_USER_ID     = 6840588025

# Client-specific text and links
WELCOME_IMAGE_URL = "https://i.postimg.cc/pr65RVVm/D6-F1-EDE3-E7-E8-4-ADC-AAFC-5-FB67-F86-BDE3.png"
WELCOME_TEXT = (
    "✌️Bom dia tropa!🔥\n"
    "Il Giovane Bandito è pronto per portarti i prodotti della miglior qualità al minor prezzo possibile 🤝"
)
CONTACT_URL = "https://t.me/GI0VANEBANDIT0"
REVIEWS_URL = "https://t.me/+x6I1LGcB_OY2MGQ0"

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

# Categories requested by the client
CATEGORIES = [
    ("cannabis", "🍃 Cannabis"),
    ("psichedelici", "🎆 Psichedelici"),
    ("stimolanti", "🏃 Stimolanti"),
    ("sintetiche", "🥳 Sintetiche"),
    ("pharma", "💊 Pharma"),
    ("cannabis_sintetica", "🧪 Cannabis sintetica"),
]

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)
if not BOT_TOKEN:
    logger.critical("❌ BOT_TOKEN missing."); sys.exit(1)

# ─────────────────────────  BOT CLASS  ────────────────────── #

class ShopBot:
    def __init__(self):
        # Products registry (empty now; add later as real items)
        # product_id: {"category": str, "name": str, "price": str|None, "description": str|None,
        #              "caption": str|None, "video_file_id": str|None}
        self.products = {}

        # Track users for broadcast
        self.user_ids = set()

    # ────────────────────  HELPER: relay  ─────────────────── #
    async def _relay_to_admin(self, context: ContextTypes.DEFAULT_TYPE, who, what: str) -> None:
        message = f"👤 {who.full_name} ({who.id})\n💬 {what}"
        logger.info(message)
        try:
            await context.bot.send_message(ADMIN_USER_ID, message)
        except Exception as e:
            logger.warning(f"Failed to relay to admin: {e}")

    async def delete_last_menu(self, context, chat_id):
        msg_id = context.user_data.get("last_menu_msg_id")
        if msg_id:
            try:
                await context.bot.delete_message(chat_id=chat_id, message_id=msg_id)
            except:
                pass
            context.user_data["last_menu_msg_id"] = None

    # ────────────────────────  KEYBOARDS  ──────────────────────── #
    def home_keyboard(self) -> InlineKeyboardMarkup:
        kb = [
            [InlineKeyboardButton("🛍️ Menù", callback_data="menu")],
            [InlineKeyboardButton("⭐️ Recensioni", url=REVIEWS_URL)],
            [InlineKeyboardButton("🔌 Contatto", url=CONTACT_URL)],
            [InlineKeyboardButton("📋 T.O.S", callback_data="tos")],
        ]
        return InlineKeyboardMarkup(kb)

    def categories_keyboard(self) -> InlineKeyboardMarkup:
        rows = []
        row = []
        for key, label in CATEGORIES:
            row.append(InlineKeyboardButton(label, callback_data=f"cat_{key}"))
            if len(row) == 2:
                rows.append(row)
                row = []
        if row:
            rows.append(row)
        rows.append([InlineKeyboardButton("⬅️ Indietro", callback_data="back_to_home")])
        return InlineKeyboardMarkup(rows)

    def products_keyboard(self, cat_key: str):
        # Build a list of products in category
        prod_rows = []
        for pid, p in self.products.items():
            if p.get("category") == cat_key:
                prod_rows.append([InlineKeyboardButton(p.get("name", f"Prodotto {pid}"), callback_data=f"product_{pid}")])
        # Add back
        prod_rows.append([InlineKeyboardButton("⬅️ Indietro", callback_data="menu")])
        return InlineKeyboardMarkup(prod_rows)

    # ────────────────────────  COMMANDS  ──────────────────────── #
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        self.user_ids.add(update.effective_user.id)
        await self.delete_last_menu(context, update.effective_chat.id)

        m = update.effective_message
        try:
            sent = await m.reply_photo(photo=WELCOME_IMAGE_URL, caption=WELCOME_TEXT, reply_markup=self.home_keyboard())
            context.user_data["last_menu_msg_id"] = sent.message_id
        except BadRequest:
            sent = await m.reply_text(text=WELCOME_TEXT, reply_markup=self.home_keyboard())
            context.user_data["last_menu_msg_id"] = sent.message_id

    async def broadcast(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id != ADMIN_USER_ID:
            await update.message.reply_text("❌ Non sei autorizzato a usare questo comando.")
            return

        if not context.args:
            await update.message.reply_text("❗ Usa correttamente: /broadcast <messaggio>")
            return

        message = " ".join(context.args)
        count = 0
        for uid in list(self.user_ids):
            try:
                await context.bot.send_message(uid, f"📢 {message}")
                count += 1
            except Exception as e:
                logger.warning(f"Impossibile inviare a {uid}: {e}")

        await update.message.reply_text(f"✅ Messaggio inviato a {count} utenti.")

    # ────────────────────────  CALLBACKS  ──────────────────────── #
    async def button_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        q   = update.callback_query
        d   = q.data
        cid = q.message.chat.id
        self.user_ids.add(update.effective_user.id)

        await q.answer()

        if update.effective_user.id != ADMIN_USER_ID:
            await self._relay_to_admin(context, update.effective_user, f"Pressed button: {d}")

        await self.delete_last_menu(context, cid)

        # ---------- HOME NAV ---------- #
        if d == "back_to_home":
            await self.start(update, context)
            return

        if d == "tos":
            kb = [[InlineKeyboardButton("⬅️ Indietro", callback_data="back_to_home")]]
            sent = await context.bot.send_message(chat_id=cid, text=TOS_TEXT, reply_markup=InlineKeyboardMarkup(kb))
            context.user_data["last_menu_msg_id"] = sent.message_id
            return

        # ---------- MENU ---------- #
        if d == "menu":
            sent = await context.bot.send_message(
                chat_id=cid,
                text="Scegli una categoria:",
                reply_markup=self.categories_keyboard()
            )
            context.user_data["last_menu_msg_id"] = sent.message_id
            return

        # ---------- CATEGORIA ---------- #
        if d.startswith("cat_"):
            cat_key = d.split("_", 1)[1]
            # If products exist, show list; else show placeholder with back
            has_any = any(p.get("category") == cat_key for p in self.products.values())
            if has_any:
                sent = await context.bot.send_message(
                    chat_id=cid,
                    text=f"{dict(CATEGORIES).get(cat_key, cat_key)} — Elenco prodotti:",
                    reply_markup=self.products_keyboard(cat_key)
                )
                context.user_data["last_menu_msg_id"] = sent.message_id
            else:
                kb = [[InlineKeyboardButton("⬅️ Indietro", callback_data="menu")]]
                sent = await context.bot.send_message(
                    chat_id=cid,
                    text=f"{dict(CATEGORIES).get(cat_key, cat_key)}\n\nNessun prodotto in questa categoria al momento.",
                    reply_markup=InlineKeyboardMarkup(kb)
                )
                context.user_data["last_menu_msg_id"] = sent.message_id
            return

        # ---------- PRODOTTO ---------- #
        if d.startswith("product_"):
            pid = d.split("_", 1)[1]
            prod = self.products.get(pid)
            if not prod:
                await q.answer("❌ Prodotto non trovato!")
                return

            # Compose caption
            if prod.get("caption"):
                caption = prod["caption"]
            else:
                parts = [f"📦 *{prod.get('name','Prodotto')}*"]
                price = (prod.get("price") or "").strip()
                if price:
                    parts.append(f"💵 Prezzo:\n{price}")
                desc = (prod.get("description") or "").strip()
                if desc:
                    parts.append(f"📝 Descrizione: {desc}")
                caption = "\n".join(parts)

            cat_key = prod.get("category") or ""
            back_cb = f"cat_{cat_key}" if cat_key else "menu"
            kb_back = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Indietro", callback_data=back_cb)]])

            if prod.get("video_file_id"):
                try:
                    sent = await context.bot.send_video(
                        chat_id=cid,
                        video=prod["video_file_id"],
                        caption=caption,
                        parse_mode=ParseMode.MARKDOWN,
                        supports_streaming=True,
                        reply_markup=kb_back
                    )
                    context.user_data["last_menu_msg_id"] = sent.message_id
                except BadRequest:
                    sent = await context.bot.send_message(
                        chat_id=cid, text=caption, parse_mode=ParseMode.MARKDOWN, reply_markup=kb_back
                    )
                    context.user_data["last_menu_msg_id"] = sent.message_id
            else:
                sent = await context.bot.send_message(
                    chat_id=cid, text=caption, parse_mode=ParseMode.MARKDOWN, reply_markup=kb_back
                )
                context.user_data["last_menu_msg_id"] = sent.message_id
            return

    # ────────────────────────  MESSAGES  ──────────────────────── #
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        m   = update.effective_message
        usr = update.effective_user
        self.user_ids.add(usr.id)

        if usr and usr.id != ADMIN_USER_ID:
            txt = (
                m.text or m.caption or
                (f"<{type(m.effective_attachment).__name__}>" if m.effective_attachment else "<no text>")
            )
            await self._relay_to_admin(context, usr, txt)

        if usr and usr.id == ADMIN_USER_ID:
            if m.video:
                await m.reply_text(f"File ID del video:\n<code>{m.video.file_id}</code>", parse_mode=ParseMode.HTML); return
            if m.photo:
                await m.reply_text(f"File ID della foto:\n<code>{m.photo[-1].file_id}</code>", parse_mode=ParseMode.HTML); return

        t = m.text.lower() if m.text else ""
        if any(w in t for w in ("ciao", "salve")):
            await m.reply_text("Ciao! 👋 Usa /start per iniziare.")
        elif "aiuto" in t or "help" in t:
            await m.reply_text("Usa /start per vedere il menu principale.")
        else:
            await m.reply_text("Non ho capito. Usa /start per vedere le opzioni disponibili.")

# ──────────────────────────  MAIN  ────────────────────────── #
def main():
    logger.info("Avvio del bot...")
    try:
        app = Application.builder().token(BOT_TOKEN).build()
        bot = ShopBot()

        app.add_handler(CommandHandler("start", bot.start))
        app.add_handler(CommandHandler("broadcast", bot.broadcast))
        app.add_handler(CallbackQueryHandler(bot.button_handler))
        app.add_handler(MessageHandler(filters.ALL, bot.handle_message))

        app.run_polling()
        logger.info("Bot terminato.")
    except Exception as e:
        logger.exception(f"❌ Errore critico: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
