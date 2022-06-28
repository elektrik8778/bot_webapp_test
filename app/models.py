from app import db, login, Config
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import jwt
from time import time
from telegram import Update, WebAppInfo, InlineKeyboardButton, ReplyKeyboardMarkup, InlineKeyboardMarkup, \
    ReplyKeyboardRemove, KeyboardButton, InputMediaVideo, InputMediaPhoto, LabeledPrice
from telegram.constants import ParseMode
# from googleapiclient.discovery import build
# from google.oauth2 import service_account
import os
import json


@login.user_loader
def load_user(id):
    return User.query.get(int(id))


group_moderators = db.Table('group_moderators',
                            db.Column('group_id', db.Integer, db.ForeignKey('group.id')),
                            db.Column('user_id', db.Integer, db.ForeignKey('user.id'))
                            )


class UserTag(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'))
    tag_id = db.Column(db.Integer, db.ForeignKey('tag.id', ondelete='CASCADE'))
    receipt_date = db.Column(db.DateTime, default=datetime.now())


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    tg_id = db.Column(db.BIGINT, index=True)
    username = db.Column(db.String(64), index=True)
    is_bot = db.Column(db.Boolean, index=True, default=False)
    first_name = db.Column(db.String(64), index=True)
    last_name = db.Column(db.String(64), index=True)
    language_code = db.Column(db.String(5), index=True, default='ru')
    password_hash = db.Column(db.String(128))
    email = db.Column(db.Text)
    phone = db.Column(db.Text)
    status = db.Column(db.String(30), index=True, default='')
    role = db.Column(db.String(12), index=True, default='user')
    group = db.Column(db.Integer, db.ForeignKey('group.id'))
    registered = db.Column(db.DateTime)
    last_visit = db.Column(db.DateTime)
    unsubscribed = db.Column(db.Boolean, default=False)
    # promo_codes = db.Column(db.JSON)

    def set_unsubscribed(self):
        self.unsubscribed = True
        db.session.commit()

    def set_subscribed(self):
        self.unsubscribed = False
        db.session.commit()

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def get_group(self):
        if self.group:
            return Group.query.filter_by(id=self.group).first()

    def get_tags(self):
        return Tag.query.join(UserTag, Tag.id == UserTag.tag_id).filter(UserTag.user_id == self.id).all()

    def add_tag(self, tag):
        if not UserTag.query.filter(UserTag.tag_id == tag.id, UserTag.user_id == self.id).first():
            ut = UserTag()
            ut.user_id = self.id
            ut.tag_id = tag.id
            db.session.add(ut)
            db.session.commit()
            return Tag.query.get(tag.id).name

    def del_tag(self, tag):
        if ut := UserTag.query.filter(UserTag.tag_id == tag.id, UserTag.user_id == self.id).first():
            db.session.delete(ut)
            db.session.commit()
            return Tag.query.get(tag.id).name

    def get_reset_password_token(self, expires_in=600):
        return jwt.encode(
            {
                'reset_password': self.id,
                'exp': time() + expires_in
            },
            Config.SECRET_KEY,
            algorithm='HS256').decode('utf-8')

    def get_received_scheduled_messages(self):
        return [r.id for r in self.received]


    @staticmethod
    def verify_reset_password_token(token):
        try:
            id = jwt.decode(token, Config.SECRET_KEY, algorithms=['HS256'])['reset_password']
        except:
            return
        return User.query.get(id)

    def set_item(self, item, value):
        if item in self.__dict__:
            setattr(self, item, value)
            db.session.commit()
        else:
            raise Exception('WrongItem')

    def __repr__(self):
        return f'{self.first_name}'



    def write_to_google_sheet(self):
        SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
        SERVICE_ACCOUNT_FILE = os.path.join(Config.STATIC_FOLDER, 'json', 'credentials.json')
        SPREADSHEET_ID = os.environ.get('SPREADSHEET_ID')
        SHEET_RANGE = 'Пользователи'
        credentials = service_account.Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
        service = build('sheets', 'v4', credentials=credentials)
        sheet = service.spreadsheets()

        # result = sheet.values().get(spreadsheetId=SPREADSHEET_ID, range=USERS_RANGE, majorDimension='ROWS').execute()
        # values = result.get('values', [])
        # print(values)

        new_values = {
            'values': [[self.id, self.tg_id, self.first_name, str(self.registered), f'tg://user?id={self.tg_id}']]}

        response = sheet.values().append(
            spreadsheetId=SPREADSHEET_ID,
            range=SHEET_RANGE,
            valueInputOption='USER_ENTERED',
            insertDataOption='INSERT_ROWS',
            body=new_values).execute()


class Group(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(30), index=True)
    time_zone = db.Column(db.Integer, default=9)
    inst = db.Column(db.Text)
    code = db.Column(db.String(10))
    moderators = db.relationship('User',
                                 secondary=group_moderators,
                                 lazy='subquery',
                                 backref=db.backref('moderators', lazy=True))
    users = db.relationship('User', backref='users', lazy=True)

    def __repr__(self):
        return self.name


class Tag(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(30), index=True)
    description = db.Column(db.String(128), index=True)


class ScheduledMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    message_type = db.Column(db.String(20), nullable=False)
    date_time = db.Column(db.DateTime)
    text = db.Column(db.String(4096), nullable=False)
    content_link = db.Column(db.String(256), nullable=False)
    group = db.Column(db.Integer, db.ForeignKey('group.id'))
    sent = db.Column(db.Boolean, default=False)

    def get_tasks_for_sending(self, sent=False, deleted=False):
        if sent and not deleted:
            return TaskForSending.query.filter(TaskForSending.scheduled_message_id == self.id,
                                               TaskForSending.sent.is_(sent)).all()
        if sent and deleted:
            return TaskForSending.query.filter(TaskForSending.scheduled_message_id == self.id,
                                               TaskForSending.sent.is_(sent),
                                               TaskForSending.deleted.is_(sent)).all()
        else:
            return TaskForSending.query.filter(TaskForSending.task_id == self.id).all()


class TaskForSending(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    scheduled_message_id = db.Column(db.Integer, db.ForeignKey('scheduled_message.id', ondelete='CASCADE'))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'))
    plan_sending_time = db.Column(db.DateTime)
    sent = db.Column(db.Boolean, default=False)
    message_id = db.Column(db.Integer, default=None)
    fact_sending_time = db.Column(db.DateTime)
    deleted = db.Column(db.Boolean, default=False)
    deleted_time = db.Column(db.DateTime)
    comment = db.Column(db.Text)

    def get_schedule_message(self):
        return ScheduledMessage.query.get(self.scheduled_message_id)

    def get_scheduled_message_type(self):
        task = ScheduledMessage.query.get(self.scheduled_message_id)
        return task.message_type

    def get_user(self):
        return User.query.get(int(self.user_id))

    def set_deleted(self):
        self.deleted = True
        db.session.commit()


class Account(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.Text)
    # юр наименоование
    # адрес
    # инн


class Place(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.Text)
    description = db.Column(db.Text)
    city = db.Column(db.Text)
    addr = db.Column(db.Text)

    def get_placements(self):
        return Placement.query.filter(Placement.place == self.id).all()


class Placement(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.Text)
    place = db.Column(db.Integer, db.ForeignKey('place.id'))
    placement = db.Column(db.ARRAY(db.JSON))
    excel_filename = db.Column(db.Text)

    def get_place(self) -> Place:
        return Place.query.get(self.place)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name
        }

    def set_seats_busy_free(self, seats, free=False):
        places = None
        path = os.path.join(Config.UPLOAD_FOLDER, 'placements', str(self.id), self.excel_filename.split('.')[0] + '.js')
        with open(path, 'r') as placement:
            places = json.loads(placement.read().split('var schemeData = ')[1])
            for s in seats:
                for p in places:
                    if p['Seat'] == str(s["seat"]) and p['Row'] == str(s["row"]) and p['name_sec'] == str(s["sectorName"]):
                        p['avail'] = free
        with open(path, 'w') as placement:
            placement.write(f'var schemeData = {json.dumps(places)}')


class Event(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.Text)
    description = db.Column(db.Text)
    poster = db.Column(db.JSON, default={'files': []}) # афиша - картинки и видео {'file_id':'sdfgsdg', 'file_type': 'photo/video', 'filename': 'name'}
    organizer = db.Column(db.Integer, db.ForeignKey('account.id'))
    place = db.Column(db.Integer, db.ForeignKey('place.id'))
    placement = db.Column(db.Integer, db.ForeignKey('placement.id'))
    date = db.Column(db.Date)
    time = db.Column(db.Time)

    def add_poster(self, f):
        event_poster = self.poster
        filename = f.filename
        poster_cat = os.path.join(Config.UPLOAD_FOLDER, 'events', str(self.id), 'posters')
        if not os.path.exists(poster_cat):
            os.makedirs(poster_cat)
        f.save(os.path.join(poster_cat, filename))
        print(filename, f.headers['Content-Type'].split('/')[0])
        event_poster['files'].append({
            'file_id': '',
            'file_type': f.headers['Content-Type'].split('/')[0],
            'filename': filename
        })
        self.poster = ''
        db.session.commit()
        self.poster = event_poster
        db.session.commit()

    def del_poster(self, filename):
        event_poster = self.poster
        poster_cat = os.path.join(Config.UPLOAD_FOLDER, 'events', str(self.id), 'posters')
        for index, f in enumerate(event_poster['files']):
            if f['filename'] == filename:
                del event_poster['files'][index]
                os.remove(os.path.join(poster_cat, filename))
        self.poster = ''
        db.session.commit()
        self.poster = event_poster
        db.session.commit()

    async def send_info(self, update, context):
        from app.telegram_bot import buttons as btns
        posters = self.poster['files']
        media_group = []
        poster_cat = os.path.join(Config.UPLOAD_FOLDER, 'events', str(self.id), 'posters')
        btn = [InlineKeyboardButton(text='Купить билеты',
                                    web_app=WebAppInfo(url=f'{Config.SERVER}/event/{self.id}/chairs'),
                                    )]
        if len(posters) > 1:
            for f in posters:
                media = open(os.path.join(poster_cat, f['filename']), 'rb') if not f['file_id'] else f['file_id']
                if f['file_type'] == 'image':
                    media_group.append(InputMediaPhoto(media=media,
                                                       caption=self.description,
                                                       parse_mode=ParseMode.MARKDOWN))
                elif f['file_type'] == 'video':
                    media_group.append(InputMediaVideo(media=media,
                                                       caption=self.description,
                                                       parse_mode=ParseMode.MARKDOWN))

            response = await update.effective_message.reply_media_group(media=media_group,
                                                                  protect_content=True)
            for index, msg in enumerate(response):
                posters[index]['file_id'] = msg.photo[-1].file_id if posters[index]['file_type'] == 'image' else msg.video.file_id
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f'*{self.name}*\n{self.date.strftime("%d.%m.%y")}, {self.time.strftime("%H:%M")}\n\n{self.description}',
                reply_markup=InlineKeyboardMarkup([btn, [btns.hide_btn()]]),
                protect_content=True,
                parse_mode=ParseMode.MARKDOWN)
        elif len(posters) == 1:
            media = open(os.path.join(poster_cat, posters[0]['filename']), 'rb') if not posters[0]['file_id'] else posters[0]['file_id']
            if posters[0]['file_type'] == 'image':
                response = await context.bot.send_photo(
                    chat_id=update.effective_chat.id,
                    photo=media,
                    caption=f'*{self.name}*\n{self.date.strftime("%d.%m.%y")}, {self.time.strftime("%H:%M")}\n\n{self.description}',
                    reply_markup=InlineKeyboardMarkup([btn, [btns.hide_btn()]]),
                    protect_content=True,
                    parse_mode=ParseMode.MARKDOWN)
                posters[0]['file_id'] = response.photo[-1].file_id
            elif posters[0]['file_type'] == 'video':
                response = await context.bot.send_video(
                    chat_id=update.effective_chat.id,
                    video=media,
                    caption=f'*{self.name}*\n{self.date.strftime("%d.%m.%y")}, {self.time.strftime("%H:%M")}\n\n{self.description}',
                    reply_markup=InlineKeyboardMarkup([btn, [btns.hide_btn()]]),
                    protect_content=True,
                    parse_mode=ParseMode.MARKDOWN)
                posters[0]['file_id'] = response.video.file_id
        elif len(posters) == 0:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f'*{self.name}*\n{self.date.strftime("%d.%m.%y")}, {self.time.strftime("%H:%M")}\n\n{self.description}',
                reply_markup=InlineKeyboardMarkup([btn, [btns.hide_btn()]]),
                protect_content=True,
                parse_mode=ParseMode.MARKDOWN)
        self.poster = ''
        db.session.commit()
        self.poster = {'files': posters}
        db.session.commit()
        return 'ok'

    def get_placement(self) -> Placement:
        return Placement.query.get(self.placement)

    def get_place(self) -> Place:
        return Place.query.get(self.place)


class Order(db.Model):
    def __init__(self):
        self.date = datetime.now()
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='SET NULL'))
    event = db.Column(db.Integer, db.ForeignKey('event.id', ondelete='SET NULL'))
    date = db.Column(db.DateTime)
    seats = db.Column(db.ARRAY(db.JSON))
    price = db.Column(db.Integer)
    paid = db.Column(db.Boolean, default=False)
    invoice_msg = db.Column(db.Integer)
    pre_checkout_query_id = db.Column(db.Text)
    provider_payment_charge_id = db.Column(db.Text)
    telegram_payment_charge_id = db.Column(db.Text)
    payment_date = db.Column(db.DateTime)

    def cancel(self):
        self.get_event().get_placement().set_seats_busy_free(seats=self.seats, free=True)
        db.session.delete(self)
        db.session.commit()

    def get_event(self) -> Event:
        return Event.query.get(self.event)

    def get_user(self) -> User:
        return User.query.get(self.user)


class UserBonus(db.Model):
    def __init__(self):
        self.date = datetime.now()
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'))
    amount = db.Column(db.Integer)
    reason = db.Column(db.Text)
    date = db.Column(db.DateTime)

