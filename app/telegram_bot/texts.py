from app.models import User


SCREEN_1 = '''
*Привет, избранный!*

На безNADежный SOC опустился тревожный туман. 
Твоя задача ― обеспечить безопасность замка. 

По умолчанию у тебя есть средства защиты: стена ― NGFW, лучники ― агенты EDR и могучий великан ― MaxPatrol SIEM, который видит все и сообщает об опасности.
'''

SCREEN_2 = '''
Безумный профессор Anonimus хочет атаковать замок и получить golden ticket, который даст ему полный контроль над инфраструктурой безNADежного SOC.
Ответь на вопросы квеста и собери 9 героев-защитников в магический security-шар, чтобы остановить злодея.
'''

SCREEN_3 = '''
Alarm! У ворот Северной башни замка уже собрались атакующие. Будешь сражаться сейчас?

*ДА. Воспользуюсь тем, что уже есть.*

или

*Не сейчас. Сначала отвечу на вопросы и соберу защитников.*
'''

SCREEN_4 = '''
У ворот Северной башни замка собрались атакующие, грядет битва. Ты готов сразиться?

*ДА! Воспользуюсь бесплатными инструментами и попробую обнаружить атаки.*
или
*Не сейчас! Мне нужны средства защиты, буду отвечать на вопросы, чтобы их получить.*
'''

FINAL_BATTLE_WIN = '''
*Победа!*

Осталось узнать, кто получит призовой лутбокс.

Вдруг это ты? Объявим на  [трансляции 27 октября](https://promo.ptsecurity.com/pt-nad-11/?utm_source=tg&utm_medium=game&utm_campaign=nad-11&utm_content=bot).

Чтобы пройти квест заново  -  отправьте команду /start
'''

FINAL_BATTLE_LOSE = '''
*Поражение!*

NADежда покинула SOC. 
Безумный профессор получил полный контроль над инфраструктурой. 
Чтобы этого не случилось в реальности, приходи [на трансляцию](https://promo.ptsecurity.com/pt-nad-11/?utm_source=tg&utm_medium=game&utm_campaign=nad-11&utm_content=bot) и узнай больше про обнаружение аномалий и угроз.

Чтобы пройти квест заново  -  отправьте команду /start
'''

FINAL_BATTLE_LAZY_LOSE = '''
*Поражение!*

Случилось неприемлемое.
NADежда окончательно покинула SOC.
Чтобы этого не произошло в реальности, нужен верный подход к обнаружению атак.

Какой? [👉🏻Расскажем 27 октября](https://promo.ptsecurity.com/pt-nad-11/?utm_source=tg&utm_medium=game&utm_campaign=nad-11&utm_content=bot)

Чтобы пройти квест заново  -  отправьте команду /start
'''

def get_screen_text(screen_number):
    if screen_number == 1:
        return SCREEN_1
    if screen_number == 2:
        return SCREEN_2
    if screen_number == 3:
        return SCREEN_3



def greeting(user:User):
    return f'''
*Добро пожаловать, {user.first_name}!*

Цель квеста: защитить виртуальный город и получить реальный приз ― лутбокс, доверху наполненный золотом и подарками от Positive Technologies.
Победителя объявим в финале трансляции [ссылка на лендинг](https://ya.ru)
'''


def quest_start(user:User, way=0):
#     text = f'''
# *{user.first_name}, вы отправились на поиски компонентов для защиты замка!*
#
# {user.get_components_stat()}
# _Вы добежали до развилки_
#     '''

    text = f'''
У ворот Северной башни замка собрались атакующие, грядет битва. Ты готов сразиться?

'''

    vars = [
        'ДА! Воспользуюсь бесплатными инструментами и попробую обнаружить атаки. ',
        'Не сейчас! Мне нужны средства защиты, буду отвечать на вопросы, чтобы их получить'
    ]

    if way == 0:
        text += '\n*Куда пойдёте?*\n'
        for i, v in enumerate(vars):
            text += f'{i+1}) {vars[i]}\n'
    else:
        text += '\n*Вы выбрали*\n'
        text += vars[int(way) - 1]
    return text
