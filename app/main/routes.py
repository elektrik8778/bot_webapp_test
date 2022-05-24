import os

import config
from app.main import bp
from flask import redirect, request, render_template
from flask_login import login_required
from app import db
# from app.models import ScheduledMessage, User, TaskForSending, Quiz, Trip
# from app.telegram_bot.handlers import get_inline_menu, create_button_map
# from telegram.error import Unauthorized
from telegram.constants import ParseMode
from datetime import datetime
from config import Config



@bp.route('/', methods=['GET', 'POST'])
# @login_required
def index():
    bot_name = Config.BOT_NAME
    title = 'Главная'
    # if request.args:
    #     if 'u' in request.args:
    #         print(request.args['u'])

    return render_template('main/with-map.html',
                           bot_name=bot_name,
                           title=title)
    # return redirect('/admin')

