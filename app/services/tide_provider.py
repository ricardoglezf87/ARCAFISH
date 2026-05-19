from dataclasses import dataclass


@dataclass(frozen=True)
class TideInfo:
    state: str
    height_m: float | None
    confidence: str


class DerivedTideProvider:
    """Derives a tide trend from Open-Meteo sea-level model output.

    This is useful for fishing timing, but it is not an official tide table and must
    not be used for navigation or exposed-rock safety decisions.
    """

    min_change_m: float = 0.02

    def derive(self, times: list[str], sea_levels: list[float | None]) -> dict[str, TideInfo]:
        result: dict[str, TideInfo] = {}
        for index, time_value in enumerate(times):
            current = _safe_float(sea_levels[index] if index < len(sea_levels) else None)
            previous_value = self._nearest_value(sea_levels, index, direction=-1)
            next_value = self._nearest_value(sea_levels, index, direction=1)

            if current is None or previous_value is None or next_value is None:
                result[time_value] = TideInfo("sin datos", current, "baja")
                continue

            if previous_value < current > next_value:
                state = "pleamar"
            elif previous_value > current < next_value:
                state = "bajamar"
            else:
                delta = next_value - previous_value
                if abs(delta) < self.min_change_m:
                    state = "estable"
                elif delta > 0:
                    state = "subiendo"
                else:
                    state = "bajando"
            result[time_value] = TideInfo(state, current, "media")
        return result

    @staticmethod
    def _nearest_value(values: list[float | None], start: int, direction: int) -> float | None:
        index = start + direction
        while 0 <= index < len(values):
            value = _safe_float(values[index])
            if value is not None:
                return value
            index += direction
        return None


def _safe_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None

