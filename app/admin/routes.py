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
from app.admin import bp
from app.models import User, Group, Tag, UserTag
from app.admin.forms import ChangeWebhookForm, ScheduledMessageCreateForm, SendTGMessageForm, SendGroupTGMessageForm,\
    CreateGroupForm, CreateModerForm, CreateQuestionForm, EditQuizForm, PrizeForm
from config import Config
from flask_login import login_required, current_user
from flask import render_template, redirect, url_for, request, send_from_directory, flash, make_response
from werkzeug.utils import secure_filename
# from telegram import TelegramError, ParseMode
from telegram.error import BadRequest
# from app.telegram_bot.handlers import greet_user, create_button_map, get_inline_menu
from app.telegram_bot.helpers import with_app_context
from sqlalchemy import over, func, cast, distinct, Text, desc
from flask_sqlalchemy import BaseQuery, model
from xeger import Xeger
import re


@bp.route('/admin')
@login_required
def admin():
    if current_user.role == 'admin' or current_user.role == 'moderator':
        send_group_tg_mes_form = SendGroupTGMessageForm()
        return render_template('admin/admin.html',
                               send_group_tg_mes_form=send_group_tg_mes_form,
                               title='Админка')
    else:
        return redirect(url_for('main.index'))


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
        return redirect(url_for('main.index'))


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


@bp.get('/admin/tickets')
@bp.post('/admin/tickets')
@login_required
def tickets():
    tickets: BaseQuery = db.session.query(Ticket.id, Ticket.code, Ticket.success_description,
                                          Ticket.decline_description, Ticket.regular,
                                          func.count(TicketUser.id).label('users')) \
        .join(TicketUser, TicketUser.ticket_id == Ticket.id, full=True).distinct() \
        .group_by(Ticket.id)\
        .order_by(Ticket.id)

    def to_dict(row):
        return {
            'id': row.id,
            'code': row.code,
            'success_description': row.success_description,
            'decline_description': row.decline_description,
            'users': row.users,
            'regular': row.regular
        }

    return render_template('/admin/tickets.html', tickets=[to_dict(ticket) for ticket in tickets])


@bp.post('/admin/edit_ticket')
def edit_ticket():
    data = json.loads(request.get_data())
    print(data)
    ticket = Ticket.query.get(int(data['id']))
    ticket.code = data['code']
    ticket.regular = data['regular']
    ticket.success_description = data['success_description']
    ticket.decline_description = data['decline_description']
    db.session.commit()
    return 'ok'


@bp.get('/admin/del_ticket/<tid>')
def del_ticket(tid):
    ticket = Ticket.query.get(int(tid))
    db.session.delete(ticket)
    db.session.commit()
    return redirect(request.referrer)


@bp.get('/admin/get_tickets_data')
@bp.post('/admin/get_tickets_data')
@login_required
def get_tickets_data():
    query: BaseQuery = db.session.query(Ticket.code, Ticket.success_description, Ticket.decline_description,
                                        Ticket.regular, func.count(TicketUser.id).label('users'))\
        .join(TicketUser, TicketUser.ticket_id == Ticket.id, full=True).distinct()\
        .group_by(Ticket.id)

    # print(query)
    # print(query.all()[0].keys())

    # search filter
    search = request.args.get('search[value]')
    if search:
        query = query.filter(db.or_(
            Ticket.code.like(f'%{search}%'),
            Ticket.success_description.like(f'%{search}%'),
            Ticket.decline_description.like(f'%{search}%')
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

        if col_name not in ['id', 'code', 'success_description', 'decline_description']:
            col_name = 'id'
        descending = request.args.get(f'order[{i}][dir]') == 'desc'
        col = getattr(Ticket, col_name)

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
            'code': row.code,
            'success_description': row.success_description,
            'decline_description': row.decline_description,
            'users': row.users,
            'regular': row.regular
        }

    # response
    return {
        'data': [to_dict(user, index) for index, user in enumerate(query)],
        'recordsFiltered': total_filtered,
        'recordsTotal': len(Ticket.query.all()),
        'draw': request.args.get('draw', type=int),
    }


@bp.post('/admin/add_ticket')
def add_ticket():
    data = json.loads(request.get_data())
    print(data)
    ticket = Ticket()
    ticket.code = data['code']
    ticket.success_description = data['success_description']
    ticket.decline_description = data['decline_description']
    ticket.regular = bool(data['regular'])
    db.session.add(ticket)
    db.session.commit()
    return 'ok'


@bp.get('/admin/lottery_numbers')
def lottery_numbers():
    numbers: LotteryNumber = LotteryNumber.query.order_by(LotteryNumber.res_date).all()
    return render_template('/admin/lottery_numbers.html', numbers=numbers)


# @bp.route('/admin/get_file_id_form', methods=['GET'])
# def get_file_id_form():
#     return render_template('admin/get_file_id.html')


# @bp.route('/admin/get_file_id', methods=['POST'])
# def get_file_id():
#     print(request.files)
#     return redirect(request.referrer)


# @bp.route('/admin/votings', methods=['GET', 'POST'])
# def votings():
#     votings: Voting = Voting.query.order_by(Voting.id).all()
#     form = VotingForm()
#     vi_form = VotingItemForm()
#     vid = None
#     v_edit = False
#
#     if 'vid' in request.args:
#         vid = request.args['vid']
#         v_edit = True
#
#     if form.validate_on_submit() and form.save.data:
#         v = Voting()
#         if v_edit:
#             v = Voting.query.get(vid)
#         v.name = form.name.data
#         v.description = form.description.data
#         v.active = form.active.data
#
#         if not v_edit:
#             db.session.add(v)
#         db.session.commit()
#         return redirect('/admin/votings')
#
#     if vi_form.validate_on_submit() and vi_form.add.data:
#         vi = VotingItem()
#
#         vi.name = vi_form.name.data
#         vi.description = vi_form.description.data
#         vi.voting = int(request.form['vid'])
#         db.session.add(vi)
#         db.session.commit()
#
#         if f := vi_form.pic.data:
#             fldr = os.path.join('app', 'static', 'images', 'votings', str(vi.voting), str(vi.id))
#             if not os.path.exists(fldr):
#                 os.makedirs(fldr)
#             f.save(os.path.join(fldr, f.filename))
#
#         vi.pic = f.filename
#         db.session.commit()
#         return redirect('/admin/votings')
#
#     if vid:
#         v: Voting = Voting.query.get(vid)
#         form.name.data = v.name
#         form.description.data = v.description
#         form.active.data = v.active
#
#     return render_template('admin/votings.html',
#                            votings=votings,
#                            vi_form=vi_form,
#                            vi=request.args['createvi'] if 'createvi' in request.args else None,
#                            form=form,
#                            vid=vid,
#                            title='Голосования')


# @bp.route('/admin/del_voting/<vid>', methods=['GET', 'POST'])
# def del_voting(vid):
#     v = Voting.query.get(int(vid))
#     db.session.delete(v)
#     db.session.commit()
#     return redirect(request.referrer)


# @bp.route('/admin/del_vi/<viid>', methods=['GET', 'POST'])
# def del_vi(viid):
#     vi = VotingItem.query.get(int(viid))
#     db.session.delete(vi)
#     db.session.commit()
#     return redirect(request.referrer)


# def send_messages_in_background(users, text=None, photo=None, video=None, caption='', poll=None, task=None, reply_markup='', parse_mode='Markdown'):
#     # Разбиваем всех пользователей на группы по x чел
#     x = 3
#     groups = []
#     receivers_count = len(users)
#     for i in range(math.ceil(receivers_count / x)):
#         groups.append([])
#         for j in range(x):
#             try:
#                 groups[i].append(users.pop())
#             except IndexError:
#                 break
#             except KeyError:
#                 break
#
#     # отправляем сообщение каждой группе, затем спим 1 секунду
#     if text:
#         for index, group in enumerate(groups):
#             for user in group:
#                 response = bot.send_message(chat_id=user.tg_id,
#                                             text=text,
#                                             parse_mode='Markdown')
#                 save_message(tg_message=response, direction='income', user_tg_id=user.tg_id, seen=True)
#                 if task:
#                     cur_user = User.query.get(user.id)
#                     task.receivers.append(cur_user)
#                     db.session.commit()
#             time.sleep(1)
#     if photo:
#         for index, group in enumerate(groups):
#             for user in group:
#                 response = bot.send_photo(chat_id=user.tg_id,
#                                           photo=photo,
#                                           caption=caption,
#                                           parse_mode='Markdown')
#                 save_message(tg_message=response, direction='income', user_tg_id=user.tg_id, seen=True)
#                 if task:
#                     cur_user = User.query.get(user.id)
#                     task.receivers.append(cur_user)
#                     db.session.commit()
#             time.sleep(1)
#     if video:
#         for index, group in enumerate(groups):
#             for user in group:
#                 response = bot.send_video(chat_id=user.tg_id,
#                                           video=video,
#                                           caption=caption,
#                                           parse_mode='Markdown')
#                 save_message(tg_message=response, direction='income', user_tg_id=user.tg_id, seen=True)
#                 if task:
#                     cur_user = User.query.get(user.id)
#                     task.receivers.append(cur_user)
#                     db.session.commit()
#             time.sleep(1)
#     if poll:
#         for index, group in enumerate(groups):
#             quiz = Quiz.query.get(int(poll))
#             buttons = [
#                 {
#                     'text': 'Начинаем',
#                     'data': f'startQuiz_{poll}'
#                 }
#             ]
#             map = create_button_map(buttons, 1)
#             reply_markup = get_inline_menu(map)
#             for index, group in enumerate(groups):
#                 for user in group:
#                     response = bot.send_message(chat_id=user.tg_id,
#                                                 text=quiz.description,
#                                                 parse_mode='Markdown',
#                                                 reply_markup=reply_markup)
#                     save_message(tg_message=response, direction='income', user_tg_id=user.tg_id, seen=True)
#                     if task:
#                         cur_user = User.query.get(user.id)
#                         task.receivers.append(cur_user)
#                         db.session.commit()
#                 time.sleep(1)


# @bp.route('/admin/add_tag/<user_id>/<tag_id>', methods=['GET','POST'])
# def add_user_tag(user_id, tag_id):
#     User.query.get(user_id).add_tag(Tag.query.get(tag_id))
#     return redirect(request.referrer)


# @bp.route('/del_tag_<user_id>_<tag_id>', methods=['GET','POST'])
# def del_user_tag(user_id, tag_id):
#     user = User.query.get(user_id)
#     tag = Tag.query.get(tag_id)
#     user.tags.remove(tag)
#     db.session.commit()
#     return redirect(url_for('admin.users_list'))


@bp.route('/test_send_task_<id>')
def test_send_task(id):
    task = ScheduledMessage.query.get(id)
    text = task.text
    if task.message_type == 'photo':
        bot.send_photo(chat_id=current_user.tg_id,
                                  photo=task.content_link,
                                  caption=text,
                                  parse_mode=ParseMode.MARKDOWN)
    elif task.message_type == 'text':
        bot.send_message(chat_id=current_user.tg_id,
                         text=text,
                         parse_mode=ParseMode.MARKDOWN,
                         disable_web_page_preview=False)
    elif task.message_type == 'video':
        bot.send_video(chat_id=current_user.tg_id,
                       video=task.content_link,
                       caption=text,
                       parse_mode=ParseMode.MARKDOWN)
    elif task.message_type == 'poll':
        send_quiz_start(quiz_id=int(text), users=[current_user])
    return redirect(url_for('admin.message_schedule'))


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


@bp.route('/quiz_list', methods=['GET', 'POST'])
@login_required
def quiz_list():
    quizes = Quiz.query.all()
    create_question_form = CreateQuestionForm()
    if create_question_form.validate_on_submit():
        print('Создаем вопрос')
    return render_template('admin/quiz_list.html', quizes=quizes, create_question_form=create_question_form)


@bp.route('/create_quiz_<quiz_id>', methods=['GET', 'POST'])
@login_required
def create_quiz(quiz_id):
    if quiz_id == 'new':
        quiz = Quiz()
        quiz.name = f'Новая_{len(Quiz.query.all())+1}'
        db.session.add(quiz)
        db.session.commit()
        return redirect(url_for('admin.create_quiz', quiz_id=quiz.id))
    else:
        quiz = Quiz.query.get(quiz_id)
        create_question_form = CreateQuestionForm()
        edit_quiz_form = EditQuizForm()

        if edit_quiz_form.validate_on_submit() and edit_quiz_form.save_quiz.data:

            quiz.name = edit_quiz_form.quiz_name.data

            if not edit_quiz_form.quiz_description.data:
                quiz.description = None
            else:
                quiz.description = edit_quiz_form.quiz_description.data

            if edit_quiz_form.quiz_final_text.data == '':
                quiz.final_text = None
            else:
                quiz.final_text = edit_quiz_form.quiz_final_text.data

            if edit_quiz_form.command == '':
                quiz.command = None
            else:
                quiz.command = edit_quiz_form.command.data

            if pic:=edit_quiz_form.pic.data:
                folder = os.path.join(Config.UPLOAD_FOLDER, 'quiz', str(quiz.id))
                if quiz.pic:
                    try:
                        os.remove(os.path.join(folder, 'quiz_pic.jpg'))
                    except Exception as e:
                        print(e)
                pic.save(os.path.join(folder, 'quiz_pic.jpg'))
                with open(os.path.join(folder, 'quiz_pic.jpg'), 'rb') as photo:
                    response = bot.send_photo(chat_id=current_user.tg_id, photo=photo)
                    quiz.pic = response.photo[-1].file_id
                    bot.delete_message(chat_id=current_user.tg_id, message_id=response.message_id)

            db.session.commit()
            return redirect(url_for('admin.create_quiz', quiz_id=quiz.id))

        if create_question_form.validate_on_submit() and create_question_form.save_question.data:
            save_question(request, create_question_form, quiz)
            return redirect(url_for('admin.create_quiz', quiz_id=quiz.id, edit_quiz_form=edit_quiz_form))

        if quiz.description:
            edit_quiz_form.quiz_description.data = quiz.description
        if quiz.final_text:
            edit_quiz_form.quiz_final_text.data = quiz.final_text
        if quiz.command:
            edit_quiz_form.command.data = quiz.command

        return render_template('admin/create_quiz.html',
                               quiz=quiz,
                               create_question_form=create_question_form,
                               edit_quiz_form=edit_quiz_form)


def save_question(request, create_question_form, quiz, question=None):
    quiz_files_catalog = f'app/static/uploads/quiz/{quiz.id}'
    variants = ''
    form = request.form
    for i in form:
        if re.match('variant-\d+', i):
            right = ''
            if f'right-{i.split("-")[-1]}' in form:
                right = '(верный)'
            if right:
                variants += f'{form[i]} {right}\n'
            else:
                variants += f'{form[i]}\n'

    if not question:
        question = Question()
    question.quiz_id = quiz.id
    question.question_type = create_question_form.question_type.data
    question.question_text = create_question_form.question_text.data
    question.send_variants = True if 'send-vars' in form else False
    question.question_variants = variants.strip()

    if question.question_type != 'text':
        # проверили, что есть каталог или создали
        if not os.path.exists(quiz_files_catalog):
            os.makedirs(quiz_files_catalog)
        files = create_question_form.question_content.data

        # если в форме есть файлы для вопроса
        if files[0].filename != '':
            # удалить старые файлы физически
            if question.question_content_link:
                for old_file in question.question_content_link.split(','):
                    os.remove(old_file)
            # удалить ссылки на старые файлы из базы
            question.question_content_link = ''
            question.question_content = ''

            # добавить новые файлы
            for f in files:
                filename = f.filename
                f.save(os.path.join(quiz_files_catalog, filename))
                if not question.question_content_link:
                    question.question_content_link = f'{os.path.join(quiz_files_catalog, filename)}'
                else:
                    question.question_content_link += f',{os.path.join(quiz_files_catalog, filename)}'

            if question.question_type == 'photo':
                for link in question.question_content_link.split(','):
                    with open(link, 'rb') as photo:
                        response = bot.send_photo(chat_id=current_user.tg_id,
                                                  photo=photo,
                                                  caption=f'Викторина {quiz.id}, вопрос {question.question_text}')
                        if not question.question_content:
                            question.question_content = f'{response.photo[-1].file_id}'
                        else:
                            question.question_content += f',{response.photo[-1].file_id}'
                        bot.delete_message(chat_id=current_user.tg_id,
                                           message_id=response.message_id)
            elif question.question_type == 'video':
                with open(question.question_content_link, 'rb') as video:
                    response = bot.send_video(chat_id=current_user.tg_id,
                                              video=video,
                                              caption=f'Викторина {quiz.id}, вопрос {question.question_text}')
                    question.question_content = response.video.file_id
                    bot.delete_message(chat_id=current_user.tg_id,
                                       message_id=response.message_id)
            elif question.question_type == 'audio':
                with open(question.question_content_link, 'rb') as audio:
                    response = bot.send_audio(chat_id=current_user.tg_id,
                                              audio=audio,
                                              caption=f'Викторина {quiz.id}, вопрос {question.question_text}')
                    question.question_content = response.audio.file_id
                    bot.delete_message(chat_id=current_user.tg_id,
                                       message_id=response.message_id)
    else:
        question.question_content_link = ''
        question.question_content = ''

    question.answer_type = create_question_form.answer_type.data
    question.right_answer_text = create_question_form.right_answer_text.data
    question.wrong_answer_text = create_question_form.wrong_answer_text.data
    question.answer_explanation = create_question_form.answer_explanation.data

    if question.answer_type != 'text':
        if not os.path.exists(quiz_files_catalog):
            os.makedirs(quiz_files_catalog)
        f = create_question_form.answer_content.data
        if f.filename:
            # удалить старые фото
            if question.answer_content_link:
                os.remove(question.answer_content_link)
            # сохранить новые
            filename = f.filename
            f.save(os.path.join(quiz_files_catalog, filename))
            question.answer_content_link = os.path.join(quiz_files_catalog, filename)
            if question.answer_type == 'photo':
                with open(question.answer_content_link, 'rb') as photo:
                    response = bot.send_photo(chat_id=current_user.tg_id,
                                              photo=photo)
                    question.answer_content = response.photo[-1].file_id
                    bot.delete_message(chat_id=current_user.tg_id,
                                       message_id=response.message_id)
            elif question.answer_type == 'video':
                with open(question.answer_content_link, 'rb') as video:
                    response = bot.send_video(chat_id=current_user.tg_id,
                                              video=video)
                    question.answer_content = response.video.file_id
                    bot.delete_message(chat_id=current_user.tg_id,
                                       message_id=response.message_id)
            elif question.answer_type == 'audio':
                with open(question.answer_content_link, 'rb') as audio:
                    response = bot.send_audio(chat_id=current_user.tg_id,
                                              audio=audio)
                    question.answer_content = response.audio.file_id
                    bot.delete_message(chat_id=current_user.tg_id,
                                       message_id=response.message_id)
    else:
        question.answer_content = ''
        question.answer_content_link = ''
    db.session.add(question)
    db.session.commit()


@bp.get('/admin/question/<qid>')
def question_datailed(qid):
    q: Question = Question.query.get(int(qid))

    variants = {}
    variants_list = q.question_variants.split('\n')
    for index, var in enumerate(variants_list):
        variants[index] = {
            'text': var.split('(верный)')[0].strip(),
            'right': True if '(верный)' in var else False
        }

    q_form = CreateQuestionForm()
    q_form.question_type.data = q.question_type
    q_form.question_text.data = q.question_text
    q_form.answer_type.data = q.answer_type
    q_form.right_answer_text.data = q.right_answer_text
    q_form.wrong_answer_text.data = q.wrong_answer_text
    q_form.answer_explanation.data = q.answer_explanation

    return render_template('/admin/question_detailed.html',
                           q=q,
                           form=q_form,
                           variants=json.dumps(variants, ensure_ascii=False))


@bp.post('/admin/question/<qid>')
def question_datailed_post(qid):
    q: Question = Question.query.get(int(qid))
    q_form = CreateQuestionForm()
    if q_form.validate_on_submit():
        save_question(request, q_form, q.quiz(), q)
        return redirect(request.referrer)


@bp.route('/send_quiz_<quiz_id>_<user_id>', methods=['GET', 'POST'])
@login_required
def send_quiz(quiz_id, user_id):
    user = User.query.get(user_id)
    send_quiz_start(quiz_id, [user])
    return redirect(url_for('admin.create_quiz', quiz_id=quiz_id))


@bp.route('/del_question_<quiz_id>_<question_id>', methods=['GET', 'POST'])
@login_required
def del_question(quiz_id, question_id):
    question = Question.query.get(question_id)
    if question.question_content_link and os.path.exists(question.question_content_link):
        os.remove(question.question_content_link)
    if question.answer_content_link and os.path.exists(question.answer_content_link):
        os.remove(question.answer_content_link)
    db.session.delete(question)
    db.session.commit()
    return redirect(url_for('admin.create_quiz', quiz_id=quiz_id))


@bp.route('/del_quiz_<quiz_id>', methods=['GET', 'POST'])
@login_required
def del_quiz(quiz_id):
    quiz = Quiz.query.get(quiz_id)
    for question in quiz.questions():
        if question.question_content_link and os.path.exists(question.question_content_link):
            os.remove(question.question_content_link)
        if question.answer_content_link and os.path.exists(question.answer_content_link):
            os.remove(question.answer_content_link)
        db.session.delete(question)
    db.session.commit()
    db.session.delete(quiz)
    db.session.commit()
    return redirect(url_for('admin.quiz_list'))


@bp.get('/admin/random_lottery_number')
def random_lottery_number():
    prizes = Prizes.query.all()
    numbers = LotteryNumber.query.filter(LotteryNumber.was_drawn.is_(True)).all()
    return render_template('/admin/random_number.html',
                           prizes=prizes,
                           numbers=numbers)


@bp.get('/admin/prizes')
def prizes():
    form = PrizeForm()
    prizes = Prizes.query.all()
    return render_template('/admin/prizes.html',
                           form=form,
                           prizes=prizes)


@bp.post('/admin/prizes')
def prizes_post():
    form = PrizeForm()

    if form.validate_on_submit():
        p = Prizes()
        prizes_pic_dir = os.path.join('app', 'static', 'uploads', 'prizes')
        p.name = form.name.data
        p.description = form.description.data
        if f := form.pic.data:
            if not os.path.exists(prizes_pic_dir):
                os.makedirs(prizes_pic_dir)
            f.save(os.path.join(prizes_pic_dir, f.filename))
            p.pic = f.filename
        db.session.add(p)
        db.session.commit()

    return redirect(request.referrer)


@bp.get('/admin/del_prize/<pid>')
def del_prize(pid):
    p = Prizes.query.get(int(pid))
    if os.path.exists(f := os.path.join('app', 'static', 'uploads', 'prizes', p.pic)):
        os.remove(f)
    db.session.delete(p)
    db.session.commit()
    return redirect(request.referrer)


@bp.post('/admin/distribute_prizes')
def distribute_prizes():
    data = json.loads(request.get_data())
    pid = int(data['pid'])
    count = int(data['count'])
    p = Prizes.query.get(pid)
    lottery_numbers = LotteryNumber.query.filter(LotteryNumber.was_drawn.is_(False)).all()

    def randomize_numbers(numbers, count):
        nset = set(numbers)
        if len(nset) == count:
            return nset
        return randomize_numbers(list(nset)+random.choices(population=lottery_numbers, k=count-len(nset)), count)

    if not (len(lottery_numbers) < count):
        numbers = randomize_numbers(random.choices(population=lottery_numbers, k=count), count)
        for n in numbers:
            n.was_drawn = True
            n.prize = pid
            db.session.commit()
            try:
                response = bot.send_message(chat_id=n.get_user().tg_id,
                                            text=f'Вы выиграли приз *"{p.name}"* по тикету *#{n.id}*',
                                            parse_mode=ParseMode.MARKDOWN)
                n.message_id = response.message_id
                db.session.commit()
            except Exception as e:
                print(e)
        return json.dumps([{
            'n': x.id,
            'user': x.get_user().first_name,
            'prize': x.get_prize().name
        } for x in numbers], ensure_ascii=False)
    else:
        print('Номерков недостаточно для розыгрыша такого количества призов')
        return 'None'


@bp.get('/admin/prizes_accounting')
def prizes_accounting():
    numbers = LotteryNumber.query.filter(LotteryNumber.was_drawn.is_(True)).all()
    return render_template('/admin/prizes_accounting.html',
                           numbers=numbers)


@bp.get('/admin/give_prize/<nid>')
def give_prize(nid):
    n: LotteryNumber = LotteryNumber.query.get(int(nid))
    n.got_flag = True
    db.session.commit()
    bot.send_message(chat_id=n.get_user().tg_id,
                     text='Приз выдан',
                     reply_to_message_id=n.message_id,
                     parse_mode=ParseMode.MARKDOWN)
    return redirect(request.referrer)


@bp.route('/uploads/<path:filename>', methods=['GET', 'POST'])
@login_required
def uploads(filename):
    users = User.query.all()
    if filename == '*':
        files = os.listdir(Config.UPLOAD_FOLDER)
        filename = ''
    else:
        if os.path.isfile(os.path.join(Config.UPLOAD_FOLDER, filename)):
            current_file = os.path.join(Config.UPLOAD_FOLDER, filename)
            for user in users:
                for message in user.all_messages():
                    if message.local_link == current_file:
                        return send_from_directory(directory=Config.UPLOAD_FOLDER,
                                                   filename=filename,
                                                   as_attachment=True,
                                                   attachment_filename=f'{user}_{os.path.basename(current_file)}')
            return send_from_directory(directory=Config.UPLOAD_FOLDER,
                                       filename=filename,
                                       as_attachment=True)
        else:
            files = os.listdir(os.path.join(Config.UPLOAD_FOLDER, filename))
    return render_template('admin/my_files.html',
                           files=files,
                           filename=filename)


def create_archive(dir):
    users = User.query.all()
    os.chdir(os.path.join(Config.UPLOAD_FOLDER, dir))
    z = zipfile.ZipFile(f'{dir.split("/")[-1]}.zip', 'w', zipfile.ZIP_DEFLATED)

    for root, dirs, files in os.walk(os.path.join(Config.UPLOAD_FOLDER, dir)):
        for file in files:
            owner = ''
            if file.split('.')[-1] != 'zip':
                z.write(file)

    z.close()
    return z.filename.split('/')[-1]


@bp.route('/download/<path:filename>', methods=['GET', 'POST'])
@login_required
def download_folder(filename):
    zip_file_name = create_archive(filename)
    return send_from_directory(directory=Config.UPLOAD_FOLDER,
                               filename=os.path.join(filename, zip_file_name),
                               as_attachment=True)


def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in Config.ALLOWED_EXTENSIONS


def upload_file(file):
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file.save(os.path.join(Config.UPLOAD_FOLDER, filename))
        return redirect(url_for('uploaded_file',
                                filename=filename))


def send_quiz_start(quiz_id, users):
    quiz = Quiz.query.get(quiz_id)
    buttons = [
        {
            'text': 'Начинаем',
            'data': f'startQuiz_{quiz_id}'
        }
    ]
    map = create_button_map(buttons, 1)
    reply_markup = get_inline_menu(map)
    for user in users:
        if quiz.pic:
            bot.send_photo(chat_id=user.tg_id,
                           caption=quiz.description,
                           photo=quiz.pic,
                           reply_markup=reply_markup,
                           parse_mode=ParseMode.MARKDOWN)
        else:
            bot.send_message(chat_id=user.tg_id,
                             text=quiz.description,
                             reply_markup=reply_markup,
                             parse_mode=ParseMode.MARKDOWN)
        user.status = f'playQuiz_{quiz.id}_0'
        db.session.commit()
        return 'ok'


def send_quest_start(quest_id, users):
    quest = Quest.query.get(quest_id)
    buttons = [
        {
            'text': 'Начинаем',
            'data': f'startQuest_{quest_id}'
        }
    ]
    map = create_button_map(buttons, 1)
    reply_markup = get_inline_menu(map)
    for user in users:
        bot.send_message(chat_id=user.tg_id,
                         text=quiz.description,
                         reply_markup=reply_markup,
                         parse_mode='Markdown')
        user.status = f'quest_{quiz.id}_1'
        db.session.commit()
        return 'ok'


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
