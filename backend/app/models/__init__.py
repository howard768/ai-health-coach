# Import all models so SQLAlchemy creates the tables
from app.models.health import OuraToken, SleepRecord  # noqa
from app.models.user import User  # noqa
from app.models.chat import Conversation, ChatMessageRecord  # noqa
