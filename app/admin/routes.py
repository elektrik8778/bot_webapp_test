import json
import os
import random
import re
import threading
import math
import time
import zipfile
from datetime import datetime, timedelta
from app import db
# from app import bot
from app.admin import bp
from app.models import User, Group, Tag, UserTag, ScheduledMessage, Placement
from app.admin.forms import ChangeWebhookForm, ScheduledMessageCreateForm, SendTGMessageForm, SendGroupTGMessageForm,\
    CreateGroupForm, CreateModerForm, CreateQuestionForm, EditQuizForm, PrizeForm
from config import Config
from flask_login import login_required, current_user
from flask import render_template, redirect, url_for, request, send_from_directory, flash, make_response
from werkzeug.utils import secure_filename
# from telegram import TelegramError, ParseMode
from telegram.error import BadRequest, TelegramError
# from app.telegram_bot.handlers import greet_user, create_button_map, get_inline_menu
from app.telegram_bot.helpers import with_app_context
from sqlalchemy import over, func, cast, distinct, Text, desc
from flask_sqlalchemy import BaseQuery, model
from xeger import Xeger
import re


@bp.route('/admin')
@login_required
def admin():
    print(current_user.tg_id)
    if current_user.role == 'admin' or current_user.role == 'moderator':
        send_group_tg_mes_form = SendGroupTGMessageForm()
        return render_template('admin/admin.html',
                               send_group_tg_mes_form=send_group_tg_mes_form,
                               title='Админка')
    else:
        # return redirect(url_for('main.index'))
        bot_name = Config.BOT_NAME
        title = 'Главная'
        server = Config.SERVER
        placement: Placement.query.filter(Placement.id == 1).first()
        print(placement)
        return render_template('main/with-map.html',
                               bot_name=bot_name,
                               title=title,
                               server=server,
                               placement=placement,
                               )


@bp.route('/admin/settings', methods=['GET', 'POST'])
@login_required
def admin_settings():
    if current_user.role == 'admin' or current_user.role == 'moderator':
        webhook_form = ChangeWebhookForm()
        if webhook_form.validate_on_submit():
            try:
                bot.set_webhook(url=webhook_form.url.data)
                flash(f'Вебхук установлен на {webhook_form.url.data}')
            except(TelegramError):
                flash(f'Вебхук не установлен. Ошибка {str(TelegramError)}')
        webhook_form.url.data = url_for('telegram_bot.telegram', _external=True)
        return render_template('admin/admin_settings.html', title='Настройки', form=webhook_form)
    else:
        # return redirect(url_for('main.index'))
        return redirect('main/index.html')


@bp.route('/admin/message_schedule', methods=['GET', 'POST'])
@login_required
def message_schedule():
    if current_user.role == 'admin':
        create_task_form = ScheduledMessageCreateForm()
        create_task_form.group.choices = [('', 'выбрать группу')] + [(str(x.id), x.name) for x in Group.query.all()]
        scheduled_messages = ScheduledMessage.query.order_by(ScheduledMessage.date_time).all()
        if create_task_form.validate_on_submit():
            task = ScheduledMessage()
            task.message_type = create_task_form.message_type.data
            task.date_time = create_task_form.date_time.data
            task.text = create_task_form.text.data
            if create_task_form.group.data:
                task.group = int(create_task_form.group.data)
            if task.message_type != 'text' and task.message_type != 'poll':
                f = create_task_form.content_link.data
                filename = f.filename
                if not os.path.exists(os.path.join(Config.UPLOAD_FOLDER, 'bulk_messages')):
                    os.makedirs(os.path.join(Config.UPLOAD_FOLDER, 'bulk_messages'))
                f.save(os.path.join(Config.UPLOAD_FOLDER, 'bulk_messages', filename))
                task.content_link = os.path.join(Config.UPLOAD_FOLDER, 'bulk_messages', filename)
            else:
                task.content_link = ''
            db.session.add(task)
            db.session.commit()
            if task.content_link:
                with open(task.content_link, 'rb') as file_to_send:
                    if task.message_type == 'photo':
                        response = bot.send_photo(chat_id=current_user.tg_id,
                                                  photo=file_to_send)
                        bot.delete_message(response.chat.id, response.message_id)
                        task.content_link = response.photo[-1].file_id
                        db.session.commit()
                    if task.message_type == 'video':
                        # вычисляем размер видео
                        import cv2
                        file_path = task.content_link
                        vid = cv2.VideoCapture(file_path)
                        height = vid.get(cv2.CAP_PROP_FRAME_HEIGHT)
                        width = vid.get(cv2.CAP_PROP_FRAME_WIDTH)

                        response = bot.send_video(chat_id=current_user.tg_id,
                                                  video=file_to_send,
                                                  width=width,
                                                  height=height)

                        bot.delete_message(response.chat.id, response.message_id)
                        task.content_link = response.video.file_id
                        db.session.commit()
            return redirect(url_for('admin.message_schedule'))

        return render_template('admin/message_schedule.html',
                               title='Предустановленные сообщения',
                               form=create_task_form,
                               scheduled_messages=scheduled_messages)


    else:
        return redirect(url_for('main.index'))


@bp.route('/admin/message_schedule/delete_<id>', methods=['GET', 'POST'])
@login_required
def delete_task(id):
    task = ScheduledMessage.query.get(int(id))

    # удаляем из запланированных к отправке заданий
    TaskForSending.query.filter(TaskForSending.scheduled_message_id == task.id).delete()

    # удаляем само сообщение
    db.session.delete(task)
    db.session.commit()
    return redirect(request.referrer)


@bp.route('/admin/message_schedule/del_sent_messages/<schedule_message_id>')
@login_required
def del_sent_messages(schedule_message_id):
    sm: ScheduledMessage = ScheduledMessage.query.get(int(schedule_message_id))
    tasks = sm.get_tasks_for_sending(sent=True, deleted=False)
    # Удаление отправленных в фоне
    thr = threading.Thread(target=del_tasks, args=[tasks, db])
    thr.start()
    return redirect(request.referrer)


def set_task_deleted(t):
    t.deleted = True
    t.deleted_time = datetime.now()
    db.session.merge(t)
    db.session.commit()


@with_app_context
def del_tasks(tasks, db):
    for t in tasks:
        if (datetime.now() - t.fact_sending_time).total_seconds() < 172800 and t.message_id:
            try:
                response = bot.delete_message(chat_id=t.get_user().tg_id, message_id=t.message_id)
                set_task_deleted(t)
            except BadRequest:
                print(f'Сообщение {t.message_id} не найдено')
                set_task_deleted(t)


@bp.route('/admin/user/<id>', methods=['GET', 'POST'])
@login_required
def user_detailed(id):
    send_tg_mes_form = SendTGMessageForm()
    user = User.query.filter_by(id=int(id)).first()
    received_scheduled_messages = TaskForSending.query.filter(TaskForSending.user_id == id).order_by(TaskForSending.fact_sending_time).all()
    numbers: LotteryNumber = LotteryNumber.query.filter(LotteryNumber.user_id == id).order_by(LotteryNumber.res_date).all()
    tags = Tag.query.all()

    if send_tg_mes_form.validate_on_submit():
        if send_tg_mes_form.submit.data and send_tg_mes_form.validate():
            text = send_tg_mes_form.text.data
            bot.send_message(chat_id=user.tg_id, text=text, parse_mode='Markdown')
            return redirect(url_for('admin.user_detailed', id=user.id))
    return render_template('admin/user_detailed.html',
                           user=user,
                           send_tg_mes_form=send_tg_mes_form,
                           numbers=numbers,
                           messages=received_scheduled_messages,
                           title=f'Пользователь {user.first_name}',
                           now=datetime.now())


@bp.route('/admin/users_list', methods=['GET', 'POST'])
@login_required
def users_list():
    tags = Tag.query.all()
    return render_template('admin/users_all.html', tags=json.dumps([(str(tag.id), str(tag.name)) for tag in tags], ensure_ascii=False))


@bp.get('/admin/get_users_data')
@bp.post('/admin/get_users_data')
@login_required
def get_users_data():
    query: BaseQuery = db.session.query(User.id, User.tg_id, User.first_name, User.status, User.role, Group.name.label('group'),
                             over(func.string_agg(cast(Tag.id, Text)+'_'+Tag.name, '\n'),
                                  partition_by=User.id).label('tags'),
                             # over(func.string_agg(cast(ScheduledMessage.id, Text), ', '),
                             #      partition_by=User.id).label('messages'),
                             ).distinct()\
        .join(Group, Group.id == User.group)\
        .join(UserTag, User.id == UserTag.user_id, full=True)\
        .join(Tag, Tag.id == UserTag.tag_id, isouter=True)\
        .group_by(User.id, Group.name, Tag.id)

    # print(query)
    # print(query.all()[0].keys())

    # search filter
    search = request.args.get('search[value]')
    if search:
        query = query.filter(db.or_(
            User.status.like(f'%{search}%'),
            User.first_name.like(f'%{search}%'),
            Group.name.like(f'%{search}%'),
            Tag.name.like(f'%{search}%')
        ))
    total_filtered = query.count()

    # sorting
    order = []
    i = 0
    while True:
        col_index = request.args.get(f'order[{i}][column]')
        if col_index is None:
            break
        col_name = request.args.get(f'columns[{col_index}][data]')
        if col_name == 'tickets':
            descending = request.args.get(f'order[{i}][dir]') == 'desc'
            if descending:
                order.append(desc('tickets'))
            else:
                order.append('tickets')
        if col_name not in ['id', 'first_name']:
            col_name = 'id'
        descending = request.args.get(f'order[{i}][dir]') == 'desc'
        col = getattr(User, col_name)

        if descending:
            col = col.desc()
        order.append(col)
        i += 1
    if order:
        query = query.order_by(*order)

    # pagination
    start = request.args.get('start', type=int)
    length = request.args.get('length', type=int)
    query = query.offset(start).limit(length)

    def to_dict(row, index):
        return {
            'num': index + 1,
            'id': row.id,
            'first_name': row.first_name,
            'tg_id': row.tg_id,
            'group': row.group,
            'status': row.status,
            'tags': row.tags,
            'role': row.role,
            # 'messages': row.messages,
            'tickets': 0
        }

    # response
    return {
        'data': [to_dict(user, index) for index, user in enumerate(query)],
        'recordsFiltered': total_filtered,
        'recordsTotal': len(User.query.all()),
        'draw': request.args.get('draw', type=int),
    }


@bp.get('/admin/get_user_tags/<user_id>')
def get_user_tags(user_id):
    print('admin/routes',[(str(tag.id), str(tag.name)) for tag in User.query.get(int(user_id)).get_tags()])
    return json.dumps([(str(tag.id), str(tag.name)) for tag in User.query.get(int(user_id)).get_tags()], ensure_ascii=False)


@bp.post('/admin/set_user_tag')
def set_user_tag():
    data = json.loads(request.get_data())
    print(data)
    return User.query.get(int(data['uid'])).add_tag(Tag.query.get(int(data['tid'])))


@bp.post('/admin/del_user_tag')
def del_user_tag():
    data = json.loads(request.get_data())
    return User.query.get(int(data['uid'])).del_tag(Tag.query.get(int(data['tid'])))


@bp.route('/admin/send_menu/<user_id>', methods=['GET', 'POST'])
@login_required
def admin_send_menu(user_id):
    user: User = User.query.get(user_id)
    if user.tg_id:
        greet_user(user)
    return redirect(request.referrer)


@bp.route('/admin/set_empty_status/<user_id>')
@login_required
def set_empty_status(user_id):
    User.query.get(user_id).status = ''
    db.session.commit()
    return redirect(request.referrer)


@bp.route('/admin/user_view_settings', methods=['GET', 'POST'])
@login_required
def user_view_settings():
    if current_user.role == 'admin' or current_user.role == 'moderator':
        return render_template('admin/user_view_settings.html', title='Настройки внешнего вида платформы')
    else:
        return redirect(url_for('main.index'))


@bp.route('/moderation', methods=['GET', 'POST'])
@login_required
def moderation():
    if current_user.role == 'admin':
        groups = Group.query.all()
        admins = User.query.filter_by(role='admin').all()

        current_time = {}

        create_moderator_form = CreateModerForm()
        for group in groups:
            current_time[group.name] = datetime.now() + timedelta(hours=int(group.time_zone)) - timedelta(hours=int(Config.SERVER_TIME_ZONE))

        if create_moderator_form.validate_on_submit():
            if create_moderator_form.submit.data and create_moderator_form.validate():
                for group in create_moderator_form.group.data:
                    gr = Group.query.get(group.id)
                    us = User.query.get(create_moderator_form.user.data.id)
                    gr.moderators.append(us)
                    db.session.commit()
                return redirect(request.referrer)

        create_group_form = CreateGroupForm()
        if create_group_form.validate_on_submit():
            if create_group_form.submit.data and create_group_form.validate():
                group = Group()
                group.name = create_group_form.name.data
                db.session.add(group)
                db.session.commit()
                return redirect(request.referrer)

        return render_template('admin/moderation.html', groups=groups, create_group_form=create_group_form,
                               create_moderator_form=create_moderator_form, current_time=current_time)
    else:
        return redirect(url_for('main.index'))


@bp.route('/del_moderator_<group_id>_<user_id>', methods=['GET', 'POST'])
@login_required
def del_moderator(group_id, user_id):
    group = Group.query.get(group_id)
    user = User.query.get(user_id)
    group.moderators.remove(user)
    db.session.commit()
    return redirect(url_for('admin.moderation'))


@bp.route('/del_user_<user_id>', methods=['GET', 'POST'])
@login_required
def del_user(user_id):
    user = User.query.get(user_id)
    messages = user.all_messages()
    groups = Group.query.all()
    tags = user.tags
    # chat_messages = ChatMessages.query.all()
    user_marathon_tasks: UserMarathonTask = UserMarathonTask.query.filter(UserMarathonTask.user_id == user.id).all()
    # lotocards: Lotocard = Lotocard.query.filter(Lotocard.user_id == user.id).all()
    for message in messages:
        # for chat_message in chat_messages:
        #     if message.id == chat_message.message_id:
        #         db.session.delete(chat_message)
        db.session.delete(message)
    for group in groups:
        if user in group.moderators:
            group.moderators.remove(user)
    for tag in tags:
        user.tags.remove(tag)
    for invited in user.his_invited_users:
        user.his_invited_users.remove(invited)
    for umt in user_marathon_tasks:
        db.session.delete(umt)
    # for card in lotocards:
    #     db.session.delete(card)
    db.session.commit()
    db.session.delete(user)
    db.session.commit()
    return redirect(url_for('admin.users_list'))


@bp.route('/set_role_<user_id>', methods=['GET', 'POST'])
@login_required
def set_user_role(user_id):
    user = User.query.get(user_id)
    if user.role == 'admin':
        regions = Group.query.all()
        for region in regions:
            if user in region.moderators:
                region.moderators.remove(user)
        user.role = ''
    else:
        user.role = 'admin'
    db.session.commit()
    return redirect(url_for('admin.users_list'))


@bp.route('/del_group_<group_id>', methods=['GET', 'POST'])
@login_required
def del_group(group_id):
    group = Group.query.get(group_id)
    users = User.query.all()
    for user in users:
        if user.group == group.id:
            user.group = f'{group.name}_удален'
    for moderator in group.moderators:
        group.moderators.remove(moderator)
    db.session.delete(group)
    db.session.commit()
    return redirect(url_for('admin.moderation'))


def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in Config.ALLOWED_EXTENSIONS


def upload_file(file):
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file.save(os.path.join(Config.UPLOAD_FOLDER, filename))
        return redirect(url_for('uploaded_file',
                                filename=filename))


@bp.get('/admin/generate')
def gen_reg():
    x = Xeger()
    # 1 задание
    pattern_1 = re.compile('ph_\w{0,1}\d{5}\w+')

    # 2 задание
    pattern_2 = re.compile('le_\d{3}\w+[A-Z]{3,5}')

    result_1 = []
    for i in range(4000):
        result_1.append(f'{x.xeger(pattern_1)}')
    result_1 = set(result_1)
    with open('1 набор.txt', 'w') as first:
        for i in result_1:
            first.write(f'{i}\n')

    result_2 = []
    for i in range(4000):
        result_2.append(f'{x.xeger(pattern_2)}')
    result_2 = set(result_2)
    with open('2 набор.txt', 'w') as second:
        for i in result_2:
            second.write(f'{i}\n')

    return 'ok'
