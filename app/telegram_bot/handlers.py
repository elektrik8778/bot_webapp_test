from app import db, Config
from app.models import User, Group, Quiz, QuestProcess, QuizQuestion, QuizQuestionVariant, Component, UserComponent
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto, MenuButtonWebApp, WebAppInfo
from app.telegram_bot.helpers import with_app_context
from telegram.ext import CallbackContext
from telegram.constants import ParseMode
from datetime import datetime
from app.telegram_bot import texts
import json
import os


async def get_bot_pic(name, folder='start'):
    from app.telegram_bot.routes import get_bot
    dir = os.path.join(Config.STATIC_FOLDER, 'images', folder)
    if not os.path.exists(dir):
        os.makedirs(dir)

    if not os.path.exists(os.path.join(dir, f'{name}.fid')):
        with open(os.path.join(dir, f'{name}.png'), 'rb') as photo:
            result = await get_bot().send_photo(chat_id=os.environ.get('ADMIN_TG_ID'),
                                                photo=photo)
        with open(os.path.join(dir, f'{name}.fid'), 'w') as fid:
            fid.write(result.photo[-1].file_id)

    with open(os.path.join(dir, f'{name}.fid'), 'r') as fid:
        return fid.read()


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
        user.source = update.effective_message.text.split('/start')[-1].strip()
        db.session.add(user)
    else:
        user.last_visit = datetime.now()

    db.session.commit()

    btns = [[
        InlineKeyboardButton(text='ДА!', callback_data='way_1'),
        InlineKeyboardButton(text='НЕ СЕЙЧАС!', callback_data='way_2'),
    ]]
    # после регистрации нового пользователя проверяем, не проходит ли он квест в данный момент
    if qp := QuestProcess.query.filter(QuestProcess.user == user.id).first():
        from app.telegram_bot.routes import get_bot
        # если проходит
        await update.effective_message.reply_text('Вы в процессе прохождения квеста, дойдите до конца.',
                                                  protect_content=True)
        # если статус процесса квеста = None, повторяем сообщение с картинкой 4
        if qp.status is None:
            try:
                await get_bot().delete_message(chat_id=user.tg_id, message_id=qp.current_message)
            except Exception as e:
                print(user, e)
            result = await update.effective_message.reply_photo(caption=texts.SCREEN_4,
                                                                photo=await get_bot_pic('4'),
                                                                reply_markup=InlineKeyboardMarkup(inline_keyboard=btns),
                                                                parse_mode=ParseMode.MARKDOWN,
                                                                protect_content=True)
            qp.current_message = result.message_id
            db.session.commit()
        # иначе отправляем текущий вопрос
        else:
            quiz: Quiz = Quiz.query.get(qp.status.split('_')[1])
            question = quiz.get_next_question(user)
            if question:
                try:
                    await get_bot().delete_message(chat_id=user.tg_id, message_id=qp.current_message)
                except Exception as e:
                    print(user, e)
                result = await update.effective_message.reply_text(text=question['text'],
                                                                   reply_markup=question['reply_markup'],
                                                                   parse_mode=ParseMode.MARKDOWN,
                                                                   protect_content=True)
                qp.current_message = result.message_id
                db.session.commit()
    else:
        # если не проходит - создаем процесс квеста, отдаём приветствие и заезд на игру
        quest_process = QuestProcess()
        quest_process.user = user.id
        db.session.add(quest_process)
        db.session.commit()
        # await update.effective_message.reply_photo(caption=texts.greeting(user),
        #                                            photo=await get_bot_pic('0'),
        #                                            parse_mode=ParseMode.MARKDOWN)
        media = [
            InputMediaPhoto(media=await get_bot_pic('0'), caption=texts.greeting(user), parse_mode=ParseMode.MARKDOWN),
            InputMediaPhoto(media=await get_bot_pic('1'), caption=texts.SCREEN_1, parse_mode=ParseMode.MARKDOWN),
            InputMediaPhoto(media=await get_bot_pic('2'), caption=texts.SCREEN_2, parse_mode=ParseMode.MARKDOWN),
            InputMediaPhoto(media=await get_bot_pic('3'), caption=texts.SCREEN_3, parse_mode=ParseMode.MARKDOWN)
        ]

        await update.effective_message.reply_media_group(media=media, protect_content=True)

        result = await update.effective_message.reply_photo(caption=texts.SCREEN_4,
                                                            photo=await get_bot_pic('4'),
                                                            reply_markup=InlineKeyboardMarkup(inline_keyboard=btns),
                                                            parse_mode=ParseMode.MARKDOWN,
                                                            protect_content=True)
        quest_process.current_message = result.message_id
        db.session.commit()

    db.session.remove()
    return


@with_app_context
async def quest_way(update: Update, context: CallbackContext.DEFAULT_TYPE):
    user: User = User.query.filter(User.tg_id == update.effective_user.id).first()
    way = update.callback_query.data.split('_')[-1]
    text = texts.quest_start(user, way)
    await update.effective_message.edit_caption(caption=text, reply_markup=None, parse_mode=ParseMode.MARKDOWN)
    # высылаем викторину, если она есть
    quiz: Quiz = Quiz.query.filter(Quiz.way == int(way)).first()
    if quiz:
        quest_process: QuestProcess = QuestProcess.query.filter(QuestProcess.user == user.id).first()
        quest_process.status = f'quiz_{quiz.id}_question_0'
        db.session.commit()
        pic = f'[.]({quiz.pic_link})' if quiz.pic_link else ''
        # await update.effective_message.reply_text(f'{quiz.description} {pic}', parse_mode=ParseMode.MARKDOWN)
        question = quiz.get_next_question(user)
        if question:
            result = await update.effective_message.reply_text(text=question['text'],
                                                               reply_markup=question['reply_markup'],
                                                               parse_mode=ParseMode.MARKDOWN,
                                                               protect_content=True)
            quest_process.current_message = result.message_id
            db.session.commit()
    else:
        quest_process = QuestProcess.query.filter(QuestProcess.user == user.id).all()
        for qp in quest_process:
            db.session.delete(qp)
        db.session.commit()

        # высылаем видео с поражением
        if os.path.exists(os.path.join(Config.STATIC_FOLDER, 'video', 'pt nad lose 1.fid')):
            with open(os.path.join(Config.STATIC_FOLDER, 'video', 'pt nad lose 1.fid'), 'r') as video:
                await update.effective_message.reply_video(video=video.read(),
                                                           caption=texts.FINAL_BATTLE_LAZY_LOSE,
                                                           parse_mode=ParseMode.MARKDOWN,
                                                           protect_content=True)
    db.session.remove()
    return


@with_app_context
async def quiz_answer(update: Update, context: CallbackContext.DEFAULT_TYPE):
    user: User = User.query.filter(User.tg_id == update.effective_user.id).first()
    variant: QuizQuestionVariant = QuizQuestionVariant.query.get(update.callback_query.data.split('_')[-1])
    quiz = variant.get_question().get_quiz()
    qp: QuestProcess = user.get_quest_process()
    await update.effective_message.edit_reply_markup(reply_markup=None)
    current_question_number = int(qp.status.split('_')[-1])
    qp.status = f'quiz_{quiz.id}_question_{current_question_number + 1}'

    if variant.components:
        # высылаем компоненты на выбор
        # components = Component.query.filter(Component.id.in_(variant.components)).all()
        # btns = []
        # for c in components:
        #     btns.append([InlineKeyboardButton(text=c.name, callback_data=f'component_{c.id}')])
        # await update.effective_message.reply_text(text='Это верный ответ, выбирайте компонент защиты',
        #                                           reply_markup=InlineKeyboardMarkup(inline_keyboard=btns),
        #                                           parse_mode=ParseMode.MARKDOWN)
        # btns = []
        # text = '*Это верный ответ. Какую награду вы хотите за него?*'
        # for index, components_set in enumerate(variant.components):
        #     components = Component.query.filter(Component.id.in_(components_set)).all()
        #     text += f'\n\n{index+1})'
        #     text += ', '.join([c.name for c in components])
        #     btns.append([InlineKeyboardButton(text=str(index+1), callback_data=f'component_{components_set}')])
        # await update.effective_message.reply_text(text=text,
        #                                           reply_markup=InlineKeyboardMarkup(inline_keyboard=btns),
        #                                           parse_mode=ParseMode.MARKDOWN)
        for c in Component.query.filter(Component.id.in_(variant.components)).all():
            user_component = UserComponent()
            user_component.user = user.id
            user_component.component = c.id
            db.session.add(user_component)
            await update.effective_message.reply_photo(photo=await get_bot_pic(c.filename, 'components'),
                                                       caption=f'Это правильный ответ, вы получаете\n\n*{c.name}*\n_{c.description}_',
                                                       parse_mode=ParseMode.MARKDOWN,
                                                       protect_content=True)
        db.session.commit()

    # высылаем следующий вопрос
    question = quiz.get_next_question(user)
    if question:
        result = await update.effective_message.reply_text(text=question['text'],
                                                           reply_markup=question['reply_markup'],
                                                           parse_mode=ParseMode.MARKDOWN,
                                                           protect_content=True)
        qp.current_message = result.message_id
        db.session.commit()
    else:
        db.session.delete(qp)
        web_app = WebAppInfo(url=f'https://{os.environ.get("TG_ADDR")}/castle')
        btns = [
            [MenuButtonWebApp('Замок', web_app=web_app)],
            # [InlineKeyboardButton(text='Финальная битва', callback_data='finalbattle')]
        ]
        result = await update.effective_message.reply_text(text='Вопросов больше нет. Перейди в замок и узнай, сколько героев-защитников удалось собрать.',
                                                           reply_markup=InlineKeyboardMarkup(inline_keyboard=btns),
                                                           parse_mode=ParseMode.MARKDOWN,
                                                           protect_content=True)
        qp.current_message = result.message_id

    db.session.commit()
    db.session.remove()
    return


async def collect_component(update: Update, context: CallbackContext.DEFAULT_TYPE):
    components = Component.query.filter(Component.id.in_(json.loads(update.callback_query.data.split('_')[-1]))).all()
    await update.effective_message.edit_reply_markup(reply_markup=None)
    user: User = User.query.filter(User.tg_id == update.effective_user.id).first()
    text = '*ПОЛУЧЕН КОМПОНЕНТ*\n'
    for c in components:
        user_component = UserComponent()
        user_component.user = user.id
        user_component.component = c.id
        db.session.add(user_component)
        text += f'\n🎁{c.name}{" - " + c.description if c.description else ""}🎁'
    db.session.commit()
    stat = user.get_components_stat()
    await update.effective_message.edit_text(text=f'{text}\n\n{stat}',
                                             parse_mode=ParseMode.MARKDOWN)

    # следующий вопрос, если он есть
    qp: QuestProcess = user.get_quest_process()
    quiz: Quiz = Quiz.query.get(qp.status.split('_')[1])

    question = quiz.get_next_question(user)
    if question:
        await update.effective_message.reply_text(text=question['text'],
                                                  reply_markup=question['reply_markup'],
                                                  parse_mode=ParseMode.MARKDOWN)
    else:
        db.session.delete(qp)
        await update.effective_message.reply_text('Ок, возвращайтесь на базу и попробуйте пройти финальную битву.')

    db.session.commit()
    db.session.remove()
    return


async def final_battle(update: Update, context: CallbackContext.DEFAULT_TYPE):
    # высылаем видео финальной битвы
    await update.effective_message.reply_text('Видео финальной битвы')
    await update.effective_message.edit_reply_markup(reply_markup=None)
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
