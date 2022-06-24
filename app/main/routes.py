import os

import config
from app.main import bp
from flask import redirect, request, render_template
from flask_login import login_required
from app import db
from app.models import Event
# from app.telegram_bot.handlers import get_inline_menu, create_button_map
# from telegram.error import Unauthorized
from telegram.constants import ParseMode
from datetime import datetime

from app.models import Placement
from config import Config


@bp.route('/categories')
@bp.route('/', methods=['GET', 'POST'])
# @login_required
def index():
    # print('/_route')
    # bot_name = Config.BOT_NAME
    # title = 'Главная'
    # server = Config.SERVER
    # placement: Placement = Placement.query.filter(Placement.id == 1).first()
    # if request.args:
    #     if 'u' in request.args:
    #         print(request.args['u'])
    #
    # return render_template('main/with-map.html',
    #                        bot_name=bot_name,
    #                        title=title,
    #                        server=server,
    #                        placement=placement)
    return redirect('/admin')


@bp.get('/event/<eid>/chairs')
def web_app_event_chairs(eid):
    max_places = Config.MAX_PLACES
    return render_template('main/with-map.html', event=Event.query.get(int(eid)), max_places=max_places)
