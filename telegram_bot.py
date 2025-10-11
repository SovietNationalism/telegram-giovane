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
WELCOME_IMAGE_URL = "https://i.postimg.cc/D038YGC5/IMG-0728.jpg"
WELCOME_TEXT = (
    "✌️Bom dia tropa!🔥\n"
    "Il Giovane Bandito è pronto per portarti i prodotti della miglior qualità al minor prezzo possibile 🤝"
)
CONTACT_URL = "https://t.me/GI0VANEBANDIT0"
REVIEWS_URL = "https://t.me/+x6I1LGcB_OY2MGQ0"

TOS_TEXT = (
    "Effettuando un ordine accetti in automatico ai seguenti termini di servizio:\n"
    "Spedizione e stealth a scelta tra InPost, UPS e BRT sempre a 10€ (eccetto il caso in cui sia specificato nell'annuncio 'spedizione gratuita').\n\n"
    "☑️\n"
    "Reship del 100% in caso di pacco smarrito o bloccato per errori del vendor nelle spedizioni tramite corriere (BRT e UPS);\n"
    "Reship del 50% in caso di pacco smarrito o bloccato per errori del vendor nelle spedizioni tramite InPost;\n"
    "Reship del 100% in caso di pacco manomesso durante la spedizione e privo dei prodotti ordinati (dimostrabile solo tramite video chiaro e ben visibile del momento del ritiro del pacco e successivamente della sua apertura).\n\n"
    "Refund del 50% in caso di pacco smarrito o bloccato per errori del vendor nelle spedizioni tramite corriere (BRT e UPS);\n"
    "Nessun refund in caso di pacco smarrito o bloccato per errori del vendor nelle spedizioni tramite InPost;\n"
    "Refund del 50% in caso di pacco manomesso durante la spedizione e privo dei prodotti ordinati (dimostrabile solo tramite video chiaro e ben visibile del momento del ritiro del pacco e successivamente della sua apertura).\n\n"
    "Reship e refund erogati solo dopo piena certezza del pacco perso (tracking) o manomesso (video).\n\n"
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
        self.products = {
        # cannabis_sintetica
        "cs_liquido": {
            "category": "cannabis_sintetica",
            "name": "🍃 Liquido svapo THC synth 😶‍🌫️😵‍💫",
            "caption": (
                "50 ml : 200€ (4€/ml)\n"
                "100 ml : 350€ (3.5€/ml)\n"
                "200 ml : 600€ (3€/ml)\n"
                "500 ml : 1000€ (2€/ml)\n"
                "1000 ml : 1600€ (1.6€/ml)\n\n"
                "Liquido per sigaretta elettronica ai cannabinoidi sintetici;\n"
                "Un paio di tiri per uno sballo come da THC ma più potente e non rilevabile ai test antidroga;\n"
                "Inodore ed insapore, usalo ovunque senza che nessuno se ne accorga, oppure aggiungi i tuoi aromi preferiti.\n"
                "spedizione e stealth : 10€"
            ),
            "video_file_id": None,
        },
        "cs_k2_spice": {
            "category": "cannabis_sintetica",
            "name": "🍃 K2 | SPICE 🤯",
            "caption": (
                "Bags da 3gr:\n"
                "2 bags : 70€ (35€/bag)\n"
                "5 bags : 120€ (24€/bag)\n"
                "10 bags : 180€ (18€/bag)\n\n"
                "L’originale Spice (o K2), leggendaria ed iconica;\n"
                "Erbe contenenti potenti cannabinoidi sintetici;\n"
                "Un high simile al classico THC, ma più potente e non rilevabile ai test antidroga.\n"
                "spedizione e stealth : 10€"
            ),
            "photo_file_id": "AgACAgQAAxkBAAN_aOmui4fOVZ838yEV4qJIbfCJ18QAAlvJMRtPrVBTbCZFNWjvp_kBAAMCAAN4AAM2BA",
        },
        "cs_synth_weed": {
            "category": "cannabis_sintetica",
            "name": "🍃 SYNTH WEED 🥦🫠",
            "caption": (
                "25 gr : 160€ (6.4€/gr)\n"
                "50 gr : 250€ (5€/gr)\n"
                "100 gr : 420€ (4.2€/gr)\n"
                "200 gr : 600€ (3€/gr)\n\n"
                "Fiori CBD di alta qualità, contenenti cannabinoidi sintetici;\n"
                "Stesso sballo del classico THC ma più potente e non rilevabile dai test antidroga.\n"
                "spedizione e stealth : 10€"
            ),
            "photo_file_id": "AgACAgQAAxkBAANnaOmuH2n7mTJxl7UhebhyPHXJ4yUAAlrJMRtPrVBTeNSJdNF_rVABAAMCAAN4AAM2BA",
        },
    
        # stimolanti
        "stim_boliviana": {
            "category": "stimolanti",
            "name": "🥥 BOLIVIANA 🌨️⛷️",
            "caption": (
                "1 gr : 90€\n"
                "3 gr : 240€ (80€/gr)\n"
                "5 gr : 300€ (60€/gr)\n"
                "10 gr : 500€ (50€/gr)\n"
                "25 gr : 1000€ (40€/gr)\n\n"
                "Direttamente dalla Bolivia;\n"
                "Prodotta nel cuore della foresta amazzonica mediante le tecniche tradizionali;\n"
                "High forte, euforico e duraturo, down quasi del tutto assente.\n"
                "spedizione e stealth : 10€"
            ),
            "video_file_id": None,
        },
        "stim_4mmc": {
            "category": "stimolanti",
            "name": "💎 4‑mmc 😻🥰",
            "caption": (
                "5 gr : 130€ (26€/gr)\n"
                "10 gr : 160€ (16€/gr)\n"
                "25 gr : 300€ (12€/gr)\n"
                "50 gr : 450€ (9€/gr)\n"
                "100 gr : 750€ (7.5€/gr)\n\n"
                "Rocce e cristalli purissimi e pulitissimi;\n"
                "Ti garantiranno un’euforia inimmaginabile e un immenso aumento di empatia ed amore verso il prossimo.\n"
                "spedizione e stealth : 10€"
            ),
            "video_file_id": None,
        },
        "stim_nep": {
            "category": "stimolanti",
            "name": "💠 NEP 🏃🏃",
            "caption": (
                "5 gr : 150€ (30€/gr)\n"
                "10 gr : 200€ (20€/gr)\n"
                "25 gr : 250€ (10€/gr)\n"
                "50 gr : 450€ (9€/gr)\n"
                "100 gr : 650€ (6.5€/gr)\n\n"
                "spedizione e stealth : 10€"
            ),
            "video_file_id": None,
        },
    
        # psichedelici
        "psy_lsd": {
            "category": "psichedelici",
            "name": "😵‍💫 L$D needlepoint 250 µg 🦄🌈",
            "caption": (
                "5 tabs : 40€ (8€/tab)\n"
                "10 tabs : 70€ (7€/tab)\n"
                "25 tabs : 125€ (5€/tab)\n"
                "dm per quantità maggiori\n\n"
                "L$D reale e di alta qualità, testata con reagenti;\n"
                "Stampa ‘Hoffman 80th’.\n"
                "spedizione e stealth : 10€"
            ),
            "video_file_id": None,
        },
        "psy_dmt_cart": {
            "category": "psichedelici",
            "name": "🤩 DMT 1ml cart 0.6gr/ml 🫥🫨",
            "caption": (
                "1 cart : 90€\n"
                "2 carts : 160€\n"
                "3 carts : 220€\n\n"
                "Cart da 1ml con 0.6gr di purissima DMT, la concentrazione più alta possibile, "
                "un paio di tiri per un breakthrough assicurato;\n"
                "È compresa nel prezzo anche la batteria ricaricabile e dal voltaggio regolabile per poter iniziare da subito.\n"
                "spedizione e stealth : 10€"
            ),
            "video_file_id": None,
        },
    
        # cannabis
        "can_gelato33": {
            "category": "cannabis",
            "name": "🍦 GELATO #33 🇺🇸🛫🇮🇹",
            "caption": (
                "3.5 gr : 50€ (14.3€/gr)\n"
                "10 gr : 90€ (9€/gr)\n"
                "20 gr : 170€ (8.5€/gr)\n"
                "25 gr : 190€ (7.6€/gr)\n\n"
                "Importata direttamente dalla California!\n"
                "Creato dall'unione tra Sunset Sherbet e Thin Mint GSC, ibrido con effetti potenti (~25% THC). "
                "Rilassa ma resta funzionale e vigile.\n"
                "Profilo dolce e goloso; effetti edificanti e stimolanti.\n"
                "spedizione e stealth : 10€"
            ),
            "video_file_id": None,
        },
        "can_svapo_thc_2ml": {
            "category": "cannabis",
            "name": "😶‍🌫️ Svapo THC 2ml 🫨💨",
            "caption": (
                "1 pod : 80€\n"
                "2 pods : 140€ (70€/pod)\n"
                "3 pods : 165€ (55€/pod)\n"
                "5 pods : 250€ (50€/pod)\n\n"
                "Svapo “PackMan” con 2ml di estratto di prima qualità!\n"
                "strain disponibili:\n"
                " - Kiwi KushBerry\n"
                " - Strawberry Slurricane\n"
                " - Blue Razzle Runtz\n"
                " - Gobstopper Gumdrop\n"
                "spedizione e stealth : 10€"
            ),
            "video_file_id": None,
        },
        "can_fruit_bert": {
            "category": "cannabis",
            "name": "🍃 FRUIT BERT 🍋🍇🍉",
            "caption": (
                "10 gr : 100€ (10€/gr)\n"
                "25 gr : 200€ (8€/gr)\n"
                "50 gr : 350€ (7€/gr)\n"
                "100 gr : 600€ (6€/gr)\n\n"
                "Ideale per gli amanti dei sapori fruttati, effetti euforici ed energizzanti.\n"
                "spedizione e stealth : 10€"
            ),
            "video_file_id": None,
        },
        "can_cookies_kush": {
            "category": "cannabis",
            "name": "🍃 COOKIES KUSH 🍪😋",
            "caption": (
                "10 gr : 100€ (10€/gr)\n"
                "25 gr : 200€ (8€/gr)\n"
                "50 gr : 350€ (7€/gr)\n"
                "100 gr : 600€ (6€/gr)\n\n"
                "Dominanza indica, relax mentale e fisico; aromi dolci e terrosi.\n"
                "spedizione e stealth : 10€"
            ),
            "video_file_id": None,
        },
        "can_ice_rock": {
            "category": "cannabis",
            "name": "🍃 ICE ROCK 🧊",
            "caption": (
                "5 gr : 100€ (20€/gr)\n"
                "10 gr : 180€ (18€/gr)\n"
                "15 gr : 240€ (16€/gr)\n"
                "25 gr : 350€ (14€/gr)\n"
                "50 gr : 550€ (11€/gr)\n"
                "100 gr : 900€ (9€/gr)\n\n"
                "Fiori ricoperti da hash oil e cristalli di THC.\n"
                "spedizione e stealth : 10€"
            ),
            "video_file_id": None,
        },
        "can_moon_rock": {
            "category": "cannabis",
            "name": "🍃 MOON ROCK 🌖",
            "caption": (
                "5 gr : 100€ (20€/gr)\n"
                "10 gr : 180€ (18€/gr)\n"
                "15 gr : 240€ (16€/gr)\n"
                "25 gr : 350€ (14€/gr)\n"
                "50 gr : 550€ (11€/gr)\n"
                "100 gr : 900€ (9€/gr)\n\n"
                "Fiori ricoperti da hash oil e successivamente di kief.\n"
                "spedizione e stealth : 10€"
            ),
            "video_file_id": None,
        },
    }
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
            [InlineKeyboardButton("💰 Pagamenti", callback_data="payments")],
            [InlineKeyboardButton("🏷️ Promo", callback_data="promo")],
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
            
                if d == "payments":
            kb = [[InlineKeyboardButton("⬅️ Indietro", callback_data="back_to_home")]]
            sent = await context.bot.send_message(
                chat_id=cid,
                text=(
                    "💰 Pagamenti\n\n"
                    "Unico metodo di pagamento accettato: crypto (solo BTC, LTC e XMR).\n"
                    "Escrow accettato (solo conosciuti ed affidabili), spese di commissione a carico del cliente.\n\n"
                    "📦 Spedizione & stealth: 10€ con InPost, UPS o BRT."
                ),
                reply_markup=InlineKeyboardMarkup(kb)
            )
            context.user_data["last_menu_msg_id"] = sent.message_id
            return

        if d == "promo":
            kb = [[InlineKeyboardButton("⬅️ Indietro", callback_data="back_to_home")]]
            sent = await context.bot.send_message(
                chat_id=cid,
                text="🏷️ Promo\n\nSconto di 10€ sull'ordine successivo se viene effettuata recensione onesta, ben curata e con fotografia.",
                reply_markup=InlineKeyboardMarkup(kb)
            )
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
            
        cat_key = d.split("_", 1)[1]
        if cat_key == "pharma":
            kb = [[InlineKeyboardButton("⬅️ Indietro", callback_data="menu")]]
            sent = await context.bot.send_message(
                chat_id=cid,
                text="🤫 per più info: @GI0VANEBANDIT0",
                reply_markup=InlineKeyboardMarkup(kb)
            )
            context.user_data["last_menu_msg_id"] = sent.message_id
            return

          

                # ---------- CATEGORIA ---------- #
                if d.startswith("cat_"):
                    cat_key = d.split("_", 1)[1]
        
                    # Special Pharma info page
                    if cat_key == "pharma":
                        kb = [[InlineKeyboardButton("⬅️ Indietro", callback_data="menu")]]
                        sent = await context.bot.send_message(
                            chat_id=cid,
                            text="🤫 per più info: @GI0VANEBANDIT0",
                            reply_markup=InlineKeyboardMarkup(kb)
                        )
                        context.user_data["last_menu_msg_id"] = sent.message_id
                        return
        
                    # Normal category flow
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
            elif prod.get("photo_file_id"):
                try:
                    sent = await context.bot.send_photo(
                        chat_id=cid,
                        photo=prod["photo_file_id"],
                        caption=caption,
                        parse_mode=ParseMode.MARKDOWN,
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
