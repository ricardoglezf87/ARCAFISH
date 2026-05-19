from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import FishingSpot
from app.services.forecast_service import ForecastService, ProviderUnavailableError


router = APIRouter(prefix="/api/spots", tags=["forecast"])


@router.get("/{spot_id}/forecast")
async def get_forecast(
    spot_id: int,
    force_refresh: bool = Query(default=False),
    db: Session = Depends(get_db),
) -> dict:
    spot = db.get(FishingSpot, spot_id)
    if spot is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Punto no encontrado.")

    service = ForecastService(db)
    try:
        return await service.get_forecast(spot, force_refresh=force_refresh)
    except ProviderUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

