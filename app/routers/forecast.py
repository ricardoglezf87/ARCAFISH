from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import FishingSpot
from app.services.forecast_export import build_forecast_pdf, pdf_filename
from app.services.forecast_service import ForecastService, ProviderUnavailableError
from app.services.fishing_score import build_fishing_context


router = APIRouter(prefix="/api/spots", tags=["forecast"])

FishingMethod = Literal["float", "bottom", "spinning", "lure_trolling_like"]
TargetZone = Literal["shoreline", "shore_break", "inner_reef", "outer_reef", "deep_cast"]
WaterColumn = Literal["surface", "mid_water", "bottom"]
SpotType = Literal["rocky", "mixed", "sandy", "reef", "harbor"]
ShoreType = Literal["volcanic", "beach", "pier", "cliff"]
SpotExposure = Literal["sheltered", "semi_exposed", "exposed"]


@router.get("/{spot_id}/forecast")
async def get_forecast(
    spot_id: int,
    force_refresh: bool = Query(default=False),
    fishing_method: FishingMethod = Query(default="float"),
    casting_distance_m: float = Query(default=20, ge=0, le=200),
    target_zone: TargetZone | None = Query(default=None),
    water_column: WaterColumn | None = Query(default=None),
    spot_type: SpotType = Query(default="rocky"),
    shore_type: ShoreType = Query(default="volcanic"),
    spot_exposure: SpotExposure = Query(default="semi_exposed"),
    water_depth_estimate_m: float | None = Query(default=None, ge=0, le=200),
    db: Session = Depends(get_db),
) -> dict:
    spot = db.get(FishingSpot, spot_id)
    if spot is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Punto no encontrado.")

    service = ForecastService(db)
    fishing_context = build_fishing_context(
        fishing_method=fishing_method,
        casting_distance_m=casting_distance_m,
        target_zone=target_zone,
        water_column=water_column,
        spot_type=spot_type,
        shore_type=shore_type,
        spot_exposure=spot_exposure,
        water_depth_estimate_m=water_depth_estimate_m,
    )
    try:
        return await service.get_forecast(spot, force_refresh=force_refresh, fishing_context=fishing_context)
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
    fishing_method: FishingMethod = Query(default="float"),
    casting_distance_m: float = Query(default=20, ge=0, le=200),
    target_zone: TargetZone | None = Query(default=None),
    water_column: WaterColumn | None = Query(default=None),
    spot_type: SpotType = Query(default="rocky"),
    shore_type: ShoreType = Query(default="volcanic"),
    spot_exposure: SpotExposure = Query(default="semi_exposed"),
    water_depth_estimate_m: float | None = Query(default=None, ge=0, le=200),
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
    fishing_context = build_fishing_context(
        fishing_method=fishing_method,
        casting_distance_m=casting_distance_m,
        target_zone=target_zone,
        water_column=water_column,
        spot_type=spot_type,
        shore_type=shore_type,
        spot_exposure=spot_exposure,
        water_depth_estimate_m=water_depth_estimate_m,
    )
    try:
        forecast = await service.get_forecast(spot, force_refresh=force_refresh, fishing_context=fishing_context)
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

