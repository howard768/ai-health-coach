# Import all models so SQLAlchemy creates the tables
from app.models.health import OuraToken, SleepRecord, HealthMetricRecord, ActivityRecord, SourcePriority  # noqa
from app.models.user import User  # noqa
from app.models.chat import Conversation, ChatMessageRecord  # noqa
from app.models.notification import DeviceToken, NotificationRecord, NotificationPreference, NotificationTemplate  # noqa
from app.models.meal import MealRecord, FoodItemRecord  # noqa
from app.models.peloton import PelotonToken, WorkoutRecord  # noqa
from app.models.garmin import GarminToken, GarminDailyRecord  # noqa
from app.models.correlation import UserCorrelation  # noqa
