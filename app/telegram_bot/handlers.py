import json
import os
from app.models import User, Event
from telegram import Update, WebAppInfo, InlineKeyboardButton, ReplyKeyboardMarkup, InlineKeyboardMarkup, \
    ReplyKeyboardRemove, KeyboardButton, InputMediaVideo, InputMediaPhoto, LabeledPrice
from config import Config
from app.telegram_bot.helpers import with_app_context
from telegram.ext import CallbackContext
from telegram.constants import ParseMode
import openpyxl
from openpyxl.cell import Cell
from openpyxl import styles


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


from colorsys import rgb_to_hls, hls_to_rgb
# From: https://stackoverflow.com/questions/58429823/getting-excel-cell-background-themed-color-as-hex-with-openpyxl/58443509#58443509
#   which refers to: https://pastebin.com/B2nGEGX2 (October 2020)
#       Updated to use list(elem) instead of the deprecated elem.getchildren() method
#       which has now been removed completely from Python 3.9 onwards.
#

#https://bitbucket.org/openpyxl/openpyxl/issues/987/add-utility-functions-for-colors-to-help

RGBMAX = 0xff  # Corresponds to 255
HLSMAX = 240  # MS excel's tint function expects that HLS is base 240. see:
# https://social.msdn.microsoft.com/Forums/en-US/e9d8c136-6d62-4098-9b1b-dac786149f43/excel-color-tint-algorithm-incorrect?forum=os_binaryfile#d3c2ac95-52e0-476b-86f1-e2a697f24969


def rgb_to_ms_hls(red, green=None, blue=None):
    """Converts rgb values in range (0,1) or a hex string of the form '[#aa]rrggbb' to HLSMAX based HLS, (alpha values are ignored)"""
    if green is None:
        if isinstance(red, str):
            if len(red) > 6:
                red = red[-6:]  # Ignore preceding '#' and alpha values
            blue = int(red[4:], 16) / RGBMAX
            green = int(red[2:4], 16) / RGBMAX
            red = int(red[0:2], 16) / RGBMAX
        else:
            red, green, blue = red
    h, l, s = rgb_to_hls(red, green, blue)
    return (int(round(h * HLSMAX)), int(round(l * HLSMAX)), int(round(s * HLSMAX)))


def ms_hls_to_rgb(hue, lightness=None, saturation=None):
    """Converts HLSMAX based HLS values to rgb values in the range (0,1)"""
    if lightness is None:
        hue, lightness, saturation = hue
    return hls_to_rgb(hue / HLSMAX, lightness / HLSMAX, saturation / HLSMAX)


def rgb_to_hex(red, green=None, blue=None):
    """Converts (0,1) based RGB values to a hex string 'rrggbb'"""
    if green is None:
        red, green, blue = red
    return ('%02x%02x%02x' % (int(round(red * RGBMAX)), int(round(green * RGBMAX)), int(round(blue * RGBMAX)))).upper()


def get_theme_colors(wb):
    """Gets theme colors from the workbook"""
    # see: https://groups.google.com/forum/#!topic/openpyxl-users/I0k3TfqNLrc
    from openpyxl.xml.functions import QName, fromstring
    xlmns = 'http://schemas.openxmlformats.org/drawingml/2006/main'
    root = fromstring(wb.loaded_theme)
    themeEl = root.find(QName(xlmns, 'themeElements').text)
    colorSchemes = themeEl.findall(QName(xlmns, 'clrScheme').text)
    firstColorScheme = colorSchemes[0]

    colors = []

    for c in ['lt1', 'dk1', 'lt2', 'dk2', 'accent1', 'accent2', 'accent3', 'accent4', 'accent5', 'accent6']:
        accent = firstColorScheme.find(QName(xlmns, c).text)
        for i in list(accent): # walk all child nodes, rather than assuming [0]
            if 'window' in i.attrib['val']:
                colors.append(i.attrib['lastClr'])
            else:
                colors.append(i.attrib['val'])

    return colors


def tint_luminance(tint, lum):
    """Tints a HLSMAX based luminance"""
    # See: http://ciintelligence.blogspot.co.uk/2012/02/converting-excel-theme-color-and-tint.html
    if tint < 0:
        return int(round(lum * (1.0 + tint)))
    else:
        return int(round(lum * (1.0 - tint) + (HLSMAX - HLSMAX * (1.0 - tint))))


def theme_and_tint_to_rgb(wb, theme, tint):
    """Given a workbook, a theme number and a tint return a hex based rgb"""
    rgb = get_theme_colors(wb)[theme]
    h, l, s = rgb_to_ms_hls(rgb)
    return rgb_to_hex(ms_hls_to_rgb(h, tint_luminance(tint, l), s))


@with_app_context
async def create_placement(update: Update, context: CallbackContext.DEFAULT_TYPE):
    wb = openpyxl.load_workbook(filename=os.path.join(Config.STATIC_FOLDER, 'js', 'Grand Arena рассадка_1.xlsx'))
    sheet_places = wb['вариант 1']
    schemeData = []
    for r in sheet_places:
        for c in r:
            if c.value:
                # print(c.value, c.coordinate)
                theme = c.fill.start_color.theme
                tint = c.fill.start_color.tint
                color = "3300CC"
                price = 0
                if type(theme) == int:
                    color = theme_and_tint_to_rgb(wb, theme, tint)
                    sheet_prices = wb['цены']
                    for row in sheet_prices:
                        for cell in row:
                            theme = cell.fill.start_color.theme
                            tint = cell.fill.start_color.tint
                            price_color = theme_and_tint_to_rgb(wb, theme, tint)
                            if color == price_color:
                                price = cell.value
                if c.value.split('\n')[0] == 'надпись':
                    schemeData.append({
                        "NomBilKn": "1338",
                        "ObjectName": "Label",
                        "ObjectType": "Label",
                        "Width": "680",
                        "Height": "60",
                        "CX": f"{c.col_idx*100}",
                        "CX2": f"{c.col_idx*100 + 50}",
                        "CY": f"{c.row*100 + 25}",
                        "CY2": f"{c.row*100 + 45}",
                        "Angle": "0.00",
                        "Row": "",
                        "Seat": "",
                        "cod_sec": "0",
                        "Name_sec": str(c.value.split('\n')[-1]),
                        "FreeOfferSeat": "0",
                        "FontColor": "000000",
                        "FontSize": "10",
                        "Label": "11",
                        "MinX": "119",
                        "MinY": "128",
                        "MaxX": "8491",
                        "MaxY": "6771",
                        "BackColor": color,
                        "avail": True,
                        "name_sec": str(c.value.split('\n')[-1]),
                        "Price": price,
                        "PriceSell": f"{price}.0000"
                    })
                elif c.value.split('\n')[0] in ['место', 'пусто']:
                    schemeData.append({
                        "NomBilKn": "1338",
                        "ObjectName": "Place",
                        "ObjectType": "Place",
                        "Width": "64",
                        "Height": "64",
                        "CX": f"{c.col_idx * 100}",
                        "CX2": f"{c.col_idx * 100 + 50}",
                        "CY": f"{c.row * 100}",
                        "CY2": f"{c.row * 100 + 20}",
                        "Angle": "0.00",
                        "Row": str(c.value.split('\n')[1].split('ряд')[1].strip()),
                        "Seat": str(c.value.split('\n')[2].split('место')[1].strip()),
                        "cod_sec": "2",
                        "Name_sec": str(c.value.split('\n')[3]),
                        "FreeOfferSeat": "0",
                        "FontColor": "",
                        "FontSize": "0",
                        "Label": "0",
                        "MinX": "119",
                        "MinY": "128",
                        "MaxX": "8491",
                        "MaxY": "6771",
                        "BackColor": color,
                        "avail": True if c.value.split('\n')[0] == 'место' else False,
                        "name_sec": str(c.value.split('\n')[3]),
                        "Price": price,
                        "PriceSell": f"{price}.0000"
                    })
    wb.close()
    with open(os.path.join(Config.STATIC_FOLDER, 'js', 'test_data.js'), 'w') as jsdata:
        jsdata.write(f'var schemeData = {json.dumps(schemeData)}')


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
