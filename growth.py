"""Growth features for the @mame_posts bot.

1. Daily report (sent to the admin every evening + a panel button).
2. "Invite Friends" with a weekly contest:
   - every user gets a personal link  t.me/<bot>?start=ref_<id>
   - a friend counts only if: new user, not yourself, joined the channel and started the bot
   - the round closes every Sunday 21:00 (Ethiopia time); the result goes to the ADMIN first,
     the admin presses "Announce to everyone" to send it to all users (in their own language)
3. "My Ads" for advertisers (status of their orders + "Order again").
4. /emojiid helper (admin): send a premium emoji, get its ID back.
"""
import asyncio
import html
import os
import re
import time
from datetime import datetime, timedelta
from urllib.parse import quote, urlparse

from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, MessageEntity, Update
from telegram.error import RetryAfter
from telegram.ext import (
    ApplicationHandlerStop,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    TypeHandler,
    filters,
)

DAILY_LIMIT = int(os.environ.get("DAILY_LIMIT", "10"))
REPORT_HOUR = int(os.environ.get("REPORT_HOUR", "20"))        # daily report time (Ethiopia time)
CLOSE_HOUR = int(os.environ.get("CONTEST_CLOSE_HOUR", "21"))  # Sunday closing time (Ethiopia time)

# ---------------- premium emoji ----------------
PE = {
    "trophy": ("5273899469287465771", "🏆"),
    "gold": ("6269400956387987689", "🥇"),
    "silver": ("5447203607294265305", "🥈"),
    "bronze": ("5453902265922376865", "🥉"),
    "ok": ("5260463209562776385", "✅"),
}
ICON_BACK = "5248948801674159296"


def pe(key):
    cid, ch = PE[key]
    return f'<tg-emoji emoji-id="{cid}">{ch}</tg-emoji>'


def plain(s):
    return re.sub(r'<tg-emoji emoji-id="\d+">(.*?)</tg-emoji>', r"\1", s)


def Bt(text, data=None, url=None, style=None, icon=None, ic=True):
    kw = {"text": text}
    if data:
        kw["callback_data"] = data
    if url:
        kw["url"] = url
    if icon and ic:
        kw["icon_custom_emoji_id"] = icon
    if style:
        kw["api_kwargs"] = {"style": style}
    return InlineKeyboardButton(**kw)


async def attempt(op, text, make_kb):
    """op(text, kb) -> awaitable. Premium emoji + icon buttons first, plain fallback second."""
    try:
        return await op(text, make_kb(True))
    except RetryAfter:
        raise
    except Exception as ex:
        print("Growth: plain fallback:", ex)
        return await op(plain(text), make_kb(False))


# ---------------- time helpers (Ethiopia = UTC+3) ----------------
def utcnow():
    return datetime.utcnow()


def eat_day(dt=None):
    return ((dt or utcnow()) + timedelta(hours=3)).strftime("%Y-%m-%d")


def day_bounds_utc(day):
    s = datetime.strptime(day, "%Y-%m-%d") - timedelta(hours=3)
    return s, s + timedelta(days=1)


def fmt_eat(dt):
    return (dt + timedelta(hours=3)).strftime("%b %d, %H:%M")


def next_close(after_utc):
    """Next Sunday CLOSE_HOUR:00 Ethiopia time strictly after `after_utc` (returned as UTC)."""
    e = after_utc + timedelta(hours=3)
    cand = e.replace(hour=CLOSE_HOUR, minute=0, second=0, microsecond=0)
    cand += timedelta(days=(6 - e.weekday()) % 7)
    if cand <= e:
        cand += timedelta(days=7)
    return cand - timedelta(hours=3)


# ---------------- platform detection + daily counters ----------------
PLATFORMS = [
    ("tiktok.com", "TikTok"), ("instagram.com", "Instagram"), ("youtube.com", "YouTube"),
    ("youtu.be", "YouTube"), ("facebook.com", "Facebook"), ("fb.watch", "Facebook"),
    ("fb.com", "Facebook"), ("twitter.com", "X"), ("x.com", "X"), ("pin.it", "Pinterest"),
    ("snapchat.com", "Snapchat"), ("threads.net", "Threads"), ("reddit.com", "Reddit"),
    ("redd.it", "Reddit"), ("soundcloud.com", "SoundCloud"), ("likee.video", "Likee"),
    ("likee.com", "Likee"), ("twitch.tv", "Twitch"), ("vimeo.com", "Vimeo"),
]


def platform_of(url):
    host = (urlparse(url if "://" in url else "https://" + url).hostname or "").lower()
    if "pinterest" in host:
        return "Pinterest"
    for dom, name in PLATFORMS:
        if host == dom or host.endswith("." + dom):
            return name
    return "Other"


def bump_stat(users_col, platform=None, kind="downloads"):
    """Blocking. kind = downloads | converts."""
    try:
        inc = {kind: 1}
        if platform:
            inc[f"p.{platform}"] = 1
        users_col.database["daily_stats"].update_one({"_id": eat_day()}, {"$inc": inc}, upsert=True)
    except Exception as ex:
        print("Stats bump error:", ex)


# ---------------- texts ----------------
I18N = {
    "am": {
        "invite": (
            "🎁 <b>ጓደኛ ጋብዙ — ሽልማት ያሸንፉ!</b>\n\n"
            "ጓደኞችዎን በዚህ ሊንክ ይጋብዙ፤ በሳምንቱ ብዙ ጓደኛ የጋበዘ <b>25 ብር ካርድ</b> ያሸንፋል።\n\n"
            "🔗 <b>የእርስዎ ሊንክ:</b>\n<code>{link}</code>\n\n"
            "👥 <b>የጋበዙት:</b> {total} ሰው (በዚህ ሳምንት፦ {week})\n"
            "⏳ <b>ቻናሉን ገና ያልተቀላቀሉ:</b> {pending}\n\n"
            "{trophy} <b>የዚህ ሳምንት Top 10</b>\n{board}\n\n"
            "📍 <b>የእርስዎ ደረጃ:</b> {myrank}\n"
            "⏰ <b>ውድድሩ የሚዘጋው:</b> እሁድ ምሽት 3:00 (ቀሪ፦ {left})\n\n"
            "<i>ጓደኛው አዲስ ተጠቃሚ ሆኖ ቻናሉን ሲቀላቀል እና ቦቱን ሲጀምር ብቻ ይቆጠራል።</i>"
        ),
        "empty": "ገና ማንም አልጋበዘም — የመጀመሪያው ይሁኑ! 🚀",
        "rank": "{r}ኛ", "people": "{n} ሰው", "left": "{d} ቀን {h} ሰዓት",
        "share_btn": "📤 ሊንኬን አጋራ",
        "share_text": "🔥 ማንኛውንም ቪዲዮ በነጻ ያውርዱ! ይህን ቦት ይሞክሩ:",
        "joined": "🎉 <b>አዲስ ጓደኛ በሊንክዎ ተቀላቀለ!</b>\n{who}\n\n👥 በአጠቃላይ የጋበዙት፦ <b>{total}</b> ሰው",
        "ann_title": "{trophy} <b>የሳምንቱ አሸናፊዎች!</b>",
        "ann_prize": "🎁 <b>አሸናፊው የ25 ብር ካርድ ተሸልሟል!</b>",
        "ann_new": "🚀 <b>አዲስ ሳምንት ተጀምሯል!</b> ጓደኛ ይጋብዙ እና ይሸለሙ።",
        "invite_btn": "🎁 ጓደኛ ጋብዝ",
        "myads_title": "📋 <b>የእኔ ማስታወቂያዎች</b>",
        "myads_none": "ገና ማስታወቂያ አላሰሩም።",
        "again": "🔄 እንደገና ላሰራ",
        "st": {
            "pending": "⏳ አድሚን እየተመለከተ ነው", "scheduled": "🗓 ይለቀቃል፦ {t}",
            "posted": "🟢 በቻናሉ ላይ አለ — እስከ {t}", "expired": "✔️ ተጠናቋል", "removed": "✔️ ተጠናቋል",
            "rejected": "❌ ውድቅ ሆኗል", "cancelled": "❌ ተሰርዟል",
        },
        "hours": "ሰዓት",
    },
    "en": {
        "invite": (
            "🎁 <b>Invite friends — win prizes!</b>\n\n"
            "Invite your friends with your link. Whoever invites the most friends this week wins a <b>25 ETB airtime card</b>.\n\n"
            "🔗 <b>Your link:</b>\n<code>{link}</code>\n\n"
            "👥 <b>Friends invited:</b> {total} (this week: {week})\n"
            "⏳ <b>Not in the channel yet:</b> {pending}\n\n"
            "{trophy} <b>Top 10 this week</b>\n{board}\n\n"
            "📍 <b>Your rank:</b> {myrank}\n"
            "⏰ <b>Closes:</b> Sunday 9:00 PM (time left: {left})\n\n"
            "<i>A friend counts only when they are a new user, join the channel and start the bot.</i>"
        ),
        "empty": "Nobody has invited anyone yet — be the first! 🚀",
        "rank": "#{r}", "people": "{n} friends", "left": "{d}d {h}h",
        "share_btn": "📤 Share my link",
        "share_text": "🔥 Download any video for free! Try this bot:",
        "joined": "🎉 <b>A new friend joined with your link!</b>\n{who}\n\n👥 Total invited: <b>{total}</b>",
        "ann_title": "{trophy} <b>This week's winners!</b>",
        "ann_prize": "🎁 <b>The winner gets a 25 ETB airtime card!</b>",
        "ann_new": "🚀 <b>A new week has started!</b> Invite friends and win.",
        "invite_btn": "🎁 Invite Friends",
        "myads_title": "📋 <b>My Ads</b>",
        "myads_none": "You have no ads yet.",
        "again": "🔄 Order again",
        "st": {
            "pending": "⏳ Waiting for the admin", "scheduled": "🗓 Scheduled: {t}",
            "posted": "🟢 Live until {t}", "expired": "✔️ Finished", "removed": "✔️ Finished",
            "rejected": "❌ Rejected", "cancelled": "❌ Cancelled",
        },
        "hours": "h",
    },
    "ar": {
        "invite": (
            "🎁 <b>ادعُ أصدقاءك واربح جوائز!</b>\n\n"
            "ادعُ أصدقاءك برابطك. من يدعو أكبر عدد من الأصدقاء هذا الأسبوع يفوز ببطاقة رصيد <b>25 بير</b>.\n\n"
            "🔗 <b>رابطك:</b>\n<code>{link}</code>\n\n"
            "👥 <b>الأصدقاء الذين دعوتهم:</b> {total} (هذا الأسبوع: {week})\n"
            "⏳ <b>لم ينضموا للقناة بعد:</b> {pending}\n\n"
            "{trophy} <b>أفضل 10 هذا الأسبوع</b>\n{board}\n\n"
            "📍 <b>ترتيبك:</b> {myrank}\n"
            "⏰ <b>ينتهي:</b> الأحد 9:00 مساءً (المتبقي: {left})\n\n"
            "<i>يُحتسب الصديق فقط إذا كان مستخدماً جديداً وانضم للقناة وبدأ البوت.</i>"
        ),
        "empty": "لم يدعُ أحد أحداً بعد — كن الأول! 🚀",
        "rank": "#{r}", "people": "{n} صديق", "left": "{d} يوم {h} ساعة",
        "share_btn": "📤 شارك رابطي",
        "share_text": "🔥 حمّل أي فيديو مجاناً! جرّب هذا البوت:",
        "joined": "🎉 <b>انضم صديق جديد عبر رابطك!</b>\n{who}\n\n👥 إجمالي من دعوتهم: <b>{total}</b>",
        "ann_title": "{trophy} <b>فائزو هذا الأسبوع!</b>",
        "ann_prize": "🎁 <b>الفائز يحصل على بطاقة رصيد 25 بير!</b>",
        "ann_new": "🚀 <b>بدأ أسبوع جديد!</b> ادعُ أصدقاءك واربح.",
        "invite_btn": "🎁 ادعُ أصدقاءك",
        "myads_title": "📋 <b>إعلاناتي</b>",
        "myads_none": "ليس لديك إعلانات بعد.",
        "again": "🔄 اطلب مرة أخرى",
        "st": {
            "pending": "⏳ بانتظار المسؤول", "scheduled": "🗓 مجدول: {t}",
            "posted": "🟢 منشور حتى {t}", "expired": "✔️ انتهى", "removed": "✔️ انتهى",
            "rejected": "❌ مرفوض", "cancelled": "❌ ملغى",
        },
        "hours": "س",
    },
}


def setup_growth(application, users_col, admin_id, translations, channel):
    db = users_col.database
    referrals = db["referrals"]
    rounds = db["contest_rounds"]
    settings = db["settings"]
    orders = db["orders"]
    channel_name = channel.lstrip("@")

    pending = {}        # invitee_id -> inviter_id   (waiting for the channel join)
    known = set()
    last_check = {}

    # ======================= small helpers =======================
    async def lang_of(uid):
        try:
            d = await asyncio.to_thread(users_col.find_one, {"_id": uid}, {"lang": 1})
            lang = d.get("lang") if d else None
        except Exception:
            lang = None
        return lang if lang in I18N else "am"

    def disp(d, uid, escape=True):
        d = d or {}
        if d.get("username"):
            s = "@" + d["username"]
        else:
            s = (d.get("name") or str(uid))[:24]
        return html.escape(s) if escape else s

    def names_for(ids):
        out = {}
        for d in users_col.find({"_id": {"$in": list(ids)}}, {"name": 1, "username": 1}):
            out[d["_id"]] = d
        return out

    def ranking(start, end, limit=500):
        return list(referrals.aggregate([
            {"$match": {"at": {"$gte": start, "$lt": end}}},
            {"$group": {"_id": "$inviter", "n": {"$sum": 1}, "last": {"$max": "$at"}}},
            {"$sort": {"n": -1, "last": 1}},
            {"$limit": limit},
        ]))

    def get_round():
        now = utcnow()
        doc = settings.find_one({"_id": "contest"})
        if not doc:
            doc = {"_id": "contest", "n": 1, "start": now, "end": next_close(now)}
            try:
                settings.insert_one(doc)
            except DuplicateKeyError:
                doc = settings.find_one({"_id": "contest"})
        return doc

    def left_text(lang, end):
        secs = max(0, int((end - utcnow()).total_seconds()))
        return I18N[lang]["left"].format(d=secs // 86400, h=(secs % 86400) // 3600)

    def rank_icon(i):
        return {1: pe("gold"), 2: pe("silver"), 3: pe("bronze")}.get(i, f"{i}.")

    def board_text(lang, rows, names):
        if not rows:
            return I18N[lang]["empty"]
        L = I18N[lang]
        return "\n".join(
            f"{rank_icon(i)} {disp(names.get(r['_id']), r['_id'])} — {L['people'].format(n=r['n'])}"
            for i, r in enumerate(rows[:10], 1))

    # ======================= referral logic =======================
    def mark_new_sync(uid):
        """True the first time a person ever presses /start."""
        try:
            r = users_col.update_one(
                {"_id": uid, "started": {"$ne": True}}, {"$set": {"joined_at": utcnow()}}, upsert=True)
            return r.modified_count == 1 or r.upserted_id is not None
        except DuplicateKeyError:
            return False
        except Exception as ex:
            print("Growth mark_new error:", ex)
            return False

    def register_sync(invitee, inviter):
        if not users_col.find_one({"_id": inviter, "started": True}, {"_id": 1}):
            return False
        r = users_col.update_one({"_id": invitee, "ref_by": {"$exists": False}}, {"$set": {"ref_by": inviter}})
        return r.modified_count == 1

    def credit_sync(invitee, inviter):
        r = users_col.update_one({"_id": invitee, "ref_ok": {"$ne": True}}, {"$set": {"ref_ok": True}})
        if r.modified_count != 1:
            return None
        d = users_col.find_one({"_id": invitee}, {"name": 1, "username": 1}) or {}
        try:
            referrals.insert_one({"_id": invitee, "inviter": inviter, "at": utcnow(),
                                  "name": d.get("name", ""), "username": d.get("username", "")})
        except DuplicateKeyError:
            return None
        return referrals.count_documents({"inviter": inviter}), disp(d, invitee)

    async def try_credit(bot, uid):
        inviter = pending.get(uid)
        if not inviter:
            return False
        try:
            m = await bot.get_chat_member(chat_id=channel, user_id=uid)
            if m.status not in ("member", "administrator", "creator"):
                return False
        except Exception as ex:
            print("Referral membership check error:", ex)
            return False
        res = await asyncio.to_thread(credit_sync, uid, inviter)
        pending.pop(uid, None)
        if res:
            total, who = res
            lang = await lang_of(inviter)
            L = I18N[lang]
            text = L["joined"].format(who=who, total=total)
            try:
                await attempt(
                    lambda t, kb: bot.send_message(inviter, t, reply_markup=kb, parse_mode="HTML"),
                    text, lambda ic: InlineKeyboardMarkup(
                        [[Bt(L["invite_btn"], "cmd_invite", style="success", ic=ic)]]))
            except Exception as ex:
                print("Referral notify error:", ex)
        return bool(res)

    async def on_start(update, context):
        """Call at the very beginning of /start (before the user is marked as started)."""
        user = update.effective_user
        if not user:
            return
        uid = user.id
        is_new = await asyncio.to_thread(mark_new_sync, uid)
        known.add(uid)
        if not is_new:
            return
        args = context.args or []
        if not args or not args[0].startswith("ref_"):
            return
        try:
            inviter = int(args[0][4:])
        except ValueError:
            return
        if inviter == uid:
            return
        if await asyncio.to_thread(register_sync, uid, inviter):
            pending[uid] = inviter
            await try_credit(context.bot, uid)

    async def tick(update, context):
        """Runs on every update: credits invited friends as soon as they are in the channel."""
        ensure_loop(context.application)
        u = update.effective_user
        if not u:
            return
        uid = u.id
        if uid not in known:
            known.add(uid)
            try:
                d = await asyncio.to_thread(users_col.find_one, {"_id": uid}, {"ref_by": 1, "ref_ok": 1})
                if d and d.get("ref_by") and not d.get("ref_ok"):
                    pending[uid] = d["ref_by"]
            except Exception as ex:
                print("Referral load error:", ex)
        if uid in pending:
            cb = update.callback_query
            force = bool(cb and cb.data == "check_join")
            if force or time.time() - last_check.get(uid, 0) > 30:
                last_check[uid] = time.time()
                await try_credit(context.bot, uid)

    # ======================= user screens =======================
    def invite_data(uid):
        rnd = get_round()
        rows = ranking(rnd["start"], rnd["end"])
        ids = {r["_id"] for r in rows[:10]}
        names = names_for(ids) if ids else {}
        week = next((r["n"] for r in rows if r["_id"] == uid), 0)
        myrank = next((i for i, r in enumerate(rows, 1) if r["_id"] == uid), None)
        total = referrals.count_documents({"inviter": uid})
        pend = users_col.count_documents({"ref_by": uid, "ref_ok": {"$ne": True}})
        return rnd, rows, names, week, myrank, total, pend

    async def invite_screen(context, uid):
        lang = await lang_of(uid)
        L = I18N[lang]
        rnd, rows, names, week, myrank, total, pend = await asyncio.to_thread(invite_data, uid)
        link = f"https://t.me/{context.bot.username or 'mame_posts_bot'}?start=ref_{uid}"
        text = L["invite"].format(
            link=link, total=total, week=week, pending=pend, trophy=pe("trophy"),
            board=board_text(lang, rows, names),
            myrank=L["rank"].format(r=myrank) if myrank else "—",
            left=left_text(lang, rnd["end"]))
        share = f"https://t.me/share/url?url={quote(link, safe='')}&text={quote(L['share_text'], safe='')}"

        def make(ic):
            return InlineKeyboardMarkup([
                [Bt(L["share_btn"], url=share, style="success")],
                [Bt(translations[lang]["btn_back"], "cmd_back", style="primary", icon=ICON_BACK, ic=ic)],
            ])
        return text, make

    async def on_invite(update, context):
        q = update.callback_query
        await q.answer()
        try:
            text, make = await invite_screen(context, q.from_user.id)
            await attempt(lambda t, kb: q.edit_message_text(t, reply_markup=kb, parse_mode="HTML"), text, make)
        except Exception as ex:
            print("Invite screen error:", ex)
        raise ApplicationHandlerStop

    async def invite_cmd(update, context):
        if not update.message:
            return
        try:
            text, make = await invite_screen(context, update.effective_user.id)
            await attempt(lambda t, kb: update.message.reply_text(t, reply_markup=kb, parse_mode="HTML"),
                          text, make)
        except Exception as ex:
            print("Invite cmd error:", ex)

    async def on_myads(update, context):
        q = update.callback_query
        await q.answer()
        uid = q.from_user.id
        try:
            lang = await lang_of(uid)
            L = I18N[lang]
            rows = await asyncio.to_thread(
                lambda: list(orders.find({"user_id": uid}).sort("_id", -1).limit(5)))
            if not rows:
                text = f"{L['myads_title']}\n\n{L['myads_none']}"
            else:
                lines = [L["myads_title"], ""]
                for o in rows:
                    st = o.get("status")
                    key = "pending" if st == "failed" else st
                    label = L["st"].get(key, "—")
                    if key == "scheduled" and o.get("publish_at"):
                        label = label.format(t=fmt_eat(o["publish_at"]))
                    elif key == "posted" and o.get("delete_at"):
                        label = label.format(t=fmt_eat(o["delete_at"]))
                        if o.get("channel_msg"):
                            label += f' · <a href="https://t.me/{channel_name}/{o["channel_msg"]}">link</a>'
                    lines.append(f"<b>#{o['_id']}</b> · {o.get('hours')}{L['hours']} · {label}")
                text = "\n".join(lines)

            def make(ic):
                return InlineKeyboardMarkup([
                    [Bt(L["again"], "cmd_order", style="success")],
                    [Bt(translations[lang]["btn_back"], "cmd_back", style="primary", icon=ICON_BACK, ic=ic)],
                ])
            await attempt(lambda t, kb: q.edit_message_text(
                t, reply_markup=kb, parse_mode="HTML", disable_web_page_preview=True), text, make)
        except Exception as ex:
            print("My ads error:", ex)
        raise ApplicationHandlerStop

    # ======================= contest closing / announcing (admin) =======================
    def close_round_sync(force=False):
        doc = get_round()
        now = utcnow()
        if not force and doc["end"] > now:
            return None
        end = now if force else doc["end"]
        old = settings.find_one_and_update(
            {"_id": "contest", "n": doc["n"]},
            {"$set": {"n": doc["n"] + 1, "start": end, "end": next_close(end)}},
            return_document=ReturnDocument.BEFORE)
        if not old:
            return None
        top = ranking(old["start"], end, limit=10)
        res = {"_id": old["n"], "start": old["start"], "end": end,
               "ranking": [{"inviter": r["_id"], "n": r["n"]} for r in top],
               "announced": False, "at": now}
        rounds.insert_one(res)
        return res

    def round_report_data(res):
        names = names_for([r["inviter"] for r in res["ranking"]])
        lists = {}
        for r in res["ranking"]:
            lists[r["inviter"]] = list(referrals.find(
                {"inviter": r["inviter"], "at": {"$gte": res["start"], "$lt": res["end"]}}).sort("at", 1))
        return names, lists

    async def send_chunks(bot, chat_id, lines, **kw):
        buf = ""
        for ln in lines:
            if len(buf) + len(ln) + 1 > 3500:
                await bot.send_message(chat_id, buf, parse_mode="HTML", **kw)
                buf = ""
            buf += ln + "\n"
        if buf.strip():
            await bot.send_message(chat_id, buf, parse_mode="HTML", **kw)

    async def send_round_to_admin(bot, res):
        names, lists = await asyncio.to_thread(round_report_data, res)
        head = (f"🏆 <b>Contest round #{res['_id']} closed</b>\n"
                f"{fmt_eat(res['start'])} → {fmt_eat(res['end'])} (Ethiopia time)\n")
        if not res["ranking"]:
            await bot.send_message(admin_id, head + "\nNobody invited anyone this round. A new round has started.",
                                   parse_mode="HTML")
            return
        medals = {1: "🥇", 2: "🥈", 3: "🥉"}
        lines = [head]
        for i, r in enumerate(res["ranking"], 1):
            d = names.get(r["inviter"], {})
            lines.append(f"{medals.get(i, str(i) + '.')} {disp(d, r['inviter'])} · ID <code>{r['inviter']}</code> · <b>{r['n']}</b> friends")
        await send_chunks(bot, admin_id, lines)
        await bot.send_message(admin_id, "👇 Who each person invited (check for fake accounts before you send the prize):")
        for i, r in enumerate(res["ranking"], 1):
            d = names.get(r["inviter"], {})
            lines = [f"<b>#{i} {disp(d, r['inviter'])}</b> ({r['n']})"]
            for j, inv in enumerate(lists.get(r["inviter"], []), 1):
                lines.append(f"{j}. {disp(inv, inv['_id'])} · <code>{inv['_id']}</code> · {fmt_eat(inv['at'])}")
            await send_chunks(bot, admin_id, lines)
        kb = InlineKeyboardMarkup([
            [Bt("📢 Announce to everyone", f"ct_ann:{res['_id']}", style="success")],
            [Bt("🏆 Contest panel", "adm_contest", style="primary")],
        ])
        await bot.send_message(
            admin_id, "When you are happy with the result, press the button. Nothing is sent to users before that.",
            reply_markup=kb)

    def ann_text(lang, ranking_rows, names):
        L = I18N[lang]
        lines = [L["ann_title"].format(trophy=pe("trophy")), ""]
        for i, r in enumerate(ranking_rows, 1):
            lines.append(f"{rank_icon(i)} {disp(names.get(r['inviter']), r['inviter'])} — {L['people'].format(n=r['n'])}")
        lines += ["", L["ann_prize"], L["ann_new"]]
        return "\n".join(lines)

    async def announce(app, n):
        res = await asyncio.to_thread(
            rounds.find_one_and_update, {"_id": n, "announced": False}, {"$set": {"announced": True}},
            return_document=ReturnDocument.AFTER)
        if not res:
            return "⚠️ That round was already announced (or does not exist)."
        if not res["ranking"]:
            return "⚠️ Nobody invited anyone in that round, nothing to announce."
        names = await asyncio.to_thread(names_for, [r["inviter"] for r in res["ranking"]])
        users = await asyncio.to_thread(
            lambda: list(users_col.find({"banned": {"$ne": True}}, {"lang": 1})))
        texts = {lg: ann_text(lg, res["ranking"], names) for lg in I18N}
        app.create_task(broadcast(app, users, texts))
        return f"📢 Sending to {len(users)} users... I will tell you when it is done."

    async def broadcast(app, users, texts):
        ok = fail = 0
        for d in users:
            lg = d.get("lang") if d.get("lang") in I18N else "am"
            L = I18N[lg]
            try:
                async def send(text, kb, uid=d["_id"]):
                    return await app.bot.send_message(uid, text, reply_markup=kb, parse_mode="HTML")
                make = lambda ic, L=L: InlineKeyboardMarkup([[Bt(L["invite_btn"], "cmd_invite", style="success")]])
                try:
                    await attempt(send, texts[lg], make)
                except RetryAfter as e:
                    ra = e.retry_after
                    await asyncio.sleep((ra.total_seconds() if hasattr(ra, "total_seconds") else ra) + 1)
                    await attempt(send, texts[lg], make)
                ok += 1
            except Exception:
                fail += 1
            await asyncio.sleep(0.05)
        try:
            await app.bot.send_message(admin_id, f"✅ Contest announcement finished.\nSent: {ok}\nFailed: {fail}")
        except Exception:
            pass

    # ======================= daily report =======================
    def build_report(day):
        s, e_ = day_bounds_utc(day)
        st = db["daily_stats"].find_one({"_id": day}) or {}
        downloads, converts = st.get("downloads", 0), st.get("converts", 0)
        new_users = users_col.count_documents({"joined_at": {"$gte": s, "$lt": e_}})
        total = users_col.count_documents({})
        active = users_col.count_documents({"dl_date": day, "dl_count": {"$gt": 0}})
        hit = users_col.count_documents({"dl_date": day, "dl_count": {"$gte": DAILY_LIMIT}})
        refs = referrals.count_documents({"at": {"$gte": s, "$lt": e_}})
        lines = [
            f"📈 <b>Daily Report — {datetime.strptime(day, '%Y-%m-%d').strftime('%b %d')}</b>\n",
            f"👥 New users: <b>{new_users}</b>  (total {total})",
            f"📥 Downloads: <b>{downloads}</b>   🎵 Conversions: <b>{converts}</b>",
            f"🧑 Active downloaders: <b>{active}</b>   🚫 Reached the daily limit: <b>{hit}</b>",
            f"🎁 Friends invited: <b>{refs}</b>",
        ]
        plats = sorted((st.get("p") or {}).items(), key=lambda kv: -kv[1])
        if plats:
            tot = sum(v for _, v in plats) or 1
            lines.append("\n📊 <b>By platform</b>")
            lines += [f"{k} — {v} ({round(v * 100 / tot)}%)" for k, v in plats]
        return "\n".join(lines)

    def week_summary():
        out = ["\n🗓 <b>Last 7 days</b>"]
        for i in range(6, -1, -1):
            day = eat_day(utcnow() - timedelta(days=i))
            s, e_ = day_bounds_utc(day)
            st = db["daily_stats"].find_one({"_id": day}) or {}
            nu = users_col.count_documents({"joined_at": {"$gte": s, "$lt": e_}})
            out.append(f"{day[5:]}  📥 {st.get('downloads', 0)}  🎵 {st.get('converts', 0)}  👤 +{nu}")
        return "\n".join(out)

    def claim_report(today):
        try:
            r = settings.update_one({"_id": "report", "last": {"$ne": today}}, {"$set": {"last": today}}, upsert=True)
            return r.modified_count == 1 or r.upserted_id is not None
        except DuplicateKeyError:
            return False

    # ======================= background loop =======================
    async def loop(app):
        await asyncio.sleep(20)
        while True:
            try:
                today = eat_day()
                if (utcnow() + timedelta(hours=3)).hour >= REPORT_HOUR and await asyncio.to_thread(claim_report, today):
                    text = await asyncio.to_thread(build_report, today)
                    await app.bot.send_message(admin_id, text, parse_mode="HTML")
                res = await asyncio.to_thread(close_round_sync, False)
                if res:
                    await send_round_to_admin(app.bot, res)
            except Exception as ex:
                print("Growth loop error:", ex)
            await asyncio.sleep(60)

    def ensure_loop(app):
        if "_growth_loop" not in app.bot_data:
            app.bot_data["_growth_loop"] = asyncio.create_task(loop(app))

    prev_post_init = getattr(application, "post_init", None)

    async def _post_init(app):
        if prev_post_init:
            await prev_post_init(app)
        ensure_loop(app)

    try:
        application.post_init = _post_init
    except AttributeError:
        print("Growth: could not wrap post_init; the loop starts on the first update instead.")

    # ======================= admin panel buttons =======================
    def back_kb(extra=None):
        rows = list(extra or [])
        rows.append([Bt("⬅️ Back", "adm_back", style="primary")])
        return InlineKeyboardMarkup(rows)

    async def contest_panel():
        def _q():
            rnd = get_round()
            rows = ranking(rnd["start"], rnd["end"], limit=10)
            names = names_for([r["_id"] for r in rows]) if rows else {}
            last = rounds.find_one(sort=[("_id", -1)])
            return rnd, rows, names, last
        rnd, rows, names, last = await asyncio.to_thread(_q)
        secs = max(0, int((rnd["end"] - utcnow()).total_seconds()))
        lines = [f"🏆 <b>Contest — round #{rnd['n']}</b>",
                 f"Closes: {fmt_eat(rnd['end'])} (in {secs // 86400}d {(secs % 86400) // 3600}h)\n",
                 "<b>Standings now</b>"]
        if rows:
            medals = {1: "🥇", 2: "🥈", 3: "🥉"}
            for i, r in enumerate(rows, 1):
                lines.append(f"{medals.get(i, str(i) + '.')} {disp(names.get(r['_id']), r['_id'])} · "
                             f"<code>{r['_id']}</code> · <b>{r['n']}</b>")
        else:
            lines.append("Nobody has invited anyone yet.")
        kb = []
        if last:
            kb.append([Bt("📜 Last round's results", "ct_last", style="primary")])
            if not last.get("announced") and last["ranking"]:
                kb.append([Bt(f"📢 Announce round #{last['_id']} to everyone", f"ct_ann:{last['_id']}", style="success")])
        kb.append([Bt("⏩ Close this round now", "ct_close", style="danger")])
        return "\n".join(lines), back_kb(kb)

    async def on_admin_btn(update, context):
        q = update.callback_query
        if q.from_user.id != admin_id:
            await q.answer("Not allowed", show_alert=True)
            raise ApplicationHandlerStop
        d = q.data
        try:
            if d == "adm_report":
                await q.answer()
                text = await asyncio.to_thread(lambda: build_report(eat_day()) + "\n" + week_summary())
                await q.edit_message_text(text, parse_mode="HTML", reply_markup=back_kb())
            elif d == "adm_contest":
                await q.answer()
                text, kb = await contest_panel()
                await q.edit_message_text(text, parse_mode="HTML", reply_markup=kb)
            elif d == "ct_last":
                await q.answer()
                last = await asyncio.to_thread(lambda: rounds.find_one(sort=[("_id", -1)]))
                if not last:
                    await q.answer("No round has been closed yet.", show_alert=True)
                else:
                    await send_round_to_admin(context.bot, last)
            elif d.startswith("ct_ann:"):
                await q.answer()
                msg = await announce(context.application, int(d.split(":")[1]))
                await context.bot.send_message(admin_id, msg)
            elif d == "ct_close":
                await q.answer()
                kb = InlineKeyboardMarkup([
                    [Bt("✅ Yes, close it now", "ct_closey", style="danger")],
                    [Bt("Cancel", "adm_contest", style="primary")]])
                await q.edit_message_text(
                    "⏩ Close the current round now? The result will be sent to you only, and a new round starts.",
                    reply_markup=kb)
            elif d == "ct_closey":
                await q.answer()
                res = await asyncio.to_thread(close_round_sync, True)
                if res:
                    await send_round_to_admin(context.bot, res)
        except Exception as ex:
            print("Growth admin error:", ex)
        raise ApplicationHandlerStop

    async def emoji_ids(update, context):
        msg = update.message
        ids = [ent.custom_emoji_id for ent in (msg.entities or []) if ent.type == MessageEntity.CUSTOM_EMOJI]
        if ids:
            await msg.reply_text("\n".join(f"<code>{i}</code>" for i in ids), parse_mode="HTML")

    # ======================= register =======================
    # group -7: every other TypeHandler in the bot lives in a different group
    # (only ONE handler per group runs, so they must not share a group)
    application.add_handler(TypeHandler(Update, tick), group=-7)
    application.add_handler(CallbackQueryHandler(on_invite, pattern=r"^cmd_invite$"), group=-2)
    application.add_handler(CallbackQueryHandler(on_myads, pattern=r"^cmd_myads$"), group=-2)
    application.add_handler(
        CallbackQueryHandler(on_admin_btn, pattern=r"^(adm_(report|contest)|ct_(last|close|closey|ann:\d+))$"),
        group=-2)
    application.add_handler(CommandHandler("invite", invite_cmd))
    application.add_handler(
        MessageHandler(filters.User(user_id=admin_id) & filters.Entity(MessageEntity.CUSTOM_EMOJI) & ~filters.REPLY,
                       emoji_ids), group=-1)

    class Api:
        pass
    api = Api()
    api.on_start = on_start
    api._locals = locals()   # used by the self-tests only
    return api
