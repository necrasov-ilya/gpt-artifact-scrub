import os
import json
import time
from pathlib import Path
from typing import Tuple, Dict, List, Optional
import logging
from html import escape

from dotenv import load_dotenv
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters, CallbackQueryHandler
from telegram.constants import ParseMode
from normalize import normalize_text

load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
USER_LOG_MAX_BYTES = int(os.getenv("USER_LOG_MAX_BYTES", "1048576"))
LOGS_WHITELIST_IDS = {int(x) for x in os.getenv("LOGS_WHITELIST_IDS", "").replace(" ", "").split(",") if x.isdigit()}
LOGS_PAGE_SIZE = int(os.getenv("LOGS_PAGE_SIZE", "20"))

DATA_DIR = Path("./data/user")
DATA_DIR.mkdir(parents=True, exist_ok=True)

logger = logging.getLogger(__name__)

def _split_for_code_block(text: str, max_message_len: int = 3800) -> List[str]:
    if len(text) <= max_message_len:
        return [text]
    parts: List[str] = []
    current = []
    current_len = 0
    for line in text.splitlines(keepends=True):
        if current_len + len(line) > max_message_len and current:
            parts.append("".join(current))
            current = []
            current_len = 0
        if len(line) > max_message_len:
            start = 0
            while start < len(line):
                end = min(start + max_message_len, len(line))
                parts.append(line[start:end])
                start = end
            continue
        current.append(line)
        current_len += len(line)
    if current:
        parts.append("".join(current))
    return parts

def write_user_log(user_id: int, entry: Dict, max_bytes: int = USER_LOG_MAX_BYTES) -> None:
    user_dir = DATA_DIR / str(user_id)
    user_dir.mkdir(parents=True, exist_ok=True)
    log_path = user_dir / "history.jsonl"

    entry["ts"] = int(time.time())
    line = json.dumps(entry, ensure_ascii=False) + "\n"

    with open(log_path, "a", encoding="utf-8") as f:
        f.write(line)

    try:
        if log_path.stat().st_size > max_bytes:
            with open(log_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            keep = int(len(lines) * 0.7)
            keep_lines = lines[-keep:]
            with open(log_path, "w", encoding="utf-8") as f:
                f.writelines(keep_lines)
            logger.info("trimmed user log id=%s to last %s lines", user_id, len(keep_lines))
    except FileNotFoundError:
        pass

START_TEXT = (
    "Убираю признаки ИИ из вашего текста. Просто отправьте ваш текст, а я верну очищенную версию.\n\n"
    "Что я делаю: заменяю длинные тире на '-', кавычки-ёлочки и типографские кавычки на \"\","
    " маркеры списков на '-', а также убираю артефакты от LLM ([cite], (turn0search1) и т.п.)."
)
HELP_TEXT = START_TEXT + "\n\nТех. поддержка - @mentsev"


async def on_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    kb = ReplyKeyboardMarkup([["ℹ️ Помощь"]], resize_keyboard=True)
    await update.message.reply_text(START_TEXT, reply_markup=kb)


async def on_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(HELP_TEXT)


async def on_help_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(HELP_TEXT)


def build_stats_text(stats: Dict[str, int]) -> str:
    parts = []
    if stats.get("dashes"):
        parts.append(f"тире: {stats['dashes']}")
    if stats.get("quotes"):
        parts.append(f"кавычки: {stats['quotes']}")
    if stats.get("bullets"):
        parts.append(f"маркеры списков: {stats['bullets']}")
    if stats.get("nbsp"):
        parts.append(f"неразрывные пробелы: {stats['nbsp']}")
    # LLM artifacts
    if stats.get("llm_tokens"):
        parts.append(f"маркеры LLM: {stats['llm_tokens']}")
    if stats.get("llm_cite"):
        parts.append(f"cite: {stats['llm_cite']}")
    if stats.get("llm_bracket_groups"):
        parts.append(f"скобочные группы: {stats['llm_bracket_groups']}")
    if not parts:
        return "Ничего не пришлось заменять — текст уже в порядке."
    return "Заменил: " + ", ".join(parts) + "."


async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.text:
        return

    user = update.effective_user
    original = update.message.text

    cleaned, stats = normalize_text(original)

    write_user_log(
        user_id=user.id,
        entry={
            "type": "text",
            "user": {"id": user.id, "username": user.username, "name": user.full_name},
            "input_len": len(original),
            "output_len": len(cleaned),
            "input": original,
            "output": cleaned,
            "stats": stats,
        },
    )
    logger.info(
        "user=%s input_len=%s output_len=%s stats=%s",
        user.id,
        len(original),
        len(cleaned),
        stats,
    )

    for chunk in _split_for_code_block(cleaned):
        html_block = f"<pre><code>{escape(chunk)}</code></pre>"
        await update.message.reply_text(html_block, parse_mode=ParseMode.HTML, disable_web_page_preview=True)
    await update.message.reply_text(build_stats_text(stats))


async def on_unknown(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("Пришлите текст сообщением — я его очищу.")


def _is_whitelisted(user) -> bool:
    if user is None:
        return False
    if user.id in LOGS_WHITELIST_IDS:
        return True
    return False


def _aggregate_logs() -> List[str]:
    counts: Dict[str, int] = {}
    names: Dict[str, str] = {}
    if not DATA_DIR.exists():
        return []
    for child in DATA_DIR.iterdir():
        if not child.is_dir():
            continue
        log_path = child / "history.jsonl"
        if not log_path.exists():
            continue
        try:
            with open(log_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                    except Exception:
                        continue
                    u = obj.get("user") or {}
                    uid = str(u.get("id") or child.name)
                    uname = u.get("username")
                    display = (uname or u.get("name") or f"id:{uid}")
                    key = (uname or f"id:{uid}").lower()
                    counts[key] = counts.get(key, 0) + 1
                    if key not in names:
                        names[key] = display
        except Exception:
            continue
    ordered = [f"{names.get(k, k)} — {counts[k]}" for k in sorted(counts.keys(), key=lambda k: (-counts[k], names.get(k, k)))]
    return ordered


def _render_logs_page(page: int, page_size: int) -> Tuple[str, Optional[InlineKeyboardMarkup]]:
    lines = _aggregate_logs()
    total = len(lines)
    header = f"📊 <b>Статистика пользователей</b>\nВсего: {total}"
    if total == 0:
        return header, None
    max_page = max(0, (total - 1) // page_size)
    page = max(0, min(page, max_page))
    start = page * page_size
    end = min(start + page_size, total)
    body_lines = []
    for i, line in enumerate(lines[start:end], start=start+1):
        body_lines.append(f"{i}. {line}")
    body = "\n".join(body_lines)
    page_info = f"\n\n📄 Страница {page+1} из {max_page+1}"
    text = header + ("\n\n" + body if body else "") + page_info
    if total <= page_size:
        return text, None
    buttons: List[List[InlineKeyboardButton]] = []
    row: List[InlineKeyboardButton] = []
    if page > 0:
        row.append(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"logs:page:{page-1}"))
    if page < max_page:
        row.append(InlineKeyboardButton(text="Дальше ➡️", callback_data=f"logs:page:{page+1}"))
    if row:
        buttons.append(row)
    return text, InlineKeyboardMarkup(buttons)


async def on_logs(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not _is_whitelisted(user):
        await update.message.reply_text("Пришлите текст сообщением — я его очищу.")
        return
    text, keyboard = _render_logs_page(0, LOGS_PAGE_SIZE)
    await update.message.reply_text(text, reply_markup=keyboard, parse_mode=ParseMode.HTML)


async def on_logs_page_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    if not q:
        return
    user = q.from_user
    if not _is_whitelisted(user):
        try:
            await q.answer()
        except Exception:
            pass
        return
    data = q.data or ""
    try:
        _, _, page_str = data.partition(":page:")
        page = int(page_str)
    except Exception:
        page = 0
    text, keyboard = _render_logs_page(page, LOGS_PAGE_SIZE)
    try:
        await q.edit_message_text(text=text, reply_markup=keyboard, parse_mode=ParseMode.HTML)
    except Exception:
        try:
            await q.message.reply_text(text, reply_markup=keyboard, parse_mode=ParseMode.HTML)
        except Exception:
            pass
    try:
        await q.answer()
    except Exception:
        pass


def main() -> None:
    if not BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not set. Add it to .env or environment.")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logger.info("starting bot, user_log_max_bytes=%s", USER_LOG_MAX_BYTES)
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", on_start))
    app.add_handler(CommandHandler("help", on_help))
    app.add_handler(CommandHandler("logs", on_logs))
    app.add_handler(MessageHandler(filters.StatusUpdate.ALL, on_unknown))
    app.add_handler(MessageHandler(filters.Regex(r"^ℹ️ Помощь$"), on_help_button))
    app.add_handler(CallbackQueryHandler(on_logs_page_cb, pattern=r"^logs:page:\d+$"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    app.add_handler(MessageHandler(filters.ALL, on_unknown))

    app.run_polling(close_loop=False)


if __name__ == "__main__":
    main()
