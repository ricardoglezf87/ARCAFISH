# ARCAFISH

ARCAFISH es una aplicacion web en Python para estimar ventanas de pesca desde costa en Canarias. Permite guardar puntos, consultar una prediccion de hasta 7 dias, ver un score general de pesca y comparar scores por especie con ajuste estacional por mes.

## Stack

- FastAPI + Jinja2
- SQLite + SQLAlchemy
- Leaflet + OpenStreetMap + capa satelite Esri
- Open-Meteo Weather API
- Open-Meteo Marine API
- Calculo astronomico local aproximado para amanecer, atardecer y fase lunar

## Instalacion

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

## Ejecucion

```bash
uvicorn app.main:app --reload
```

Abre `http://127.0.0.1:8000`.

En Windows tambien puedes ejecutar `run_arcafish.bat`. El script crea `.venv` si hace falta, instala dependencias, crea `.env` desde `.env.example`, abre el navegador y arranca el servidor.

## Variables de entorno

Las principales estan en `.env.example`:

- `DATABASE_URL`: por defecto `sqlite:///./arcafish.db`
- `FORECAST_DAYS`: dias de prediccion, por defecto `7`
- `FORECAST_CACHE_TTL_MINUTES`: duracion del cache
- `HTTP_VERIFY_SSL`: dejalo en `true`; si tu Python local falla con certificados, para desarrollo puedes usar `false`
- `AEMET_API_KEY`, `STORMGLASS_API_KEY`, `WORLDTIDES_API_KEY`: reservadas para proveedores futuros

En Windows, `tzdata` es necesario para que Python reconozca `Atlantic/Canary`.

## APIs utilizadas

- Open-Meteo Weather: `https://open-meteo.com/en/docs`
- Open-Meteo Marine: `https://open-meteo.com/en/docs/marine-weather-api`

Open-Meteo no requiere clave en el MVP. La marea se deriva de `sea_level_height_msl`, por lo que ayuda a decidir ventanas de pesca, pero no sustituye tablas oficiales ni debe usarse para navegacion.

## Scoring

El sistema calcula:

- un score general de costa
- un score por especie
- un factor estacional mensual por especie

Cada score combina viento, rachas, oleaje, periodo, lluvia, presion, tendencia de presion, marea, luz, nubosidad, temperatura del agua, temperatura ambiente y fase lunar. En especies concretas se aplica ademas un multiplicador mensual de estacionalidad.

Categorias:

- `0-39`: Mala
- `40-59`: Regular
- `60-79`: Buena
- `80-100`: Muy buena

## Tests

```bash
pytest
```

## Limitaciones del MVP

- La marea es derivada, no oficial
- No se calcula todavia la orientacion real de costa ni viento onshore/offshore
- Los multiplicadores estacionales son una base inicial y deben calibrarse con historico local
- No hay todavia capas animadas tipo Windy

## Proximas mejoras naturales

- Validacion con historicos reales de capturas
- Ajuste de pesos por isla, fondo y modalidad
- Integracion con AEMET y mareas oficiales
- PostGIS para geometria de costa y exposicion al oleaje
