from app import db
from app.models import User, Event, Group, Order
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice
from app.telegram_bot.helpers import with_app_context
from telegram.ext import CallbackContext
from telegram.constants import ParseMode
from datetime import datetime
from app.telegram_bot import texts


@with_app_context
async def start(update: Update, context: CallbackContext.DEFAULT_TYPE):
    user: User = User.query.filter(User.tg_id == update.effective_user.id).first()
    if not user:
        user = User()
        user.first_name = update.effective_user.first_name
        user.tg_id = update.effective_user.id
        user.group = Group.query.first().id
        user.registered = datetime.now()
        user.last_visit = datetime.now()
        user.role = 'admin' if len(User.query.all()) == 0 else 'user'
        user.set_password('pwd')
        db.session.add(user)
    else:
        user.last_visit = datetime.now()

    db.session.commit()
    await update.effective_message.reply_text(text=texts.greeting(user),
                                              parse_mode=ParseMode.MARKDOWN)


@with_app_context
async def echo(update: Update, context: CallbackContext.DEFAULT_TYPE):
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=update.message.text)


@with_app_context
async def help_command(update: Update, context: CallbackContext.DEFAULT_TYPE):
    chat_id = int(update.message.from_user.id)
    message_id = int(update.message.message_id)
    sender: User = User.query.filter(User.tg_id == chat_id).first()

    await update.message.delete()

    confirm_btn = InlineKeyboardButton(text='Да, помощь нужна', callback_data='help')
    cancel_btn = InlineKeyboardButton(text='Нет, помощь не нужна', callback_data='deleteMessage')

    keyboard = [[confirm_btn], [cancel_btn]]

    await update.message.reply_text(text='🆘 Вы нажали кнопку помощи 🆘.\n\nЗачастую её нажимают просто так. А обработка каждого запроса требует времени.\n\n*Вам действительно нужна наша помощь?*',
                              reply_markup=InlineKeyboardMarkup(keyboard),
                              parse_mode=ParseMode.MARKDOWN)


@with_app_context
async def events(update: Update, context: CallbackContext.DEFAULT_TYPE):
    from app.telegram_bot import buttons as btns
    chat_id = int(update.message.from_user.id)
    message_id = int(update.message.message_id)
    sender: User = User.query.filter(User.tg_id == chat_id).first()

    await update.message.delete()

    events: Event = Event.query.order_by(Event.date, Event.time).all()
    buttons = []
    for index, i in enumerate(events):
        text = f'{i.name} ({i.date.strftime("%d.%m.%y")}, {i.time.strftime("%H:%M")})'
        callback = f'event_{i.id}'
        buttons.append(
            InlineKeyboardButton(text=text,
                                 callback_data=callback)
        )

    buttons.append(btns.hide_btn())

    await update.message.reply_text(
        text='Список предстоящих концертов:',
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[x] for x in buttons]))


@with_app_context
async def send_event(update: Update, context: CallbackContext.DEFAULT_TYPE):
    await Event.query.get(int(update.callback_query.data.split('_')[-1])).send_info(update, context)
    return 'ok'


@with_app_context
async def hide_msg(update: Update, context: CallbackContext.DEFAULT_TYPE):
    await update.effective_message.delete()
    return 'ok'


@with_app_context
async def cancel_order(update: Update, context: CallbackContext.DEFAULT_TYPE):
    if order := Order.query.get(int(update.callback_query.data.split('_')[-1])):
        if not order.paid:
            order.cancel()
            await update.effective_message.delete()
        else:
            await update.effective_message.reply_text('Нельзя отменить оплаченный заказ.')
    return 'ok'


@with_app_context
async def help(update: Update, context: CallbackContext.DEFAULT_TYPE):
    user = User.query.filter(User.tg_id == update.callback_query.from_user.id).first()
    await update.callback_query.delete_message()
    # texts.help(user)


@with_app_context
async def delete_message(update: Update, context: CallbackContext.DEFAULT_TYPE):
    await update.callback_query.delete_message()

@with_app_context
async def send_pay(update: Update, context: CallbackContext.DEFAULT_TYPE):
    user: User = User.query.filter(User.tg_id == update.effective_user.id).first()
    prices = [LabeledPrice(label='Концерт', amount=int(5 * 10000))]
    need_phone_number = False
    if not user.phone:
        need_phone_number = True
    await update.effective_message.reply_invoice(title='name',
                                           description='описание',
                                           payload=str(2),
                                           provider_token=('284685063:TEST:MTlkMTA0NDBkM2U0'),
                                           currency='RUB',
                                           prices=prices,
                                           protect_content=True,
                                           need_phone_number=need_phone_number,
                                           max_tip_amount=40000,
                                           suggested_tip_amounts=[19900, 29900, 39900])
