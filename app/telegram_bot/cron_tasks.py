from app.telegram_bot import bp
from app import Config, db
from app.models import Event, Order, User
from app.telegram_bot.routes import get_bot
import os


# установить крон на проверку раз в 2 минуты
@bp.get('/cron/check_bookings')
async def check_bookings():
    # проверяем все неоплаченные бронирования, которые созданы более 20 минут назад
    query_string = f'''
    select *
    from (
        select id, "date", seats, price, paid, "user", event, invoice_msg, (now()+ interval '{Config.DB_TIMEZONE_PATCH} hour' - "order"."date") as DateDifference
        from "order"
        where not "order".paid
        ) as diffs
    where DateDifference >= interval '{Config.BOOKING_FREEZE_INTERVAL} minutes'
    order by id;
    '''
    data = db.session.execute(query_string)
    for i in data:
        order: Order = Order.query.get(int(i['id']))
        event: Event = Event.query.get(int(i['event']))
        # места помечаем свободными
        event.get_placement().set_seats_busy_free(seats=i['seats'], free=True)
        try:
            bot = get_bot()
            # удаляем сообщения с инвойсами
            await bot.delete_message(chat_id=order.get_user().tg_id,
                               message_id=i['invoice_msg'])
        except Exception as e:
            print(e)
        # удаляем сами заказы
        db.session.delete(order)
        db.session.commit()
    return 'ok'
