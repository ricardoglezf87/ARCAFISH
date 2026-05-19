from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class FishingSpotBase(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    notes: str | None = Field(default=None, max_length=1000)


class FishingSpotCreate(FishingSpotBase):
    pass


class FishingSpotRead(FishingSpotBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ErrorResponse(BaseModel):
    detail: str

