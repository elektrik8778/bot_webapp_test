from telegram import InlineKeyboardButton


def hide_btn(text='Скрыть 🫣'):
    return InlineKeyboardButton(text=text, callback_data='hidemsg')
