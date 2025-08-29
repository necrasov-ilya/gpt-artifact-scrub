import os
import json
import time
from pathlib import Path
from typing import Tuple, Dict, List
import logging
from html import escape

from dotenv import load_dotenv
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
from telegram.constants import ParseMode
from normalize import normalize_text

load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
USER_LOG_MAX_BYTES = int(os.getenv("USER_LOG_MAX_BYTES", "1048576"))

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
    " маркеры списков на '-'."
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


def main() -> None:
    if not BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not set. Add it to .env or environment.")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logger.info("starting bot, user_log_max_bytes=%s", USER_LOG_MAX_BYTES)
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", on_start))
    app.add_handler(CommandHandler("help", on_help))
    app.add_handler(MessageHandler(filters.Regex(r"^ℹ️ Помощь$"), on_help_button))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    app.add_handler(MessageHandler(filters.ALL, on_unknown))

    app.run_polling(close_loop=False)


if __name__ == "__main__":
    main()
