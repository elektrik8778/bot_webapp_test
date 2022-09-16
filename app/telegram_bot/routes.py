from app import db
import requests
from config import Config
from app.telegram_bot import bp
from telegram import Update
from telegram.constants import ParseMode
from app.telegram_bot import handlers, payments
import os
from flask import request
from pprint import pprint
from telegram.ext import CommandHandler, MessageHandler, filters, CallbackQueryHandler, PreCheckoutQueryHandler
from telegram import LabeledPrice, InlineKeyboardButton, InlineKeyboardMarkup
from app.models import User
from sqlalchemy.engine import CursorResult
import json
from telegram.ext import ApplicationBuilder, ExtBot


def get_bot() -> ApplicationBuilder.bot:
    # application = ApplicationBuilder().token(Config.TG_TOKEN).build()
    # set_bot_handlers(application)
    # return application.bot
    bot = ExtBot(token=Config.TG_TOKEN)
    return bot


def set_bot_handlers(application):
    application.add_handler(CommandHandler('start', handlers.start))
    # application.add_handler(CommandHandler('help', handlers.help_command))
    # application.add_handler(CommandHandler('events', handlers.events))
    # application.add_handler(CommandHandler('ppay', handlers.send_pay))

    # application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handlers.echo))

    # application.add_handler(CallbackQueryHandler(pattern='help', callback=handlers.help))
    # application.add_handler(CallbackQueryHandler(pattern='deleteMessage', callback=handlers.delete_message))
    # application.add_handler(CallbackQueryHandler(pattern='event', callback=handlers.send_event))
    # application.add_handler(CallbackQueryHandler(pattern='cancelorder', callback=handlers.cancel_order))
    application.add_handler(CallbackQueryHandler(pattern='hidemsg', callback=handlers.hide_msg))
    application.add_handler(CallbackQueryHandler(pattern='way', callback=handlers.quest_way))
    application.add_handler(CallbackQueryHandler(pattern='answer', callback=handlers.quiz_answer))
    application.add_handler(CallbackQueryHandler(pattern='component', callback=handlers.collect_component))

    # payments
    # application.add_handler(PreCheckoutQueryHandler(callback=payments.pre_checkout))
    # application.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, callback=payments.successful_payment))


if (addr := os.environ.get("TG_ADDR")) != "":
    print(f"Setting webhook for {addr}")
    requests.get(f'https://api.telegram.org/bot{Config.TG_TOKEN}/setWebhook?url={Config.SERVER}/telegram')
    # print(requests.get(f'https://api.telegram.org/bot{Config.TG_TOKEN}/getwebhookinfo').content)


@bp.route('/telegram', methods=['GET', 'POST'])
async def telegram():
    application = ApplicationBuilder().token(Config.TG_TOKEN).build()
    set_bot_handlers(application)
    update = Update.de_json(request.get_json(force=True), bot=application.bot)
    async with application:
        await application.process_update(update)
    db.session.remove()
    return 'ok'


@bp.route('/webappresponse', methods=['POST'])
async def post_response():
    # нажатие main button
    return
