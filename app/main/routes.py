from app import db
from app.main import bp
from flask import render_template, request, make_response
from app.models import User, QuestProcess
from config import Config
from app.telegram_bot.routes import get_bot
from app.telegram_bot.texts import quest_start
from telegram.constants import ParseMode
from telegram import InlineKeyboardButton, InlineKeyboardMarkup


@bp.route('/categories')
@bp.route('/', methods=['GET', 'POST'])
def index():
    # print(request.__dict__)
    bot_name = Config.BOT_NAME
    title = 'Замок'
    return render_template('main/index.html',
                           bot_name=bot_name,
                           title=title)


@bp.route('/get_user/<uid>')
def get_user(uid):
    user: User = User.query.filter(User.tg_id == int(uid)).first()
    return make_response(user.first_name, 200)


@bp.route('/check_quest_process/<uid>')
def check_quest_process(uid):
    user: User = User.query.filter(User.tg_id == int(uid)).first()
    quest_process: QuestProcess = QuestProcess.query.filter(QuestProcess.user == user.id).first()
    if quest_process:
        return make_response(str(quest_process.id), 200)
    return make_response('нет процесса', 201)


@bp.route('/quest/<uid>')
async def quest(uid):
    user: User = User.query.filter(User.tg_id == int(uid)).first()
    quest_process = QuestProcess()
    quest_process.user = user.id
    db.session.add(quest_process)
    db.session.commit()
    bot = get_bot()
    btns = [
        InlineKeyboardButton(text='1', callback_data='way_1'),
        InlineKeyboardButton(text='2', callback_data='way_2'),
        InlineKeyboardButton(text='3', callback_data='way_3')
    ]
    keyboard = InlineKeyboardMarkup(inline_keyboard=[btns])

    await bot.send_message(chat_id=uid,
                           text=quest_start(user),
                           reply_markup=keyboard,
                           parse_mode=ParseMode.MARKDOWN)
    return user.first_name


@bp.route('/final_battle/<uid>')
async def final_battle(uid):
    user: User = User.query.filter(User.tg_id == int(uid)).first()
    bot = get_bot()
    await bot.send_message(chat_id=uid,
                           text='Получаем видео финальной битвы')
    return user.first_name
