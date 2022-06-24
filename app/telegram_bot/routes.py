from app import application, db
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
from telegram import LabeledPrice
from app.models import User, Event, Order
from sqlalchemy.engine import CursorResult
import json


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
    async with application:
        await application.process_update(update)
    return 'ok'


@bp.route('/webappresponse', methods=['POST'])
async def post_response():
    eid = int(request.referrer.split('/')[4])
    seats = request.json['seats']
    uid = request.json['uid']
    user: User = User.query.filter(User.tg_id == uid).first()
    event: Event = Event.query.get(eid)

    # проверяем, нет ли этих билетов уже в заказах
    for s in seats:
        query_string = f'''
        select *
        from "order"
        where
            event = {eid}
            and
            seats[1].to_jsonb ->> 'sectorName' = '{seats[s]["sectorName"]}'
            and
            seats[1].to_jsonb ->> 'seat' = '{seats[s]["seat"]}'
            and
            seats[1].to_jsonb ->> 'row' = '{seats[s]["row"]}';
        '''

        result: CursorResult = db.session.execute(query_string)
        if len(result.all()):
            await application.bot.send_message(chat_id=user.tg_id,
                                               text=f'Билет в секции *{seats[s]["sectorName"]}* с местом *{seats[s]["seat"]}* в ряду *{seats[s]["row"]}* уже куплен другим клиентом, выберите, пожалуйста, другое место.',
                                               parse_mode=ParseMode.MARKDOWN)
            return 'ok'

    # если всё в порядке - сохраняем заказ
    order = Order()
    order.user = user.id
    order.event = eid
    order.seats = [seats[seat] for seat in seats]
    price = 0
    for i in seats:
        price += float(seats[i]['price'])
    order.price = price
    db.session.add(order)
    db.session.commit()

    # помечаем билеты в файле js как недоступные
    event.get_placement().set_seats_busy_free(seats, free=False)

    # отправляем кнопку оплаты
    prices = [LabeledPrice(label=f'Ряд {s["row"]}, место {s["seat"]}', amount=(int(s["price"]) * 100)) for s in order.seats]
    await application.bot.send_invoice(chat_id=uid,
                                       title=f'{event.name}',
                                       description=f'{event.get_place().name}, {event.date.strftime("%d.%m.%y")}, {event.time.strftime("%H:%M")}. Оплатите счет ниже в течении 20 минут. Спустя 20 минут бронь билетов будет анулирована.',
                                       payload=f'{event.id}_{user.id}',
                                       provider_token=(os.environ.get('PAYMENT_TOKEN')),
                                       currency='RUB',
                                       prices=prices,
                                       protect_content=True,
                                       need_phone_number=False,
                                       )
    return 'ok'
