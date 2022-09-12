from app.models import User


def greeting(user:User):
    return f'''
*Привет, {user.first_name}!*

_Описание, ввод в игровую легенду..._
'''
