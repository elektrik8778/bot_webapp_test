from app import db
from app.main import bp
from flask import render_template, request, make_response
from app.models import User, QuestProcess
from config import Config
from app.telegram_bot.routes import get_bot
from app.telegram_bot.texts import quest_start
from telegram.constants import ParseMode
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
import json
import os
import random
from string import ascii_letters


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
            'description': c.description
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

    await bot.send_message(chat_id=uid,
                           text=quest_start(user),
                           reply_markup=keyboard,
                           parse_mode=ParseMode.MARKDOWN)
    db.session.remove()
    return user.first_name


@bp.route('/final_battle/<uid>')
async def final_battle(uid):
    user: User = User.query.filter(User.tg_id == int(uid)).first()
    bot = get_bot()

    # получить компоненты пользователя
    components = user.get_components()
    components_count = len(components)

    # если их 5, то победа
    # если их 0, то поражение с первого раза
    # если их N, то поражение со второго раза
    # если их 2, то поражение с третьего раза
    # если их 3, то поражение с четвертого раза
    # если их 4, то поражение с пятого раза
    if components_count == 5:
        if os.path.exists(os.path.join(Config.STATIC_FOLDER, 'video', 'pt nad win.fid')):
            vfile = os.path.join(Config.STATIC_FOLDER, 'video', 'pt nad win.fid')
        else:
            vfile = os.path.join(Config.STATIC_FOLDER, 'video', 'pt nad win.mp4')
    else:
        if os.path.exists(os.path.join(Config.STATIC_FOLDER, 'video', f'pt nad lose {components_count+1}.fid')):
            vfile = os.path.join(Config.STATIC_FOLDER, 'video', f'pt nad lose {components_count+1}.fid')
        else:
            vfile = os.path.join(Config.STATIC_FOLDER, 'video', f'pt nad lose {components_count + 1}.mp4')

    if vfile.split('.')[-1] == 'mp4':
        with open(vfile, 'rb') as video:
            result = await bot.send_video(chat_id=uid,
                                          video=video,
                                          caption='Ваша финальная битва')
            with open(os.path.join(Config.STATIC_FOLDER, 'video', f'pt nad lose {components_count+1}.fid'), 'w') as fid:
                fid.write(result.video.file_id)
    else:
        with open(vfile, 'r') as video:
            result = await bot.send_video(chat_id=uid,
                                          video=video.read(),
                                          caption='Ваша финальная битва')
    for c in components:
        db.session.delete(c)
    db.session.commit()
    return 'ok'
