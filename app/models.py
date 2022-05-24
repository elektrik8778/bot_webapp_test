from app import db, login, Config
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import jwt
from time import time
# import requests
from telegram.constants import ParseMode
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto, InputMediaVideo, \
    InputMediaAudio
from googleapiclient.discovery import build
from google.oauth2 import service_account
import os
# import random
# import cv2
# from io import BufferedReader


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

    # def create_lottery_number(self, reason, description=''):
    #     ln = LotteryNumber()
    #     ln.user_id = self.id
    #     ln.reason = reason
    #     ln.description = description
    #     db.session.add(ln)
    #     db.session.commit()
    #     return ln

    # def get_lottery_numbers(self):
    #     return LotteryNumber.query.filter(LotteryNumber.user_id == self.id).all()

    # def get_lottery_cards(self):
    #     # https://lotto.idurn.ru/api/get_cards_list/<game_id>/<owner_id>/<api_token>
    #     resp = requests.get(
    #         f'{Config.LOTTO_URL}/get_cards_list/{self.get_group().lotto_game_id}/{self.tg_id}/{Config.LOTTO_API_TOKEN}')
    #     return sorted(resp.json())

    # def add_lottery_cards(self, count=1):
    #     # '/create_card/<game_id>/<owner_id>/<api_token>'
    #     cards = []
    #     for i in range(count):
    #         cards.append(requests.get(f'{Config.LOTTO_URL}/create_card/{self.get_group().lotto_game_id}/{self.tg_id}/{Config.LOTTO_API_TOKEN}'))
    #     return cards

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

    # def get_quest_tasks(self):
    #     return UserQuestTask.query.filter(UserQuestTask.user == self.id).all()

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


# class ScheduledMessage(db.Model):
#     id = db.Column(db.Integer, primary_key=True, autoincrement=True)
#     message_type = db.Column(db.String(20), nullable=False)
#     date_time = db.Column(db.DateTime)
#     text = db.Column(db.String(4096), nullable=False)
#     content_link = db.Column(db.String(256), nullable=False)
#     group = db.Column(db.Integer, db.ForeignKey('group.id'))
#
#     def get_tasks_for_sending(self, sent=False, deleted=False):
#         if sent and not deleted:
#             return TaskForSending.query.filter(TaskForSending.scheduled_message_id == self.id,
#                                                TaskForSending.sent.is_(sent)).all()
#         if sent and deleted:
#             return TaskForSending.query.filter(TaskForSending.scheduled_message_id == self.id,
#                                                TaskForSending.sent.is_(sent),
#                                                TaskForSending.deleted.is_(sent)).all()
#         else:
#             return TaskForSending.query.filter(TaskForSending.task_id == self.id).all()


# class Quiz(db.Model):
#     id = db.Column(db.Integer, primary_key=True, autoincrement=True)
#     name = db.Column(db.String(128), nullable=False)
#     description = db.Column(db.String(4096))
#     final_text = db.Column(db.String(4096))
#     final_callback = db.Column(db.String(128), default=None)
#     command = db.Column(db.Text)
#
#     def questions(self):
#         return Question.query.filter(Question.quiz_id == self.id).all()


# class Question(db.Model):
#     id = db.Column(db.Integer, primary_key=True, autoincrement=True)
#     quiz_id = db.Column(db.Integer, db.ForeignKey('quiz.id'))
#     question_type = db.Column(db.String(20), nullable=False)
#     question_text = db.Column(db.String(1024), nullable=False)
#     question_variants = db.Column(db.String(1024), nullable=False)
#     question_content = db.Column(db.String(1024))
#     question_content_link = db.Column(db.String(1024))
#     answer_type = db.Column(db.String(1024), nullable=False)
#     right_answer_text = db.Column(db.String(1024))
#     wrong_answer_text = db.Column(db.String(1024))
#     answer_explanation = db.Column(db.String(1024))
#     answer_content = db.Column(db.String(1024))
#     answer_content_link = db.Column(db.String(1024))
#
#     def quiz(self):
#         return Quiz.query.get(self.quiz_id)
#
#     def get_right_answers(self):
#         return [index for index, x in enumerate(self.question_variants.split('\n')) if '(верный)' in x]
#
#     def get_answer_by_index(self, index):
#         return self.question_variants.split('\n')[index].split('(верный)')[0].strip()


# class UserQuestion(db.Model):
#     id = db.Column(db.Integer, primary_key=True, autoincrement=True)
#     user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'))
#     question_id = db.Column(db.Integer, db.ForeignKey('question.id', ondelete='CASCADE'))
#     answer = db.Column(db.Text)
#     right = db.Column(db.Boolean)


# class TaskForSending(db.Model):
#     id = db.Column(db.Integer, primary_key=True, autoincrement=True)
#     scheduled_message_id = db.Column(db.Integer, db.ForeignKey('scheduled_message.id', ondelete='CASCADE'))
#     user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'))
#     plan_sending_time = db.Column(db.DateTime)
#     sent = db.Column(db.Boolean, default=False)
#     message_id = db.Column(db.Integer, default=None)
#     fact_sending_time = db.Column(db.DateTime)
#     deleted = db.Column(db.Boolean, default=False)
#     deleted_time = db.Column(db.DateTime)
#     comment = db.Column(db.Text)
#
#     def get_schedule_message(self):
#         return ScheduledMessage.query.get(self.scheduled_message_id)
#
#     def get_scheduled_message_type(self):
#         task = ScheduledMessage.query.get(self.scheduled_message_id)
#         return task.message_type
#
#     def get_user(self):
#         return User.query.get(int(self.user_id))
#
#     def set_deleted(self):
#         self.deleted = True
#         db.session.commit()


# class Trip(db.Model):
#     id = db.Column(db.Integer, primary_key=True, autoincrement=True)
#     name = db.Column(db.String(128), nullable=False)
#     description = db.Column(db.String(1024))
#     status = db.Column(db.Boolean, default=False)
#     media = db.Column(db.JSON, default={"files": []})
#     price = db.Column(db.Float, default=999)
#     payment_invite = db.Column(db.Text)
#     success_payment_text = db.Column(db.String(1024))
#     final_text = db.Column(db.String(1024))
#
#     def upgrade_media(self):
#         media = self.media
#         for f in media['files']:
#             if not os.path.exists(os.path.join(Config.UPLOAD_FOLDER, 'trips', str(self.id), f['filename'])):
#                 media['files'].remove(f)
#         self.media = ''
#         db.session.commit()
#         self.media = media
#         db.session.commit()
#         return self.media['files']
#
#     def upgrade_points_orders(self):
#         points = self.get_all_points()
#         for i, p in enumerate(points):
#             p.order = i+1
#         db.session.commit()
#
#     def get_all_points(self):
#         return TripPoint.query.filter(TripPoint.trip == self.id).order_by(TripPoint.order).all()
#
#     def get_active_points(self):
#         return TripPoint.query.filter(TripPoint.trip == self.id, TripPoint.status == True).order_by(TripPoint.order).all()
#
#     def send_point(self, user: User, order_number: int):
#         point: TripPoint = self.get_active_points()[order_number]
#
#         def send_media_group_from_files_dict(files_dict: dict, path: str):
#             files = files_dict
#             media_group = []
#             for f in files['files']:
#                 if not (media := f['file_id']):
#                     media = open(os.path.join(path, f['filename']), 'rb')
#                 if 'video' in f['file_type']:
#                     vheight = vwidth = None
#                     vcap = cv2.VideoCapture(os.path.join(path, f['filename']))
#                     vwidth = int(vcap.get(cv2.CAP_PROP_FRAME_WIDTH))
#                     vheight = int(vcap.get(cv2.CAP_PROP_FRAME_HEIGHT))
#                     media_group.append(InputMediaVideo(media=media,
#                                                        caption=f['description'],
#                                                        width=vwidth,
#                                                        height=vheight,
#                                                        parse_mode=ParseMode.MARKDOWN))
#                 elif 'image' in f['file_type']:
#                     media_group.append(InputMediaPhoto(media=media,
#                                                        caption=f['description'],
#                                                        parse_mode=ParseMode.MARKDOWN))
#                 elif 'audio' in f['file_type']:
#                     media_group.append(InputMediaAudio(media=media,
#                                                        caption=f['description'],
#                                                        parse_mode=ParseMode.MARKDOWN))
#                 if isinstance(media, BufferedReader):
#                     media.close()
#
#             # response = update.effective_message.reply_media_group(media=media_group)
#             response = bot.send_media_group(chat_id=user.tg_id,
#                                             protect_content=True,
#                                             media=media_group)
#
#             for i, r in enumerate(response):
#                 if 'video' in files['files'][i]['file_type']:
#                     files['files'][i]['file_id'] = r.video.file_id
#                 elif 'image' in files['files'][i]['file_type']:
#                     files['files'][i]['file_id'] = r.photo[-1].file_id
#                 elif 'audio' in files['files'][i]['file_type']:
#                     files['files'][i]['file_id'] = r.audio.file_id
#
#             return files
#
#         # выслать название места
#         bot.send_message(chat_id=user.tg_id,
#                          text=f'*{point.name}*\n\n{point.description}',
#                          protect_content=True,
#                          parse_mode=ParseMode.MARKDOWN)
#
#         # выслать место встречи фото и/или локация
#         if point.meet_point_pic['files']:
#             files = send_media_group_from_files_dict(files_dict=point.meet_point_pic,
#                                                      path=os.path.join(Config.UPLOAD_FOLDER,
#                                                                        'trips',
#                                                                        str(point.trip),
#                                                                        str(point.id),
#                                                                        'meet_point'))
#             point.meet_point_pic = ''
#             db.session.commit()
#             point.meet_point_pic = files
#             db.session.commit()
#
#         bot.send_location(chat_id=user.tg_id,
#                           latitude=float(point.location.split(',')[0].strip()),
#                           longitude=float(point.location.split(',')[-1].strip()),
#                           protect_content=True)
#
#         # выслать голосовое
#         if point.voice['files']:
#             files = send_media_group_from_files_dict(files_dict=point.voice,
#                                                      path=os.path.join(Config.UPLOAD_FOLDER,
#                                                                        'trips',
#                                                                        str(point.trip),
#                                                                        str(point.id), 'voice'))
#             point.voice = ''
#             db.session.commit()
#             point.voice = files
#             db.session.commit()
#
#         # выслать фоточки
#         if point.media['files']:
#             files = send_media_group_from_files_dict(files_dict=point.media,
#                                                      path=os.path.join(Config.UPLOAD_FOLDER,
#                                                                        'trips',
#                                                                        str(point.trip),
#                                                                        str(point.id)))
#             point.media = ''
#             db.session.commit()
#             point.media = files
#             db.session.commit()
#
#         # выслать кнопку "Пошли гулять" или текст окончания экскурсии
#         user_trip: UserTrip = UserTrip.query.filter(UserTrip.user == user.id,
#                                                     UserTrip.trip == self.id).first()
#         go_btn = [InlineKeyboardButton(text='Пошли гулять',
#                                        callback_data=f'letswalk_{user_trip.id}')]
#         if len(self.get_active_points())-1 > order_number:
#             bot.send_message(chat_id=user.tg_id,
#                              text='Когда готовы будете идти в следующее место - нажмите кнопку "Пошли гулять"',
#                              reply_markup=InlineKeyboardMarkup([go_btn]),
#                              protect_content=True,
#                              parse_mode=ParseMode.MARKDOWN)
#         else:
#             bot.send_message(chat_id=user.tg_id,
#                              text=self.final_text,
#                              protect_content=True,
#                              parse_mode=ParseMode.MARKDOWN)
#
#         return 'ok'
#
#
# class TripPoint(db.Model):
#     id = db.Column(db.Integer, primary_key=True, autoincrement=True)
#     trip = db.Column(db.Integer, db.ForeignKey('trip.id'))
#     order = db.Column(db.Integer)
#     name = db.Column(db.String(128), nullable=False)
#     status = db.Column(db.Boolean, default=False)
#     description = db.Column(db.String(1024))
#     meet_point_pic = db.Column(db.JSON, default={"files": []})
#     location = db.Column(db.String)
#     media = db.Column(db.JSON, default={"files": []})
#     voice = db.Column(db.JSON, default={"files": []})
#
#     def get_trip(self) -> Trip:
#         return Trip.query.get(self.trip)
#
#     def upgrade_media(self):
#         # media
#         media = self.media
#         for f in media['files']:
#             if not os.path.exists(os.path.join(Config.UPLOAD_FOLDER, 'trips', str(self.trip), str(self.id), f['filename'])):
#                 media['files'].remove(f)
#         self.media = ''
#         db.session.commit()
#         self.media = media
#         db.session.commit()
#
#         # meet_point
#         meet_point_pic = self.meet_point_pic
#         for f in meet_point_pic['files']:
#             if not os.path.exists(os.path.join(Config.UPLOAD_FOLDER, 'trips', str(self.trip), str(self.id), 'meet_point', f['filename'])):
#                 meet_point_pic['files'].remove(f)
#         self.meet_point_pic = ''
#         db.session.commit()
#         self.meet_point_pic = meet_point_pic
#         db.session.commit()
#
#         # voice
#         voice = self.voice
#         for f in voice['files']:
#             if not os.path.exists(
#                     os.path.join(Config.UPLOAD_FOLDER, 'trips', str(self.trip), str(self.id), 'voice', f['filename'])):
#                 voice['files'].remove(f)
#         self.voice = ''
#         db.session.commit()
#         self.voice = voice
#         db.session.commit()
#
#         return {'media': self.media['files'], 'meet_point': self.meet_point_pic['files'], 'voice': self.voice['files']}
#
#
# class UserTrip(db.Model):
#     id = db.Column(db.Integer, primary_key=True, autoincrement=True)
#     user = db.Column(db.Integer, db.ForeignKey('user.id'))
#     trip = db.Column(db.Integer, db.ForeignKey('trip.id'))
#     paid = db.Column(db.Boolean, default=False)
#     payment_date = db.Column(db.DateTime)
#     payment_code = db.Column(db.String(10), unique=True)
#     price = db.Column(db.Float)
#     current_point = db.Column(db.Integer, default=-1)
#     provider_payment_charge_id = db.Column(db.Text)
#     telegram_payment_charge_id = db.Column(db.Text)
#     pre_checkout_query_id = db.Column(db.Text)
#
#
#     def set_payment_code(self):
#         seq = 'abcdefghijkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789'
#         payment_code = ''
#         for i in range(6):
#             payment_code += random.choice(seq)
#
#         self.payment_code = payment_code
#         db.session.commit()
#
#     def get_user(self) -> User:
#         return User.query.get(self.user)
#
#     def get_trip(self) -> Trip:
#         return Trip.query.get(self.trip)
