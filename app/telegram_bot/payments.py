from telegram.ext import CallbackContext
from app.telegram_bot.helpers import with_app_context
from app import db
from app.models import Order
from telegram import Update
from datetime import datetime


@with_app_context
async def pre_checkout(update: Update, context: CallbackContext.DEFAULT_TYPE):
    from app.telegram_bot.routes import get_bot
    bot = get_bot()
    order: Order = Order.query.get(int(update.pre_checkout_query.invoice_payload.split('_')[-1]))
    if order:
        if not order.paid:
            order.pre_checkout_query_id = str(update.pre_checkout_query.id)
            if update.pre_checkout_query.order_info.phone_number:
                order.get_user().phone = update.pre_checkout_query.order_info.phone_number
            db.session.commit()
            response = await bot.answer_pre_checkout_query(pre_checkout_query_id=update.pre_checkout_query.id,
                                                           ok=True)
        else:
            await bot.answer_pre_checkout_query(pre_checkout_query_id=update.pre_checkout_query.id,
                                                ok=False,
                                                error_message='Вы уже оплачивали этот заказ.')
    else:
        await bot.answer_pre_checkout_query(pre_checkout_query_id=update.pre_checkout_query.id,
                                            ok=False,
                                            error_message='Вы просрочили оплату данного заказа.')
        # await update.effective_message.reply_text('Вы просрочили оплату вашего заказа.')
        # await update.effective_message.delete()
    return 'ok'


@with_app_context
async def successful_payment(update: Update, context:CallbackContext.DEFAULT_TYPE):
    order: Order = Order.query.get(int(update.effective_message.successful_payment.invoice_payload.split('_')[-1]))
    order.paid = True
    order.price = update.effective_message.successful_payment.total_amount/100
    order.payment_date = datetime.now()
    order.provider_payment_charge_id = update.effective_message.successful_payment.provider_payment_charge_id
    order.telegram_payment_charge_id = update.effective_message.successful_payment.telegram_payment_charge_id
    db.session.commit()

    # отправляем пользователю подтверждение платежа и билеты
    # go_btn = [InlineKeyboardButton(text='Пошли гулять', callback_data=f'letswalk_{user_trip.id}')]
    # bot.send_message(chat_id=user_trip.get_user().tg_id,
    #                  text='user_trip.get_trip().success_payment_text',
    #                  reply_markup=InlineKeyboardMarkup([go_btn]),
    #                  protect_content=True,
    #                  parse_mode=ParseMode.MARKDOWN)
    await update.effective_message.reply_text('Заказ успешно оплачен. Ваши билеты в Меню -> Мои билеты.')
    # await update.effective_message.delete()
    return 'ok'
