from telegram import Update, WebAppInfo, InlineKeyboardButton, InlineKeyboardMarkup

from config import Config
from app.telegram_bot.helpers import with_app_context
from telegram.ext import CallbackContext
from telegram.constants import ParseMode

# Define a few command handlers. These usually take the two arguments update and
# context.


@with_app_context
async def start(update: Update, context: CallbackContext.DEFAULT_TYPE):
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="I'm a bot, please talk to me!"
    )


@with_app_context
async def help_command(update, context):
    """Send a message when the command /help is issued."""
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text='Help',
    )


@with_app_context
async def echo(update: Update, context: CallbackContext.DEFAULT_TYPE):
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=update.message.text)



@with_app_context
async def web(update: Update, context: CallbackContext.DEFAULT_TYPE):
    btn = [
        InlineKeyboardButton(text='текст кнопки',
        web_app=WebAppInfo(url=f'{Config.SERVER}'),
        )]
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="WebAppTest",
        reply_markup=InlineKeyboardMarkup([btn]),
        protect_content=True,
        parse_mode=ParseMode.MARKDOWN,
    )