from app import db
from app.models import User, Group, Quiz, QuestProcess, QuizQuestion, QuizQuestionVariant, Component, UserComponent
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice
from app.telegram_bot.helpers import with_app_context
from telegram.ext import CallbackContext
from telegram.constants import ParseMode
from datetime import datetime
from app.telegram_bot import texts


@with_app_context
async def start(update: Update, context: CallbackContext.DEFAULT_TYPE):
    await update.effective_message.delete()
    user: User = User.query.filter(User.tg_id == update.effective_user.id).first()
    if not user:
        user = User()
        user.first_name = update.effective_user.first_name
        user.tg_id = update.effective_user.id
        user.group = Group.query.first().id
        user.registered = datetime.now()
        user.last_visit = datetime.now()
        user.role = 'admin' if len(User.query.all()) == 0 else 'user'
        user.set_password('pwd')
        db.session.add(user)
    else:
        user.last_visit = datetime.now()

    db.session.commit()
    await update.effective_message.reply_text(text=texts.greeting(user),
                                              parse_mode=ParseMode.MARKDOWN)
    return


@with_app_context
async def quest_way(update: Update, context: CallbackContext.DEFAULT_TYPE):
    user: User = User.query.filter(User.tg_id == update.effective_user.id).first()
    way = update.callback_query.data.split('_')[-1]
    text = texts.quest_start(user, way)
    await update.effective_message.edit_text(text=text, reply_markup=None, parse_mode=ParseMode.MARKDOWN)
    # высылаем викторину, если она есть
    quiz: Quiz = Quiz.query.filter(Quiz.way == int(way)).first()
    if quiz:
        quest_process: QuestProcess = QuestProcess.query.filter(QuestProcess.user == user.id).first()
        quest_process.status = f'quiz_{quiz.id}_question_0'
        db.session.commit()
        await update.effective_message.reply_text(quiz.description, parse_mode=ParseMode.MARKDOWN)
        question = quiz.get_next_question(user)
        await update.effective_message.reply_text(text=question['text'], reply_markup=question['reply_markup'], parse_mode=ParseMode.MARKDOWN)
    else:
        quest_process = QuestProcess.query.filter(QuestProcess.user == user.id).all()
        for qp in quest_process:
            db.session.delete(qp)
        db.session.commit()
        await update.effective_message.reply_text('В таком случае, возвращайтесь на базу и попробуйте пройти финальную битву.')
    return


@with_app_context
async def quiz_answer(update: Update, context: CallbackContext.DEFAULT_TYPE):
    user: User = User.query.filter(User.tg_id == update.effective_user.id).first()
    variant: QuizQuestionVariant = QuizQuestionVariant.query.get(update.callback_query.data.split('_')[-1])
    quiz = variant.get_question().get_quiz()
    qp: QuestProcess = user.get_quest_process()
    await update.effective_message.edit_reply_markup(reply_markup=None)

    async def next_step(last=False):
        if variant.components:
            components = Component.query.filter(Component.id.in_(variant.components)).all()
            btns = []
            for c in components:
                btns.append([InlineKeyboardButton(text=c.name, callback_data=f'component_{c.id}')])
            await update.effective_message.reply_text(text='Это верный ответ, выбирайте компонент защиты',
                                                      reply_markup=InlineKeyboardMarkup(inline_keyboard=btns),
                                                      parse_mode=ParseMode.MARKDOWN)
        if not last:
            question = quiz.get_next_question(user)
            await update.effective_message.reply_text(text=question['text'], reply_markup=question['reply_markup'],
                                                      parse_mode=ParseMode.MARKDOWN)

    current_question_number = int(qp.status.split('_')[-1])
    questions_count = len(quiz.get_questions())
    if current_question_number+1 < questions_count:
        qp.status = f'quiz_{quiz.id}_question_{current_question_number+1}'
        await next_step()
    else:
        await next_step(last=True)
        db.session.delete(qp)
        db.session.commit()
        await update.effective_message.reply_text('Ок, возвращайтесь на базу и попробуйте пройти финальную битву.')
    db.session.commit()

    return


async def collect_component(update: Update, context: CallbackContext.DEFAULT_TYPE):
    await update.effective_message.edit_reply_markup(reply_markup=None)
    user: User = User.query.filter(User.tg_id == update.effective_user.id).first()
    component: Component = Component.query.get(int(update.callback_query.data.split('_')[-1]))
    user_component = UserComponent()
    user_component.user = user.id
    user_component.component = component.id
    db.session.add(user_component)
    db.session.commit()
    await update.effective_message.edit_text(text=f'*Вы получили {component.name}*\n\n{component.description if component.description else ""}',
                                             parse_mode=ParseMode.MARKDOWN)
    return


@with_app_context
async def help_command(update: Update, context: CallbackContext.DEFAULT_TYPE):
    chat_id = int(update.message.from_user.id)
    message_id = int(update.message.message_id)
    sender: User = User.query.filter(User.tg_id == chat_id).first()

    await update.message.delete()

    confirm_btn = InlineKeyboardButton(text='Да, помощь нужна', callback_data='help')
    cancel_btn = InlineKeyboardButton(text='Нет, помощь не нужна', callback_data='deleteMessage')

    keyboard = [[confirm_btn], [cancel_btn]]

    await update.message.reply_text(text='🆘 Вы нажали кнопку помощи 🆘.\n\nЗачастую её нажимают просто так. А обработка каждого запроса требует времени.\n\n*Вам действительно нужна наша помощь?*',
                              reply_markup=InlineKeyboardMarkup(keyboard),
                              parse_mode=ParseMode.MARKDOWN)


@with_app_context
async def hide_msg(update: Update, context: CallbackContext.DEFAULT_TYPE):
    await update.effective_message.delete()
    return 'ok'


@with_app_context
async def help(update: Update, context: CallbackContext.DEFAULT_TYPE):
    user = User.query.filter(User.tg_id == update.callback_query.from_user.id).first()
    await update.callback_query.delete_message()
    # texts.help(user)


@with_app_context
async def delete_message(update: Update, context: CallbackContext.DEFAULT_TYPE):
    await update.callback_query.delete_message()
