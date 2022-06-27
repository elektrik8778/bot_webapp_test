from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, DateTimeField, IntegerField, TextAreaField, FileField, SelectField, \
    SelectMultipleField, MultipleFileField, BooleanField
# from wtforms.ext.sqlalchemy.fields import QuerySelectMultipleField, QuerySelectField
from wtforms.validators import DataRequired, ValidationError
from app.models import User, Group
from app import Config


class ChangeWebhookForm(FlaskForm):
    url = StringField('Webhook URL', validators=[DataRequired()])
    submit = SubmitField('Если не знаешь зачем эта кнопка - не нажимай, пожалуйста')


class ScheduledMessageCreateForm(FlaskForm):
    message_type = SelectField('Тип сообщения', choices=[('text', 'Текст'), ('photo', 'Фото'), ('video', 'Видео'), ('poll', 'Опрос')])
    date_time = DateTimeField('Дата и время отправки')
    text = TextAreaField('Текст сообщения')
    content_link = FileField('Ссылка на вложение')
    group = SelectField('Группа адрессатов')
    submit = SubmitField('Запланировать')


class SendTGMessageForm(FlaskForm):
    text = TextAreaField('Текст', validators=[DataRequired()])
    submit = SubmitField('Отправить')


class SendGroupTGMessageForm(FlaskForm):
    groups = SelectField('Группа', choices=[('всем', 'всем')])
    tags = SelectField('Атрибут', choices=[('всем', 'всем')])
    text = TextAreaField('Текст', validators=[DataRequired()])
    submit = SubmitField('Отправить')


class CreateGroupForm(FlaskForm):
    name = StringField('Название', validators=[DataRequired()])
    submit = SubmitField('Добавить')


class CreateModerForm(FlaskForm):
    from app import create_app
    app = create_app(config_class=Config)
    with app.app_context():
        group = SelectMultipleField('Группа',
                                    query_factory=Group.query.all,
                                    get_pk=lambda group: group.id,
                                    get_label=lambda group: group.name)
        user = SelectField('Пользователь',
                           query_factory=User.query.filter(User.role == 'admin').all,
                           get_pk=lambda user: user.tg_id,
                           get_label=lambda user: user.first_name)
        submit = SubmitField('Добавить')


class CreateQuestionForm(FlaskForm):
    question_type = SelectField('Тип вопроса',
                                choices=[('text', 'text'), ('photo', 'photo'), ('video', 'video'), ('audio', 'audio')])
    question_text = TextAreaField('Текст вопроса', validators=[DataRequired()])
    send_variants = BooleanField('Отправлять варианты ответов?', default=True)
    variants = TextAreaField('Варианты ответов')
    question_content = MultipleFileField('Ссылка на вложение')
    answer_type = SelectField('Тип ответа',
                              choices=[('text', 'text'), ('photo', 'photo'), ('video', 'video'), ('audio', 'audio')])
    right_answer_text = TextAreaField('Текст верного ответа')
    wrong_answer_text = TextAreaField('Текст неверного ответа')
    answer_content = FileField('Ссылка на вложение')
    answer_explanation = TextAreaField('Пояснение')
    save_question = SubmitField('Сохранить')


class EditQuizForm(FlaskForm):
    quiz_name = StringField('Название викторины')
    quiz_description = TextAreaField('Сообщение перед началом')
    quiz_final_text = TextAreaField('Сообщение после окончания')
    command = StringField('Команда для запуска')
    pic = FileField('Картинка')
    save_quiz = SubmitField('Сохранить')


class SearchUserForm(FlaskForm):
    name = StringField('ФИО')
    search = SubmitField('Найти')


class VotingForm(FlaskForm):
    name = StringField('Название')
    description = TextAreaField('Описание')
    active = BooleanField('Активно')
    save = SubmitField('Сохранить')


class VotingItemForm(FlaskForm):
    name = StringField('Название')
    description = TextAreaField('Описание')
    pic = FileField('Картинка')
    add = SubmitField('Сохранить')


class PrizeForm(FlaskForm):
    name = StringField('Название')
    description = TextAreaField('Описание')
    pic = FileField('Картинка')
    add = SubmitField('Сохранить')


class PlaceForm(FlaskForm):
    name = StringField('Название', validators=[DataRequired()])
    description = TextAreaField('Описание')
    save = SubmitField('Сохранить')


class PlacementForm(FlaskForm):
    name = StringField('Название', validators=[DataRequired()])
    excel_file = FileField('Загрузить excel', validators=[DataRequired()])
    save_placement = SubmitField('Сохранить')

    def validate_excel_file(self, excel_file):
        if excel_file.data.filename.split('.')[-1] != 'xlsx':
            raise ValidationError('Файл должен быть формата .xlsx')


class EventForm(FlaskForm):
    name = StringField('Название', validators=[DataRequired()])
    description = TextAreaField('Описание')
    poster = MultipleFileField('Афиша')
    save_event = SubmitField('Сохранить')
