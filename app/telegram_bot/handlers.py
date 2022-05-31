import json
import os

from app.models import User, Event
from telegram import Update, WebAppInfo, InlineKeyboardButton, ReplyKeyboardMarkup, InlineKeyboardMarkup, \
    ReplyKeyboardRemove, KeyboardButton, InputMediaVideo, InputMediaPhoto, LabeledPrice

from config import Config
from app.telegram_bot.helpers import with_app_context
from telegram.ext import CallbackContext
from telegram.constants import ParseMode


@with_app_context
async def start(update: Update, context: CallbackContext.DEFAULT_TYPE):
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="I'm a bot, please talk to me!"
    )


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
    chat_id = int(update.message.from_user.id)
    message_id = int(update.message.message_id)
    sender: User = User.query.filter(User.tg_id == chat_id).first()

    await update.message.delete()

    events: Event = Event.query.order_by(Event.id).all()
    buttons = []
    for index, i in enumerate(events):
        text = f'{index + 1}) {i.date} {i.name}'
        callback = f'event_{i.id}'
        buttons.append(
            InlineKeyboardButton(text=text,
                                 callback_data=callback)
        )


    await update.message.reply_text(
        text='Список предстоящих концертов:',
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[x] for x in buttons]))


@with_app_context
async def send_event(update: Update, context: CallbackContext.DEFAULT_TYPE):
    event: Event = Event.query.get(int(update.callback_query.data.split('_')[-1]))
    poster = event.poster
    media_group = []
    # await update.callback_query.delete_message()
    media = open(os.path.join(Config.UPLOAD_FOLDER, 'events', str(event.id), poster['filename']), 'rb')
    if 'photo' in poster['file_type']:
        media_group.append(InputMediaPhoto(media=media,
                                           caption=event.description,
                                           parse_mode=ParseMode.MARKDOWN)
                           )
    btn = [
        InlineKeyboardButton(text='Купить билеты',
                             web_app=WebAppInfo(url=f'{Config.SERVER}'),
                             )]
    await update.effective_message.reply_media_group(media=media_group,
                                                     protect_content=True,
                                                     )


    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=f"Купить билеты",
        reply_markup=InlineKeyboardMarkup([btn]),
        protect_content=True,
        parse_mode=ParseMode.MARKDOWN,
    )


@with_app_context
async def help(update: Update, context: CallbackContext.DEFAULT_TYPE):
    user = User.query.filter(User.tg_id == update.callback_query.from_user.id).first()
    print(user)
    await update.callback_query.delete_message()
    # texts.help(user)


@with_app_context
async def delete_message(update: Update, context: CallbackContext.DEFAULT_TYPE):
    await update.callback_query.delete_message()



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
