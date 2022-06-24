from telegram.ext import CallbackContext

from app.telegram_bot.helpers import with_app_context
from app import db
# from app.models import UserTrip
from telegram import Update
from datetime import datetime
from pprint import pprint


@with_app_context
async def pre_checkout(update: Update, context: CallbackContext.DEFAULT_TYPE):
    # user_trip: UserTrip = UserTrip.query.get(int(update.pre_checkout_query.invoice_payload))
    # user_trip.pre_checkout_query_id = str(update.pre_checkout_query.id)
    # if update.pre_checkout_query.order_info.phone_number:
    #     user_trip.get_user().phone = update.pre_checkout_query.order_info.phone_number
    # db.session.commit()

    await application.bot.answer_pre_checkout_query(pre_checkout_query_id=update.pre_checkout_query.id,
                                      ok=True)

    # return 'ok'


@with_app_context
async def successful_payment(update: Update, context:CallbackContext.DEFAULT_TYPE):
    # user_trip: UserTrip = UserTrip.query.get(int(update.effective_message.successful_payment.invoice_payload))
    # user_trip.paid = True
    # user_trip.price = update.effective_message.successful_payment.total_amount/100
    # user_trip.payment_date = datetime.now()
    # user_trip.provider_payment_charge_id = update.effective_message.successful_payment.provider_payment_charge_id
    # user_trip.telegram_payment_charge_id = update.effective_message.successful_payment.telegram_payment_charge_id
    # db.session.commit()
    #
    # # отправляем пользователю подтверждение платежа и кнопку "Пошли гулять"
    # go_btn = [InlineKeyboardButton(text='Пошли гулять', callback_data=f'letswalk_{user_trip.id}')]
    # bot.send_message(chat_id=user_trip.get_user().tg_id,
    #                  text='user_trip.get_trip().success_payment_text',
    #                  reply_markup=InlineKeyboardMarkup([go_btn]),
    #                  protect_content=True,
    #                  parse_mode=ParseMode.MARKDOWN)
    #
    # update.effective_message.delete()
    print('payed')
    return 'ok'
