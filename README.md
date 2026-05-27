# ARCAFISH

ARCAFISH es una aplicacion web en Python para estimar ventanas de pesca desde costa en Canarias. Permite guardar puntos, consultar una prediccion de hasta 7 dias, ver un score general de pesca y comparar scores por especie con ajuste estacional por mes.

Tambien permite exportar a PDF la vista actual del pronostico o todas las especies para el dia o semana que tengas seleccionado.

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
uvicorn app.main:app --host 0.0.0.0 --port 6990 --reload
```

Abre `http://127.0.0.1:6990` desde el propio equipo servidor.

En Windows tambien puedes ejecutar `run_arcafish.bat`. El script crea `.venv` si hace falta, instala dependencias, crea `.env` desde `.env.example`, abre el navegador y arranca el servidor. Por defecto escucha en `0.0.0.0:6990`; puedes cambiarlo definiendo `ARCAFISH_HOST` o `ARCAFISH_PORT` antes de ejecutar el BAT.

Ejemplo para dejarlo solo local:

```bat
set ARCAFISH_HOST=127.0.0.1
set ARCAFISH_PORT=6990
run_arcafish.bat
```

## Acceso desde fuera

Para entrar desde Internet no basta con redirigir el puerto del router: la aplicacion tambien debe escuchar en la interfaz de red. Por eso el arranque usa `--host 0.0.0.0`.

Checklist de red:

- Fija la IP local del equipo servidor, idealmente con reserva DHCP en el router.
- Redirige en el router el puerto TCP externo `6990` hacia `IP_LOCAL_DEL_SERVIDOR:6990`.
- Permite el puerto TCP `6990` en el firewall de Windows del equipo servidor.
- Comprueba que la IP WAN del router coincide con tu IP publica. Si no coincide, probablemente estas bajo CG-NAT y necesitaras pedir IP publica al operador o usar una VPN tipo Tailscale/ZeroTier/WireGuard.
- Ten en cuenta que ARCAFISH no tiene autenticacion todavia. Para exponerlo a Internet de forma continuada, es mas seguro usar VPN o poner delante un proxy con HTTPS y autenticacion.

## Uso rapido

1. Guarda o selecciona un punto.
2. Ajusta el dia desde las pestanas de la tabla.
3. Cambia el intervalo horario a 1 h, 3 h, 6 h o el valor que prefieras.
4. Selecciona una especie concreta o deja `General costa`.
5. Exporta `PDF vista actual` o `PDF todas las especies`.

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

## Rendimiento de pronosticos

El servicio cachea cada punto durante `FORECAST_CACHE_TTL_MINUTES` y pide Weather + Marine en paralelo para reducir la espera en cargas nuevas. Si necesitas que responda aun mas rapido, reduce `FORECAST_DAYS` a `3` o `5` en `.env`; la primera carga pedira menos datos y las siguientes usaran cache mientras no fuerces refresco.

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
