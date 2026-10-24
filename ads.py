"""Advertising orders for @mame_posts  (v2)

USER   : [Advertise] -> pick hours -> pick payment method -> send payment
         screenshot -> send the post.          (12 h = negotiable: no payment step)
ADMIN  : gets post + screenshot -> "Edit post?" -> (sends edited post) ->
         types publish date & time (Ethiopia time) -> the bot publishes at that
         time and removes the ad automatically when the hours are over.
All user messages are in Amharic / English / Arabic, with bold text,
Premium emoji and coloured buttons like the rest of the bot.
"""
import asyncio
import base64
import difflib
import html
import json
import os
import re
import time
import uuid
from datetime import datetime, timedelta

import requests
from pymongo import ReturnDocument
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationHandlerStop,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    filters,
)

PRICES = {12: "Negotiable", 24: "500 ETB", 48: "700 ETB"}
FLOW_TTL = 30 * 60          # seconds a user / admin may take to finish a step
CHECK_EVERY = 30            # seconds between publish / remove checks
# Telegram only lets bots delete messages younger than 48 h -> 48 h ads are removed 10 min early.
MAX_DELETE_SECONDS = 48 * 3600 - 600

# ---------------- premium emoji (same IDs as the rest of the bot) ----------------
PREMIUM = {
    "ok": ("5260463209562776385", "✅"),
    "wait": ("5305254783542667121", "⏳"),
    "ad": ("5197304993920616826", "📢"),
    "card": ("5186349709169525403", "💳"),
    "money": ("5447458260200214425", "💰"),
    "down": ("5305634553140912174", "👇"),
    "bank": ("5961054379350955385", "🏦"),
    "tele": ("5960632377339285724", "📱"),
    "cam": ("5305551797711053969", "📸"),
    "chat": ("5305545479814161889", "💬"),
    "info": ("5305739801314501775", "ℹ️"),
}
# icons shown inside buttons (custom emoji ids already used by the main menu)
ICON = {
    "dur": "5305254783542667121",
    "cbe": "5961054379350955385",
    "tele": "5960632377339285724",
    "back": "5248948801674159296",
    "ok": "5895288332581082241",
    "orders": "5431577498364158238",
}


def e(key):
    cid, ch = PREMIUM[key]
    return f'<tg-emoji emoji-id="{cid}">{ch}</tg-emoji>'


def T(s):
    """Replace [ok] [down] ... tokens with premium emoji tags."""
    return re.sub(r"\[(\w+)\]", lambda m: e(m.group(1)) if m.group(1) in PREMIUM else m.group(0), s)


TXT = {
    "am": {
        "intro": T('[ad] <b>@mame_posts ቻናል ላይ ማስታወቂያ ለማሰራት</b>\n\n⏱ <b>ማስታወቂያው ስንት ሰዓት እንዲቆይ ይፈልጋሉ?</b>\n\n[down] ከስር ይምረጡ'),
        "pay_choose": T('[card] <b>የክፍያ አማራጭ ይምረጡ</b>\n\n⏱ ቆይታ: <b>{hours} Hours</b>\n[money] ዋጋ: <b>{price}</b>\n\n[down] ከስር ይምረጡ'),
        "pay_cbe": T('[bank] <b>ንግድ ባንክ (CBE)</b>\n<code>1000528274394</code>\n\nMohammed Seid\n\n[money] መጠን: <b>{price}</b>\n\n[cam] <b>ክፍያውን ከፈጸሙ በኋላ የክፍያ ስክሪንሹት እዚህ ይላኩ።</b>'),
        "pay_tele": T('[tele] <b>ቴሌ ብር (TELE BIRR)</b>\n<code>+251963266849</code>\n\n[money] መጠን: <b>{price}</b>\n\n[cam] <b>ክፍያውን ከፈጸሙ በኋላ የክፍያ ስክሪንሹት እዚህ ይላኩ።</b>'),
        "ask_post": T('[ok] <b>ስክሪንሹቱን ተቀብለናል!</b>\n\n[down] አሁን ማሰራት የሚፈልጉትን <b>Post</b> ይላኩ (ጽሑፍ፣ ፎቶ ወይም ቪዲዮ)።'),
        "ask_post_neg": T('⏱ <b>12 Hours — በስምምነት</b>\n\nዋጋውን ከአድሚን ጋር ተነጋግራችሁ ትስማማላችሁ።\n\n[down] ማሰራት የሚፈልጉትን <b>Post</b> ይላኩ (ጽሑፍ፣ ፎቶ ወይም ቪዲዮ)።'),
        "received": T('[ok] <b>ትዕዛዝ #{n} ተቀብለናል!</b>\n\nአድሚን ክፍያውን እና ፖስቱን አይቶ እስኪያጸድቅ ይጠብቁ፤ ውጤቱን እዚሁ እንነግርዎታለን።'),
        "received_neg": T('[ok] <b>ትዕዛዝ #{n} ለአድሚን ተልኳል!</b>\n\nአድሚን ዋጋውን ለመስማማት ያነጋግርዎታል።'),
        "scheduled": T('[ok] <b>ማስታወቂያዎ ጸድቋል!</b>\n\n🗓 የሚለቀቅበት: <b>{when}</b> (የኢትዮጵያ ሰዓት)\n⏱ ቆይታ: <b>{hours} Hours</b>'),
        "posted": '🎉 <b>ማስታወቂያዎ @mame_posts ላይ ተለጥፏል!</b>\n\n⏱ ቆይታ: <b>{hours} Hours</b>\n🔗 {link}\n\nእናመሰግናለን!',
        "rejected": '❌ <b>ትዕዛዝ #{n} አልጸደቀም።</b>\n\nለበለጠ መረጃ እዚሁ ቦት ላይ መልዕክት ይጻፉ፤ አድሚን ይመልስልዎታል።',
        "expired": '⏰ <b>የማስታወቂያዎ ጊዜ አብቅቷል</b> (ትዕዛዝ #{n})\n\nእናመሰግናለን! እንደገና ለማሰራት ከምናሌው «ማስታወቂያ ለማሰራት» ይጫኑ።',
        "cancelled": '❎ <b>ተሰርዟል።</b>',
        "bad_receipt": '❌ <b>እባክዎ የክፍያ ስክሪንሹቱን እንደ ፎቶ ይላኩ፤ ወይም ሰርዝ ይጫኑ።</b>',
        "session": "⌛ ጊዜው አልፏል፤ እባክዎ ከምናሌው «ማስታወቂያ ለማሰራት» እንደገና ይጫኑ።",
        "dur12": "12 Hours — በስምምነት", "dur24": "24 Hours — 500 ETB", "dur48": "48 Hours — 700 ETB",
        "cbe": "ንግድ ባንክ (CBE)", "tele": "ቴሌ ብር (TELE BIRR)", "cancel": "❌ ሰርዝ", "back": "⬅️ ተመለስ",
    },
    "en": {
        "intro": T('[ad] <b>To Advertise on @mame_posts Channel</b>\n\n⏱ <b>How long should your ad stay on the channel?</b>\n\n[down] Choose below'),
        "pay_choose": T('[card] <b>Choose a payment method</b>\n\n⏱ Duration: <b>{hours} Hours</b>\n[money] Price: <b>{price}</b>\n\n[down] Choose below'),
        "pay_cbe": T('[bank] <b>Commercial Bank of Ethiopia (CBE)</b>\n<code>1000528274394</code>\n\nMohammed Seid\n\n[money] Amount: <b>{price}</b>\n\n[cam] <b>After paying, send the payment screenshot here.</b>'),
        "pay_tele": T('[tele] <b>TELEBIRR</b>\n<code>+251963266849</code>\n\n[money] Amount: <b>{price}</b>\n\n[cam] <b>After paying, send the payment screenshot here.</b>'),
        "ask_post": T('[ok] <b>Screenshot received!</b>\n\n[down] Now send the <b>post</b> you want to advertise (text, photo or video).'),
        "ask_post_neg": T('⏱ <b>12 Hours — Negotiable</b>\n\nYou will agree on the price with the admin.\n\n[down] Send the <b>post</b> you want to advertise (text, photo or video).'),
        "received": T('[ok] <b>Order #{n} received!</b>\n\nPlease wait while the admin checks your payment and post. We will tell you the result here.'),
        "received_neg": T('[ok] <b>Order #{n} sent to the admin!</b>\n\nThe admin will contact you to agree on the price.'),
        "scheduled": T('[ok] <b>Your ad was approved!</b>\n\n🗓 It will be published on: <b>{when}</b> (Ethiopia time)\n⏱ Duration: <b>{hours} Hours</b>'),
        "posted": '🎉 <b>Your ad is now live on @mame_posts!</b>\n\n⏱ Duration: <b>{hours} Hours</b>\n🔗 {link}\n\nThank you!',
        "rejected": '❌ <b>Order #{n} was not approved.</b>\n\nWrite a message here to ask the admin for details.',
        "expired": '⏰ <b>Your ad time has ended</b> (order #{n})\n\nThank you! To advertise again, tap “Promote / Advertise” in the menu.',
        "cancelled": '❎ <b>Cancelled.</b>',
        "bad_receipt": '❌ <b>Please send the payment screenshot as a photo, or tap Cancel.</b>',
        "session": "⌛ Session expired. Please tap “Promote / Advertise” in the menu again.",
        "dur12": "12 Hours — Negotiable", "dur24": "24 Hours — 500 ETB", "dur48": "48 Hours — 700 ETB",
        "cbe": "Commercial Bank (CBE)", "tele": "TELEBIRR", "cancel": "❌ Cancel", "back": "⬅️ Back",
    },
    "ar": {
        "intro": T('[ad] <b>للإعلان على قناة @mame_posts</b>\n\n⏱ <b>كم ساعة تريد أن يبقى إعلانك في القناة؟</b>\n\n[down] اختر من الأسفل'),
        "pay_choose": T('[card] <b>اختر طريقة الدفع</b>\n\n⏱ المدة: <b>{hours} ساعة</b>\n[money] السعر: <b>{price}</b>\n\n[down] اختر من الأسفل'),
        "pay_cbe": T('[bank] <b>البنك التجاري الإثيوبي (CBE)</b>\n<code>1000528274394</code>\n\nMohammed Seid\n\n[money] المبلغ: <b>{price}</b>\n\n[cam] <b>بعد الدفع أرسل لقطة شاشة الإيصال هنا.</b>'),
        "pay_tele": T('[tele] <b>تلي بر (TELE BIRR)</b>\n<code>+251963266849</code>\n\n[money] المبلغ: <b>{price}</b>\n\n[cam] <b>بعد الدفع أرسل لقطة شاشة الإيصال هنا.</b>'),
        "ask_post": T('[ok] <b>تم استلام لقطة الشاشة!</b>\n\n[down] أرسل الآن <b>المنشور</b> الذي تريد الإعلان عنه (نص أو صورة أو فيديو).'),
        "ask_post_neg": T('⏱ <b>12 ساعة — حسب الاتفاق</b>\n\nستتفق على السعر مع المسؤول.\n\n[down] أرسل <b>المنشور</b> الذي تريد الإعلان عنه (نص أو صورة أو فيديو).'),
        "received": T('[ok] <b>تم استلام الطلب #{n}!</b>\n\nيرجى الانتظار حتى يراجع المسؤول الدفع والمنشور وسنخبرك بالنتيجة هنا.'),
        "received_neg": T('[ok] <b>تم إرسال الطلب #{n} إلى المسؤول!</b>\n\nسيتواصل معك المسؤول للاتفاق على السعر.'),
        "scheduled": T('[ok] <b>تمت الموافقة على إعلانك!</b>\n\n🗓 سيتم نشره في: <b>{when}</b> (بتوقيت إثيوبيا)\n⏱ المدة: <b>{hours} ساعة</b>'),
        "posted": '🎉 <b>إعلانك الآن منشور في @mame_posts!</b>\n\n⏱ المدة: <b>{hours} ساعة</b>\n🔗 {link}\n\nشكراً لك!',
        "rejected": '❌ <b>لم تتم الموافقة على الطلب #{n}.</b>\n\nاكتب رسالة هنا لسؤال المسؤول عن التفاصيل.',
        "expired": '⏰ <b>انتهت مدة إعلانك</b> (الطلب #{n})\n\nشكراً لك! للإعلان مرة أخرى اضغط «طلب إعلان» من القائمة.',
        "cancelled": '❎ <b>تم الإلغاء.</b>',
        "bad_receipt": '❌ <b>يرجى إرسال لقطة شاشة الدفع كصورة، أو اضغط إلغاء.</b>',
        "session": "⌛ انتهت الجلسة. اضغط «طلب إعلان» من القائمة مرة أخرى.",
        "dur12": "12 ساعة — حسب الاتفاق", "dur24": "24 ساعة — 500 ETB", "dur48": "48 ساعة — 700 ETB",
        "cbe": "البنك التجاري (CBE)", "tele": "تلي بر (TELE BIRR)", "cancel": "❌ إلغاء", "back": "⬅️ رجوع",
    },
}

EXTRA = {
    "am": {
        "txid_checking": T('[wait] <b>ክፍያውን እያረጋገጥኩ ነው...</b>'),
        "txid_wait": '⏳ <b>እባክዎ ትንሽ ይጠብቁ፣ ክፍያው እየተረጋገጠ ነው።</b>',
        "scr_ok": T('[ok] <b>ክፍያዎን ተቀብለናል!</b>\n\n[down] አሁን ማሰራት የሚፈልጉትን <b>Post</b> ይላኩ (ጽሑፍ፣ ፎቶ ወይም ቪዲዮ)።'),
        "scr_notreceipt": '❌ <b>ይህ የክፍያ ደረሰኝ አይመስልም።</b>\n\nየክፍያውን ስክሪንሹት በትክክል ይላኩ። (የቀሩ ሙከራዎች: {left})',
        "scr_wrong": '❌ <b>ክፍያው ወደ ትክክለኛው አካውንት የተፈጸመ አይመስልም።</b>\n\nከላይ ባለው አካውንት ከፍለው ስክሪንሹቱን ይላኩ። (የቀሩ ሙከራዎች: {left})',
        "scr_low": '❌ <b>የተከፈለው መጠን ከዋጋው ያነሰ ነው።</b>\n\nሙሉውን መጠን ከፍለው ስክሪንሹቱን ይላኩ። (የቀሩ ሙከራዎች: {left})',
        "scr_old": '❌ <b>ይህ ደረሰኝ የቆየ ነው።</b>\n\nአሁን የፈጸሙትን ክፍያ ስክሪንሹት ይላኩ። (የቀሩ ሙከራዎች: {left})',
        "scr_dup": '❌ <b>ይህ ደረሰኝ ከዚህ በፊት ጥቅም ላይ ውሏል።</b>\n\nአዲስ ክፍያ ከፈጸሙ ስክሪንሹቱን ይላኩ። (የቀሩ ሙከራዎች: {left})',
        "txid_blocked": '⛔ <b>ክፍያውን ማረጋገጥ አልተቻለም።</b>\n\nትክክለኛ ክፍያ ከፈጸሙ እዚሁ ቦት ላይ የደረሰኙን ስክሪንሹት ይላኩ፤ አድሚን ይመለከታል።',
    },
    "en": {
        "txid_checking": T('[wait] <b>Checking your payment...</b>'),
        "txid_wait": '⏳ <b>Please wait, your payment is being checked.</b>',
        "scr_ok": T('[ok] <b>Payment received!</b>\n\n[down] Now send the <b>post</b> you want to advertise (text, photo or video).'),
        "scr_notreceipt": '❌ <b>This does not look like a payment receipt.</b>\n\nPlease send the payment screenshot. (Tries left: {left})',
        "scr_wrong": '❌ <b>The payment does not look like it went to the correct account.</b>\n\nPay to the account shown above and send the screenshot. (Tries left: {left})',
        "scr_low": '❌ <b>The amount paid is lower than the price.</b>\n\nPay the full amount and send the screenshot. (Tries left: {left})',
        "scr_old": '❌ <b>This receipt is too old.</b>\n\nSend the screenshot of the payment you just made. (Tries left: {left})',
        "scr_dup": '❌ <b>This receipt was already used.</b>\n\nIf you made a new payment, send its screenshot. (Tries left: {left})',
        "txid_blocked": '⛔ <b>We could not verify your payment.</b>\n\nIf you really paid, send your receipt screenshot here in the bot and the admin will check it.',
    },
    "ar": {
        "txid_checking": T('[wait] <b>جاري التحقق من الدفع...</b>'),
        "txid_wait": '⏳ <b>يرجى الانتظار، جاري التحقق من الدفع.</b>',
        "scr_ok": T('[ok] <b>تم استلام الدفع!</b>\n\n[down] أرسل الآن <b>المنشور</b> الذي تريد الإعلان عنه (نص أو صورة أو فيديو).'),
        "scr_notreceipt": '❌ <b>هذه ليست إيصال دفع.</b>\n\nيرجى إرسال لقطة شاشة الدفع. (المحاولات المتبقية: {left})',
        "scr_wrong": '❌ <b>لا يبدو أن الدفع تم إلى الحساب الصحيح.</b>\n\nادفع إلى الحساب الموضح أعلاه وأرسل لقطة الشاشة. (المحاولات المتبقية: {left})',
        "scr_low": '❌ <b>المبلغ المدفوع أقل من السعر.</b>\n\nادفع المبلغ كاملاً وأرسل لقطة الشاشة. (المحاولات المتبقية: {left})',
        "scr_old": '❌ <b>هذا الإيصال قديم.</b>\n\nأرسل لقطة شاشة الدفعة التي أجريتها الآن. (المحاولات المتبقية: {left})',
        "scr_dup": '❌ <b>تم استخدام هذا الإيصال من قبل.</b>\n\nإذا أجريت دفعة جديدة أرسل لقطتها. (المحاولات المتبقية: {left})',
        "txid_blocked": '⛔ <b>تعذر التحقق من الدفع.</b>\n\nإذا دفعت فعلاً، أرسل لقطة شاشة الإيصال هنا في البوت وسيراجعها المسؤول.',
    },
}
for _l, _d in EXTRA.items():
    TXT[_l].update(_d)

PAY_LABEL = {"cbe": "Commercial Bank (CBE)", "tele": "TeleBirr", None: "— (negotiable)"}
_WHEN_RE = re.compile(
    r"^(?:(\d{4})-(\d{1,2})-(\d{1,2})|(\d{1,2})[/\-.](\d{1,2})(?:[/\-.](\d{4}))?)?"
    r"\s*(\d{1,2})[:.](\d{2})\s*(am|pm)?$"
)


# ---------------- payment verification (Transaction ID check) ----------------
# Set these in Render -> Environment.  Without VERIFY_API_KEY the check is OFF
# (the bot still asks for the ID and shows it to you, marked "not checked").
VERIFY_API_KEY = os.environ.get("VERIFY_API_KEY", "")
VERIFY_URL = os.environ.get("VERIFY_URL", "https://verify.et/api/verify")
PAY_NAME = os.environ.get("PAY_NAME", "Mohammed Seid Mohammed")
PAY_CBE_ACCOUNT = os.environ.get("PAY_CBE_ACCOUNT", "1000528274394")
PAY_TELE_PHONE = os.environ.get("PAY_TELE_PHONE", "251963266849")
MAX_TRIES = 3

_BAD_AMT = ("fee", "charge", "vat", "tax", "commission", "service", "balance", "discount")
_RCV = ("receiver", "credited", "beneficiary", "recipient", "payee", "creditor")
VERDICT = {
    "verified": "✅ <b>Verified by the bank</b>",
    "ok": "🟡 <b>Screenshot looks correct</b> (receiver, amount, date) — not confirmed by the bank",
    "bankwarn": "⚠️ <b>Screenshot looks correct, but the bank check did not confirm it — check manually</b>",
    "unknown": "⚪ <b>Could not be read automatically — please check it yourself</b>",
    "off": "⚪ <b>Not checked (screenshot check is off)</b>",
}


def valid_ref(method, ref):
    if ref.lower().startswith("http"):
        return True
    if method == "cbe":
        return bool(re.fullmatch(r"FT[A-Z0-9]{8,20}", ref.upper()))
    return bool(re.fullmatch(r"[A-Z0-9]{10}", ref.upper()))


def _flat(o, out=None, key=""):
    out = {} if out is None else out
    if isinstance(o, dict):
        for k, v in o.items():
            _flat(v, out, f"{key}.{k}".lower() if key else str(k).lower())
    elif isinstance(o, list):
        for i, v in enumerate(o):
            _flat(v, out, f"{key}.{i}")
    else:
        out[key] = o
    return out


def _num(v):
    m = re.search(r"\d[\d,]*(?:\.\d+)?", str(v))
    if not m:
        return None
    try:
        return float(m.group(0).replace(",", ""))
    except ValueError:
        return None


def judge(method, price, data, status):
    """-> (verdict, note). verdict: verified | unknown | notfound | mismatch | low"""
    if status == 404:
        return "notfound", "HTTP 404"
    if status >= 400:
        return "unknown", f"HTTP {status}"
    if not isinstance(data, (dict, list)):
        return "unknown", "unreadable response"
    flat = _flat(data)
    for k, v in flat.items():
        if k.split(".")[-1] in ("success", "verified", "valid", "isvalid", "exists", "found") and v is False:
            return "notfound", f"{k}=false"
    amount = None
    for k, v in flat.items():
        if "amount" in k and not any(b in k for b in _BAD_AMT):
            amount = _num(v)
            if amount is not None:
                break
    rcv = " ".join(str(v) for k, v in flat.items() if any(r in k for r in _RCV))
    if amount is None or not rcv.strip():
        return "unknown", "response had no amount / receiver"
    tail = (PAY_CBE_ACCOUNT if method == "cbe" else PAY_TELE_PHONE)[-4:]
    digits = re.sub(r"\D", "", rcv)
    low = rcv.lower()
    name_ok = all(tok in low for tok in PAY_NAME.lower().split())
    if not (name_ok or tail in digits):
        return "mismatch", f"receiver: {rcv[:80]}"
    if amount + 0.01 < price:
        return "low", f"amount {amount} < {price}"
    return "verified", f"amount {amount}"


def verify_payment(method, ref, price):
    """Blocking call (run it in a thread). Returns (verdict, note)."""
    if not VERIFY_API_KEY:
        return "off", "verification not configured"
    body = {"bank": "cbe" if method == "cbe" else "telebirr"}
    if method == "cbe":
        body["referenceNumber"] = ref
        body["accountSuffix"] = PAY_CBE_ACCOUNT[-8:]
    else:
        body["transactionNumber"] = ref
    try:
        r = requests.post(
            VERIFY_URL, params={"waitMs": 5000}, json=body, timeout=20,
            headers={"x-api-key": VERIFY_API_KEY, "Idempotency-Key": str(uuid.uuid4())},
        )
    except Exception as ex:
        return "unknown", f"service error: {ex}"
    try:
        data = r.json()
    except ValueError:
        data = None
    print("Verify response:", r.status_code, str(data)[:500])  # needed to tune the parser
    return judge(method, price, data, r.status_code)


# ---------------- screenshot reading (AI vision) ----------------
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")      # FREE tier (Google AI Studio)
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-flash-latest")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")  # paid alternative
OCR_MODEL = os.environ.get("OCR_MODEL", "claude-haiku-5-5")
MAX_AGE_H = int(os.environ.get("MAX_AGE_H", "48"))   # receipts older than this are rejected
RECEIPT_PROMPT = (
    "You read Ethiopian payment receipt screenshots (CBE, Telebirr, other banks). "
    "Return ONLY one JSON object and nothing else, with these keys: "
    'is_receipt (true/false), bank ("cbe", "telebirr" or "other"), '
    "receiver_name (the person or company the money was sent TO, or null), "
    "receiver_phone_or_account (the receiver's phone/account exactly as printed, may be masked, or null), "
    "amount (number in ETB that was transferred, or null), "
    'date (as printed, converted to "YYYY-MM-DD HH:MM" 24-hour, or null), '
    "transaction_id (or null). "
    "The sender is the account the money was debited FROM; the receiver is who it was paid TO "
    '(for CBE, the name after the word "for"; for Telebirr, the credited party). '
    "Use null for anything you cannot read clearly. Never guess."
)


def read_receipt(image_bytes, media_type="image/jpeg"):
    """Blocking (run in a thread). Returns a dict of fields or None."""
    try:
        if GEMINI_API_KEY:
            r = requests.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent",
                headers={"x-goog-api-key": GEMINI_API_KEY, "content-type": "application/json"},
                json={"contents": [{"parts": [
                          {"inline_data": {"mime_type": media_type,
                                           "data": base64.b64encode(image_bytes).decode()}},
                          {"text": RECEIPT_PROMPT}]}],
                      "generationConfig": {"responseMimeType": "application/json", "temperature": 0}},
                timeout=40,
            )
            if r.status_code != 200:
                print("Receipt read (Gemini) HTTP", r.status_code, r.text[:300])
                return None
            parts = r.json()["candidates"][0]["content"]["parts"]
            text = "".join(p.get("text", "") for p in parts)
            m = re.search(r"\{.*\}", text, re.S)
            return json.loads(m.group(0)) if m else None
        r = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": ANTHROPIC_API_KEY, "anthropic-version": "2023-06-01",
                     "content-type": "application/json"},
            json={"model": OCR_MODEL, "max_tokens": 400, "messages": [{"role": "user", "content": [
                {"type": "image", "source": {"type": "base64", "media_type": media_type,
                                             "data": base64.b64encode(image_bytes).decode()}},
                {"type": "text", "text": RECEIPT_PROMPT}]}]},
            timeout=40,
        )
        if r.status_code != 200:
            print("Receipt read HTTP", r.status_code, r.text[:300])
            return None
        text = "".join(b.get("text", "") for b in r.json().get("content", []) if b.get("type") == "text")
        m = re.search(r"\{.*\}", text, re.S)
        return json.loads(m.group(0)) if m else None
    except Exception as ex:
        print("Receipt read error:", ex)
        return None


def judge_receipt(method, price, f, now_eat):
    """-> (verdict, note). verdict: ok | unknown | notreceipt | wrong | low | old"""
    if not isinstance(f, dict):
        return "unknown", "could not read the image"
    if f.get("is_receipt") is False:
        return "notreceipt", "not a payment receipt"
    amount = _num(f.get("amount")) if f.get("amount") is not None else None
    rname = str(f.get("receiver_name") or "").strip()
    racc = str(f.get("receiver_phone_or_account") or "").strip()
    if amount is None and not rname and not racc:
        return "unknown", "nothing readable"
    if not rname and not racc:
        return "unknown", "receiver not readable"
    bank = f.get("bank")
    src = PAY_CBE_ACCOUNT if (bank == "cbe" or (bank not in ("cbe", "telebirr") and method == "cbe")) else PAY_TELE_PHONE
    digs = re.sub(r"\D", "", racc)
    tail_ok = src[-4:] in digs
    if not tail_ok and src is PAY_TELE_PHONE:   # masked phones like 0963***849
        tail_ok = digs.startswith(("0963", "251963", "963")) and digs.endswith(src[-3:])
    words = re.findall(r"[a-z]+", rname.lower())
    name_ok = bool(words) and all(
        any(difflib.SequenceMatcher(None, tok, w).ratio() >= 0.8 for w in words)
        for tok in PAY_NAME.lower().split())
    if not (name_ok or tail_ok):
        return "wrong", f"receiver: {(rname or racc)[:80]}"
    if amount is None:
        return "unknown", "amount not readable"
    if amount + 0.01 < price:
        return "low", f"amount {amount:g} < {price}"
    d = None
    try:
        d = datetime.strptime(str(f.get("date"))[:16], "%Y-%m-%d %H:%M")
    except (ValueError, TypeError):
        pass
    if d:
        age_h = (now_eat - d).total_seconds() / 3600
        if age_h > MAX_AGE_H or age_h < -3:
            return "old", f"receipt date {d:%Y-%m-%d %H:%M}"
    return "ok", f"amount {amount:g}"


def fmt_eat(dt):
    """UTC datetime -> 'Oct 24, 18:30 EAT' (Ethiopia time)."""
    return (dt + timedelta(hours=3)).strftime("%b %d, %H:%M") + " EAT"


def parse_when(text, now_eat):
    """Parse an admin-typed Ethiopia date/time. Returns naive EAT datetime or None."""
    t = (text or "").strip().lower()
    if t == "now":
        return now_eat
    m = _WHEN_RE.match(t)
    if not m:
        return None
    y1, mo1, d1, d2, mo2, y2, hh, mm, ap = m.groups()
    hh, mm = int(hh), int(mm)
    if ap:
        if not 1 <= hh <= 12:
            return None
        hh = hh % 12 + (12 if ap == "pm" else 0)
    if hh > 23 or mm > 59:
        return None
    try:
        if y1:
            day = datetime(int(y1), int(mo1), int(d1))
        elif d2:
            year = int(y2) if y2 else now_eat.year
            day = datetime(year, int(mo2), int(d2))          # day / month
            if not y2 and day.date() < now_eat.date():
                day = day.replace(year=year + 1)
        else:
            day = None
        if day is None:
            dt = now_eat.replace(hour=hh, minute=mm, second=0, microsecond=0)
            if dt < now_eat - timedelta(minutes=1):
                dt += timedelta(days=1)
            return dt
        return day.replace(hour=hh, minute=mm)
    except ValueError:
        return None


def setup_ads(application, users_col, admin_id, translations, channel):
    db = users_col.database
    orders = db["orders"]
    counters = db["counters"]
    pay_refs = db["pay_refs"]

    # ---------------- buttons (coloured, with premium icons, safe fallback) ----------------
    def B(text, data, style=None, icon=None, ic=True):
        kw = {"text": text, "callback_data": data}
        if icon and ic:
            kw["icon_custom_emoji_id"] = icon
        if style:
            kw["api_kwargs"] = {"style": style}
        return InlineKeyboardButton(**kw)

    async def kb_call(make_send, make_kb):
        """Send with icon buttons; if Telegram refuses, retry with plain buttons."""
        try:
            return await make_send(make_kb(True))
        except Exception as ex:
            print("Ads: retrying without button icons:", ex)
            return await make_send(make_kb(False))

    async def lang_of(uid):
        try:
            d = await asyncio.to_thread(users_col.find_one, {"_id": uid}, {"lang": 1})
            lang = d.get("lang") if d else None
        except Exception:
            lang = None
        return lang if lang in TXT else "am"

    def post_link(o):
        return f"https://t.me/{channel.lstrip('@')}/{o.get('channel_msg')}"

    def now_utc():
        return datetime.utcnow()

    # ---------------- user keyboards ----------------
    def dur_kb(lang):
        t = TXT[lang]
        def make(ic):
            return InlineKeyboardMarkup([
                [B(t["dur12"], "ad_dur:12", "primary", ICON["dur"], ic)],
                [B(t["dur24"], "ad_dur:24", "success", ICON["dur"], ic),
                 B(t["dur48"], "ad_dur:48", "success", ICON["dur"], ic)],
                [InlineKeyboardButton(
                    translations[lang]["btn_back"], callback_data="cmd_back",
                    **({"icon_custom_emoji_id": ICON["back"]} if ic else {}),
                    api_kwargs={"style": "primary"})],
            ])
        return make

    def pay_kb(lang):
        t = TXT[lang]
        def make(ic):
            return InlineKeyboardMarkup([
                [B(t["cbe"], "ad_pay:cbe", "primary", ICON["cbe"], ic)],
                [B(t["tele"], "ad_pay:tele", "success", ICON["tele"], ic)],
                [B(t["back"], "ad_back", "primary", None, ic), B(t["cancel"], "ad_cancel", "danger", None, ic)],
            ])
        return make

    def cancel_kb(lang):
        def make(ic):
            return InlineKeyboardMarkup([[B(TXT[lang]["cancel"], "ad_cancel", "danger", None, ic)]])
        return make

    def back_menu_kb(lang):
        def make(ic):
            return InlineKeyboardMarkup([[InlineKeyboardButton(
                translations[lang]["btn_back"], callback_data="cmd_back",
                **({"icon_custom_emoji_id": ICON["back"]} if ic else {}),
                api_kwargs={"style": "primary"})]])
        return make

    # ---------------- admin keyboards & texts ----------------
    def decision_kb(n):
        def make(ic):
            return InlineKeyboardMarkup([
                [B("✏️ Edit post", f"ad_ed:{n}", "primary", None, ic),
                 B("Continue (no edit)", f"ad_go:{n}", "success", ICON["ok"], ic)],
                [B("❌ Reject", f"ad_no:{n}", "danger", None, ic)],
            ])
        return make

    def sched_kb(n):
        def make(ic):
            return InlineKeyboardMarkup([[
                B("⚡ Publish now", f"ad_now:{n}", "success", None, ic),
                B("❌ Cancel", f"ad_sc:{n}", "danger", None, ic),
            ]])
        return make

    def header(o, status, ask=None):
        uname = f"@{html.escape(o['username'])}" if o.get("username") else "-"
        lines = [
            f"🧾 <b>Order #{o['_id']}</b>",
            f"👤 <b>Name:</b> {html.escape(o['name'])}  {uname}",
            f"🆔 <b>ID:</b> <code>{o['user_id']}</code>",
            f"⏱ <b>Duration:</b> {o['hours']} Hours — {o['price']}",
            f"{e('card')} <b>Payment:</b> {PAY_LABEL.get(o.get('method'))}",
            *(
                ([f"🔖 <b>Transaction ID:</b> <code>{html.escape(str(o['txid']))}</code>"] if o.get("txid") else [])
                + ([f"🔎 <b>Check:</b> {VERDICT.get(o['verdict'], '—')}"
                    + (f" <i>({html.escape(str(o.get('vnote'))[:100])})</i>"
                       if o.get("verdict") in ("unknown", "bankwarn", "ok") else "")]
                   if o.get("verdict") else [])
            ),
            f"📅 <b>Ordered:</b> {fmt_eat(o['created'])}",
            "",
            f"<b>Status:</b> {status}",
        ]
        if ask:
            lines += ["", ask]
        return "\n".join(lines)

    ST_PENDING = f"{e('wait')} Pending"
    ASK_EDIT = f"{e('info')} <b>Do you want to edit this post before publishing?</b>"

    async def send_order_to_admin(bot, o):
        try:
            await bot.copy_message(chat_id=admin_id, from_chat_id=o["post_chat"], message_id=o["post_msg"])
        except Exception as ex:
            await bot.send_message(admin_id, f"⚠️ Could not copy the post of order #{o['_id']}: {ex}")
        h = header(o, ST_PENDING, ASK_EDIT)
        if o.get("rcpt_msg"):
            m = await kb_call(
                lambda kb: bot.copy_message(
                    chat_id=admin_id, from_chat_id=o["rcpt_chat"], message_id=o["rcpt_msg"],
                    caption=h, parse_mode="HTML", reply_markup=kb),
                decision_kb(o["_id"]))
            cap = True
        else:
            h2 = h + "\n\n💬 <i>Price is negotiable. Reply to this message to talk to the user.</i>"
            m = await kb_call(
                lambda kb: bot.send_message(admin_id, h2, parse_mode="HTML", reply_markup=kb),
                decision_kb(o["_id"]))
            cap = False
        await asyncio.to_thread(
            orders.update_one, {"_id": o["_id"]}, {"$set": {"admin_msg": m.message_id, "admin_cap": cap}}
        )

    async def mark_admin(bot, o, status, ask=None):
        """Rewrite the admin's order message (and remove its buttons)."""
        if not o.get("admin_msg"):
            return
        h = header(o, status, ask)
        try:
            if o.get("admin_cap"):
                await bot.edit_message_caption(chat_id=admin_id, message_id=o["admin_msg"], caption=h, parse_mode="HTML")
            else:
                await bot.edit_message_text(chat_id=admin_id, message_id=o["admin_msg"], text=h, parse_mode="HTML")
        except Exception as ex:
            print("Ads mark_admin error:", ex)

    async def notify(bot, o, key, **extra):
        lang = await lang_of(o["user_id"])
        try:
            await bot.send_message(
                o["user_id"],
                TXT[lang][key].format(n=o["_id"], hours=o["hours"], price=o["price"], link=post_link(o), **extra),
                parse_mode="HTML",
            )
            return True
        except Exception as ex:
            print("Ads notify error:", ex)
            return False

    def _make_order(user, st, lang):
        n = counters.find_one_and_update(
            {"_id": "orders"}, {"$inc": {"n": 1}}, upsert=True, return_document=ReturnDocument.AFTER
        )["n"]
        doc = {
            "_id": n, "user_id": user.id, "lang": lang, "name": user.full_name,
            "username": user.username or "",
            "post_chat": st["post_chat"], "post_msg": st["post_msg"],
            "hours": st["hours"], "price": PRICES[st["hours"]], "method": st.get("method"),
            "rcpt_chat": st.get("rcpt_chat"), "rcpt_msg": st.get("rcpt_msg"),
            "txid": st.get("txid"), "verdict": st.get("verdict"), "vnote": st.get("vnote"),
            "status": "pending", "created": now_utc(),
        }
        orders.insert_one(doc)
        if doc.get("txid"):
            try:  # reserve the ID so it can never be used again
                pay_refs.insert_one({"_id": doc["txid"], "order": n, "at": now_utc()})
            except Exception:
                pass
        return doc

    def ensure_loop(app):
        if "_ads_loop" not in app.bot_data:
            app.bot_data["_ads_loop"] = asyncio.create_task(expiry_loop(app))

    # ================= USER SIDE =================
    async def clear_state(update, context):
        ensure_loop(context.application)
        context.user_data.pop("ad", None)
        context.user_data.pop("adm_ad", None)

    async def show_intro(q, lang):
        await kb_call(
            lambda kb: q.edit_message_text(TXT[lang]["intro"], reply_markup=kb, parse_mode="HTML"),
            dur_kb(lang))

    async def on_order_start(update, context):
        q = update.callback_query
        await q.answer()
        lang = await lang_of(q.from_user.id)
        context.user_data["ad"] = {"step": "duration", "ts": time.time()}
        try:
            await show_intro(q, lang)
        except Exception as ex:
            print("Ads intro error:", ex)
        raise ApplicationHandlerStop

    REASONS = {"notreceipt": "scr_notreceipt", "wrong": "scr_wrong", "low": "scr_low",
               "old": "scr_old", "dup": "scr_dup"}

    async def run_verify(bot, chat_id, st, lang, file_id, user_data):
        """Reads the screenshot in the background so the bot stays responsive."""
        t = TXT[lang]
        method = st.get("method")
        price = int(PRICES[st["hours"]].split()[0])
        verdict, note, txid = "unknown", "", None
        try:
            if not (GEMINI_API_KEY or ANTHROPIC_API_KEY):
                verdict, note = "off", "screenshot check is off"
            else:
                tg_file = await bot.get_file(file_id)
                data = bytes(await tg_file.download_as_bytearray())
                mt = ("image/png" if data[:8] == b"\x89PNG\r\n\x1a\n"
                      else "image/webp" if data[8:12] == b"WEBP" else "image/jpeg")
                fields = await asyncio.to_thread(read_receipt, data, mt)
                print("Receipt read:", fields)
                now_eat = now_utc() + timedelta(hours=3)
                verdict, note = judge_receipt(method, price, fields, now_eat)
                if isinstance(fields, dict):
                    tid = str(fields.get("transaction_id") or "").strip().upper()
                    txid = tid if re.fullmatch(r"[A-Z0-9]{8,24}", tid) else None
                if verdict in ("ok", "unknown") and txid:
                    if await asyncio.to_thread(pay_refs.find_one, {"_id": txid}):
                        verdict, note = "dup", "receipt already used"
                if verdict == "ok" and txid and VERIFY_API_KEY:
                    bm = "cbe" if fields.get("bank") == "cbe" else "tele"
                    bv, bnote = await asyncio.to_thread(verify_payment, bm, txid, price)
                    # the bank check can only upgrade or warn, it never rejects on its own
                    if bv == "verified":
                        verdict, note = "verified", bnote
                    elif bv in ("notfound", "mismatch", "low"):
                        verdict, note = "bankwarn", bnote
        except Exception as ex:
            print("Ads verify error:", ex)
            verdict, note = "unknown", f"error: {ex}"

        if user_data.get("ad") is not st:      # the user cancelled meanwhile
            return

        async def say(k, kbf, **fmt):
            await kb_call(
                lambda kb: bot.send_message(chat_id, t[k].format(**fmt), reply_markup=kb, parse_mode="HTML"), kbf)

        if verdict in REASONS:
            st["tries"] = st.get("tries", 0) + 1
            print(f"Ads receipt rejected ({verdict}): {note}")
            if st["tries"] >= MAX_TRIES:
                user_data.pop("ad", None)
                await say("txid_blocked", back_menu_kb(lang))
                return
            st["step"] = "receipt"
            await say(REASONS[verdict], cancel_kb(lang), left=MAX_TRIES - st["tries"])
            return
        st.update(step="post", txid=txid, verdict=verdict, vnote=note[:200], ts=time.time())
        await say("scr_ok", cancel_kb(lang))

    async def capture(update, context):
        ensure_loop(context.application)
        msg = update.message
        if not msg or update.effective_chat.type != "private":
            return
        uid = update.effective_user.id
        text = (msg.text or "").strip()

        # ---- admin: editing a post / typing the publish time ----
        ast = context.user_data.get("adm_ad")
        if ast and uid == admin_id:
            if time.time() - ast["ts"] > FLOW_TTL or text == "🏠 Menu":
                context.user_data.pop("adm_ad", None)
                return
            n = ast["n"]
            if ast["mode"] == "edit":
                await asyncio.to_thread(
                    orders.update_one, {"_id": n, "status": {"$in": ["pending", "failed"]}},
                    {"$set": {"post_chat": msg.chat_id, "post_msg": msg.message_id, "edited": True}})
                await msg.reply_text(f"{e('ok')} <b>Edited post saved.</b>", parse_mode="HTML")
                await ask_schedule(context, n)
                raise ApplicationHandlerStop
            if ast["mode"] == "sched":
                now_eat = now_utc() + timedelta(hours=3)
                when = parse_when(text, now_eat)
                if when is None:
                    await msg.reply_text(
                        "❌ <b>I couldn't read that.</b>\nSend like <code>2026-10-25 18:30</code>, "
                        "<code>25/10 6:30 PM</code> or <code>18:30</code>.", parse_mode="HTML")
                    raise ApplicationHandlerStop
                if when < now_eat - timedelta(minutes=1):
                    await msg.reply_text("❌ <b>That time is in the past.</b> Send a future date and time.", parse_mode="HTML")
                    raise ApplicationHandlerStop
                context.user_data.pop("adm_ad", None)
                await do_schedule(context.bot, n, when - timedelta(hours=3))
                raise ApplicationHandlerStop
            return

        # ---- user: order flow ----
        st = context.user_data.get("ad")
        if not st:
            return
        if time.time() - st["ts"] > FLOW_TTL:
            context.user_data.pop("ad", None)
            return
        if text == "🏠 Menu":
            context.user_data.pop("ad", None)
            return
        lang = await lang_of(uid)
        t = TXT[lang]
        step = st["step"]

        if step == "duration":
            await kb_call(lambda kb: msg.reply_text(t["intro"], reply_markup=kb, parse_mode="HTML"), dur_kb(lang))
            raise ApplicationHandlerStop

        if step == "payment":
            await kb_call(
                lambda kb: msg.reply_text(
                    t["pay_choose"].format(hours=st["hours"], price=PRICES[st["hours"]]),
                    reply_markup=kb, parse_mode="HTML"),
                pay_kb(lang))
            raise ApplicationHandlerStop

        if step == "receipt":
            is_img = bool(msg.photo) or bool(msg.document and (msg.document.mime_type or '').startswith('image/'))
            if not is_img:
                await kb_call(lambda kb: msg.reply_text(t["bad_receipt"], reply_markup=kb, parse_mode="HTML"), cancel_kb(lang))
                raise ApplicationHandlerStop
            st.update(step="verifying", rcpt_chat=msg.chat_id, rcpt_msg=msg.message_id, ts=time.time())
            file_id = msg.photo[-1].file_id if msg.photo else msg.document.file_id
            await msg.reply_text(t["txid_checking"], parse_mode="HTML")
            context.application.create_task(
                run_verify(context.bot, update.effective_chat.id, st, lang, file_id, context.user_data))
            raise ApplicationHandlerStop

        if step == "verifying":
            await msg.reply_text(t["txid_wait"], parse_mode="HTML")
            raise ApplicationHandlerStop

        if step == "post":
            st.update(post_chat=msg.chat_id, post_msg=msg.message_id)
            o = await asyncio.to_thread(_make_order, update.effective_user, st, lang)
            context.user_data.pop("ad", None)
            key = "received" if st.get("rcpt_msg") else "received_neg"
            await msg.reply_text(t[key].format(n=o["_id"]), parse_mode="HTML")
            try:
                await send_order_to_admin(context.bot, o)
            except Exception as ex:
                print("Ads send to admin error:", ex)
            raise ApplicationHandlerStop

    async def on_user_cb(update, context):
        q = update.callback_query
        uid = q.from_user.id
        lang = await lang_of(uid)
        t = TXT[lang]
        st = context.user_data.get("ad")
        data = q.data

        if data == "ad_cancel":
            context.user_data.pop("ad", None)
            await q.answer()
            try:
                await kb_call(lambda kb: q.edit_message_text(t["cancelled"], reply_markup=kb, parse_mode="HTML"), back_menu_kb(lang))
            except Exception:
                pass
            return

        if not st or time.time() - st["ts"] > FLOW_TTL:
            context.user_data.pop("ad", None)
            await q.answer(t["session"], show_alert=True)
            return
        await q.answer()
        st["ts"] = time.time()

        try:
            if data == "ad_back":
                st["step"] = "duration"
                await show_intro(q, lang)

            elif data.startswith("ad_dur:"):
                hours = int(data.split(":")[1])
                if hours not in PRICES:
                    return
                st["hours"] = hours
                if hours == 12:                       # negotiable: no payment step
                    st.update(step="post", method=None)
                    await kb_call(lambda kb: q.edit_message_text(t["ask_post_neg"], reply_markup=kb, parse_mode="HTML"), cancel_kb(lang))
                else:
                    st["step"] = "payment"
                    await kb_call(
                        lambda kb: q.edit_message_text(
                            t["pay_choose"].format(hours=hours, price=PRICES[hours]),
                            reply_markup=kb, parse_mode="HTML"),
                        pay_kb(lang))

            elif data.startswith("ad_pay:"):
                if st.get("step") != "payment":
                    return
                method = data.split(":")[1]
                if method not in ("cbe", "tele"):
                    return
                st.update(step="receipt", method=method)
                key = "pay_cbe" if method == "cbe" else "pay_tele"
                await kb_call(
                    lambda kb: q.edit_message_text(
                        t[key].format(price=PRICES[st["hours"]]), reply_markup=kb, parse_mode="HTML"),
                    cancel_kb(lang))
        except Exception as ex:
            print("Ads user callback error:", ex)

    # ================= ADMIN SIDE =================
    async def ask_schedule(context, n):
        context.user_data["adm_ad"] = {"mode": "sched", "n": n, "ts": time.time()}
        now_eat = now_utc() + timedelta(hours=3)
        tmr = now_eat + timedelta(days=1)
        text = (
            f"{e('ad')} <b>Order #{n}</b> — when should it be published?\n\n"
            f"🕒 Now: <b>{now_eat.strftime('%b %d, %H:%M')} EAT</b>\n\n"
            "Send the <b>date and time</b> (Ethiopia time), for example:\n"
            f"<code>{tmr.strftime('%Y-%m-%d')} 18:30</code>\n"
            f"<code>{tmr.strftime('%d/%m')} 6:30 PM</code>\n"
            "<code>18:30</code> (today, or tomorrow if it has passed)\n\n"
            "Or press <b>Publish now</b>."
        )
        await kb_call(
            lambda kb: context.bot.send_message(admin_id, text, parse_mode="HTML", reply_markup=kb),
            sched_kb(n))

    async def do_schedule(bot, n, publish_at):
        o = await asyncio.to_thread(
            orders.find_one_and_update, {"_id": n, "status": {"$in": ["pending", "failed"]}},
            {"$set": {"status": "scheduled", "publish_at": publish_at}}, return_document=ReturnDocument.AFTER,
        )
        if not o:
            await bot.send_message(admin_id, f"Order #{n} was already handled.")
            return
        if publish_at <= now_utc() + timedelta(seconds=45):
            await publish_order(bot, n)
            return
        await mark_admin(bot, o, f"🗓 <b>Scheduled</b> — {fmt_eat(publish_at)}")
        await bot.send_message(
            admin_id, f"{e('ok')} <b>Order #{n} scheduled</b> for <b>{fmt_eat(publish_at)}</b>.", parse_mode="HTML")
        if not await notify(bot, o, "scheduled", when=fmt_eat(publish_at)):
            await bot.send_message(admin_id, f"⚠️ Order #{n} is scheduled, but I couldn't message the user.")

    async def publish_order(bot, n):
        o = await asyncio.to_thread(
            orders.find_one_and_update, {"_id": n, "status": "scheduled"},
            {"$set": {"status": "publishing"}}, return_document=ReturnDocument.AFTER,
        )
        if not o:
            return
        try:
            sent = await bot.copy_message(chat_id=channel, from_chat_id=o["post_chat"], message_id=o["post_msg"])
        except Exception as ex:
            await asyncio.to_thread(orders.update_one, {"_id": n}, {"$set": {"status": "failed", "error": str(ex)[:200]}})
            await bot.send_message(
                admin_id,
                f"⚠️ <b>Could not publish order #{n} to {channel}</b>\n<code>{html.escape(str(ex))}</code>\n\n"
                "Make sure the bot is an admin of the channel with permission to post, then open the order "
                "from 🧾 Orders and schedule it again.", parse_mode="HTML")
            return
        now = now_utc()
        end = now + timedelta(seconds=min(o["hours"] * 3600, MAX_DELETE_SECONDS))
        await asyncio.to_thread(
            orders.update_one, {"_id": n},
            {"$set": {"status": "posted", "channel_msg": sent.message_id, "posted_at": now, "delete_at": end}})
        o.update(status="posted", channel_msg=sent.message_id, delete_at=end)
        await mark_admin(bot, o, f"{e('ok')} <b>Live</b> — removes {fmt_eat(end)}")
        await bot.send_message(
            admin_id, f"{e('ok')} <b>Order #{n} is live</b> on {channel}.\n🔗 {post_link(o)}\n"
            f"⏰ Removes automatically: <b>{fmt_eat(end)}</b>", parse_mode="HTML", disable_notification=True)
        if not await notify(bot, o, "posted"):
            await bot.send_message(admin_id, f"⚠️ Order #{n} is live, but I couldn't message the user.")

    async def orders_view():
        def _q():
            pend = list(orders.find({"status": {"$in": ["pending", "failed"]}}).sort("_id", 1).limit(8))
            sched = list(orders.find({"status": "scheduled"}).sort("publish_at", 1).limit(8))
            live = list(orders.find({"status": "posted"}).sort("delete_at", 1).limit(8))
            c = {s: orders.count_documents({"status": s})
                 for s in ("pending", "failed", "scheduled", "posted", "expired", "removed", "rejected", "cancelled")}
            return pend, sched, live, c

        pend, sched, live, c = await asyncio.to_thread(_q)
        lines = [
            "🧾 <b>Orders</b>\n",
            f"{e('wait')} Pending: <b>{c['pending'] + c['failed']}</b>   🗓 Scheduled: <b>{c['scheduled']}</b>   🟢 Live: <b>{c['posted']}</b>",
            f"✔️ Finished: <b>{c['expired'] + c['removed']}</b>   ❌ Rejected: <b>{c['rejected'] + c['cancelled']}</b>",
        ]
        rows = []

        def row(text, data, style, icon=None):
            return (text, data, style, icon)

        if pend:
            lines.append("\n<b>Waiting for you</b>")
            for o in pend:
                warn = " ⚠️ failed" if o["status"] == "failed" else ""
                lines.append(f"#{o['_id']} · {html.escape(o['name'])} · {o['hours']}h{warn}")
                rows.append(row(f"#{o['_id']} · {o['hours']}h · open", f"ad_open:{o['_id']}", "primary", ICON["dur"]))
        if sched:
            lines.append("\n<b>Scheduled</b>")
            for o in sched:
                lines.append(f"#{o['_id']} · publishes {fmt_eat(o['publish_at'])}")
                rows.append(row(f"🗓 Cancel #{o['_id']}", f"ad_cx:{o['_id']}", "danger"))
        if live:
            lines.append("\n<b>Live ads</b>")
            for o in live:
                lines.append(f"#{o['_id']} · ends {fmt_eat(o['delete_at'])}")
                rows.append(row(f"🗑 Remove #{o['_id']}", f"ad_rm:{o['_id']}", "danger"))
        rows.append(row("⬅️ Back", "adm_back", "primary", ICON["back"]))

        def make(ic):
            return InlineKeyboardMarkup([[B(t_, d_, s_, i_, ic)] for (t_, d_, s_, i_) in rows])
        return "\n".join(lines), make

    async def cmd_orders(update, context):
        text, make = await orders_view()
        await kb_call(lambda kb: update.message.reply_text(text, reply_markup=kb, parse_mode="HTML"), make)

    async def on_orders_btn(update, context):
        q = update.callback_query
        if q.from_user.id != admin_id:
            await q.answer("Not allowed", show_alert=True)
            return
        await q.answer()
        text, make = await orders_view()
        try:
            await kb_call(lambda kb: q.edit_message_text(text, reply_markup=kb, parse_mode="HTML"), make)
        except Exception as ex:
            print("Ads orders view error:", ex)
        raise ApplicationHandlerStop

    async def on_admin_cb(update, context):
        q = update.callback_query
        if q.from_user.id != admin_id:
            await q.answer("Not allowed", show_alert=True)
            return
        await q.answer()
        act, n = q.data.split(":")
        n = int(n)
        bot = context.bot

        async def get(statuses):
            return await asyncio.to_thread(orders.find_one, {"_id": n, "status": {"$in": statuses}})

        if act == "ad_open":
            o = await get(["pending", "failed"])
            if o:
                await send_order_to_admin(bot, o)
            else:
                await bot.send_message(admin_id, f"Order #{n} is not waiting for you anymore.")
            return

        if act == "ad_ed":
            o = await get(["pending", "failed"])
            if not o:
                await bot.send_message(admin_id, f"Order #{n} was already handled.")
                return
            context.user_data["adm_ad"] = {"mode": "edit", "n": n, "ts": time.time()}
            await mark_admin(bot, o, "✏️ <b>Editing</b> — waiting for your edited post")
            await bot.send_message(
                admin_id,
                f"✏️ <b>Order #{n}</b> — send the <b>edited post</b> now (text, photo or video).\n\n"
                "The bot will publish exactly what you send. Send /cancel to go back.",
                parse_mode="HTML")
            return

        if act == "ad_go":
            o = await get(["pending", "failed"])
            if not o:
                await bot.send_message(admin_id, f"Order #{n} was already handled.")
                return
            await mark_admin(bot, o, "🗓 <b>Choosing publish time…</b>")
            await ask_schedule(context, n)
            return

        if act == "ad_now":
            context.user_data.pop("adm_ad", None)
            await do_schedule(bot, n, now_utc())
            return

        if act == "ad_sc":
            context.user_data.pop("adm_ad", None)
            o = await get(["pending", "failed"])
            if o:
                await send_order_to_admin(bot, o)
            return

        if act == "ad_no":
            o = await asyncio.to_thread(
                orders.find_one_and_update, {"_id": n, "status": {"$in": ["pending", "failed"]}},
                {"$set": {"status": "rejected"}}, return_document=ReturnDocument.AFTER)
            if not o:
                await bot.send_message(admin_id, f"Order #{n} was already handled.")
                return
            await mark_admin(bot, o, "❌ <b>Rejected</b>")
            if not await notify(bot, o, "rejected"):
                await bot.send_message(admin_id, f"⚠️ Order #{n} rejected, but I couldn't message the user.")
            return

        if act in ("ad_rm", "ad_cx"):
            what = "Remove ad" if act == "ad_rm" else "Cancel the scheduled order"
            yes = "ad_rmy" if act == "ad_rm" else "ad_cxy"
            kb = lambda ic: InlineKeyboardMarkup([[
                B("✅ Yes", f"{yes}:{n}", "danger", None, ic), B("⬅️ No", "adm_orders", "primary", None, ic)]])
            await kb_call(
                lambda k: q.edit_message_text(f"<b>{what} #{n}?</b>", reply_markup=k, parse_mode="HTML"), kb)
            return

        if act == "ad_rmy":
            o = await asyncio.to_thread(
                orders.find_one_and_update, {"_id": n, "status": "posted"},
                {"$set": {"status": "removed"}}, return_document=ReturnDocument.AFTER)
            if o:
                try:
                    await bot.delete_message(chat_id=channel, message_id=o["channel_msg"])
                except Exception as ex:
                    await bot.send_message(admin_id, f"⚠️ Could not delete ad #{n}: {ex}\nDelete it manually: {post_link(o)}")
                await notify(bot, o, "expired")
            text, make = await orders_view()
            await kb_call(lambda k: q.edit_message_text(text, reply_markup=k, parse_mode="HTML"), make)
            return

        if act == "ad_cxy":
            o = await asyncio.to_thread(
                orders.find_one_and_update, {"_id": n, "status": "scheduled"},
                {"$set": {"status": "cancelled"}}, return_document=ReturnDocument.AFTER)
            if o:
                await bot.send_message(
                    admin_id, f"Order #{n} cancelled. The user was not notified — reply to the order message to tell them.")
            text, make = await orders_view()
            await kb_call(lambda k: q.edit_message_text(text, reply_markup=k, parse_mode="HTML"), make)

    # ================= AUTO PUBLISH + AUTO REMOVE =================
    async def expiry_loop(app):
        await asyncio.sleep(15)
        while True:
            try:
                now = now_utc()
                # 1) scheduled ads whose time has come
                due_pub = await asyncio.to_thread(
                    lambda: list(orders.find({"status": "scheduled", "publish_at": {"$lte": now}})))
                for d in due_pub:
                    await publish_order(app.bot, d["_id"])
                # 2) live ads whose hours are over
                due = await asyncio.to_thread(
                    lambda: list(orders.find({"status": "posted", "delete_at": {"$lte": now}})))
                for d in due:
                    o = await asyncio.to_thread(
                        orders.find_one_and_update, {"_id": d["_id"], "status": "posted"},
                        {"$set": {"status": "expired"}}, return_document=ReturnDocument.AFTER)
                    if not o:
                        continue
                    try:
                        await app.bot.delete_message(chat_id=channel, message_id=o["channel_msg"])
                        await app.bot.send_message(
                            admin_id, f"⏰ Ad #{o['_id']} finished and was removed from the channel.",
                            disable_notification=True)
                    except Exception as ex:
                        await app.bot.send_message(
                            admin_id,
                            f"⚠️ Ad #{o['_id']} time is over but I couldn't delete it ({ex}).\n"
                            f"Please delete it manually: {post_link(o)}")
                    await notify(app.bot, o, "expired")
            except Exception as ex:
                print("Ads loop error:", ex)
            await asyncio.sleep(CHECK_EVERY)

    prev_post_init = getattr(application, "post_init", None)

    async def _post_init(app):
        if prev_post_init:
            await prev_post_init(app)
        ensure_loop(app)

    try:
        application.post_init = _post_init
    except AttributeError:
        print("Ads: could not wrap post_init; the loop starts on the first update instead.")

    # ---------------- register ----------------
    # -5 ban gate (admin_panel) | -4 clear flow | -3 admin panel input | -2 ads | 0 main bot
    application.add_handler(MessageHandler(filters.COMMAND, clear_state), group=-4)
    application.add_handler(CallbackQueryHandler(clear_state, pattern=r"^(cmd_|lang_)"), group=-4)

    application.add_handler(CallbackQueryHandler(on_order_start, pattern=r"^cmd_order$"), group=-2)
    application.add_handler(CallbackQueryHandler(on_orders_btn, pattern=r"^adm_orders$"), group=-2)
    application.add_handler(
        CallbackQueryHandler(on_user_cb, pattern=r"^ad_(dur:\d+|pay:(cbe|tele)|back|cancel)$"), group=-2)
    application.add_handler(
        CallbackQueryHandler(on_admin_cb, pattern=r"^ad_(ed|go|no|now|sc|open|rm|rmy|cx|cxy):\d+$"), group=-2)
    application.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, capture), group=-2)
    application.add_handler(CommandHandler("orders", cmd_orders, filters=filters.User(user_id=admin_id)))
