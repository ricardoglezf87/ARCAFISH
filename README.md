# ARCAFISH

ARCAFISH es un MVP web en Python para estimar ventanas de pesca desde costa en las Islas Canarias. Permite guardar puntos en un mapa, consultar previsión horaria y obtener un score heurístico de pesca de 0 a 100 con explicación y alertas básicas de seguridad.

## Stack

- FastAPI + Jinja2
- SQLite + SQLAlchemy
- Leaflet + OpenStreetMap
- Open-Meteo Weather API para meteorología
- Open-Meteo Marine API para oleaje, temperatura superficial y nivel del mar
- Cálculo astronómico local aproximado para amanecer, atardecer y fase lunar

## Instalación

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

## Ejecución

```bash
uvicorn app.main:app --reload
```

Abre `http://127.0.0.1:8000`.

En Windows también puedes hacer doble clic en `run_arcafish.bat`. El script crea `.venv` si no existe, instala dependencias, copia `.env.example` a `.env` si hace falta y arranca el servidor.

## Variables de entorno

Las variables principales están en `.env.example`:

- `DATABASE_URL`: por defecto `sqlite:///./arcafish.db`.
- `FORECAST_DAYS`: días de previsión. El MVP usa 3.
- `FORECAST_CACHE_TTL_MINUTES`: duración del cache de previsiones.
- `HTTP_VERIFY_SSL`: déjalo en `true`. En algunos entornos corporativos o Python local sin CA correcta puede requerirse `false` para desarrollo, aceptando el riesgo de no verificar TLS.
- `AEMET_API_KEY`, `STORMGLASS_API_KEY`, `WORLDTIDES_API_KEY`: preparadas para proveedores futuros.

## APIs utilizadas

- Open-Meteo Weather: `https://open-meteo.com/en/docs`
- Open-Meteo Marine: `https://open-meteo.com/en/docs/marine-weather-api`

Open-Meteo no requiere clave para uso no comercial básico. La API marina ofrece `wave_height`, `wave_period`, `wave_direction`, `sea_surface_temperature` y `sea_level_height_msl`. En este MVP, el estado de marea se deriva de la tendencia de `sea_level_height_msl`; esto no sustituye tablas oficiales ni sirve para navegación.

AEMET OpenData es una opción natural para España/Canarias, pero requiere API key. Queda preparada como proveedor futuro para predicción oficial y avisos.

## Modelo de datos

- `FishingSpot`: nombre, latitud, longitud, notas y fecha de creación.
- `ForecastCache`: cache por punto/proveedor con JSON normalizado, fecha de creación y expiración.

La estructura se puede migrar a PostgreSQL/PostGIS sustituyendo `DATABASE_URL` y añadiendo geometrías reales para costa, exposición a oleaje y distancia al punto marino más cercano.

## Scoring

El score inicial es heurístico y explicable, no una predicción científica cerrada. Considera:

- viento y rachas;
- altura, periodo y dirección de ola;
- lluvia;
- temperatura;
- presión y tendencia;
- marea derivada;
- fase lunar;
- amanecer, atardecer, día/noche;
- límites de seguridad por viento y oleaje.

Categorías:

- `0-39`: Mala
- `40-59`: Regular
- `60-79`: Buena
- `80-100`: Muy buena

Si hay condiciones peligrosas, el score queda limitado aunque otros factores sean favorables.

## Tests

```bash
pytest
```

## Limitaciones del MVP

- La marea se infiere de un modelo de nivel del mar; no es una tabla oficial de mareas.
- No se calcula todavía la orientación real de costa ni si el viento/oleaje entra de cara en el pesquero.
- No distingue especie objetivo.
- No incluye avisos oficiales AEMET ni capas animadas tipo Windy.
- Leaflet usa teselas de OpenStreetMap, por lo que el mapa necesita conexión a internet.

## Próximas mejoras

- Adaptador AEMET con avisos y predicción oficial.
- Adaptador WorldTides/Stormglass para mareas verificadas si se configura API key.
- PostGIS con geometría de costa para viento onshore/offshore y exposición al oleaje.
- Perfiles por especie, modalidad y tipo de fondo.
- Capas meteorológicas: viento, lluvia, oleaje y alertas.
- PWA con favoritos, exportación y uso móvil en costa.
