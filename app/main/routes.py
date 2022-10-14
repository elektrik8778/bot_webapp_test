from app import db
from app.main import bp
from app.telegram_bot import texts
from flask import render_template, request, make_response
from app.models import User, QuestProcess, Component, UserComponent, Tag, UserQuest
from config import Config
from app.telegram_bot.routes import get_bot
from app.telegram_bot.texts import quest_start
from telegram.constants import ParseMode
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
import json
import os
import random
from string import ascii_letters
from sqlalchemy.engine.cursor import CursorResult
from datetime import datetime


@bp.route('/test1')
async def test1():
    user: User = User.query.get(1)
    db.session.remove()
    bot = get_bot()
    try:
        result = await bot.send_message(chat_id=user.tg_id,
                                        text=random.choices(population=ascii_letters, k=10))
        await result.edit_text(text=random.choices(population=ascii_letters, k=10))
        await result.delete()
    except Exception as e:
        print(e)
    return 'ok'


@bp.route('/test2')
def test2():
    return 'ok'


@bp.route('/castle')
# @bp.route('/', methods=['GET', 'POST'])
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
    db.session.remove()
    return make_response(user.first_name, 200)


@bp.route('/get_components/<uid>')
def get_components(uid):
    user: User = User.query.filter(User.tg_id == int(uid)).first()
    components = user.get_components()
    result = []
    for uc in components:
        c = uc.get_component()
        result.append({
            'id': uc.component,
            'name': c.name,
            'description': c.description,
            'filename': c.filename+'_web.png'
        })
    db.session.remove()
    return json.dumps(result)


@bp.route('/check_quest_process/<uid>')
def check_quest_process(uid):
    user: User = User.query.filter(User.tg_id == int(uid)).first()
    quest_process: QuestProcess = QuestProcess.query.filter(QuestProcess.user == user.id).first()
    db.session.remove()
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

    components = user.get_components()
    for c in components:
        db.session.delete(c)
    db.session.commit()

    await bot.send_message(chat_id=uid,
                           text=quest_start(user),
                           reply_markup=keyboard,
                           parse_mode=ParseMode.MARKDOWN)
    db.session.remove()
    return user.first_name


@bp.route('/final_battle/<uid>')
async def final_battle(uid):
    from app.telegram_bot.handlers import get_bot_pic
    user: User = User.query.filter(User.tg_id == int(uid)).first()
    bot = get_bot()
    user_components = UserComponent.query.filter(UserComponent.user == user.id).all()
    user_quest: UserQuest = UserQuest.query.filter(UserQuest.user == user.id).order_by(UserQuest.id.desc()).first()
    user_quest.finish = datetime.now()
    # если собраны все, то победа
    # если их меньше, то поражение
    text = ''
    if len(user_components) >= len(Component.query.all()):
        text = texts.FINAL_BATTLE_WIN
        tag: Tag = Tag.query.filter(Tag.name == 'Победил в квесте').first()
        user.add_tag(tag)
        db.session.commit()
        video = await get_bot_pic(name='win', folder='final_battle', format='mp4')
        user_quest.result = 'win'
    else:
        text = texts.FINAL_BATTLE_LOSE
        video = await get_bot_pic(name='lose_1_8', folder='final_battle', format='mp4')
        user_quest.result = 'lose'
    try:
        result = await bot.send_video(chat_id=uid,
                                      video=video,
                                      caption=text,
                                      parse_mode=ParseMode.MARKDOWN,
                                      protect_content=True)
    except Exception as e:
        print(user, e)

    # удаляем компоненты пользователя
    for c in UserComponent.query.filter(UserComponent.user == user.id).all():
        db.session.delete(c)
    user.finished_quest = datetime.now()

    db.session.commit()
    db.session.remove()
    return 'ok'
