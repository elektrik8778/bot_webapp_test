from app import db, login, Config
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import jwt
from time import time
# import requests
# from telegram.constants import ParseMode
# from telegram import InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto, InputMediaVideo, \
#     InputMediaAudio
from googleapiclient.discovery import build
from google.oauth2 import service_account
import os



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
    registered = db.Column(db.DateTime, index=True, nullable=True, default=datetime.now())
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
    lotto_game_id = db.Column(db.Integer)
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


class Account(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    # юр наименоование
    # адрес
    # инн
    #


class Event(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    # название,
    # описание,
    # афиша - картинки и видео {'file_id':'sdfgsdg', 'file_type': 'photo/video', 'filename': 'name'}
    # Организатор - внешний ключ Account
    # площадка - внешний ключ Place
    # размещение -  внешний ключ Placement

# Place
# название
# город
# адрес

# Placement
# площадка - внешний ключ на Place
# placement - файл js с местами
