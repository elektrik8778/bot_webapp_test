from app import application
import requests
from config import Config
from app.telegram_bot import bp
from telegram import Update
from app.telegram_bot import handlers, payments
import os
from flask import request
from pprint import pprint
from telegram.ext import CommandHandler, MessageHandler, filters, CallbackQueryHandler, PreCheckoutQueryHandler
from telegram import LabeledPrice
from app.models import User


application.add_handler(CommandHandler('start', handlers.start))
application.add_handler(CommandHandler('help', handlers.help_command))
application.add_handler(CommandHandler('events', handlers.events))
application.add_handler(CommandHandler('ppay', handlers.send_pay))

application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handlers.echo))


application.add_handler(CallbackQueryHandler(pattern='help', callback=handlers.help))
application.add_handler(CallbackQueryHandler(pattern='deleteMessage', callback=handlers.delete_message))
application.add_handler(CallbackQueryHandler(pattern='event', callback=handlers.send_event))



# payments
application.add_handler(PreCheckoutQueryHandler(callback=payments.pre_checkout))
application.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, callback=payments.successful_payment))



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
    print(request.json)
    customer_tg_id = request.json['user_tg_id']
    user: User = User.query.filter(User.tg_id == customer_tg_id).first()
    places = [i for i in request.json.keys() if 'place_' in i]
    prices = [request.json[i] for i in request.json.keys() if 'place_' in i]
    prices = [LabeledPrice(label='Места', amount=(sum(prices) * 100))]
    print(user, places, prices)
    # await application.bot.send_invoice(chat_id=customer_tg_id,
    #                              title='Места',
    #                              description=places,
    #                              payload='Custom-Payload',
    #                              provider_token=('284685063:TEST:MTlkMTA0NDBkM2U0'),
    #                              currency='RUB',
    #                              prices=prices,
    #                              protect_content=True,
    #                              need_phone_number=False,
    #                              max_tip_amount=40000,
    #                              # suggested_tip_amounts=[19900, 29900, 39900]
    #                             )
    return 'ok'
