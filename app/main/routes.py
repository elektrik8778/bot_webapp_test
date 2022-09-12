from app.main import bp
from flask import render_template
from app.models import User
from config import Config
from app.telegram_bot.routes import get_bot


@bp.route('/categories')
@bp.route('/', methods=['GET', 'POST'])
def index():
    bot_name = Config.BOT_NAME
    title = 'Замок'
    return render_template('main/index.html',
                           bot_name=bot_name,
                           title=title)


@bp.route('/quest/<uid>')
async def quest(uid):
    user: User = User.query.filter(User.tg_id == int(uid)).first()
    bot = get_bot()
    await bot.send_message(chat_id=uid,
                           text='Проходим квест')
    return user.first_name


@bp.route('/final_battle/<uid>')
async def final_battle(uid):
    user: User = User.query.filter(User.tg_id == int(uid)).first()
    bot = get_bot()
    await bot.send_message(chat_id=uid,
                           text='Получаем видео финальной битвы')
    return user.first_name
