from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import FishingSpot
from app.schemas import FishingSpotCreate, FishingSpotRead


router = APIRouter(prefix="/api/spots", tags=["spots"])


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
    )
    db.add(spot)
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

