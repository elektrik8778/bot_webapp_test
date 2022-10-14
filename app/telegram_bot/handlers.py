from app import db, Config
from app.models import User, Group, Quiz, QuestProcess, QuizQuestion, QuizQuestionVariant, Component, UserComponent, \
    UserQuest
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto, MenuButtonWebApp, WebAppInfo
from app.telegram_bot.helpers import with_app_context
from telegram.ext import CallbackContext
from telegram.constants import ParseMode
from datetime import datetime, timedelta
from app.telegram_bot import texts
import json
import os
from random import choice


async def get_bot_pic(name, folder='start', format='png'):
    from app.telegram_bot.routes import get_bot
    dir = os.path.join(Config.STATIC_FOLDER, 'images', folder)
    if not os.path.exists(dir):
        os.makedirs(dir)

    if not os.path.exists(os.path.join(dir, f'{name}.fid')):
        photo_formats = ['png', 'jpg', 'jpeg']
        video_formats = ['mp4']
        with open(os.path.join(dir, f'{name}.{format}'), 'rb') as media:
            if format in photo_formats:
                result = await get_bot().send_photo(chat_id=os.environ.get('ADMIN_TG_ID'),
                                                    photo=media)
            elif format in video_formats:
                result = await get_bot().send_video(chat_id=os.environ.get('ADMIN_TG_ID'),
                                                    video=media)
            await result.delete()
        with open(os.path.join(dir, f'{name}.fid'), 'w') as fid:
            if format in photo_formats:
                fid.write(result.photo[-1].file_id)
            elif format in video_formats:
                fid.write(result.video.file_id)

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

    # после регистрации нового пользователя проверяем, не проходит ли он квест в данный момент
    if qp := QuestProcess.query.filter(QuestProcess.user == user.id).first():
        from app.telegram_bot.routes import get_bot
        # если проходит, то уведомляем его
        await update.effective_message.reply_text('Вы в процессе прохождения квеста, дойдите до конца.',
                                                  protect_content=True)
        # и если статус процесса не пустой, отправляем текущий вопрос
        if qp.status is not None:
            quiz: Quiz = Quiz.query.get(qp.status.split('_')[1])
            question = quiz.get_next_question(user)
            if question:
                try:
                    # await get_bot().delete_message(chat_id=user.tg_id, message_id=qp.current_message)
                    await get_bot().edit_message_reply_markup(chat_id=user.tg_id,
                                                              message_id=qp.current_message,
                                                              reply_markup=None)
                except Exception as e:
                    print(user, e)
                result = await update.effective_message.reply_text(text=question['text'],
                                                                   reply_markup=question['reply_markup'],
                                                                   parse_mode=ParseMode.MARKDOWN,
                                                                   protect_content=True)
                qp.current_message = result.message_id
                db.session.commit()
    else:
        if user.finished_quest:
            rest = 3600 - (datetime.now()-user.finished_quest).total_seconds()
            if rest > 0:
                await update.effective_message.reply_text(f'Квест можно пробовать пройти 1 раз в час. Ваша следующая попытка будет доступна через {int(rest/60)} минут')
                return
        # если не проходит - создаем процесс квеста, отдаём приветствие и заезд на игру
        quest_process = QuestProcess()
        quest_process.user = user.id
        db.session.add(quest_process)
        db.session.commit()

        btn_next = InlineKeyboardButton(text='Далее >>', callback_data='screen_1_1_2')
        await update.effective_message.reply_photo(caption=texts.SCREEN_1,
                                                   photo=await get_bot_pic('1'),
                                                   reply_markup=InlineKeyboardMarkup(inline_keyboard=[[btn_next]]),
                                                   parse_mode=ParseMode.MARKDOWN,
                                                   protect_content=True)

    db.session.remove()
    return


@with_app_context
async def show_screen(update: Update, context: CallbackContext.DEFAULT_TYPE):
    next_screen = int(update.callback_query.data.split('_')[-1])
    prev_screen = int(update.callback_query.data.split('_')[-2])
    direction = int(update.callback_query.data.split('_')[-3])

    btns = []
    battle_btns = []
    keyboard = []
    if prev_screen+direction>-1:
        btn_prev = InlineKeyboardButton(text='<< Назад', callback_data=f'screen_-1_{prev_screen - 1}_{next_screen - 1}')
        btns.append(btn_prev)
    if next_screen+direction<4:
        btn_next = InlineKeyboardButton(text='Далее >>', callback_data=f'screen_1_{prev_screen + 1}_{next_screen + 1}')
        btns.append(btn_next)
    if next_screen+direction>=4:
        battle_btns = [
            InlineKeyboardButton(text='ДА!', callback_data='way_1'),
            InlineKeyboardButton(text='НЕ СЕЙЧАС!', callback_data='way_2'),
        ]
    if btns:
        keyboard.append(btns)
    if battle_btns:
        keyboard.append(battle_btns)

    media = InputMediaPhoto(media=await get_bot_pic(str(next_screen)))

    await update.effective_message.edit_media(media=media)
    await update.effective_message.edit_caption(caption=texts.get_screen_text(next_screen),
                                                parse_mode=ParseMode.MARKDOWN)
    await update.effective_message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))
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
        user_quest = UserQuest()
        user_quest.user = user.id
        user_quest.start = datetime.now()
        db.session.add(user_quest)
        db.session.commit()
        pic = f'[.]({quiz.pic_link})' if quiz.pic_link else ''
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
        await update.effective_message.reply_video(video=await get_bot_pic(name='lose_full', folder='final_battle', format='mp4'),
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
    db.session.commit()

    btn_next_question = InlineKeyboardButton(text='Следующий вопрос', callback_data=f'nextquestion_{quiz.id}_{current_question_number + 1}')
    if variant.components:
        if variant.components[0] == 0:
            user_components = UserComponent.query.filter(UserComponent.user == user.id).all()
            components = Component.query.all()
            components_diff = list(set(components)-set(user_components))
            component = choice(components_diff)
            user_component = UserComponent()
            user_component.user = user.id
            user_component.component = component.id
            db.session.add(user_component)
            result = await update.effective_message.reply_photo(photo=await get_bot_pic(component.filename, 'components'),
                                                                caption=f'Это правильный ответ, вы получаете\n\n*{component.name}*',
                                                                parse_mode=ParseMode.MARKDOWN,
                                                                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[btn_next_question]]),
                                                                protect_content=True)
            qp.current_message = result.message_id
            db.session.commit()
        else:
            for c in Component.query.filter(Component.id.in_(variant.components)).all():
                user_component = UserComponent()
                user_component.user = user.id
                user_component.component = c.id
                db.session.add(user_component)
                result = await update.effective_message.reply_photo(photo=await get_bot_pic(c.filename, 'components'),
                                                                    caption=f'Это правильный ответ, вы получаете\n\n*{c.name}*',
                                                                    parse_mode=ParseMode.MARKDOWN,
                                                                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[[btn_next_question]]),
                                                                    protect_content=True)
                qp.current_message = result.message_id
                db.session.commit()
        user_components_count = len(UserComponent.query.filter(UserComponent.user == user.id).all())
        components_count = len(Component.query.all())
        if user_components_count >= components_count:
            from app.telegram_bot.routes import get_bot
            await get_bot().edit_message_reply_markup(chat_id=user.tg_id,
                                                      message_id=qp.current_message,
                                                      reply_markup=None)
            db.session.delete(qp)
            web_app = WebAppInfo(url=f'https://{os.environ.get("TG_ADDR")}/castle')
            btns = [
                [MenuButtonWebApp('Замок', web_app=web_app)]
            ]
            result = await update.effective_message.reply_video(
                video=await get_bot_pic(name='components_collected', folder='final_battle', format='mp4'),
                caption='Вопросов больше нет. Перейди в замок и узнай, сколько героев-защитников удалось собрать.',
                reply_markup=InlineKeyboardMarkup(inline_keyboard=btns),
                parse_mode=ParseMode.MARKDOWN,
                protect_content=True)
            qp.current_message = result.message_id
            db.session.commit()
    else:
        result = await update.effective_message.reply_text(text=f'Это неправильный ответ',
                                                           parse_mode=ParseMode.MARKDOWN,
                                                           reply_markup=InlineKeyboardMarkup(inline_keyboard=[[btn_next_question]]),
                                                           protect_content=True)
        qp.current_message = result.message_id
        db.session.commit()

    db.session.remove()
    return


async def next_question(update: Update, context: CallbackContext.DEFAULT_TYPE):
    user: User = User.query.filter(User.tg_id == update.effective_user.id).first()
    quiz: Quiz = Quiz.query.get(int(update.callback_query.data.split('_')[-2]))
    qp: QuestProcess = user.get_quest_process()
    await update.effective_message.edit_reply_markup(reply_markup=None)
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
        # вот тут проверяем сколько элементов не хватает
        user_components_count = len(UserComponent.query.filter(UserComponent.user == user.id).all())
        components_count = len(Component.query.all())
        # если более трех или 0, то отдаем "Вопросов больше нет"
        if (components_count - user_components_count) > 3 or (components_count - user_components_count) == 0 or quiz.id == 2:
            db.session.delete(qp)
            web_app = WebAppInfo(url=f'https://{os.environ.get("TG_ADDR")}/castle')
            btns = [
                [MenuButtonWebApp('Замок', web_app=web_app)]
            ]
            result = await update.effective_message.reply_video(
                video=await get_bot_pic(name='components_collected', folder='final_battle', format='mp4'),
                caption='Вопросов больше нет. Перейди в замок и узнай, сколько героев-защитников удалось собрать.',
                reply_markup=InlineKeyboardMarkup(inline_keyboard=btns),
                parse_mode=ParseMode.MARKDOWN,
                protect_content=True)
            qp.current_message = result.message_id
        # иначе даем столько доп вопросов, сколько не хватает компонентов
        else:
            text = f'У вас есть {user_components_count} из {components_count} героев защитников. Чтобы собрать все, ответьте еще на {components_count-user_components_count} {"вопроса" if components_count-user_components_count>1 else "вопрос"} правильно.'
            btn_ok = InlineKeyboardButton(text='Ок', callback_data=f'additionalQuestions_{components_count-user_components_count}')
            btn_cancel = InlineKeyboardButton(text='Не хочу', callback_data='escapeAdditionalQuestions')
            reply_markup = InlineKeyboardMarkup(inline_keyboard=[[btn_ok, btn_cancel]])
            await update.effective_message.reply_text(text=text,
                                                      reply_markup=reply_markup,
                                                      parse_mode=ParseMode.MARKDOWN,
                                                      protect_content=True)

    db.session.commit()
    db.session.remove()
    return


async def additional_questions(update: Update, context: CallbackContext.DEFAULT_TYPE):
    # await update.effective_message.edit_reply_markup(reply_markup=None)
    user: User = User.query.filter(User.tg_id == update.effective_user.id).first()
    quiz: Quiz = Quiz.query.get(2)
    qp: QuestProcess = user.get_quest_process()
    qp.status = f'quiz_{quiz.id}_question_0'
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

    db.session.remove()
    return


async def escape_additional_questions(update: Update, context: CallbackContext.DEFAULT_TYPE):
    await update.effective_message.edit_reply_markup(reply_markup=None)
    user: User = User.query.filter(User.tg_id == update.effective_user.id).first()
    qp: QuestProcess = user.get_quest_process()

    db.session.delete(qp)
    web_app = WebAppInfo(url=f'https://{os.environ.get("TG_ADDR")}/castle')
    btns = [
        [MenuButtonWebApp('Замок', web_app=web_app)]
    ]
    result = await update.effective_message.reply_video(
        video=await get_bot_pic(name='components_collected', folder='final_battle', format='mp4'),
        caption='Вопросов больше нет. Перейди в замок и узнай, сколько героев-защитников удалось собрать.',
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
