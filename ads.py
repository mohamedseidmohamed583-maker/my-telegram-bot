"""Advertising orders for @mame_posts.

Flow
 1. User taps "Advertise" -> sends the post -> picks 12/24/48 hours.
 2. 24/48 h: user pays and sends the payment screenshot.
    12 h (negotiable): order goes to the admin without a receipt.
 3. Admin gets the post + receipt with [Approve] / [Reject].
 4. Approve -> the bot posts it to the channel and removes it automatically
    when the time is over. The user is told every step (am / en / ar).
"""
import asyncio
import time
from datetime import datetime, timedelta

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
FLOW_TTL = 30 * 60            # seconds a user may take to finish the order flow
CHECK_EVERY = 60              # seconds between "ad time is over" checks
# Telegram only lets bots delete messages younger than 48 hours,
# so a 48 h ad is removed 10 minutes early.
MAX_DELETE_SECONDS = 48 * 3600 - 600

OK = '<tg-emoji emoji-id="5260463209562776385">✅</tg-emoji>'
DOWN = '<tg-emoji emoji-id="5305634553140912174">👇</tg-emoji>'

TXT = {
    "am": {
        "dur_prompt": f'{OK} <b>ፖስትዎን ተቀብለናል!</b>\n\n⏱ <b>ማስታወቂያው ስንት ሰዓት እንዲቆይ ይፈልጋሉ?</b>\n\n{DOWN} ከስር ይምረጡ',
        "dur12": "12 Hours — በስምምነት",
        "dur24": "24 Hours — 500 ETB",
        "dur48": "48 Hours — 700 ETB",
        "cancel": "❌ ሰርዝ",
        "ask_receipt": '📸 <b>ክፍያውን ከፈጸሙ በኋላ የክፍያ ስክሪንሹት እዚህ ይላኩ።</b>',
        "received": f'{OK} <b>ትዕዛዝ #{{n}} ተቀብለናል!</b>\n\nአድሚን ክፍያውን አይቶ እስኪያጸድቅ ይጠብቁ፤ ውጤቱን እዚሁ እንነግርዎታለን።',
        "received_neg": f'{OK} <b>ትዕዛዝ #{{n}} ለአድሚን ተልኳል!</b>\n\nአድሚን ዋጋውን ለመስማማት ያነጋግርዎታል።',
        "approved": '🎉 <b>ማስታወቂያዎ ጸድቆ @mame_posts ላይ ተለጥፏል!</b>\n\n⏱ ቆይታ: <b>{hours} Hours</b>\n🔗 {link}\n\nእናመሰግናለን!',
        "rejected": '❌ <b>ትዕዛዝ #{n} አልጸደቀም።</b>\n\nለበለጠ መረጃ እዚሁ ቦት ላይ መልዕክት ይጻፉ፤ አድሚን ይመልስልዎታል።',
        "expired": '⏰ <b>የማስታወቂያዎ ጊዜ አብቅቷል</b> (ትዕዛዝ #{n})\n\nእናመሰግናለን! እንደገና ለማሰራት ከምናሌው «ማስታወቂያ ለማሰራት» ይጫኑ።',
        "cancelled": "❎ ተሰርዟል።",
        "bad_receipt": "❌ እባክዎ የክፍያ ስክሪንሹቱን እንደ ፎቶ ይላኩ፤ ወይም ሰርዝ ይጫኑ።",
        "session": "⌛ ጊዜው አልፏል፤ እባክዎ ከምናሌው «ማስታወቂያ ለማሰራት» እንደገና ይጫኑ።",
    },
    "en": {
        "dur_prompt": f'{OK} <b>Post received!</b>\n\n⏱ <b>How long should the ad stay on the channel?</b>\n\n{DOWN} Choose below',
        "dur12": "12 Hours — Negotiable",
        "dur24": "24 Hours — 500 ETB",
        "dur48": "48 Hours — 700 ETB",
        "cancel": "❌ Cancel",
        "ask_receipt": '📸 <b>After paying, send the payment screenshot here.</b>',
        "received": f'{OK} <b>Order #{{n}} received!</b>\n\nPlease wait while the admin checks your payment. We will tell you the result here.',
        "received_neg": f'{OK} <b>Order #{{n}} sent to the admin!</b>\n\nThe admin will contact you to agree on the price.',
        "approved": '🎉 <b>Your ad was approved and posted on @mame_posts!</b>\n\n⏱ Duration: <b>{hours} Hours</b>\n🔗 {link}\n\nThank you!',
        "rejected": '❌ <b>Order #{n} was not approved.</b>\n\nWrite a message here to ask the admin for details.',
        "expired": '⏰ <b>Your ad time has ended</b> (order #{n})\n\nThank you! To advertise again, tap “Promote / Advertise” in the menu.',
        "cancelled": "❎ Cancelled.",
        "bad_receipt": "❌ Please send the payment screenshot as a photo, or tap Cancel.",
        "session": "⌛ Session expired. Please tap “Promote / Advertise” in the menu again.",
    },
    "ar": {
        "dur_prompt": f'{OK} <b>تم استلام منشورك!</b>\n\n⏱ <b>كم ساعة تريد أن يبقى الإعلان في القناة؟</b>\n\n{DOWN} اختر من الأسفل',
        "dur12": "12 ساعة — حسب الاتفاق",
        "dur24": "24 ساعة — 500 ETB",
        "dur48": "48 ساعة — 700 ETB",
        "cancel": "❌ إلغاء",
        "ask_receipt": '📸 <b>بعد الدفع أرسل لقطة شاشة الإيصال هنا.</b>',
        "received": f'{OK} <b>تم استلام الطلب #{{n}}!</b>\n\nيرجى الانتظار حتى يراجع المسؤول الدفع وسنخبرك بالنتيجة هنا.',
        "received_neg": f'{OK} <b>تم إرسال الطلب #{{n}} إلى المسؤول!</b>\n\nسيتواصل معك المسؤول للاتفاق على السعر.',
        "approved": '🎉 <b>تمت الموافقة على إعلانك ونشره في @mame_posts!</b>\n\n⏱ المدة: <b>{hours} ساعة</b>\n🔗 {link}\n\nشكراً لك!',
        "rejected": '❌ <b>لم تتم الموافقة على الطلب #{n}.</b>\n\nاكتب رسالة هنا لسؤال المسؤول عن التفاصيل.',
        "expired": '⏰ <b>انتهت مدة إعلانك</b> (الطلب #{n})\n\nشكراً لك! للإعلان مرة أخرى اضغط «طلب إعلان» من القائمة.',
        "cancelled": "❎ تم الإلغاء.",
        "bad_receipt": "❌ يرجى إرسال لقطة شاشة الدفع كصورة، أو اضغط إلغاء.",
        "session": "⌛ انتهت الجلسة. اضغط «طلب إعلان» من القائمة مرة أخرى.",
    },
}


def fmt_eat(dt):
    """UTC datetime -> 'Oct 24, 18:30 EAT' (Ethiopia time)."""
    return (dt + timedelta(hours=3)).strftime("%b %d, %H:%M") + " EAT"


def setup_ads(application, users_col, admin_id, translations, channel):
    db = users_col.database
    orders = db["orders"]
    counters = db["counters"]

    def B(text, data, style=None):
        kw = {"text": text, "callback_data": data}
        if style:
            kw["api_kwargs"] = {"style": style}
        return InlineKeyboardButton(**kw)

    async def lang_of(uid):
        try:
            d = await asyncio.to_thread(users_col.find_one, {"_id": uid}, {"lang": 1})
            lang = d.get("lang") if d else None
        except Exception:
            lang = None
        return lang if lang in TXT else "am"

    def post_link(o):
        return f"https://t.me/{channel.lstrip('@')}/{o.get('channel_msg')}"

    # ---------------- keyboards ----------------
    def dur_kb(lang):
        t = TXT[lang]
        return InlineKeyboardMarkup([
            [B(t["dur12"], "ad_dur:12", "primary")],
            [B(t["dur24"], "ad_dur:24", "success"), B(t["dur48"], "ad_dur:48", "success")],
            [B(t["cancel"], "ad_cancel", "danger")],
        ])

    def cancel_kb(lang):
        return InlineKeyboardMarkup([[B(TXT[lang]["cancel"], "ad_cancel", "danger")]])

    def back_kb(lang):
        return InlineKeyboardMarkup(
            [[InlineKeyboardButton(translations[lang]["btn_back"], callback_data="cmd_back")]]
        )

    def decision_kb(n):
        return InlineKeyboardMarkup([[
            B("✅ Approve & Post", f"ad_ok:{n}", "success"),
            B("❌ Reject", f"ad_no:{n}", "danger"),
        ]])

    # ---------------- admin message helpers ----------------
    def header(o, status):
        uname = f"@{o['username']}" if o.get("username") else "-"
        return (
            f"🧾 Order #{o['_id']}\n"
            f"👤 {o['name']}  {uname}\n"
            f"🆔 ID: {o['user_id']}\n"
            f"⏱ {o['hours']} Hours — {o['price']}\n"
            f"📅 {fmt_eat(o['created'])}\n\n"
            f"Status: {status}"
        )

    async def send_order_to_admin(bot, o):
        try:
            await bot.copy_message(chat_id=admin_id, from_chat_id=o["post_chat"], message_id=o["post_msg"])
        except Exception as e:
            await bot.send_message(admin_id, f"⚠️ Could not copy the post of order #{o['_id']}: {e}")
        h = header(o, "⏳ Pending")
        if o.get("rcpt_msg"):
            m = await bot.copy_message(
                chat_id=admin_id, from_chat_id=o["rcpt_chat"], message_id=o["rcpt_msg"],
                caption=h, reply_markup=decision_kb(o["_id"]),
            )
            cap = True
        else:
            m = await bot.send_message(
                admin_id,
                h + "\n\n💬 Price is negotiable. Reply to this message to talk to the user, then press Approve.",
                reply_markup=decision_kb(o["_id"]),
            )
            cap = False
        await asyncio.to_thread(
            orders.update_one, {"_id": o["_id"]}, {"$set": {"admin_msg": m.message_id, "admin_cap": cap}}
        )

    async def mark_admin(bot, o, status):
        if not o.get("admin_msg"):
            return
        h = header(o, status)
        try:
            if o.get("admin_cap"):
                await bot.edit_message_caption(chat_id=admin_id, message_id=o["admin_msg"], caption=h)
            else:
                await bot.edit_message_text(chat_id=admin_id, message_id=o["admin_msg"], text=h)
        except Exception as e:
            print("Ads mark_admin error:", e)

    async def notify(bot, o, key):
        lang = await lang_of(o["user_id"])
        try:
            await bot.send_message(
                o["user_id"],
                TXT[lang][key].format(n=o["_id"], hours=o["hours"], link=post_link(o)),
                parse_mode="HTML",
            )
            return True
        except Exception as e:
            print("Ads notify error:", e)
            return False

    def _make_order(user, st, lang, rcpt):
        n = counters.find_one_and_update(
            {"_id": "orders"}, {"$inc": {"n": 1}}, upsert=True, return_document=ReturnDocument.AFTER
        )["n"]
        doc = {
            "_id": n,
            "user_id": user.id,
            "lang": lang,
            "name": user.full_name,
            "username": user.username or "",
            "post_chat": st["post_chat"],
            "post_msg": st["post_msg"],
            "hours": st["hours"],
            "price": PRICES[st["hours"]],
            "rcpt_chat": rcpt[0] if rcpt else None,
            "rcpt_msg": rcpt[1] if rcpt else None,
            "status": "pending",
            "created": datetime.utcnow(),
        }
        orders.insert_one(doc)
        return doc

    def ensure_loop(app):
        if "_ads_loop" not in app.bot_data:
            app.bot_data["_ads_loop"] = asyncio.create_task(expiry_loop(app))

    # ---------------- user side ----------------
    async def clear_state(update, context):
        ensure_loop(context.application)
        context.user_data.pop("ad", None)

    async def on_order_start(update, context):
        q = update.callback_query
        await q.answer()
        lang = await lang_of(q.from_user.id)
        context.user_data["ad"] = {"step": "post", "ts": time.time()}
        try:
            await q.edit_message_text(
                translations[lang]["order"], reply_markup=back_kb(lang), parse_mode="HTML"
            )
        except Exception as e:
            print("Ads order screen error:", e)
        raise ApplicationHandlerStop

    async def capture(update, context):
        ensure_loop(context.application)
        msg = update.message
        st = context.user_data.get("ad")
        if not msg or not st or update.effective_chat.type != "private":
            return
        if time.time() - st["ts"] > FLOW_TTL:
            context.user_data.pop("ad", None)
            return
        if (msg.text or "").strip() == "🏠 Menu":
            context.user_data.pop("ad", None)
            return
        lang = await lang_of(update.effective_user.id)
        t = TXT[lang]
        step = st["step"]

        if step == "post":
            st.update(step="duration", post_chat=msg.chat_id, post_msg=msg.message_id, ts=time.time())
            await msg.reply_text(t["dur_prompt"], reply_markup=dur_kb(lang), parse_mode="HTML")
            raise ApplicationHandlerStop

        if step == "duration":
            await msg.reply_text(t["dur_prompt"], reply_markup=dur_kb(lang), parse_mode="HTML")
            raise ApplicationHandlerStop

        if step == "receipt":
            if not (msg.photo or msg.document):
                await msg.reply_text(t["bad_receipt"], reply_markup=cancel_kb(lang))
                raise ApplicationHandlerStop
            o = await asyncio.to_thread(
                _make_order, update.effective_user, st, lang, (msg.chat_id, msg.message_id)
            )
            context.user_data.pop("ad", None)
            await msg.reply_text(t["received"].format(n=o["_id"]), parse_mode="HTML")
            try:
                await send_order_to_admin(context.bot, o)
            except Exception as e:
                print("Ads send to admin error:", e)
            raise ApplicationHandlerStop

    async def on_user_cb(update, context):
        q = update.callback_query
        uid = q.from_user.id
        lang = await lang_of(uid)
        t = TXT[lang]
        st = context.user_data.get("ad")

        if q.data == "ad_cancel":
            context.user_data.pop("ad", None)
            await q.answer()
            try:
                await q.edit_message_text(t["cancelled"], reply_markup=back_kb(lang))
            except Exception:
                pass
            return

        # ad_dur:<hours>
        if not st or st.get("step") != "duration" or time.time() - st["ts"] > FLOW_TTL:
            context.user_data.pop("ad", None)
            await q.answer(t["session"], show_alert=True)
            return
        await q.answer()
        hours = int(q.data.split(":")[1])
        if hours not in PRICES:
            return
        st["hours"] = hours
        st["ts"] = time.time()

        if hours == 12:  # negotiable: straight to the admin, no receipt
            o = await asyncio.to_thread(_make_order, q.from_user, st, lang, None)
            context.user_data.pop("ad", None)
            try:
                await q.edit_message_text(t["received_neg"].format(n=o["_id"]), parse_mode="HTML")
            except Exception:
                pass
            try:
                await send_order_to_admin(context.bot, o)
            except Exception as e:
                print("Ads send to admin error:", e)
            return

        st["step"] = "receipt"
        text = translations[lang]["payment"] + "\n\n" + t["ask_receipt"]
        try:
            await q.edit_message_text(text, reply_markup=cancel_kb(lang), parse_mode="HTML")
        except Exception as e:
            print("Ads payment screen error:", e)

    # ---------------- admin side ----------------
    async def orders_view():
        def _q():
            pend = list(orders.find({"status": "pending"}).sort("_id", 1).limit(8))
            live = list(orders.find({"status": "posted"}).sort("delete_at", 1).limit(8))
            c = {s: orders.count_documents({"status": s})
                 for s in ("pending", "posted", "expired", "removed", "rejected")}
            return pend, live, c

        pend, live, c = await asyncio.to_thread(_q)
        lines = [
            "🧾 Orders\n",
            f"⏳ Pending: {c['pending']}   🟢 Live: {c['posted']}",
            f"✔️ Finished: {c['expired'] + c['removed']}   ❌ Rejected: {c['rejected']}",
        ]
        rows = []
        if pend:
            lines.append("\n⏳ Pending")
            for o in pend:
                lines.append(f"#{o['_id']} · {o['name']} · {o['hours']}h")
                rows.append([B(f"⏳ #{o['_id']} · {o['hours']}h · open", f"ad_open:{o['_id']}", "primary")])
        if live:
            lines.append("\n🟢 Live ads")
            for o in live:
                lines.append(f"#{o['_id']} · ends {fmt_eat(o['delete_at'])}")
                rows.append([B(f"🗑 Remove #{o['_id']}", f"ad_rm:{o['_id']}", "danger")])
        rows.append([B("⬅️ Back", "adm_back", "primary")])
        return "\n".join(lines), InlineKeyboardMarkup(rows)

    async def cmd_orders(update, context):
        text, kb = await orders_view()
        await update.message.reply_text(text, reply_markup=kb)

    async def on_orders_btn(update, context):
        q = update.callback_query
        if q.from_user.id != admin_id:
            await q.answer("Not allowed", show_alert=True)
            return
        await q.answer()
        text, kb = await orders_view()
        try:
            await q.edit_message_text(text, reply_markup=kb)
        except Exception as e:
            print("Ads orders view error:", e)
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

        if act == "ad_open":
            o = await asyncio.to_thread(orders.find_one, {"_id": n})
            if o and o["status"] == "pending":
                await send_order_to_admin(bot, o)
            else:
                await bot.send_message(admin_id, f"Order #{n} is not pending anymore.")
            return

        if act == "ad_rm":
            kb = InlineKeyboardMarkup([[
                B("✅ Yes, remove now", f"ad_rmy:{n}", "danger"),
                B("⬅️ No", "adm_orders", "primary"),
            ]])
            await q.edit_message_text(f"Remove ad #{n} from the channel now?", reply_markup=kb)
            return

        if act == "ad_rmy":
            o = await asyncio.to_thread(
                orders.find_one_and_update, {"_id": n, "status": "posted"},
                {"$set": {"status": "removed"}}, return_document=ReturnDocument.AFTER,
            )
            if o:
                try:
                    await bot.delete_message(chat_id=channel, message_id=o["channel_msg"])
                except Exception as e:
                    await bot.send_message(admin_id, f"⚠️ Could not delete ad #{n}: {e}\nDelete it manually: {post_link(o)}")
                await notify(bot, o, "expired")
            text, kb = await orders_view()
            await q.edit_message_text(text, reply_markup=kb)
            return

        if act == "ad_ok":
            o = await asyncio.to_thread(
                orders.find_one_and_update, {"_id": n, "status": "pending"},
                {"$set": {"status": "posting"}}, return_document=ReturnDocument.AFTER,
            )
            if not o:
                await bot.send_message(admin_id, f"Order #{n} was already handled.")
                return
            try:
                sent = await bot.copy_message(
                    chat_id=channel, from_chat_id=o["post_chat"], message_id=o["post_msg"]
                )
            except Exception as e:
                await asyncio.to_thread(orders.update_one, {"_id": n}, {"$set": {"status": "pending"}})
                await bot.send_message(
                    admin_id,
                    f"⚠️ Could not post order #{n} to {channel}: {e}\n"
                    "Make sure the bot is an admin of the channel with permission to post.",
                )
                return
            now = datetime.utcnow()
            secs = min(o["hours"] * 3600, MAX_DELETE_SECONDS)
            end = now + timedelta(seconds=secs)
            await asyncio.to_thread(
                orders.update_one, {"_id": n},
                {"$set": {"status": "posted", "channel_msg": sent.message_id, "posted_at": now, "delete_at": end}},
            )
            o.update(status="posted", channel_msg=sent.message_id, delete_at=end)
            await mark_admin(bot, o, f"✅ Posted — auto-removes {fmt_eat(end)}")
            if not await notify(bot, o, "approved"):
                await bot.send_message(admin_id, f"⚠️ Order #{n} is posted, but I couldn't message the user.")
            return

        if act == "ad_no":
            o = await asyncio.to_thread(
                orders.find_one_and_update, {"_id": n, "status": "pending"},
                {"$set": {"status": "rejected"}}, return_document=ReturnDocument.AFTER,
            )
            if not o:
                await bot.send_message(admin_id, f"Order #{n} was already handled.")
                return
            await mark_admin(bot, o, "❌ Rejected")
            if not await notify(bot, o, "rejected"):
                await bot.send_message(admin_id, f"⚠️ Order #{n} rejected, but I couldn't message the user.")

    # ---------------- auto removal ----------------
    async def expiry_loop(app):
        await asyncio.sleep(15)
        while True:
            try:
                now = datetime.utcnow()
                due = await asyncio.to_thread(
                    lambda: list(orders.find({"status": "posted", "delete_at": {"$lte": now}}))
                )
                for d in due:
                    o = await asyncio.to_thread(
                        orders.find_one_and_update, {"_id": d["_id"], "status": "posted"},
                        {"$set": {"status": "expired"}}, return_document=ReturnDocument.AFTER,
                    )
                    if not o:
                        continue
                    try:
                        await app.bot.delete_message(chat_id=channel, message_id=o["channel_msg"])
                        await app.bot.send_message(
                            admin_id, f"⏰ Ad #{o['_id']} finished and was removed from the channel.",
                            disable_notification=True,
                        )
                    except Exception as e:
                        await app.bot.send_message(
                            admin_id,
                            f"⚠️ Ad #{o['_id']} time is over but I couldn't delete it ({e}).\n"
                            f"Please delete it manually: {post_link(o)}",
                        )
                    await notify(app.bot, o, "expired")
            except Exception as e:
                print("Ads expiry loop error:", e)
            await asyncio.sleep(CHECK_EVERY)

    prev_post_init = getattr(application, "post_init", None)

    async def _post_init(app):
        if prev_post_init:
            await prev_post_init(app)
        ensure_loop(app)

    try:
        application.post_init = _post_init
    except AttributeError:
        print("Ads: could not wrap post_init; the removal loop starts on the first update instead.")

    # ---------------- register ----------------
    # -5 ban gate (admin_panel) | -4 clear flow | -3 admin panel input | -2 ads | 0 main bot
    application.add_handler(MessageHandler(filters.COMMAND, clear_state), group=-4)
    application.add_handler(CallbackQueryHandler(clear_state, pattern=r"^(cmd_|lang_)"), group=-4)

    application.add_handler(CallbackQueryHandler(on_order_start, pattern=r"^cmd_order$"), group=-2)
    application.add_handler(CallbackQueryHandler(on_orders_btn, pattern=r"^adm_orders$"), group=-2)
    application.add_handler(CallbackQueryHandler(on_user_cb, pattern=r"^ad_(dur:\d+|cancel)$"), group=-2)
    application.add_handler(CallbackQueryHandler(on_admin_cb, pattern=r"^ad_(ok|no|open|rm|rmy):\d+$"), group=-2)
    application.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, capture), group=-2)
    application.add_handler(CommandHandler("orders", cmd_orders, filters=filters.User(user_id=admin_id)))
