from app import db, login, Config
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import jwt
from time import time
from telegram import Update, WebAppInfo, InlineKeyboardButton, ReplyKeyboardMarkup, InlineKeyboardMarkup, \
    ReplyKeyboardRemove, KeyboardButton, InputMediaVideo, InputMediaPhoto, LabeledPrice, Message
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
    source = db.Column(db.Text)
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

    def get_quest_process(self):
        return QuestProcess.query.filter(QuestProcess.user == self.id).first()

    def get_components(self):
        return UserComponent.query.filter(UserComponent.user == self.id).all()


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


class QuestProcess(db.Model):
    def __init__(self):
        self.started = datetime.now()
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'))
    started = db.Column(db.DateTime)
    status = db.Column(db.Text)


class Quiz(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    description = db.Column(db.Text)
    way = db.Column(db.Integer)

    def get_questions(self):
        return QuizQuestion.query.filter(QuizQuestion.quiz == self.id).order_by(QuizQuestion.order).all()

    def get_next_question(self, user: User):
        qp: QuestProcess = user.get_quest_process()
        next_question_number = int(qp.status.split('_')[-1])
        questions = self.get_questions()
        next_question: QuizQuestion = questions[next_question_number]
        text = f'*Вопрос {next_question_number+1}*\n\n{next_question.question}'
        btns = []

        for index, qqv in enumerate(next_question.get_variants()):
            text += f'\n{index+1}) {qqv.variant}'
            btns.append([InlineKeyboardButton(text=str(index+1), callback_data=f'answer_{qqv.id}')])
        result = {
            'text': text,
            'reply_markup': InlineKeyboardMarkup(inline_keyboard=btns)
        }
        return result


class QuizQuestion(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    quiz = db.Column(db.Integer, db.ForeignKey('quiz.id', ondelete='SET NULL'))
    question = db.Column(db.Text)
    order = db.Column(db.Integer)

    def get_variants(self):
        return QuizQuestionVariant.query.filter(QuizQuestionVariant.question == self.id).order_by(QuizQuestionVariant.id).all()

    def get_quiz(self) -> Quiz:
        return Quiz.query.get(self.quiz)

class QuizQuestionVariant(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    question = db.Column(db.Integer, db.ForeignKey('quiz_question.id', ondelete='CASCADE'))
    variant = db.Column(db.Text)
    components = db.Column(db.ARRAY(db.Integer))

    def get_question(self) -> QuizQuestion:
        return QuizQuestion.query.get(self.question)


class Component(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.Text)
    description = db.Column(db.Text)


class UserComponent(db.Model):
    def __init__(self):
        self.got = datetime.now()
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'))
    component = db.Column(db.Integer, db.ForeignKey('component.id', ondelete='CASCADE'))
    got = db.Column(db.DateTime)

    def get_component(self) -> Component:
        return Component.query.get(self.component)
