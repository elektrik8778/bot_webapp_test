from app import application
import requests
from config import Config
from app.telegram_bot import bp
from telegram import Update
from app.telegram_bot import handlers
import os
from flask import request
from pprint import pprint
from telegram.ext import CommandHandler, MessageHandler, filters, CallbackQueryHandler


application.add_handler(CommandHandler('start', handlers.start))
application.add_handler(CommandHandler('help', handlers.help_command))
application.add_handler(CommandHandler('webapp', handlers.web))
application.add_handler(CommandHandler('events', handlers.events))

application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handlers.echo))

application.add_handler(CallbackQueryHandler(pattern='help', callback=handlers.help))
application.add_handler(CallbackQueryHandler(pattern='deleteMessage', callback=handlers.delete_message))
application.add_handler(CallbackQueryHandler(pattern='event', callback=handlers.send_event))

if (addr := os.environ.get("TG_ADDR")) != "":
    print(f"Setting webhook for {addr}")
    requests.get(f'https://api.telegram.org/bot{Config.TG_TOKEN}/setWebhook?url={Config.SERVER}/telegram')
    # print(requests.get(f'https://api.telegram.org/bot{Config.TG_TOKEN}/getwebhookinfo').content)


@bp.route('/telegram', methods=['GET', 'POST'])
async def telegram():

    update = Update.de_json(request.get_json(force=True), bot=application.bot)
    # pprint(update.to_dict())

    async with application:
        await application.process_update(update)

    return 'ok'


@bp.route('/webappresponse', methods=['POST'])
async def post_response():

    pprint(request.json)

    return 'ok'