from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import FishingSpot
from app.schemas import FishingSpotCreate, FishingSpotRead, FishingSpotUpdate


router = APIRouter(prefix="/api/spots", tags=["spots"])


DEFAULT_METHOD_CONTEXTS = {
    "float": {
        "shore_type": "volcanic",
        "spot_type": "rocky",
        "spot_exposure": "semi_exposed",
        "water_depth_estimate_m": None,
    },
    "bottom": {
        "shore_type": "volcanic",
        "spot_type": "rocky",
        "spot_exposure": "semi_exposed",
        "water_depth_estimate_m": None,
    },
    "spinning": {
        "shore_type": "volcanic",
        "spot_type": "rocky",
        "spot_exposure": "semi_exposed",
        "water_depth_estimate_m": None,
    },
}


@router.get("", response_model=list[FishingSpotRead])
def list_spots(db: Session = Depends(get_db)) -> list[FishingSpot]:
    return list(db.scalars(select(FishingSpot).order_by(FishingSpot.created_at.desc())))


@router.post("", response_model=FishingSpotRead, status_code=status.HTTP_201_CREATED)
def create_spot(payload: FishingSpotCreate, db: Session = Depends(get_db)) -> FishingSpot:
    settings = get_settings()
    if not settings.is_inside_canary_bounds(payload.latitude, payload.longitude):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El punto debe estar dentro del ámbito inicial de Canarias.",
        )

    spot = FishingSpot(
        name=payload.name.strip(),
        latitude=payload.latitude,
        longitude=payload.longitude,
        notes=payload.notes.strip() if payload.notes else None,
        method_contexts=_normalize_method_contexts(payload.method_contexts),
    )
    db.add(spot)
    db.commit()
    db.refresh(spot)
    return spot


@router.patch("/{spot_id}", response_model=FishingSpotRead)
def update_spot(spot_id: int, payload: FishingSpotUpdate, db: Session = Depends(get_db)) -> FishingSpot:
    spot = db.get(FishingSpot, spot_id)
    if spot is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Punto no encontrado.")

    updates = payload.model_dump(exclude_unset=True)
    if "name" in updates and payload.name is not None:
        spot.name = payload.name.strip()
    if "notes" in updates:
        spot.notes = payload.notes.strip() if payload.notes else None
    if "method_contexts" in updates:
        spot.method_contexts = _normalize_method_contexts(payload.method_contexts)

    db.commit()
    db.refresh(spot)
    return spot


@router.get("/{spot_id}", response_model=FishingSpotRead)
def get_spot(spot_id: int, db: Session = Depends(get_db)) -> FishingSpot:
    spot = db.get(FishingSpot, spot_id)
    if spot is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Punto no encontrado.")
    return spot


@router.delete("/{spot_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_spot(spot_id: int, db: Session = Depends(get_db)) -> None:
    spot = db.get(FishingSpot, spot_id)
    if spot is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Punto no encontrado.")
    db.delete(spot)
    db.commit()


def _normalize_method_contexts(method_contexts) -> dict:  # noqa: ANN001
    normalized = {method: dict(values) for method, values in DEFAULT_METHOD_CONTEXTS.items()}
    if not method_contexts:
        return normalized
    for method, values in method_contexts.items():
        if method not in normalized:
            continue
        if hasattr(values, "model_dump"):
            values = values.model_dump()
        normalized[method].update(values or {})
    return normalized

