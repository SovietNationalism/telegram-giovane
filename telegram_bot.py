import os, sys, logging, json, asyncio, tempfile
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes
)
from telegram.error import BadRequest

# ─────────────────────────  CONFIG  ───────────────────────── #

BOT_TOKEN         = os.getenv("BOT_TOKEN")
ADMIN_USER_IDS    = {6840588025, 7602444648} 
USERS_DB = "users.json"

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
    "Reship del 100% in caso di pacco smarrito o bloccato per errori del vendor nelle spedizioni tramite corriere (BRT e UPS);\n"
    "Reship del 50% in caso di pacco smarrito o bloccato per errori del vendor nelle spedizioni tramite InPost;\n"
    "Reship del 100% in caso di pacco manomesso durante la spedizione e privo dei prodotti ordinati (dimostrabile solo tramite video chiaro e ben visibile del momento del ritiro del pacco e successivamente della sua apertura).\n\n"
    "Refund del 50% in caso di pacco smarrito o bloccato per errori del vendor nelle spedizioni tramite corriere (BRT e UPS);\n"
    "Nessun refund in caso di pacco smarrito o bloccato per errori del vendor nelle spedizioni tramite InPost;\n"
    "Refund del 50% in caso di pacco manomesso durante la spedizione e privo dei prodotti ordinati (dimostrabile solo tramite video chiaro e ben visibile del momento del ritiro del pacco e successivamente della sua apertura).\n\n"
    "Reship e refund erogati solo dopo piena certezza del pacco perso (tracking) o manomesso (video).\n\n"
)

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
            "photo_file_id": "AgACAgQAAxkBAAORaOmu4cp3K785y2A-fac-55vCnZEAAlzJMRtPrVBTESIowOQ_yjABAAMCAAN4AAM2BA",
        },
        "cs_k2_spice": {
            "category": "cannabis_sintetica",
            "name": "🍃 K2 | SPICE 🤯",
            "caption": (
                "Bags da 3gr:\n"
                "2 bags : 70€ (35€ x bag)\n"
                "5 bags : 120€ (24€ x bag)\n"
                "10 bags : 180€ (18€ x bag)\n\n"
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
        
        # synth
        "syn_mdma_champ": {
            "category": "sintetiche",
            "name": "🍾MDMA Champagne😍🥂",
            "caption": (
                "1 gr : 30€\n"
                "3 gr : 60€ (20€/gr)\n"
                "10 gr : 150€ (15€/gr)\n"
                "20 gr : 220€ (11€/gr)\n"
                "50 gr : 400€ (8€/gr)\n"
                "100 gr : 600€ (6€/gr)\n\n"
                "MDMA Champagne, prodotto nei migliori laboratori olandesi;\n"
                "Cristalli puliti e puri, elevata potenza (purezza del 87%).\n"
                "spedizione e stealth : 10€"
            ),
            "video_file_id": None,
        },
        "syn_tucibi": {
            "category": "sintetiche",
            "name": "👛TUCIBI | C0CA ROSA💕",
            "caption": (
                "1 gr : 50€\n"
                "3 gr : 120€ (40€/gr)\n"
                "5 gr : 175€ (35€/gr)\n"
                "10 gr : 300€ (30€/gr)\n\n"
                "Direttamente dalla Colombia;\n"
                "Un mix, prodotto secondo la ricetta originale: 2c-b, keta, mdma e coca;\n"
                "Effetti magici, stimolanti e psichedelici.\n"
                "spedizione e stealth : 10€"
            ),
            "video_file_id": None,
        },
        "syn_keta_spray": {
            "category": "sintetiche",
            "name": "👨‍⚕️spray nasale K3TAM1NA🚨🆕",
            "caption": (
                "10 ml (100 spruzzi) : 90€\n"
                "30 ml (300 spruzzi) : 140€\n\n"
                "Pratica, veloce, discreta, delicata per il naso e facilissima da dosare.\n"
                "Ogni spruzzo eroga circa 25mg di principio attivo (di grado farmaceutico).\n"
                "spedizione e stealth : 10€"
            ),
            "photo_file_id": "AgACAgQAAxkBAAIB12jq0H4D4pse5-c0s-yirJenQgpcAAIszDEb7-5ZU5HmAa-PqGKbAQADAgADeQADNgQ",
        },
        "syn_keta_needles": {
            "category": "sintetiche",
            "name": "❄️K3TAM1NA needles🐴 — isomero-S",
            "caption": (
                "2 gr : 30€ (15€/gr)\n"
                "5 gr : 60€ (12€/gr)\n"
                "10 gr : 90€ (9€/gr)\n"
                "25 gr : 150€ (6€/gr)\n"
                "50 gr : 250€ (5€/gr)\n\n"
                "Aghetti di prima qualità, puri e privi di taglio; Prezzo più basso in Italia!\n"
                "Andate piano con i dosaggi, è molto pura.\n"
                "spedizione e stealth : 10€"
            ),
            "photo_file_id": "AgACAgQAAxkBAAIB1Wjq0HrDmB5HhEJZlTx9QlBaLYUQAAIrzDEb7-5ZU5Av8hgm7wjMAQADAgADeQADNgQ",
        },
        
        # pharma #
        "ph_ossyrup": {
            "category": "pharma",
            "name": "🍼OSSYRUP😘",
            "caption": (
                "Ogni boccia contiene 200 ml\n\n"
                "1 boccia : 60€\n"
                "3 bocce : 150€ (50€/boccia)\n"
                "Lean homebrew, prodotta seguendo ricetta originale americana;\n"
                "Sciroppo viola, al gusto di fragola 🍓 e lamponi 🍇, contenente 0xi ed antistaminico;\n"
                "Dosaggi:\n"
                "              🟢basso : 30ml\n"
                "              🟡medio : 50 ml\n"
                "              🔴forte : 100 ml (⚠️ dosaggio molto elevato, fate attenzione!)\n\n"
                "Dimenticatevi la paracodina o le varie toseina/euphon/makatuassin, poco buone, molto deboli ed estremamente costose, OSSYRUP è il real deal!\n"
                "spedizione e stealth : 10€"
            ),
            "video_file_id": "BAACAgQAAxkBAAIBjGjqy32Nw8xXKYeN_8CFSeyaoEOtAALdFwAC7-5ZU7e7OyMM76sRNgQ",
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
            "photo_file_id": "AgACAgQAAxkBAAPNaOngF7GAFjTHp5DWapUMrZT9_BMAAmrJMRtPrVBTywr34WofmCABAAMCAAN5AAM2BA",
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
            "photo_file_id": "AgACAgQAAxkBAAPPaOngG9F0f4QvKfqt29vloaIlEP8AAmvJMRtPrVBTiOvQlWUfYc0BAAMCAAN5AAM2BA",
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
            "photo_file_id": "AgACAgQAAxkBAAIBTGjqvZAViZIH6CNVIFjmNvbomS_cAALtyzEb7-5ZUxfFLUhpXXiZAQADAgADeQADNgQ",
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
            "photo_file_id": "AgACAgQAAxkBAAIBTmjqvZNeLyckRDFPqLI3OXh-Nu_oAALvyzEb7-5ZUyVwgVoU1cwjAQADAgADeQADNgQ",
        },
    
        # cannabis
        "can_gelato33": {
            "category": "cannabis",
            "c_sub": "weed",
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
            "video_file_id": "BAACAgQAAxkBAAINZ2jvMps1PT-TnRZS_SWneMtQMZ6wAALOGgACOMZ5U1CQJUwVm66MNgQ",
        },
        "can_frozen_magic": {
            "category": "cannabis",
            "c_sub": "hashish",
            "name": "🍫 Frozen Magic Farms 🪄🍃",
            "caption": (
                "2.5 gr : 60€ (24€/gr)\n"
                "5 gr : 80€ (16€/gr)\n"
                "10 gr : 150€ (15€/gr)\n"
                "20 gr : 250€ (12.5€/gr)\n"
                "50 gr : 500€ (10€/gr)\n"
                "100 gr : 900€ (9€/gr)\n\n"
                "Frozen sift di qualità elevatissima, ovuli da 10g, curato alla perfezione;\n"
                "Un vero piacere da fumare: odore fresco ma saporito, dolce ed intenso, high potente;\n"
                "Livello e qualità superiori ai soliti dry e filtrati; per chi vuole solo il top!\n"
                "spedizione e stealth : 10€"
            ),
            "video_file_id": "BAACAgQAAxkBAAINv2jwWoXBzfgkOTCeWLPEnXpVVKY8AAJtGQAChq2IU5vtVjG_SmvfNgQ",
        },
        "can_thc_lean": {
            "category": "cannabis",
            "c_sub": "edibles",
            "name": "THC Lean",
            "caption": (
                "1 boccia / 45€\n"
                "2 boccie / 70€ (35€/boccia)\n"
                "3 boccie / 95€ (31.5€/boccia)\n\n"
                "Ogni boccietta contiene 300mg di THC;\n"
                "Prodotto con un estrazione QWET da drysift di altissima qualità, emulsionata in sciroppo dolce al lampone per stabilità e biodisponibilità superiori.\n"
                "Da mescolare con qualsiasi bevanda.\n"
                "Per un aggiunta di 5€, un sapore a richiesta (es. cola, passion fruit, mela, etc) può essere preparato.\n"
                "Dosaggio consigliato (2 mg/ml):\n"
                "🟢 Principianti: 10–15 mg (5–7.5 ml circa)\n"
                "🟡 Regolari: 25–35 mg (12.5–17.5 ml)\n"
                "🔴 Esperti: 50 + mg (25 ml e oltre)\n"
                "Ricordarsi che gli ml non equivalgono ai grammi."
                "spedizione e stealth : 10€"
            ),
            "photo_file_id": "AgACAgQAAxkBAAINvWjwWk064bhCcGbSLCgxie321UfxAAIWxzEbhq2IUylsiqIzDdgfAQADAgADeQADNgQ",
        },
        "can_svapo_thc_2ml": {
            "category": "cannabis",
            "c_sub": "vapes",
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
            "photo_file_id": "AgACAgQAAxkBAAIBVGjqvnO3xJniDk1Huj6JnEGii8ymAALyyzEb7-5ZUzQprivCR4gnAQADAgADeAADNgQ",
        },
        "can_muha_thc_2ml": {
            "category": "cannabis",
            "c_sub": "vapes",
            "name": "😶‍🌫️ Muha Meds THC Vape 2ml 🫨💨",
            "caption": (
                "1 pod : 90€\n"
                "5 pods : 350 (70€/pod)\n"
                "10 pods : 650€ (65€/pod)\n"
                "Svapo premium Americana “Muha Meds” con 2ml di estratto di prima qualità!\n"
                "strain disponibili:\n"
                " - Cereal Milk\n"
                " - Jedi Kush\n"
                " - Rainbow Belts\n"
                " - Lavender Haze\n"
                " - Truffle Butter\n"
                " - Purple Champagne\n"
                " - White Raspberry\n"
                " - Citrus Tsunami\n"
                " - Venom Og\n"
                " - Mango Peach Rings\n"
                "spedizione e stealth : 10€"
            ),
            "video_file_id": "BAACAgQAAxkBAAINaWjvMp5DdZjh_h0UGMTknjmglTMPAALPGgACOMZ5Ux1wOxAnnE3VNgQ",
        },
        "can_fruit_bert": {
            "category": "cannabis",
            "c_sub": "weed",
            "name": "🍃 FRUIT BERT 🍋🍇🍉",
            "caption": (
                "10 gr : 100€ (10€/gr)\n"
                "25 gr : 200€ (8€/gr)\n"
                "50 gr : 350€ (7€/gr)\n"
                "100 gr : 600€ (6€/gr)\n\n"
                "Ideale per gli amanti dei sapori fruttati, effetti euforici ed energizzanti.\n"
                "spedizione e stealth : 10€"
            ),
            "photo_file_id": "AgACAgQAAxkBAAIBUmjqvmTA89vDQ4MON4_NIISpz9uqAALxyzEb7-5ZU68V9S2QBG79AQADAgADeAADNgQ",
        },
        "can_cookies_kush": {
            "category": "cannabis",
            "c_sub": "weed",
            "name": "🍃 COOKIES KUSH 🍪😋",
            "caption": (
                "10 gr : 100€ (10€/gr)\n"
                "25 gr : 200€ (8€/gr)\n"
                "50 gr : 350€ (7€/gr)\n"
                "100 gr : 600€ (6€/gr)\n\n"
                "Dominanza indica, relax mentale e fisico; aromi dolci e terrosi.\n"
                "spedizione e stealth : 10€"
            ),
            "photo_file_id": "AgACAgQAAxkBAAPJaOnfu3lv2bCJkrkwvzSehP2UoOwAAmjJMRtPrVBTq9c17b1tJdsBAAMCAAN4AAM2BA",
        },
        "can_ice_rock": {
            "category": "cannabis",
            "c_sub": "weed",
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
            "photo_file_id": "AgACAgQAAxkBAAPLaOnfwD1Zu2_u5wMo3cWww_nM4ywAAmnJMRtPrVBTnVHKP0UswZcBAAMCAAN4AAM2BA",
        },
        "can_moon_rock": {
            "category": "cannabis",
            "c_sub": "weed",
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
            "photo_file_id": "AgACAgQAAxkBAAPHaOnfubuu2-OyqBQgHRwx3puj_NQAAmfJMRtPrVBT1DA48qsI0QoBAAMCAAN4AAM2BA",
        },
    }
        self._uids_lock = asyncio.Lock()
        self.user_ids = self._load_user_ids()
    
    async def _send_protected_photo(self, bot, chat_id, photo, caption, reply_markup):
        return await bot.send_photo(
            chat_id=chat_id,
            photo=photo,
            caption=caption,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup,
            protect_content=True
        )
    
    async def _send_protected_video(self, bot, chat_id, video, caption, reply_markup):
        return await bot.send_video(
            chat_id=chat_id,
            video=video,
            caption=caption,
            parse_mode=ParseMode.MARKDOWN,
            supports_streaming=True,
            reply_markup=reply_markup,
            protect_content=True
        )
    
    def _load_user_ids(self):
        try:
            with open(USERS_DB, "r", encoding="utf-8") as f:
                data = json.load(f)
                return set(int(x) for x in data)
        except FileNotFoundError:
            return set()
        except Exception as e:
            logger.warning(f"Failed to load {USERS_DB}: {e}")
            return set()
    
    async def _save_user_ids(self):
        async with self._uids_lock:
            try:
                tmp_fd, tmp_path = tempfile.mkstemp(prefix="users_", suffix=".json")
                with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
                    json.dump(sorted(self.user_ids), f, ensure_ascii=False)
                os.replace(tmp_path, USERS_DB)
            except Exception as e:
                logger.warning(f"Failed to save {USERS_DB}: {e}")
    
    async def add_user(self, uid: int):
        if uid not in self.user_ids:
            self.user_ids.add(uid)
            await self._save_user_ids()


    # ────────────────────  HELPER: relay  ─────────────────── #
    async def _relay_to_admin(self, context: ContextTypes.DEFAULT_TYPE, who, what: str) -> None:
        message = f"👤 {who.full_name} ({who.id})\n💬 {what}"
        logger.info(message)
        for admin_id in ADMIN_USER_IDS:
            try:
                await context.bot.send_message(admin_id, message)
            except Exception as e:
                logger.warning(f"Failed to relay to admin {admin_id}: {e}")
        
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
        
    def cannabis_products_keyboard(self, subkey: str) -> InlineKeyboardMarkup:
        rows = []
        for pid, p in self.products.items():
            if p.get("category") == "cannabis" and p.get("c_sub") == subkey:
                rows.append([InlineKeyboardButton(p.get("name", f"Prodotto {pid}"), callback_data=f"product_{pid}")])
        rows.append([InlineKeyboardButton("⬅️ Indietro", callback_data="cat_cannabis")])
        return InlineKeyboardMarkup(rows)

    def categories_keyboard(self) -> InlineKeyboardMarkup:
        rows, row = [], []
        for key, label in CATEGORIES:
            row.append(InlineKeyboardButton(label, callback_data=f"cat_{key}"))
            if len(row) == 2:
                rows.append(row); row = []
        if row:
            rows.append(row)
        rows.append([InlineKeyboardButton("⬅️ Indietro", callback_data="back_to_home")])
        return InlineKeyboardMarkup(rows)

    def products_keyboard(self, cat_key: str):
        prod_rows = []
        for pid, p in self.products.items():
            if p.get("category") == cat_key:
                prod_rows.append([InlineKeyboardButton(p.get("name", f"Prodotto {pid}"), callback_data=f"product_{pid}")])
        prod_rows.append([InlineKeyboardButton("⬅️ Indietro", callback_data="menu")])
        return InlineKeyboardMarkup(prod_rows)
        
    def cannabis_subcategories_keyboard(self) -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🌿 Erba",     callback_data="csub_weed"),
                InlineKeyboardButton("💨 Svapo",    callback_data="csub_vapes"),
            ],
            [
                InlineKeyboardButton("🍪 Edibili",  callback_data="csub_edibles"),
                InlineKeyboardButton("🍫 Hashish",  callback_data="csub_hashish"),
            ],
            [InlineKeyboardButton("⬅️ Indietro", callback_data="menu")]
        ])

    # ────────────────────────  COMMANDS  ──────────────────────── #
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await self.add_user(update.effective_user.id)
        await self.delete_last_menu(context, update.effective_chat.id)

        m = update.effective_message
        try:
            sent = await self._send_protected_photo(
                context.bot,
                update.effective_chat.id,
                WELCOME_IMAGE_URL,
                WELCOME_TEXT,
                self.home_keyboard()
            )
            context.user_data["last_menu_msg_id"] = sent.message_id
        except BadRequest:
            sent = await m.reply_text(text=WELCOME_TEXT, reply_markup=self.home_keyboard())
            context.user_data["last_menu_msg_id"] = sent.message_id

    async def broadcast(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id not in ADMIN_USER_IDS:
            await update.message.reply_text("❌ Non sei autorizzato a usare questo comando.")
            return
        if not context.args:
            await update.message.reply_text("❗ Usa correttamente: /broadcast <messaggio>")
            return
    
        message = " ".join(context.args)
        sent_ok, removed = 0, 0
        for uid in list(self.user_ids):
            try:
                await context.bot.send_message(uid, f"📢 {message}")
                sent_ok += 1
            except Exception as e:
                logger.warning(f"Impossibile inviare a {uid}: {e}")
                self.user_ids.discard(uid)
                removed += 1
        if removed:
            await self._save_user_ids()
        await update.message.reply_text(f"✅ Inviati: {sent_ok} | Rimossi: {removed}")

    # ────────────────────────  CALLBACKS  ──────────────────────── #
    async def button_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        q   = update.callback_query
        d   = q.data
        cid = q.message.chat.id
        await self.add_user(update.effective_user.id)
    
        await q.answer()
    
        if update.effective_user.id not in ADMIN_USER_IDS:
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

        # ---------- CATEGORIA ---------- #
        if d.startswith("cat_"):
            cat_key = d.split("_", 1)[1]
        
            # Cannabis -> show the 2x2 subcategory keyboard
            if cat_key == "cannabis":
                sent = await context.bot.send_message(
                    chat_id=cid,
                    text="🍃 Cannabis — scegli una sottocategoria:",
                    reply_markup=self.cannabis_subcategories_keyboard()
                )
                context.user_data["last_menu_msg_id"] = sent.message_id
                return
        
            # Pharma special submenu (product + DM + back)
            if cat_key == "pharma":
                rows = []
                if "ph_ossyrup" in self.products:
                    rows.append([InlineKeyboardButton(self.products["ph_ossyrup"]["name"], callback_data="product_ph_ossyrup")])
                rows.append([InlineKeyboardButton("🤫 Per più info", url=CONTACT_URL)])
                rows.append([InlineKeyboardButton("⬅️ Indietro", callback_data="menu")])
                sent = await context.bot.send_message(
                    chat_id=cid,
                    text="💊 Pharma — seleziona un’opzione:",
                    reply_markup=InlineKeyboardMarkup(rows)
                )
                context.user_data["last_menu_msg_id"] = sent.message_id
                return
        
            # Normal categories
            has_any = any(p.get("category") == cat_key for p in self.products.values())
            if has_any:
                title = dict(CATEGORIES).get(cat_key, cat_key)
                extra = "\n\nEffetti analoghi al THC delta 9 senza essere rilevabili da test antidroga." if cat_key == "cannabis_sintetica" else ""
                sent = await context.bot.send_message(
                    chat_id=cid,
                    text=f"{title} — Prodotti disponibili:{extra}",
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

        # ---------- CANNABIS SUBCATS ---------- #
        if d in ("csub_weed", "csub_vapes", "csub_edibles", "csub_hashish"):
            sub = d.split("_", 1)[1]
            mapping = {
                "weed": "🌿 WEED",
                "vapes": "💨 VAPES",
                "edibles": "🍪 EDIBLES",
                "hashish": "🍫 HASHISH",
            }
            title = mapping.get(sub, sub.upper())
            has_any = any(
                p.get("category") == "cannabis" and p.get("c_sub") == sub
                for p in self.products.values()
            )
            if has_any:
                sent = await context.bot.send_message(
                    chat_id=cid,
                    text=f"{title} — Prodotti disponibili:",
                    reply_markup=self.cannabis_products_keyboard(sub)
                )
            else:
                sent = await context.bot.send_message(
                    chat_id=cid,
                    text=f"{title}\n\nNessun prodotto in questa sottocategoria al momento.",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Indietro", callback_data="cat_cannabis")]])
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
        
            # Build caption
            caption = prod.get("caption") or "\n".join(filter(None, [
                f"📦 *{prod.get('name','Prodotto')}*",
                f"💵 Prezzo:\n{(prod.get('price') or '').strip()}" if prod.get("price") else "",
                f"📝 Descrizione: {(prod.get('description') or '').strip()}" if prod.get("description") else ""
            ]))
        
            # Decide where Back goes:
            # - cannabis items with c_sub -> back to that subcategory
            # - everything else -> back to its category
            cat_key = prod.get("category") or ""
            c_sub = prod.get("c_sub")
            if cat_key == "cannabis" and c_sub:
                back_cb = f"csub_{c_sub}"
            else:
                back_cb = f"cat_{cat_key}" if cat_key else "menu"
            kb_back = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Indietro", callback_data=back_cb)]])
        
            # Send media or text with the keyboard
            if prod.get("video_file_id"):
                try:
                    sent = await self._send_protected_video(
                        context.bot,
                        cid,
                        prod["video_file_id"],
                        caption,
                        kb_back
                    )
                    context.user_data["last_menu_msg_id"] = sent.message_id
                except BadRequest:
                    sent = await context.bot.send_message(
                        chat_id=cid, text=caption, parse_mode=ParseMode.MARKDOWN, reply_markup=kb_back
                    )
                    context.user_data["last_menu_msg_id"] = sent.message_id
            elif prod.get("photo_file_id"):
                try:
                    sent = await self._send_protected_photo(
                        context.bot,
                        cid,
                        prod["photo_file_id"],
                        caption,
                        kb_back
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
        await self.add_user(usr.id)

        if usr and usr.id not in ADMIN_USER_IDS: 
            txt = (
                m.text or m.caption or
                (f"<{type(m.effective_attachment).__name__}>" if m.effective_attachment else "<no text>")
            )
            await self._relay_to_admin(context, usr, txt)

        if usr and usr.id in ADMIN_USER_IDS:
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
