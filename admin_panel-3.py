import asyncio
import csv
import io

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.error import RetryAfter
from telegram.ext import (
    ApplicationHandlerStop,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    TypeHandler,
    filters,
)

PROMPTS = {
    "adm_bc": "📢 Send the message you want to broadcast (text, photo, video...).",
    "adm_find": "🔎 Send the user ID or @username.",
    "adm_ban": "🚫 Send the user ID to ban.",
    "adm_unban": "✅ Send the user ID to unban.",
}


def setup_admin(application, users_col, admin_id):
    banned = {d["_id"] for d in users_col.find({"banned": True}, {"_id": 1})}
    seen = {}
    def B(text, callback_data, style=None):
        if style:
            return InlineKeyboardButton(text, callback_data=callback_data, api_kwargs={"style": style})
        return InlineKeyboardButton(text, callback_data=callback_data)

    # ---------- sync DB helpers (run in threads) ----------
    def _counts():
        return (
            users_col.count_documents({}),
            users_col.count_documents({"banned": True}),
        )

    def _stats():
        total, ban = _counts()
        agg = list(users_col.aggregate([{"$group": {"_id": None, "m": {"$sum": "$msg_count"}}}]))
        msgs = agg[0]["m"] if agg else 0
        langs = {
            (d["_id"] or "not set"): d["n"]
            for d in users_col.aggregate([{"$group": {"_id": "$lang", "n": {"$sum": 1}}}])
        }
        return total, ban, msgs, langs

    # ---------- keyboards ----------
    def main_kb():
        return InlineKeyboardMarkup([
            [B("📊 Stats", "adm_stats", "primary"), B("📢 Broadcast", "adm_bc", "primary")],
            [B("🔎 Find User", "adm_find", "success"), B("📄 Export Users (CSV)", "adm_export", "success")],
            [B("🚫 Ban User", "adm_ban", "danger"), B("✅ Unban User", "adm_unban", "success")],
            [B("📋 Banned List", "adm_banned", "primary"), B("🧾 Orders", "adm_orders", "primary")],
            [B("📈 Daily Report", "adm_report", "primary"), B("🏆 Contest", "adm_contest", "success")],
            [B("❌ Close", "adm_close", "danger")],
        ])

    back_kb = InlineKeyboardMarkup([[B("⬅️ Back", "adm_back", "primary")]])

    async def panel_text():
        total, ban = await asyncio.to_thread(_counts)
        try:
            pend = await asyncio.to_thread(
                users_col.database["orders"].count_documents, {"status": "pending"}
            )
        except Exception:
            pend = 0
        return (
            f"🛠 Admin Panel\n\n👥 Users: {total}   🚫 Banned: {ban}   ⏳ Pending orders: {pend}"
            "\n\nChoose an action:"
        )

    # ---------- gate: ban check + username tracking (runs first) ----------
    async def gate(update: Update, context):
        user = update.effective_user
        if not user or user.id == admin_id:
            return
        key = (user.username, user.full_name)
        if seen.get(user.id) != key:
            seen[user.id] = key
            try:
                await asyncio.to_thread(
                    users_col.update_one,
                    {"_id": user.id},
                    {"$set": {"username": (user.username or "").lower(), "name": user.full_name}},
                    True,
                )
            except Exception as e:
                print("Admin track error:", e)
        if user.id in banned:
            if update.callback_query:
                try:
                    await update.callback_query.answer("🚫 You are banned.", show_alert=True)
                except Exception:
                    pass
            raise ApplicationHandlerStop

    # ---------- /admin ----------
    async def admin_cmd(update: Update, context):
        context.user_data.pop("adm_action", None)
        await update.message.reply_text(await panel_text(), reply_markup=main_kb())

    async def cancel(update: Update, context):
        context.user_data.pop("adm_action", None)
        await update.message.reply_text("❎ Cancelled. Use /admin to open the panel.")

    # ---------- buttons ----------
    async def on_button(update: Update, context):
        q = update.callback_query
        if q.from_user.id != admin_id:
            await q.answer("Not allowed", show_alert=True)
            return
        await q.answer()
        d = q.data
        context.user_data.pop("adm_action", None)

        if d == "adm_back":
            await q.edit_message_text(await panel_text(), reply_markup=main_kb())

        elif d == "adm_close":
            try:
                await q.message.delete()
            except Exception:
                pass

        elif d == "adm_stats":
            total, ban, msgs, langs = await asyncio.to_thread(_stats)
            lang_txt = "\n".join(f"   • {k}: {v}" for k, v in langs.items()) or "   -"
            await q.edit_message_text(
                f"📊 Stats\n\n👥 Users: {total}\n🚫 Banned: {ban}\n💬 Total messages: {msgs}\n\n🌐 Languages:\n{lang_txt}",
                reply_markup=back_kb,
            )

        elif d in PROMPTS:
            context.user_data["adm_action"] = d
            await q.edit_message_text(PROMPTS[d] + "\n\n/cancel to abort", reply_markup=back_kb)

        elif d == "adm_banned":
            rows = await asyncio.to_thread(lambda: list(users_col.find({"banned": True}).limit(50)))
            if rows:
                lines = [
                    f"{r['_id']}  {'@' + r['username'] if r.get('username') else ''}".strip()
                    for r in rows
                ]
                txt = "📋 Banned users\n\n" + "\n".join(lines)
            else:
                txt = "📋 No banned users."
            await q.edit_message_text(txt, reply_markup=back_kb)

        elif d == "adm_export":
            rows = await asyncio.to_thread(lambda: list(users_col.find({})))
            buf = io.StringIO()
            w = csv.writer(buf)
            w.writerow(["id", "username", "name", "lang", "msg_count", "banned"])
            for r in rows:
                w.writerow([
                    r["_id"], r.get("username", ""), r.get("name", ""),
                    r.get("lang", ""), r.get("msg_count", 0), bool(r.get("banned", False)),
                ])
            data = io.BytesIO(buf.getvalue().encode("utf-8-sig"))
            data.name = "users.csv"
            await context.bot.send_document(
                chat_id=q.message.chat_id, document=data, caption=f"👥 {len(rows)} users"
            )

    # ---------- broadcast worker ----------
    async def run_broadcast(msg, ids, status):
        ok = fail = 0
        for uid in ids:
            if uid in banned:
                continue
            try:
                await msg.copy(chat_id=uid)
                ok += 1
            except RetryAfter as e:
                ra = e.retry_after
                ra = ra.total_seconds() if hasattr(ra, "total_seconds") else ra
                await asyncio.sleep(ra + 1)
                try:
                    await msg.copy(chat_id=uid)
                    ok += 1
                except Exception:
                    fail += 1
            except Exception:
                fail += 1
            await asyncio.sleep(0.05)
        await status.edit_text(f"✅ Broadcast done\n\n✔️ Sent: {ok}\n❌ Failed: {fail}")

    # ---------- admin's next message after pressing a button ----------
    async def admin_input(update: Update, context):
        action = context.user_data.get("adm_action")
        msg = update.message
        if not action or not msg:
            return  # normal flow continues
        text = (msg.text or "").strip()

        if action == "adm_bc":
            context.user_data.pop("adm_action", None)
            ids = await asyncio.to_thread(lambda: [d["_id"] for d in users_col.find({}, {"_id": 1})])
            status = await msg.reply_text(f"📢 Broadcasting to {len(ids)} users...")
            context.application.create_task(run_broadcast(msg, ids, status))
            raise ApplicationHandlerStop

        if action == "adm_find":
            context.user_data.pop("adm_action", None)
            if text.lstrip("-").isdigit():
                query = {"_id": int(text)}
            else:
                query = {"username": text.lstrip("@").lower()}
            doc = await asyncio.to_thread(users_col.find_one, query)
            if doc:
                uname = f"@{doc['username']}" if doc.get("username") else "-"
                out = (
                    "🔎 User found\n\n"
                    f"🆔 ID: {doc['_id']}\n"
                    f"👤 Name: {doc.get('name', '-')}\n"
                    f"🔗 Username: {uname}\n"
                    f"🌐 Language: {doc.get('lang', '-')}\n"
                    f"💬 Messages: {doc.get('msg_count', 0)}\n"
                    f"🚫 Banned: {'Yes' if doc.get('banned') else 'No'}"
                )
            else:
                out = "❌ User not found."
            await msg.reply_text(out, reply_markup=back_kb)
            raise ApplicationHandlerStop

        if action in ("adm_ban", "adm_unban"):
            if not text.isdigit():
                await msg.reply_text("❌ Please send a numeric user ID (or /cancel).")
                raise ApplicationHandlerStop
            context.user_data.pop("adm_action", None)
            uid = int(text)
            if uid == admin_id:
                await msg.reply_text("❌ You can't ban yourself.", reply_markup=back_kb)
                raise ApplicationHandlerStop
            is_ban = action == "adm_ban"
            await asyncio.to_thread(
                users_col.update_one, {"_id": uid}, {"$set": {"banned": is_ban}}, True
            )
            if is_ban:
                banned.add(uid)
            else:
                banned.discard(uid)
            await msg.reply_text(
                f"{'🚫 Banned' if is_ban else '✅ Unbanned'}: {uid}", reply_markup=back_kb
            )
            raise ApplicationHandlerStop

    # ---------- register ----------
    application.add_handler(TypeHandler(Update, gate), group=-5)
    application.add_handler(
        MessageHandler(filters.User(user_id=admin_id) & ~filters.COMMAND, admin_input), group=-3
    )
    application.add_handler(CommandHandler("admin", admin_cmd, filters=filters.User(user_id=admin_id)))
    application.add_handler(CommandHandler("cancel", cancel, filters=filters.User(user_id=admin_id)))
    application.add_handler(CallbackQueryHandler(on_button, pattern=r"^adm_"))
