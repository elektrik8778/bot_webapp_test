from app.models import User


def greeting(user:User):
    return f'*Привет, {user.first_name}!*\n\nВ этом боте ты можешь купить билеты на концерты в Благовещенске. ' \
           f'Чтобы получить расписание концертов - нажимай кнопку "Будущие концерты" в меню.'
