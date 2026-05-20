from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import FishingSpot
from app.services.forecast_export import build_forecast_pdf, pdf_filename
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


@router.get("/{spot_id}/forecast/export")
async def export_forecast_pdf(
    spot_id: int,
    day: str = Query(default="all"),
    species_scope: str = Query(default="selected"),
    species_id: str = Query(default="general"),
    interval_hours: int = Query(default=3, ge=1, le=12),
    force_refresh: bool = Query(default=False),
    db: Session = Depends(get_db),
) -> Response:
    spot = db.get(FishingSpot, spot_id)
    if spot is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Punto no encontrado.")
    if species_scope not in {"selected", "all"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="species_scope invalido.")
    if day != "all":
        try:
            parts = day.split("-")
            if len(parts) != 3:
                raise ValueError
            int(parts[0]), int(parts[1]), int(parts[2])
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="day debe ser YYYY-MM-DD o all.") from exc

    service = ForecastService(db)
    try:
        forecast = await service.get_forecast(spot, force_refresh=force_refresh)
    except ProviderUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    pdf_bytes = build_forecast_pdf(
        forecast=forecast,
        selected_day=day,
        species_scope=species_scope,
        species_id=species_id,
        interval_hours=interval_hours,
    )
    filename = pdf_filename(forecast, day, species_scope, species_id)
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return Response(content=pdf_bytes, media_type="application/pdf", headers=headers)

