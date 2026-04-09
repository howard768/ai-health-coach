from pydantic import BaseModel


class FoodItemCreate(BaseModel):
    name: str
    serving_size: str
    serving_count: float = 1.0
    calories: int
    protein: float
    carbs: float
    fat: float
    quality: str = "mixed"  # whole, mixed, processed
    data_source: str = "manual"
    confidence: float = 1.0


class FoodItemResponse(BaseModel):
    id: int | None = None
    name: str
    serving_size: str
    serving_count: float = 1.0
    calories: int
    protein: float
    carbs: float
    fat: float
    quality: str
    data_source: str
    confidence: float


class MealCreate(BaseModel):
    meal_type: str | None = None  # Auto-assigned by time if omitted
    source: str = "manual"
    items: list[FoodItemCreate]
    photo_hash: str | None = None


class MealResponse(BaseModel):
    id: int
    date: str
    meal_type: str
    source: str
    items: list[FoodItemResponse]
    total_calories: int
    total_protein: float
    total_carbs: float
    total_fat: float
    created_at: str


class DailyMealsResponse(BaseModel):
    date: str
    meals: list[MealResponse]
    total_calories: int
    total_protein: float
    total_carbs: float
    total_fat: float


class FoodRecognitionRequest(BaseModel):
    image_base64: str
    media_type: str = "image/jpeg"
    meal_type: str | None = None


class FoodRecognitionResponse(BaseModel):
    items: list[FoodItemResponse]
    meal_type: str


class FoodSearchRequest(BaseModel):
    query: str
