from config import Config


def with_app_context(func):
    """
    Adds app context to function
    """
    async def wrapper(*args):
        from app import create_app
        app = create_app(config_class=Config)
        with app.app_context():
            await func(*args)
    return wrapper
