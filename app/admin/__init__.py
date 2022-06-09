import asyncio

from flask import Blueprint

bp = Blueprint('admin', __name__)

from app.admin import routes, places, events
from app.telegram_bot.helpers import with_app_context
from app.models import Group
from app import db


@with_app_context
async def check_groups():
    try:
        if len(Group.query.all()) == 0:
            group = Group()
            group.name = 'def'
            group.time_zone = 9
            db.session.add(group)
            db.session.commit()
            print(f'def Group created, id={group.id}')
        else:
            print(f'def group exists, id={Group.query.order_by(Group.id).first().id}')
    except Exception as e:
        print(e)

loop=asyncio.get_event_loop()
loop.run_until_complete(check_groups())
loop.close()
