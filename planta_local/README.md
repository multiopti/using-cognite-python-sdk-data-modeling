# Servidor de planta — apps de producción fuera de CDF

Publica en la red de la planta las mismas apps de Streamlit que corren en Cognite Data Fusion
(Fusion), para verlas en el televisor de planta y en las PCs de los operadores, sin iniciar
sesión en Fusion.

| Qué | Dirección | Para quién |
|---|---|---|
| Rotación Línea 1 / Línea 3 | `http://<servidor>:8500/tv.html` | Televisor de planta |
| Línea 1 - Vista de Planta | `http://<servidor>:8501` | Cualquiera |
| Línea 3 - Vista de Planta | `http://<servidor>:8502` | Cualquiera |
| Reporte de Producción | `http://<servidor>:8503` | PCs de los operadores (solo lectura) |

Los datos se actualizan solos cada 60 segundos. Cada operador conserva los filtros que eligió
(fecha, máquina, turno).

## Cómo funciona

- `run_app.py` ejecuta el `main.py` de cada app **sin modificarlo**. Por eso una mejora en una
  app sirve a la vez en Fusion y en planta. Fusion permite `await` al nivel principal del
  script y el Streamlit normal no; el lanzador compila el script para permitirlo.
- `planta_server.py` arranca las tres apps y la página del TV, y reinicia cualquiera que se
  caiga. Escribe los logs en `planta_local\logs\`.
- `tv\tv.html` alterna a pantalla completa entre Línea 1 y Línea 3. Cada vista se recarga
  mientras está oculta, así el TV nunca muestra una pantalla de "cargando".
- Las apps se conectan a CDF con la cuenta de servicio de `cognite-sdk\.env`. Los operadores
  no inician sesión, por eso el Reporte de Producción se publica **en solo lectura**: no permite
  editar observaciones.

## Requisitos del servidor

- Windows 10/11 o Windows Server, encendido de forma permanente y en la red de la planta.
- Salida a internet hacia `https://aw-was-gp-001.cognitedata.com` y hacia el proveedor de
  identidad de la cuenta de servicio. Si la planta usa proxy, configúralo para la cuenta SYSTEM.
- Python 3.11 o superior (https://www.python.org, con la opción "Add to PATH").
- La carpeta `cognite-sdk` completa (este repositorio) y el archivo `cognite-sdk\.env` con las
  credenciales de CDF. Lo ideal es una cuenta de servicio **de solo lectura** (series de tiempo
  y eventos).

## Instalación

1. Copia la carpeta `cognite-sdk` al servidor, por ejemplo en `C:\planta\cognite-sdk`, y coloca
   el `.env`.
2. Abre PowerShell **como Administrador** y ejecuta:
   ```powershell
   cd C:\planta\cognite-sdk
   powershell -ExecutionPolicy Bypass -File planta_local\install_service.ps1
   ```
   El script crea el entorno de Python, abre los puertos 8500–8503 en el firewall y registra la
   tarea programada **"Planta - Servidor Streamlit"**. Esa tarea arranca el servidor al encender
   el equipo y lo reinicia si se detiene. Al terminar muestra las direcciones con la IP del
   servidor.
3. Comprueba que las cuatro direcciones abren desde otra PC de la red.

Para desinstalar: `planta_local\uninstall_service.ps1` (como Administrador).

## Televisor

- **Con una mini-PC conectada por HDMI (recomendado):** crea un acceso directo en el inicio
  automático de Windows con:
  ```
  "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" --kiosk "http://<servidor>:8500/tv.html" --edge-kiosk-type=fullscreen --no-first-run
  ```
  Edge abre en pantalla completa, sin barras ni menús.
- **Smart TV con navegador:** abre `http://<servidor>:8500/tv.html` y pon el navegador en
  pantalla completa. Algunos navegadores de TV no aceptan bien páginas dentro de otras; si falla,
  usa una mini-PC.

Opciones de la página del TV (se agregan al final de la dirección):

| Opción | Efecto | Ejemplo |
|---|---|---|
| `s` | Segundos en cada vista (30 por defecto) | `tv.html?s=45` |
| `ports` | Qué apps rotar | `tv.html?ports=8501,8502,8503` |
| `vw`, `vh` | Tamaño virtual de cada vista antes de ajustarla a la pantalla | `tv.html?vh=1250` |

## Configuración

En `planta_server.py`:

- `REFRESH_S`: cada cuántos segundos se actualizan los datos (60 por defecto).
- `APPS`: qué apps se publican, en qué puerto y si son de solo lectura.

Después de cambiarlo, reinicia la tarea: `Restart-ScheduledTask "Planta - Servidor Streamlit"`
(o reinicia el servidor).

## Si algo no funciona

- **No abre ninguna dirección:** revisa que la tarea esté en ejecución
  (`Get-ScheduledTask "Planta - Servidor Streamlit"`) y el firewall.
- **Una app muestra un error de CDF:** revisa `planta_local\logs\<app>.log`. Lo habitual es que
  el `.env` esté incompleto o que falte la salida a internet o el proxy.
- **Todos los valores en 0:** las máquinas no están enviando datos válidos a CDF (falla de red o
  del PLC en planta). Las apps muestran correctamente lo que hay en CDF. Puedes comprobarlo en la
  misma app dentro de Fusion.
