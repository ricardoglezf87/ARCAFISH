from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


FishingMethod = Literal["float", "bottom", "spinning"]
SpotType = Literal["rocky", "mixed", "sandy", "reef", "harbor"]
ShoreType = Literal["volcanic", "beach", "pier", "cliff"]
SpotExposure = Literal["sheltered", "semi_exposed", "exposed"]


class FishingSpotMethodContext(BaseModel):
    shore_type: ShoreType = "volcanic"
    spot_type: SpotType = "rocky"
    spot_exposure: SpotExposure = "semi_exposed"
    water_depth_estimate_m: float | None = Field(default=None, ge=0, le=200)


class FishingSpotBase(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    notes: str | None = Field(default=None, max_length=1000)
    method_contexts: dict[FishingMethod, FishingSpotMethodContext] | None = None


class FishingSpotCreate(FishingSpotBase):
    pass


class FishingSpotUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    notes: str | None = Field(default=None, max_length=1000)
    method_contexts: dict[FishingMethod, FishingSpotMethodContext] | None = None


class FishingSpotRead(FishingSpotBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ErrorResponse(BaseModel):
    detail: str

