"""Other services for the @mame_posts bot.

* "Other services" sub-menu (more services can be added here later)
* Photo -> PDF   (up to 10 photos, "original quality" or "scan" look)
* Daily gift     (+2 extra downloads every day, +10 more on every 7th day in a row)

Nothing the user sends is stored: only Telegram file ids are kept in memory while the
user is collecting photos; the photos are downloaded when the PDF is made and thrown
away right after.
"""
import asyncio
import html
import io
import os
import random
import re
import shutil
import subprocess
import tempfile
import time
from datetime import timedelta
from urllib.parse import quote

try:
    from PIL import Image, ImageChops, ImageFilter, ImageOps
    HAVE_PIL = True
except ImportError:             # Pillow missing -> only the PDF tool is switched off, the bot keeps running
    HAVE_PIL = False
    print("⚠️ Pillow is not installed: add 'pillow' to requirements.txt to enable Photo -> PDF")
from telegram import InlineKeyboardMarkup
from telegram.ext import ApplicationHandlerStop, CallbackQueryHandler, MessageHandler, filters

from growth import Bt, attempt, bump_stat, eat_day, utcnow

MAX_PHOTOS = int(os.environ.get("PDF_MAX_PHOTOS", "10"))
PDF_DAILY = int(os.environ.get("PDF_DAILY_LIMIT", "5"))
PDF_TTL = 30 * 60                       # a half finished PDF is forgotten after 30 minutes
MAX_FILE = 20 * 1024 * 1024             # Telegram bots cannot download bigger files
MAX_PDF = 49 * 1024 * 1024              # Telegram bots cannot upload bigger files
DAILY_LIMIT = int(os.environ.get("DAILY_LIMIT", "10"))
GIFT_BONUS = int(os.environ.get("GIFT_BONUS", "2"))
VM_DAILY = int(os.environ.get("VOICE_DAILY_LIMIT", "15"))     # Voice <-> MP3 conversions per user per day
VM_MAX_MIN = int(os.environ.get("VOICE_MAX_MIN", "10"))        # longest audio we convert (minutes)
VM_TTL = 30 * 60
STREAK_BONUS = int(os.environ.get("GIFT_STREAK_BONUS", "10"))
STREAK_DAYS = 7

# ---------------- premium emoji ----------------
EM = {
    "svc": ("5305677335310147047", "🙂"),
    "photo": ("5257974976094412956", "🖼"),
    "pdf": ("5258477770735885832", "📄"),
    "trash": ("5258130763148172425", "🗑"),
    "cross": ("5260342697075416641", "❌"),
    "wait": ("6050887597486513073", "⏳"),
    "done": ("5305749202997911340", "✔️"),
    "again": ("6005843436479975944", "🔁"),
    "link": ("5042101437237036298", "🔗"),
    "rocket": ("5379614492936122870", "🚀"),
    "gift": ("5041975203853239332", "🎁"),
    "ok": ("5260463209562776385", "✅"),
    "pen": ("5305789043114549850", "✍️"),
    "art": ("5904516155715883760", "🎨"),
    "hundred": ("5042297717242463211", "💯"),
    "mic1": ("5321004106494526877", "🎤"),
    "mic2": ("5990251773187593445", "🎤"),
    "hp": ("5307705891313721642", "🎧"),
}
ICON = {k: v[0] for k, v in EM.items()}
ICON["back"] = "5248948801674159296"


def em(key):
    cid, ch = EM[key]
    return f'<tg-emoji emoji-id="{cid}">{ch}</tg-emoji>'


EMJ = {k: em(k) for k in EM}

# ---------------- Fancy Text engine ----------------
FANCY_MAX = int(os.environ.get("FANCY_MAX", "40"))      # longest text we accept
FANCY_TTL = 30 * 60
_UP = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
_LO = "abcdefghijklmnopqrstuvwxyz"
_DG = "0123456789"


def _mk(up=None, lo=None, dg=None, exc=None, upper_only=False):
    m = {}
    for i, c in enumerate(_UP):
        if up is not None:
            m[c] = chr(up + i)
    for i, c in enumerate(_LO):
        if lo is not None:
            m[c] = chr(lo + i)
        elif up is not None and upper_only:
            m[c] = chr(up + i)
    if dg is not None:
        for i, c in enumerate(_DG):
            m[c] = chr(dg + i)
    m.update(exc or {})
    return m


_SMALL = dict(zip(_LO, "ᴀʙᴄᴅᴇꜰɢʜɪᴊᴋʟᴍɴᴏᴘǫʀꜱᴛᴜᴠᴡxʏᴢ"))
_SMALL.update({k.upper(): v for k, v in _SMALL.items()})
_MIX = dict(zip(_LO, "αв¢∂єƒgнιנкℓмησρqя" + "ѕтυνωχуz"))
_MIX.update({k.upper(): v for k, v in _MIX.items()})
_CIRCLE_DIGITS = {"0": "\u24ea", **{str(i): chr(0x2460 + i - 1) for i in range(1, 10)}}

_STYLES = [
    _mk(0x1D4D0, 0x1D4EA),                                                      # 𝓜𝓪𝓶𝓮
    _mk(0x1D400, 0x1D41A, 0x1D7CE),                                             # 𝐌𝐚𝐦𝐞
    _mk(0x1D434, 0x1D44E, None, {"h": "\u210e"}),                               # 𝑀𝑎𝑚𝑒
    _mk(0x1D468, 0x1D482),                                                      # 𝑴𝒂𝒎𝒆
    _mk(0x1D538, 0x1D552, 0x1D7D8, {"C": "\u2102", "H": "\u210d", "N": "\u2115", "P": "\u2119",
                                    "Q": "\u211a", "R": "\u211d", "Z": "\u2124"}),   # 𝕄𝕒𝕞𝕖
    _mk(0x1D504, 0x1D51E, None, {"C": "\u212d", "H": "\u210c", "I": "\u2111", "R": "\u211c",
                                 "Z": "\u2128"}),                                # 𝔐𝔞𝔪𝔢
    _mk(0x1D56C, 0x1D586),                                                      # 𝕸𝖆𝖒𝖊
    _mk(0x1D5D4, 0x1D5EE, 0x1D7EC),                                             # 𝗠𝗮𝗺𝗲
    _mk(0x1D608, 0x1D622),                                                      # 𝘔𝘢𝘮𝘦
    _mk(0x1D670, 0x1D68A, 0x1D7F6),                                             # 𝙼𝚊𝚖𝚎
    _SMALL,                                                                     # ᴍᴀᴍᴇ
    _MIX,                                                                       # мαмє
    _mk(0x24B6, 0x24D0, None, _CIRCLE_DIGITS),                                  # Ⓜⓐⓜⓔ
    _mk(0x1F150, upper_only=True),                                              # 🅜🅐🅜🅔
    _mk(0x1F130, upper_only=True),                                              # 🄼🄰🄼🄴
    _mk(0x1F170, upper_only=True),                                              # 🅼🅰🅼🅴
    _mk(0xFF21, 0xFF41, 0xFF10, {" ": "\u3000"}),                               # Ｍａｍｅ
]
_DECOS = ["★彡 {t} 彡★", "『 {t} 』", "「 {t} 」", "✨ {t} ✨", "ღ {t} ღ", "⚡ {t} ⚡", "🔥 {t} 🔥", "•°•{t}•°•"]


def fancy_lines(text):
    """-> (has_latin, [styled strings]).  Latin styles only change A-Z a-z 0-9;
    underline, strike-through and the decorations work for ANY text (also Amharic)."""
    latin = bool(re.search(r"[A-Za-z0-9]", text))
    out = []
    if latin:
        out += ["".join(m.get(ch, ch) for ch in text) for m in _STYLES]
    out.append("".join(ch if ch.isspace() else ch + "\u0332" for ch in text))
    out.append("".join(ch if ch.isspace() else ch + "\u0336" for ch in text))
    out += [d.replace("{t}", text) for d in _DECOS]
    seen, uniq = set(), []
    for x in out:
        if x not in seen:
            seen.add(x)
            uniq.append(x)
    return latin, uniq


# ---------------- Voice <-> MP3 converter ----------------
_vm_sem = None
VM_AUDIO_EXT = (".mp3", ".m4a", ".wav", ".ogg", ".oga", ".opus", ".flac", ".aac", ".wma", ".amr")


def vm_semaphore():
    global _vm_sem
    if _vm_sem is None:
        _vm_sem = asyncio.Semaphore(3)         # at most 3 conversions at the same time
    return _vm_sem


def clean_name(text):
    name = re.sub(r'[\\/:*?"<>|\r\n\t]+', " ", text or "")
    name = re.sub(r"\s+", " ", name).strip()
    name = re.sub(r"(?i)\.mp3$", "", name).strip(" .")
    return name[:60]


def random_name():
    return f"Audio_{eat_day().replace('-', '')}_{random.randint(1000, 9999)}"


def convert_audio(data, kind):
    """kind 'to_mp3' (voice message -> MP3 file) or 'to_voice' (MP3/audio file -> voice message).
    Blocking: run it with asyncio.to_thread. Returns the converted bytes."""
    ffmpeg = shutil.which("ffmpeg") or "ffmpeg"
    folder = tempfile.mkdtemp(prefix="vm_")
    try:
        src = os.path.join(folder, "in.bin")
        dst = os.path.join(folder, "out." + ("mp3" if kind == "to_mp3" else "ogg"))
        with open(src, "wb") as f:
            f.write(data)
        if kind == "to_mp3":
            cmd = [ffmpeg, "-y", "-i", src, "-vn", "-acodec", "libmp3lame", "-q:a", "2", dst]
        else:   # Telegram shows a real voice message only for OPUS inside OGG
            cmd = [ffmpeg, "-y", "-i", src, "-vn", "-ac", "1", "-ar", "48000", "-c:a", "libopus",
                   "-b:a", "32k", "-application", "voip", "-f", "ogg", dst]
        res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=180)
        if res.returncode != 0 or not os.path.exists(dst) or os.path.getsize(dst) == 0:
            raise RuntimeError("ffmpeg failed")
        with open(dst, "rb") as f:
            return f.read()
    finally:
        shutil.rmtree(folder, ignore_errors=True)


# ---------------- texts (all bold, 3 languages) ----------------
TX = {
    "am": {
        "svc_title": "{svc} <b>ሌሎች አገልግሎቶች</b>\n\n<b>የሚፈልጉትን አገልግሎት ይምረጡ፦</b>",
        "svc_pdf": "ፎቶ ➝ PDF",
        "svc_vm": "ድምጽ ⇄ MP3 | Voice ⇄ MP3",
        "vm_intro": ("{mic1} <b>ድምጽ ⇄ MP3</b> {hp} <b>| Voice</b> {mic2} <b>⇄ MP3</b> {hp}\n\n"
                     "<b>ፋይል ይላኩ፤ ቦቱ ራሱ ይለያል፦</b>\n"
                     "{hp} <b>MP3 / ዘፈን ፋይል ➝ የድምጽ መልዕክት (Voice)</b>\n"
                     "{mic1} <b>የድምጽ መልዕክት ➝ MP3 ፋይል</b>\n\n"
                     "<b>ከፍተኛ {mb}MB እና {mins} ደቂቃ።</b>\n\n"
                     "{hp} {again}{mic1}"),
        "vm_name": ("{ok} <b>የድምጽ መልዕክትዎ ተቀብለናል!</b>\n\n"
                    "{pen} <b>ለ MP3 ፋይሉ ስም ይጻፉ፦</b>\n"
                    "<b>ወይም «ራንደም ስም» ይጫኑ።</b>"),
        "vm_making": "{wait} <b>እየተሰራ ነው...</b>",
        "vm_done_mp3": "{done} <b>MP3 ፋይልዎ ዝግጁ ነው</b> @{bot}\n\n{hp} {again}{mic1}",
        "vm_done_voice": "{done} <b>የድምጽ መልዕክትዎ ዝግጁ ነው</b> @{bot}\n\n{hp} {again}{mic1}",
        "vm_big": "{cross} <b>ፋይሉ ከ {mb}MB በላይ ነው።</b>",
        "vm_long": "{cross} <b>ርዝመቱ ከ {mins} ደቂቃ በላይ ነው።</b>",
        "vm_notaudio": "<b>እባክዎ MP3 ወይም የድምጽ ፋይል / የድምጽ መልዕክት ይላኩ።</b>",
        "vm_fail": "{cross} <b>መቀየር አልተቻለም። ሌላ ፋይል ይሞክሩ።</b>",
        "vm_limit": "{cross} <b>ዛሬ {limit} ጊዜ ተጠቅመዋል።</b>\n\n<b>ነገ (ከኢትዮጵያ እኩለ ሌሊት በኋላ) ይሞክሩ።</b>",
        "vm_again": "አዲስ ፋይል",
        "vm_random": "🎲 ራንደም ስም",
        "vm_cancel": "ሰርዝ",
        "svc_fancy": "ስም ማሳመሪያ | Fancy Text",
        "f_intro": ("{pen} <b>ስም ማሳመሪያ</b>\n\n"
                    "{art} <b>ስማችሁን ውብ አድርጉ፦</b>\n\n"
                    "<b>ስማችሁን ወይም ማንኛውንም ጽሑፍ በእንግሊዝኛ ፊደል ይጻፉ።</b>\n"
                    "<b>ምሳሌ፦ Mame ➝ 𝓜𝓪𝓶𝓮 · 𝐌𝐚𝐦𝐞 · мαмє · ᴍᴀᴍᴇ እና ወደ ሌሎችም....</b>\n"
                    "<b>ከውጤቱ የወደዳችሁትን ነክታችሁ Copy ማድረግ ትችላላችሁ።</b> {hundred}"),
        "f_result": "{art} <b>ውጤቱ ይኸው፦</b>",
        "f_tap": "{hundred} <b>የወደዳችሁትን ነክታችሁ Copy አድርጉ።</b>",
        "f_nolatin": "<b>የአማርኛ ፊደል አይቀየርም፤ ለአማርኛ ማስጌጫዎች ብቻ ተሰጥተዋል።</b>",
        "f_long": "<b>ጽሑፉ ረጅም ነው፤ ከ {max} ፊደል አይበልጥ።</b>",
        "f_again": "አዲስ ጽሑፍ",
        "f_back": "ወደ ሌሎች አገልግሎቶች",
        "svc_gift": "ዕለታዊ ስጦታ",
        "intro": ("{photo} <b>ፎቶ ➝</b> {pdf} <b>PDF</b>\n\n"
                  "<b>ፎቶዎችዎን ይላኩ (እስከ {max} ፎቶ)።</b>\n"
                  "<b>ለተሻለ ጥራት ፎቶውን እንደ File (Document) ይላኩ።</b>\n"
                  "<b>ሲጨርሱ «PDF ስራ» ይጫኑ።</b>"),
        "status": ("{photo} <b>የተቀበልኳቸው ፎቶዎች: {n} / {max}</b>\n\n"
                   "<b>ተጨማሪ ፎቶ መላክ ይችላሉ፣ ሲጨርሱ «PDF ስራ» ይጫኑ።</b>"),
        "choose": ("{pdf} <b>የ PDF አይነት ይምረጡ፦</b>\n\n"
                   "{photo} <b>ዋናው ጥራት — ፎቶው እንዳለ</b>\n"
                   "{pdf} <b>Scan | ስካን — ጥቁር-ነጭ፣ ብሩህ እና ጥርት ያለ (ለሰነድ)</b>"),
        "making": "{wait} <b>PDF'ኡ እየተሰራ ነው...</b>",
        "ready": "{done} <b>PDF'ዎ ዝግጁ ነው — {pages} ገጽ</b>\n\n<b>@{bot}</b>",
        "skipped": "\n<b>⚠️ {k} ፋይል ማንበብ አልተቻለም (ተዘሏል)።</b>",
        "cancelled": "{trash} <b>ተሰርዟል።</b>",
        "too_many": "<b>⚠️ ከፍተኛው {max} ፎቶ ነው።</b>",
        "too_big": "<b>⚠️ ፋይሉ ከ 20MB በላይ ነው፤ ትንሽ ፋይል ይላኩ።</b>",
        "only_photos": "<b>⚠️ ፎቶ ብቻ ይላኩ።</b>",
        "no_photos": "መጀመሪያ ፎቶ ይላኩ",
        "expired": "ጊዜው አልፏል፤ እንደገና ይጀምሩ",
        "limit": "<b>⛔ ዛሬ የሚፈቀደውን {limit} PDF ጨርሰዋል።</b>\n\n<b>ነገ እንደገና ይሞክሩ (ቆጠራው በኢትዮጵያ ሰዓት እኩለ ሌሊት ይታደሳል)።</b>",
        "fail": "<b>💔 PDF መስራት አልተቻለም። ፎቶዎቹን ደግመው ይላኩ።</b>",
        "b_done": "PDF ስራ", "b_undo": "የመጨረሻውን አውጣ", "b_clear": "ሁሉንም ሰርዝ", "b_cancel": "ሰርዝ",
        "b_orig": "ዋናው ጥራት", "b_scan": "Scan | ስካን", "b_new": "አዲስ PDF", "b_share": "Share Bot 🚀",
        "share_text": "🔥 ፎቶዎችዎን ወደ PDF ይቀይሩ እና ቪዲዮ በነጻ ያውርዱ! ይህን ቦት ይሞክሩ:",
        "gift_new": ("{gift} <b>ዕለታዊ ስጦታ</b>\n\n{ok} <b>ዛሬ +{amount} ተጨማሪ ማውረድ አግኝተዋል!</b>\n\n"
                     "<b>🔥 ተከታታይ ቀን: {day} / {days}</b>\n"
                     "<b>በ{days}ኛው ተከታታይ ቀን +{bonus} ተጨማሪ ማውረድ ያገኛሉ።</b>\n\n"
                     "<b>📥 ዛሬ: {used} / {limit}</b>\n<b>ነገ እንደገና ይመለሱ!</b>"),
        "gift_again": ("{gift} <b>ዕለታዊ ስጦታ</b>\n\n<b>ዛሬ ስጦታዎን ወስደዋል ✅</b>\n\n"
                       "<b>🔥 ተከታታይ ቀን: {day} / {days}</b>\n"
                       "<b>📥 ዛሬ: {used} / {limit}</b>\n\n"
                       "<b>ነገ (በኢትዮጵያ ሰዓት እኩለ ሌሊት በኋላ) እንደገና ይውሰዱ!</b>"),
    },
    "en": {
        "svc_title": "{svc} <b>Other services</b>\n\n<b>Choose a service:</b>",
        "svc_pdf": "Photo ➝ PDF",
        "svc_vm": "Voice ⇄ MP3",
        "vm_intro": ("{mic1} <b>ድምጽ ⇄ MP3</b> {hp} <b>| Voice</b> {mic2} <b>⇄ MP3</b> {hp}\n\n"
                     "<b>Send a file, the bot detects the type:</b>\n"
                     "{hp} <b>MP3 / song file ➝ voice message</b>\n"
                     "{mic1} <b>Voice message ➝ MP3 file</b>\n\n"
                     "<b>Up to {mb}MB and {mins} minutes.</b>\n\n"
                     "{hp} {again}{mic1}"),
        "vm_name": ("{ok} <b>Your voice message is received!</b>\n\n"
                    "{pen} <b>Type a name for the MP3 file:</b>\n"
                    "<b>or press «Random name».</b>"),
        "vm_making": "{wait} <b>Working on it...</b>",
        "vm_done_mp3": "{done} <b>Your MP3 file is ready</b> @{bot}\n\n{hp} {again}{mic1}",
        "vm_done_voice": "{done} <b>Your voice message is ready</b> @{bot}\n\n{hp} {again}{mic1}",
        "vm_big": "{cross} <b>The file is bigger than {mb}MB.</b>",
        "vm_long": "{cross} <b>It is longer than {mins} minutes.</b>",
        "vm_notaudio": "<b>Please send an MP3 / audio file or a voice message.</b>",
        "vm_fail": "{cross} <b>Could not convert it. Please try another file.</b>",
        "vm_limit": "{cross} <b>You used it {limit} times today.</b>\n\n<b>Try again tomorrow (after midnight Ethiopia time).</b>",
        "vm_again": "New file",
        "vm_random": "🎲 Random name",
        "vm_cancel": "Cancel",
        "svc_fancy": "Fancy Text",
        "f_intro": ("{pen} <b>Fancy Text</b>\n\n"
                    "{art} <b>Make your name beautiful:</b>\n\n"
                    "<b>Type your name or any text in English letters.</b>\n"
                    "<b>Example: Mame ➝ 𝓜𝓪𝓶𝓮 · 𝐌𝐚𝐦𝐞 · мαмє · ᴍᴀᴍᴇ and many more....</b>\n"
                    "<b>Tap the style you like to copy it.</b> {hundred}"),
        "f_result": "{art} <b>Here you go:</b>",
        "f_tap": "{hundred} <b>Tap the style you like to copy it.</b>",
        "f_nolatin": "<b>Amharic letters do not change; only decorations are given for them.</b>",
        "f_long": "<b>That text is too long. Please keep it under {max} characters.</b>",
        "f_again": "New text",
        "f_back": "Back to Other services",
        "svc_gift": "Daily Gift",
        "intro": ("{photo} <b>Photo ➝</b> {pdf} <b>PDF</b>\n\n"
                  "<b>Send your photos (up to {max}).</b>\n"
                  "<b>For the best quality send them as a File (Document).</b>\n"
                  "<b>When you are done, press “Create PDF”.</b>"),
        "status": ("{photo} <b>Photos received: {n} / {max}</b>\n\n"
                   "<b>You can send more, or press “Create PDF”.</b>"),
        "choose": ("{pdf} <b>Choose the PDF type:</b>\n\n"
                   "{photo} <b>Original quality — photos as they are</b>\n"
                   "{pdf} <b>Scan — black & white, bright and sharp (for documents)</b>"),
        "making": "{wait} <b>Your PDF is being made...</b>",
        "ready": "{done} <b>Your PDF is ready — {pages} pages</b>\n\n<b>@{bot}</b>",
        "skipped": "\n<b>⚠️ {k} file(s) could not be read (skipped).</b>",
        "cancelled": "{trash} <b>Cancelled.</b>",
        "too_many": "<b>⚠️ The maximum is {max} photos.</b>",
        "too_big": "<b>⚠️ That file is bigger than 20MB. Please send a smaller one.</b>",
        "only_photos": "<b>⚠️ Please send photos only.</b>",
        "no_photos": "Send some photos first",
        "expired": "Session expired, please start again",
        "limit": "<b>⛔ You have used today's limit of {limit} PDFs.</b>\n\n<b>Try again tomorrow (it resets at midnight Ethiopia time).</b>",
        "fail": "<b>💔 The PDF could not be made. Please send the photos again.</b>",
        "b_done": "Create PDF", "b_undo": "Remove last", "b_clear": "Clear all", "b_cancel": "Cancel",
        "b_orig": "Original quality", "b_scan": "Scan (B&W)", "b_new": "New PDF", "b_share": "Share Bot 🚀",
        "share_text": "🔥 Turn photos into PDF and download videos for free! Try this bot:",
        "gift_new": ("{gift} <b>Daily Gift</b>\n\n{ok} <b>You got +{amount} extra downloads today!</b>\n\n"
                     "<b>🔥 Streak: day {day} / {days}</b>\n"
                     "<b>On every {days}th day in a row you get +{bonus} more.</b>\n\n"
                     "<b>📥 Today: {used} / {limit}</b>\n<b>Come back tomorrow!</b>"),
        "gift_again": ("{gift} <b>Daily Gift</b>\n\n<b>You already took today's gift ✅</b>\n\n"
                       "<b>🔥 Streak: day {day} / {days}</b>\n"
                       "<b>📥 Today: {used} / {limit}</b>\n\n"
                       "<b>Come back tomorrow (after midnight Ethiopia time)!</b>"),
    },
    "ar": {
        "svc_title": "{svc} <b>خدمات أخرى</b>\n\n<b>اختر الخدمة:</b>",
        "svc_pdf": "صورة ➝ PDF",
        "svc_vm": "صوت ⇄ MP3 | Voice ⇄ MP3",
        "vm_intro": ("{mic1} <b>صوت ⇄ MP3</b> {hp} <b>| Voice</b> {mic2} <b>⇄ MP3</b> {hp}\n\n"
                     "<b>أرسل ملفاً، والبوت يتعرف على نوعه:</b>\n"
                     "{hp} <b>ملف MP3 / أغنية ➝ رسالة صوتية</b>\n"
                     "{mic1} <b>رسالة صوتية ➝ ملف MP3</b>\n\n"
                     "<b>حتى {mb}MB و {mins} دقائق.</b>\n\n"
                     "{hp} {again}{mic1}"),
        "vm_name": ("{ok} <b>تم استلام رسالتك الصوتية!</b>\n\n"
                    "{pen} <b>اكتب اسماً لملف MP3:</b>\n"
                    "<b>أو اضغط «اسم عشوائي».</b>"),
        "vm_making": "{wait} <b>جاري المعالجة...</b>",
        "vm_done_mp3": "{done} <b>ملف MP3 جاهز</b> @{bot}\n\n{hp} {again}{mic1}",
        "vm_done_voice": "{done} <b>رسالتك الصوتية جاهزة</b> @{bot}\n\n{hp} {again}{mic1}",
        "vm_big": "{cross} <b>الملف أكبر من {mb}MB.</b>",
        "vm_long": "{cross} <b>المدة أطول من {mins} دقائق.</b>",
        "vm_notaudio": "<b>يرجى إرسال ملف MP3 / صوت أو رسالة صوتية.</b>",
        "vm_fail": "{cross} <b>تعذر التحويل. جرّب ملفاً آخر.</b>",
        "vm_limit": "{cross} <b>استخدمتها {limit} مرات اليوم.</b>\n\n<b>حاول غداً (بعد منتصف الليل بتوقيت إثيوبيا).</b>",
        "vm_again": "ملف جديد",
        "vm_random": "🎲 اسم عشوائي",
        "vm_cancel": "إلغاء",
        "svc_fancy": "زخرفة الأسماء | Fancy Text",
        "f_intro": ("{pen} <b>زخرفة الأسماء</b>\n\n"
                    "{art} <b>اجعل اسمك جميلاً:</b>\n\n"
                    "<b>اكتب اسمك أو أي نص بالأحرف الإنجليزية.</b>\n"
                    "<b>مثال: Mame ➝ 𝓜𝓪𝓶𝓮 · 𝐌𝐚𝐦𝐞 · мαмє · ᴍᴀᴍᴇ والمزيد....</b>\n"
                    "<b>اضغط على الشكل الذي يعجبك لنسخه.</b> {hundred}"),
        "f_result": "{art} <b>تفضل:</b>",
        "f_tap": "{hundred} <b>اضغط على الشكل الذي يعجبك لنسخه.</b>",
        "f_nolatin": "<b>الأحرف العربية والأمهرية لا تتغير؛ تم إعطاء الزخارف فقط.</b>",
        "f_long": "<b>النص طويل جداً. الحد الأقصى {max} حرفاً.</b>",
        "f_again": "نص جديد",
        "f_back": "رجوع إلى خدمات أخرى",
        "svc_gift": "هدية يومية",
        "intro": ("{photo} <b>صورة ➝</b> {pdf} <b>PDF</b>\n\n"
                  "<b>أرسل صورك (حتى {max} صور).</b>\n"
                  "<b>للحصول على أفضل جودة أرسلها كملف (Document).</b>\n"
                  "<b>عند الانتهاء اضغط «إنشاء PDF».</b>"),
        "status": ("{photo} <b>الصور المستلمة: {n} / {max}</b>\n\n"
                   "<b>يمكنك إرسال المزيد أو الضغط على «إنشاء PDF».</b>"),
        "choose": ("{pdf} <b>اختر نوع الـ PDF:</b>\n\n"
                   "{photo} <b>الجودة الأصلية — الصور كما هي</b>\n"
                   "{pdf} <b>مسح ضوئي — أبيض وأسود، ساطع وواضح (للمستندات)</b>"),
        "making": "{wait} <b>جاري إنشاء الـ PDF...</b>",
        "ready": "{done} <b>ملف PDF جاهز — {pages} صفحة</b>\n\n<b>@{bot}</b>",
        "skipped": "\n<b>⚠️ تعذرت قراءة {k} ملف (تم تخطيه).</b>",
        "cancelled": "{trash} <b>تم الإلغاء.</b>",
        "too_many": "<b>⚠️ الحد الأقصى {max} صور.</b>",
        "too_big": "<b>⚠️ الملف أكبر من 20MB. أرسل ملفاً أصغر.</b>",
        "only_photos": "<b>⚠️ أرسل صوراً فقط.</b>",
        "no_photos": "أرسل صوراً أولاً",
        "expired": "انتهت الجلسة، ابدأ من جديد",
        "limit": "<b>⛔ لقد استنفدت الحد اليومي: {limit} ملفات PDF.</b>\n\n<b>حاول غداً (يتجدد عند منتصف الليل بتوقيت إثيوبيا).</b>",
        "fail": "<b>💔 تعذر إنشاء الـ PDF. أعد إرسال الصور.</b>",
        "b_done": "إنشاء PDF", "b_undo": "حذف الأخير", "b_clear": "مسح الكل", "b_cancel": "إلغاء",
        "b_orig": "الجودة الأصلية", "b_scan": "مسح ضوئي", "b_new": "PDF جديد", "b_share": "Share Bot 🚀",
        "share_text": "🔥 حوّل صورك إلى PDF وحمّل الفيديوهات مجاناً! جرّب هذا البوت:",
        "gift_new": ("{gift} <b>الهدية اليومية</b>\n\n{ok} <b>حصلت على +{amount} تحميلات إضافية اليوم!</b>\n\n"
                     "<b>🔥 الأيام المتتالية: {day} / {days}</b>\n"
                     "<b>في كل يوم {days} متتالٍ تحصل على +{bonus} إضافية.</b>\n\n"
                     "<b>📥 اليوم: {used} / {limit}</b>\n<b>عد غداً!</b>"),
        "gift_again": ("{gift} <b>الهدية اليومية</b>\n\n<b>لقد أخذت هدية اليوم ✅</b>\n\n"
                       "<b>🔥 الأيام المتتالية: {day} / {days}</b>\n"
                       "<b>📥 اليوم: {used} / {limit}</b>\n\n"
                       "<b>عد غداً (بعد منتصف الليل بتوقيت إثيوبيا)!</b>"),
    },
}


# =====================================================================
# PDF engine (pure functions, no Telegram)
# =====================================================================
_SCAN_LUT = [0 if p < 95 else 255 if p > 190 else int((p - 95) * 255 / 95) for p in range(256)]


def scan_filter(im):
    """Document-scanner look: flatten uneven light/shadows, white paper, dark crisp ink."""
    g = ImageOps.grayscale(im)
    radius = max(12, max(g.size) // 40)
    bg = g.filter(ImageFilter.GaussianBlur(radius))
    diff = ImageChops.subtract(bg, g, 0.4)          # >0 where the pixel is darker than its surroundings
    out = ImageOps.invert(diff)                      # paper ~255, ink darker
    out = ImageOps.autocontrast(out, cutoff=1)
    return out.point(_SCAN_LUT)


def _page(blob, mode, small=False):
    """-> (jpeg_bytes, width, height, components)"""
    im = Image.open(io.BytesIO(blob))
    orient = None
    try:
        orient = im.getexif().get(274)
    except Exception:
        pass
    if (mode == "o" and not small and im.format == "JPEG" and im.mode in ("RGB", "L")
            and orient in (None, 1) and len(blob) <= 4 * 1024 * 1024):
        w, h = im.size
        return blob, w, h, (3 if im.mode == "RGB" else 1)      # embedded untouched: zero quality loss
    maxside = 1800 if small else (2200 if mode == "s" else 3000)
    try:
        im.draft("RGB", (maxside, maxside))
    except Exception:
        pass
    im = ImageOps.exif_transpose(im)
    if im.mode in ("RGBA", "LA") or (im.mode == "P" and "transparency" in im.info):
        im = im.convert("RGBA")
        bg = Image.new("RGB", im.size, "white")
        bg.paste(im, mask=im.split()[-1])
        im = bg
    im.thumbnail((maxside, maxside))
    if mode == "s":
        im, comps = scan_filter(im.convert("RGB")), 1
    else:
        im, comps = im.convert("RGB"), 3
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=80 if small else (88 if mode == "s" else 92), optimize=True)
    w, h = im.size
    return buf.getvalue(), w, h, comps


def write_pdf(pages):
    """Tiny PDF writer: every page is one JPEG scaled to fit A4 (long side 842 pt)."""
    out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = []

    def add(b):
        offsets.append(len(out))
        out.extend(b)

    n = len(pages)
    add(b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n")
    kids = " ".join(f"{3 + 3 * i} 0 R" for i in range(n))
    add(f"2 0 obj\n<< /Type /Pages /Kids [{kids}] /Count {n} >>\nendobj\n".encode())
    for i, (jpg, w, h, comps) in enumerate(pages):
        scale = 842.0 / max(w, h)
        pw, ph = w * scale, h * scale
        page, cont, img = 3 + 3 * i, 4 + 3 * i, 5 + 3 * i
        add(f"{page} 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {pw:.2f} {ph:.2f}] "
            f"/Resources << /XObject << /Im0 {img} 0 R >> >> /Contents {cont} 0 R >>\nendobj\n".encode())
        content = f"q {pw:.2f} 0 0 {ph:.2f} 0 0 cm /Im0 Do Q".encode()
        add(f"{cont} 0 obj\n<< /Length {len(content)} >>\nstream\n".encode() + content + b"\nendstream\nendobj\n")
        cs = "/DeviceRGB" if comps == 3 else "/DeviceGray"
        add(f"{img} 0 obj\n<< /Type /XObject /Subtype /Image /Width {w} /Height {h} /ColorSpace {cs} "
            f"/BitsPerComponent 8 /Filter /DCTDecode /Length {len(jpg)} >>\nstream\n".encode()
            + jpg + b"\nendstream\nendobj\n")
    xref = len(out)
    out.extend(f"xref\n0 {len(offsets) + 1}\n".encode())
    out.extend(b"0000000000 65535 f \n")
    for off in offsets:
        out.extend(f"{off:010d} 00000 n \n".encode())
    out.extend(f"trailer\n<< /Size {len(offsets) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode())
    return bytes(out)


def make_pdf(blobs, mode):
    """-> (pdf_bytes or None, pages, skipped)"""
    for small in (False, True):
        pages, skipped = [], 0
        for b in blobs:
            try:
                pages.append(_page(b, mode, small))
            except Exception as ex:
                print("PDF page error:", ex)
                skipped += 1
        if not pages:
            return None, 0, skipped
        pdf = write_pdf(pages)
        if len(pdf) <= MAX_PDF:
            return pdf, len(pages), skipped
    return None, 0, skipped


# =====================================================================
def setup_tools(application, users_col, admin_id, translations, send_menu, require_join=None):
    async def lang_of(uid):
        try:
            d = await asyncio.to_thread(users_col.find_one, {"_id": uid}, {"lang": 1})
            lang = d.get("lang") if d else None
        except Exception:
            lang = None
        return lang if lang in TX else "am"

    def T(lang, key, **kw):
        return TX[lang][key].format(**EMJ, **kw)

    # ---------------- daily gift (sync, Mongo) ----------------
    def claim_gift_sync(uid):
        today = eat_day()
        yesterday = eat_day(utcnow() - timedelta(days=1))
        users_col.update_one({"_id": uid}, {"$setOnInsert": {"msg_count": 0}}, upsert=True)
        d = users_col.find_one({"_id": uid}, {"gift_date": 1, "gift_streak": 1}) or {}
        if d.get("gift_date") == today:
            return "again", d.get("gift_streak", 1), 0
        streak = d.get("gift_streak", 0) + 1 if d.get("gift_date") == yesterday else 1
        amount = GIFT_BONUS + (STREAK_BONUS if streak % STREAK_DAYS == 0 else 0)
        r = users_col.update_one({"_id": uid, "gift_date": {"$ne": today}},
                                 {"$set": {"gift_date": today, "gift_streak": streak}})
        if r.modified_count != 1:
            return "again", streak, 0
        users_col.update_one({"_id": uid, "dl_date": {"$ne": today}},
                             {"$set": {"dl_date": today, "dl_count": 0, "dl_bonus": 0}})
        users_col.update_one({"_id": uid}, {"$inc": {"dl_bonus": amount}})
        return "ok", streak, amount

    def usage_sync(uid):
        d = users_col.find_one({"_id": uid}, {"dl_date": 1, "dl_count": 1, "dl_bonus": 1}) or {}
        if d.get("dl_date") == eat_day():
            return d.get("dl_count", 0), DAILY_LIMIT + d.get("dl_bonus", 0)
        return 0, DAILY_LIMIT

    def take_pdf_sync(uid):
        if uid == admin_id:
            return True
        today = eat_day()
        users_col.update_one({"_id": uid}, {"$setOnInsert": {"msg_count": 0}}, upsert=True)
        users_col.update_one({"_id": uid, "pdf_date": {"$ne": today}}, {"$set": {"pdf_date": today, "pdf_count": 0}})
        r = users_col.update_one({"_id": uid, "pdf_date": today, "pdf_count": {"$lt": PDF_DAILY}},
                                 {"$inc": {"pdf_count": 1}})
        return r.modified_count == 1

    def refund_pdf_sync(uid):
        if uid != admin_id:
            users_col.update_one({"_id": uid, "pdf_date": eat_day(), "pdf_count": {"$gt": 0}},
                                 {"$inc": {"pdf_count": -1}})

    def take_vm_sync(uid):
        if uid == admin_id:
            return True
        today = eat_day()
        users_col.update_one({"_id": uid}, {"$setOnInsert": {"msg_count": 0}}, upsert=True)
        users_col.update_one({"_id": uid, "vm_date": {"$ne": today}}, {"$set": {"vm_date": today, "vm_count": 0}})
        r = users_col.update_one({"_id": uid, "vm_date": today, "vm_count": {"$lt": VM_DAILY}},
                                 {"$inc": {"vm_count": 1}})
        return r.modified_count == 1

    def refund_vm_sync(uid):
        if uid != admin_id:
            users_col.update_one({"_id": uid, "vm_date": eat_day(), "vm_count": {"$gt": 0}},
                                 {"$inc": {"vm_count": -1}})

    # ---------------- keyboards ----------------
    def back_row(lang, ic):
        return [Bt(translations[lang]["btn_back"], "cmd_back", style="primary", icon=ICON["back"], ic=ic)]

    def kb_status(lang):
        def make(ic):
            L = TX[lang]
            return InlineKeyboardMarkup([
                [Bt(L["b_done"], "pdf_done", style="success", icon=ICON["pdf"], ic=ic)],
                [Bt(L["b_undo"], "pdf_undo", style="primary", icon=ICON["cross"], ic=ic),
                 Bt(L["b_clear"], "pdf_clear", style="danger", icon=ICON["trash"], ic=ic)],
            ])
        return make

    def kb_cancel(lang):
        return lambda ic: InlineKeyboardMarkup(
            [[Bt(TX[lang]["b_cancel"], "pdf_cancel", style="danger", icon=ICON["trash"], ic=ic)]])

    def kb_choose(lang):
        def make(ic):
            L = TX[lang]
            return InlineKeyboardMarkup([
                [Bt(L["b_orig"], "pdf_t:o", style="success", icon=ICON["photo"], ic=ic)],
                [Bt(L["b_scan"], "pdf_t:s", style="primary", icon=ICON["pdf"], ic=ic)],
                [Bt(L["b_cancel"], "pdf_cancel", style="danger", icon=ICON["trash"], ic=ic)],
            ])
        return make

    def kb_back(lang):
        return lambda ic: InlineKeyboardMarkup([back_row(lang, ic)])

    # ---------------- state ----------------
    def get_st(context):
        st = context.user_data.get("pdf")
        if st and time.time() - st["ts"] > PDF_TTL:
            st["alive"] = False
            context.user_data.pop("pdf", None)
            return None
        return st

    def drop_st(context):
        context.user_data.pop("vm", None)
        st = context.user_data.pop("pdf", None)
        if st:
            st["alive"] = False

    async def clear_pdf(update, context):
        drop_st(context)
        context.user_data.pop("fancy", None)

    def new_st(chat_id):
        return {"files": [], "ts": time.time(), "tick": 0, "status_id": None, "chat": chat_id,
                "step": "collect", "alive": True, "warn": 0}

    # ---------------- sub-menu + gift ----------------
    async def on_services(update, context):
        q = update.callback_query
        await q.answer()
        lang = await lang_of(q.from_user.id)
        L = TX[lang]

        def make(ic):
            return InlineKeyboardMarkup([
                [Bt(L["svc_pdf"], "pdf_start", style="success", icon=ICON["photo"], ic=ic)],
                [Bt(L["svc_fancy"], "fancy_start", style="success", icon=ICON["pen"], ic=ic)],
                [Bt(L["svc_vm"], "vm_start", style="success", icon=ICON["mic1"], ic=ic)],
                [Bt(L["svc_gift"], "cmd_gift", style="success", icon=ICON["gift"], ic=ic)],
                back_row(lang, ic),
            ])
        try:
            await attempt(lambda t, kb: q.edit_message_text(t, reply_markup=kb, parse_mode="HTML"),
                          T(lang, "svc_title"), make)
        except Exception as ex:
            print("Services menu error:", ex)
        raise ApplicationHandlerStop

    async def on_gift(update, context):
        q = update.callback_query
        await q.answer()
        uid = q.from_user.id
        lang = await lang_of(uid)
        try:
            status, streak, amount = await asyncio.to_thread(claim_gift_sync, uid)
            used, limit = await asyncio.to_thread(usage_sync, uid)
            day = ((streak - 1) % STREAK_DAYS) + 1
            key = "gift_new" if status == "ok" else "gift_again"
            text = T(lang, key, amount=amount, day=day, days=STREAK_DAYS, bonus=STREAK_BONUS,
                     used=used, limit=limit)
            await attempt(lambda t, kb: q.edit_message_text(t, reply_markup=kb, parse_mode="HTML"),
                          text, kb_back(lang))
        except Exception as ex:
            print("Daily gift error:", ex)
        raise ApplicationHandlerStop

    # ---------------- Photo -> PDF ----------------
    async def joined_or_ask(update, context):
        """Force-join check (same message as for links). False = the user must join first."""
        if require_join is None:
            return True
        context.user_data["join_for"] = "pdf"
        ok = await require_join(update, context)
        if ok:
            context.user_data.pop("join_for", None)
        return ok

    async def show_intro(send, lang):
        await attempt(send, T(lang, "intro", max=MAX_PHOTOS), kb_cancel(lang))

    async def on_pdf_start(update, context):
        q = update.callback_query
        if not HAVE_PIL:
            await q.answer("Photo → PDF is not available right now.", show_alert=True)
            raise ApplicationHandlerStop
        await q.answer()
        if not await joined_or_ask(update, context):
            raise ApplicationHandlerStop
        lang = await lang_of(q.from_user.id)
        drop_st(context)
        context.user_data["pdf"] = new_st(q.message.chat_id)
        try:
            await show_intro(lambda t, kb: q.edit_message_text(t, reply_markup=kb, parse_mode="HTML"), lang)
        except Exception as ex:
            print("PDF intro error:", ex)
        raise ApplicationHandlerStop

    async def on_pdf_new(update, context):
        q = update.callback_query
        await q.answer()
        if not await joined_or_ask(update, context):
            raise ApplicationHandlerStop
        lang = await lang_of(q.from_user.id)
        drop_st(context)
        context.user_data["pdf"] = new_st(q.message.chat_id)
        try:
            await show_intro(lambda t, kb: context.bot.send_message(
                q.message.chat_id, t, reply_markup=kb, parse_mode="HTML"), lang)
        except Exception as ex:
            print("PDF new error:", ex)
        raise ApplicationHandlerStop

    async def refresh_later(app, st, lang, my_tick):
        """Waits a moment so an album of photos produces ONE status message, not ten."""
        await asyncio.sleep(1.0)
        if not st["alive"] or st["tick"] != my_tick or st["step"] != "collect":
            return
        if st["status_id"]:
            try:
                await app.bot.delete_message(st["chat"], st["status_id"])
            except Exception:
                pass
        text = T(lang, "status", n=len(st["files"]), max=MAX_PHOTOS)
        try:
            m = await attempt(lambda t, kb: app.bot.send_message(st["chat"], t, reply_markup=kb, parse_mode="HTML"),
                              text, kb_status(lang))
            st["status_id"] = m.message_id
        except Exception as ex:
            print("PDF status error:", ex)

    async def collect(update, context):
        st = get_st(context)
        if not st or st["step"] == "busy":
            return                                    # not in PDF mode -> the normal bot handles it
        msg = update.message
        if not msg:
            return
        uid = update.effective_user.id
        lang = await lang_of(uid)
        if msg.photo:
            fid, size = msg.photo[-1].file_id, msg.photo[-1].file_size
        elif msg.document and (msg.document.mime_type or "").startswith("image/"):
            fid, size = msg.document.file_id, msg.document.file_size
        else:
            await msg.reply_text(T(lang, "only_photos"), parse_mode="HTML")
            raise ApplicationHandlerStop
        if size and size > MAX_FILE:
            await msg.reply_text(T(lang, "too_big"), parse_mode="HTML")
            raise ApplicationHandlerStop
        if len(st["files"]) >= MAX_PHOTOS:
            if time.time() - st["warn"] > 4:
                st["warn"] = time.time()
                await msg.reply_text(T(lang, "too_many", max=MAX_PHOTOS), parse_mode="HTML")
            raise ApplicationHandlerStop
        st["files"].append(fid)
        st["ts"] = time.time()
        st["tick"] += 1
        st["step"] = "collect"
        context.application.create_task(refresh_later(context.application, st, lang, st["tick"]))
        raise ApplicationHandlerStop

    async def on_pdf_cb(update, context):
        q = update.callback_query
        uid = q.from_user.id
        d = q.data
        lang = await lang_of(uid)
        L = TX[lang]
        st = get_st(context)
        try:
            if d == "pdf_cancel":
                await q.answer()
                drop_st(context)
                await attempt(lambda t, kb: q.edit_message_text(t, reply_markup=kb, parse_mode="HTML"),
                              T(lang, "cancelled"), kb_back(lang))
            elif not st:
                await q.answer(L["expired"], show_alert=True)
            elif d == "pdf_done":
                if not st["files"]:
                    await q.answer(L["no_photos"], show_alert=True)
                else:
                    await q.answer()
                    if await joined_or_ask(update, context):        # force join again before converting
                        st["step"] = "type"
                        await attempt(lambda t, kb: q.edit_message_text(t, reply_markup=kb, parse_mode="HTML"),
                                      T(lang, "choose"), kb_choose(lang))
            elif d in ("pdf_undo", "pdf_clear"):
                await q.answer()
                if d == "pdf_undo" and st["files"]:
                    st["files"].pop()
                if d == "pdf_clear":
                    st["files"].clear()
                st["ts"] = time.time()
                await attempt(lambda t, kb: q.edit_message_text(t, reply_markup=kb, parse_mode="HTML"),
                              T(lang, "status", n=len(st["files"]), max=MAX_PHOTOS), kb_status(lang))
            elif d.startswith("pdf_t:"):
                await q.answer()
                if st["step"] == "busy":
                    return
                await build_and_send(update, context, st, lang, d.split(":")[1])
        except Exception as ex:
            print("PDF callback error:", ex)
        raise ApplicationHandlerStop

    async def build_and_send(update, context, st, lang, mode):
        q = update.callback_query
        uid = q.from_user.id
        chat_id = q.message.chat_id
        L = TX[lang]
        if not await asyncio.to_thread(take_pdf_sync, uid):
            drop_st(context)
            await attempt(lambda t, kb: q.edit_message_text(t, reply_markup=kb, parse_mode="HTML"),
                          T(lang, "limit", limit=PDF_DAILY), kb_back(lang))
            return
        st["step"] = "busy"
        await attempt(lambda t, kb: q.edit_message_text(t, reply_markup=kb, parse_mode="HTML"),
                      T(lang, "making"), lambda ic: None)
        ok = False
        try:
            blobs = []
            for fid in list(st["files"]):
                try:
                    f = await context.bot.get_file(fid)
                    blobs.append(bytes(await f.download_as_bytearray()))
                except Exception as ex:
                    print("PDF download error:", ex)
            skipped_dl = len(st["files"]) - len(blobs)
            pdf, pages, skipped = (None, 0, 0)
            if blobs:
                pdf, pages, skipped = await asyncio.to_thread(make_pdf, blobs, mode)
            blobs.clear()
            if pdf:
                name = f"Photos_{(utcnow() + timedelta(hours=3)).strftime('%d-%m-%Y')}.pdf"
                bot_name = context.bot.username or "mame_posts_bot"
                caption = T(lang, "ready", pages=pages, bot=bot_name)
                if skipped + skipped_dl:
                    caption += L["skipped"].format(k=skipped + skipped_dl)
                share = (f"https://t.me/share/url?url={quote(f'https://t.me/{bot_name}?start=share', safe='')}"
                         f"&text={quote(L['share_text'], safe='')}")

                def kb(ic):
                    return InlineKeyboardMarkup([
                        [Bt(L["b_new"], "pdf_new", style="success", icon=ICON["again"], ic=ic),
                         Bt(L["b_share"], url=share, style="primary", icon=ICON["link"], ic=ic)],
                        [Bt(translations[lang]["btn_back"], "pdf_menu", style="primary", icon=ICON["back"], ic=ic)],
                    ])

                async def send(t, k):
                    return await context.bot.send_document(
                        chat_id, document=io.BytesIO(pdf), filename=name, caption=t, reply_markup=k,
                        parse_mode="HTML", read_timeout=120, write_timeout=120, connect_timeout=30)
                await attempt(send, caption, kb)
                ok = True
        except Exception as ex:
            print("PDF build error:", ex)
        drop_st(context)
        if ok:
            if uid != admin_id:
                await asyncio.to_thread(bump_stat, users_col, None, "pdfs")
            try:
                await q.message.delete()
            except Exception:
                pass
        else:
            await asyncio.to_thread(refund_pdf_sync, uid)
            try:
                await attempt(lambda t, k: q.edit_message_text(t, reply_markup=k, parse_mode="HTML"),
                              T(lang, "fail"), kb_back(lang))
            except Exception:
                pass

    # ---------------- Fancy Text ----------------
    def kb_fancy(lang, again=False):
        def make(ic):
            L = TX[lang]
            rows = []
            if again:
                rows.append([Bt(L["f_again"], "fancy_again", style="success", icon=ICON["again"], ic=ic)])
            rows.append([Bt(L["f_back"], "cmd_services", style="primary", icon=ICON["back"], ic=ic)])
            return InlineKeyboardMarkup(rows)
        return make

    async def on_fancy_start(update, context):
        q = update.callback_query
        await q.answer()
        lang = await lang_of(q.from_user.id)
        drop_st(context)
        context.user_data["fancy"] = {"ts": time.time()}
        try:
            await attempt(lambda t, kb: q.edit_message_text(t, reply_markup=kb, parse_mode="HTML"),
                          T(lang, "f_intro"), kb_fancy(lang))
        except Exception as ex:
            print("Fancy start error:", ex)
        raise ApplicationHandlerStop

    async def on_fancy_again(update, context):
        q = update.callback_query
        await q.answer()
        lang = await lang_of(q.from_user.id)
        context.user_data["fancy"] = {"ts": time.time()}
        try:
            await attempt(lambda t, kb: context.bot.send_message(
                q.message.chat_id, t, reply_markup=kb, parse_mode="HTML"), T(lang, "f_intro"), kb_fancy(lang))
        except Exception as ex:
            print("Fancy again error:", ex)
        raise ApplicationHandlerStop

    async def fancy_text(update, context):
        st = context.user_data.get("fancy")
        if not st:
            return
        if time.time() - st["ts"] > FANCY_TTL:
            context.user_data.pop("fancy", None)
            return
        msg = update.message
        text = (msg.text or "").strip()
        low = text.lower()
        if not text or "http" in low or "www." in low:      # a link -> the downloader handles it
            return
        if text == "🏠 Menu":                                # the bottom menu button leaves the tool
            context.user_data.pop("fancy", None)
            return
        uid = update.effective_user.id
        lang = await lang_of(uid)
        try:
            if len(text) > FANCY_MAX:
                await msg.reply_text(T(lang, "f_long", max=FANCY_MAX), parse_mode="HTML")
                raise ApplicationHandlerStop
            latin, lines = fancy_lines(text)
            out = [T(lang, "f_result"), ""] + [f"<code>{html.escape(x)}</code>" for x in lines] + [""]
            if not latin:
                out += [TX[lang]["f_nolatin"], ""]
            out.append(T(lang, "f_tap"))
            st["ts"] = time.time()
            await attempt(lambda t, kb: msg.reply_text(t, reply_markup=kb, parse_mode="HTML"),
                          "\n".join(out), kb_fancy(lang, again=True))
            await asyncio.to_thread(bump_stat, users_col, None, "fancy")
        except ApplicationHandlerStop:
            raise
        except Exception as ex:
            print("Fancy text error:", ex)
        raise ApplicationHandlerStop

    # ---------------- Voice <-> MP3 ----------------
    def kb_vm_intro(lang):
        def make(ic):
            return InlineKeyboardMarkup([[Bt(TX[lang]["f_back"], "cmd_services", style="primary",
                                             icon=ICON["back"], ic=ic)]])
        return make

    def kb_vm_name(lang):
        def make(ic):
            L = TX[lang]
            return InlineKeyboardMarkup([
                [Bt(L["vm_random"], "vm_rnd", style="success")],
                [Bt(L["vm_cancel"], "vm_cancel", style="danger", icon=ICON["trash"], ic=ic)],
            ])
        return make

    def kb_vm_done(lang):
        def make(ic):
            L = TX[lang]
            return InlineKeyboardMarkup([
                [Bt(L["vm_again"], "vm_again", style="success", icon=ICON["again"], ic=ic)],
                [Bt(L["f_back"], "cmd_services", style="primary", icon=ICON["back"], ic=ic)],
            ])
        return make

    def vm_get(context):
        st = context.user_data.get("vm")
        if st and time.time() - st["ts"] > VM_TTL:
            context.user_data.pop("vm", None)
            return None
        return st

    def vm_intro_text(lang):
        return T(lang, "vm_intro", mb=MAX_FILE // (1024 * 1024), mins=VM_MAX_MIN)

    async def on_vm_start(update, context):
        q = update.callback_query
        await q.answer()
        lang = await lang_of(q.from_user.id)
        drop_st(context)
        context.user_data.pop("fancy", None)
        context.user_data["vm"] = {"ts": time.time(), "step": "file"}
        try:
            await attempt(lambda t, kb: q.edit_message_text(t, reply_markup=kb, parse_mode="HTML"),
                          vm_intro_text(lang), kb_vm_intro(lang))
        except Exception as ex:
            print("Voice start error:", ex)
        raise ApplicationHandlerStop

    async def on_vm_again(update, context):
        q = update.callback_query
        await q.answer()
        lang = await lang_of(q.from_user.id)
        drop_st(context)
        context.user_data["vm"] = {"ts": time.time(), "step": "file"}
        try:
            await attempt(lambda t, kb: context.bot.send_message(
                q.message.chat_id, t, reply_markup=kb, parse_mode="HTML"), vm_intro_text(lang), kb_vm_intro(lang))
        except Exception as ex:
            print("Voice again error:", ex)
        raise ApplicationHandlerStop

    async def run_vm(context, chat_id, uid, st, lang, name=None):
        """Converts the file kept in `st`. For 'to_mp3' `name` is the file name chosen by the user."""
        st["step"] = "busy"
        bot = context.bot
        try:
            if not await asyncio.to_thread(take_vm_sync, uid):
                await bot.send_message(chat_id, T(lang, "vm_limit", limit=VM_DAILY), parse_mode="HTML")
                return
            status = await bot.send_message(chat_id, T(lang, "vm_making"), parse_mode="HTML")
            done = False
            try:
                async with vm_semaphore():
                    tg_file = await bot.get_file(st["file_id"])
                    data = bytes(await tg_file.download_as_bytearray())
                    out = await asyncio.to_thread(convert_audio, data, st["kind"])
                bot_name = bot.username or "mame_posts_bot"
                if st["kind"] == "to_mp3":
                    fname = name or random_name()
                    text = T(lang, "vm_done_mp3", bot=bot_name)
                    await attempt(lambda t, kb: bot.send_audio(
                        chat_id, audio=io.BytesIO(out), filename=f"{fname}.mp3", title=fname,
                        performer="🎧 Mame Posts Bot", caption=t, parse_mode="HTML", reply_markup=kb),
                        text, kb_vm_done(lang))
                else:
                    text = T(lang, "vm_done_voice", bot=bot_name)
                    await attempt(lambda t, kb: bot.send_voice(
                        chat_id, voice=io.BytesIO(out), caption=t, parse_mode="HTML", reply_markup=kb),
                        text, kb_vm_done(lang))
                done = True
                await asyncio.to_thread(bump_stat, users_col, None, "voice")
                try:
                    await bot.delete_message(chat_id, status.message_id)
                except Exception:
                    pass
            except Exception as ex:
                print("Voice convert error:", ex)
                await asyncio.to_thread(refund_vm_sync, uid)
                try:
                    await bot.edit_message_text(T(lang, "vm_fail"), chat_id=chat_id,
                                                message_id=status.message_id, parse_mode="HTML")
                except Exception:
                    pass
            _ = done
        finally:
            context.user_data.pop("vm", None)

    async def vm_message(update, context):
        st = vm_get(context)
        if not st:
            return
        msg = update.message
        text = (msg.text or "").strip()
        low = text.lower()
        if text == "🏠 Menu":                                    # the bottom menu button leaves the tool
            context.user_data.pop("vm", None)
            return
        if msg.text and ("http" in low or "www." in low):       # a link -> the downloader handles it
            return
        uid = update.effective_user.id
        chat_id = update.effective_chat.id
        lang = await lang_of(uid)
        if st["step"] == "busy":
            raise ApplicationHandlerStop
        if st["step"] == "file":
            kind, f = None, None
            if msg.voice:
                kind, f = "to_mp3", msg.voice
            elif msg.audio:
                kind, f = "to_voice", msg.audio
            elif msg.document:
                fname = (msg.document.file_name or "").lower()
                mime = (msg.document.mime_type or "").lower()
                if mime.startswith("audio/") or fname.endswith(VM_AUDIO_EXT):
                    f = msg.document
                    kind = "to_mp3" if fname.endswith((".ogg", ".oga", ".opus")) else "to_voice"
            if not f:
                await msg.reply_text(T(lang, "vm_notaudio"), parse_mode="HTML")
                raise ApplicationHandlerStop
            if (f.file_size or 0) > MAX_FILE:
                await msg.reply_text(T(lang, "vm_big", mb=MAX_FILE // (1024 * 1024)), parse_mode="HTML")
                raise ApplicationHandlerStop
            dur = getattr(f, "duration", None)
            if dur and int(dur) > VM_MAX_MIN * 60:
                await msg.reply_text(T(lang, "vm_long", mins=VM_MAX_MIN), parse_mode="HTML")
                raise ApplicationHandlerStop
            st.update(kind=kind, file_id=f.file_id, ts=time.time())
            if kind == "to_voice":                               # a voice message has no file name
                await run_vm(context, chat_id, uid, st, lang)
            else:
                st["step"] = "name"
                await attempt(lambda t, kb: msg.reply_text(t, reply_markup=kb, parse_mode="HTML"),
                              T(lang, "vm_name"), kb_vm_name(lang))
            raise ApplicationHandlerStop
        if st["step"] == "name":
            name = clean_name(text) if msg.text else ""
            if not name:
                await attempt(lambda t, kb: msg.reply_text(t, reply_markup=kb, parse_mode="HTML"),
                              T(lang, "vm_name"), kb_vm_name(lang))
                raise ApplicationHandlerStop
            await run_vm(context, chat_id, uid, st, lang, name)
            raise ApplicationHandlerStop

    async def on_vm_cb(update, context):
        q = update.callback_query
        await q.answer()
        uid = q.from_user.id
        st = vm_get(context)
        if q.data == "vm_cancel":
            context.user_data.pop("vm", None)
            await on_services(update, context)                  # shows "Other services" again
            return
        if not st or st.get("step") != "name":
            raise ApplicationHandlerStop
        lang = await lang_of(uid)
        await run_vm(context, q.message.chat_id, uid, st, lang, random_name())
        raise ApplicationHandlerStop

    async def on_pdf_menu(update, context):
        q = update.callback_query
        await q.answer()
        try:
            await q.edit_message_reply_markup(reply_markup=None)
        except Exception:
            pass
        await send_menu(q.message.chat_id, context, q.from_user.id)
        raise ApplicationHandlerStop

    # ---------------- register ----------------
    application.add_handler(MessageHandler(filters.COMMAND, clear_pdf), group=-3)
    application.add_handler(CallbackQueryHandler(clear_pdf, pattern=r"^(cmd_|lang_)"), group=-3)
    application.add_handler(CallbackQueryHandler(on_services, pattern=r"^cmd_services$"), group=-2)
    application.add_handler(CallbackQueryHandler(on_gift, pattern=r"^cmd_gift$"), group=-2)
    application.add_handler(CallbackQueryHandler(on_pdf_start, pattern=r"^pdf_start$"), group=-2)
    application.add_handler(CallbackQueryHandler(on_pdf_new, pattern=r"^pdf_new$"), group=-2)
    application.add_handler(CallbackQueryHandler(on_pdf_menu, pattern=r"^pdf_menu$"), group=-2)
    application.add_handler(
        CallbackQueryHandler(on_pdf_cb, pattern=r"^pdf_(cancel|done|undo|clear|t:[os])$"), group=-2)
    application.add_handler(CallbackQueryHandler(on_fancy_start, pattern=r"^fancy_start$"), group=-2)
    application.add_handler(CallbackQueryHandler(on_fancy_again, pattern=r"^fancy_again$"), group=-2)
    application.add_handler(CallbackQueryHandler(on_vm_start, pattern=r"^vm_start$"), group=-2)
    application.add_handler(CallbackQueryHandler(on_vm_again, pattern=r"^vm_again$"), group=-2)
    application.add_handler(CallbackQueryHandler(on_vm_cb, pattern=r"^vm_(rnd|cancel)$"), group=-2)
    # group -4: runs before the other message handlers, but only acts while the user is inside this tool
    application.add_handler(
        MessageHandler((filters.VOICE | filters.AUDIO | filters.Document.ALL | filters.TEXT) & ~filters.COMMAND,
                       vm_message), group=-4)
    application.add_handler(MessageHandler(filters.PHOTO | filters.Document.ALL, collect), group=-1)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, fancy_text), group=-1)
