# DisplayPad for Mac

Usa el **Mountain DisplayPad** (USB `3282:0009`) en macOS sin BaseCamp: una imagen o
animación en cada una de las 12 teclas, varias páginas y una o varias acciones por tecla
(abrir apps, atajos de teclado, texto, teclas multimedia, macros, scripts, brillo de las
pantallas). Funciona como un servicio en segundo plano, con un **configurador gráfico**
en el navegador y un **servidor MCP** opcional para que un asistente de IA te ayude a
configurar tus teclas.

[English](README.md)

![El configurador al abrirse: el DisplayPad sube en el centro de la pantalla, se encienden sus 12 teclas y vuela a su lugar en la página](docs/intro.gif)

> **Hecho con IA.** Este proyecto se escribió con [Claude Code](https://claude.com/claude-code)
> (el asistente de programación con IA de Anthropic), dirigido y probado por una persona en
> un DisplayPad real. Ver [Hecho con IA](#hecho-con-ia).

## Funciones

- **12 teclas con imagen:** emoji, PNG/JPG, GIF/WebP/APNG animado o **Lottie**
  (`.json`, `.lottie`, `.tgs`), con texto, colores y tamaño del ícono de 30 % a 200 %.
  Puedes **ocultar el texto de una tecla** sin borrarlo.
- **Fondos degradados y efectos al pulsar:** el fondo de una tecla puede ser un color liso,
  un degradado de dos o tres colores, un degradado que no deja de moverse u olas que
  ruedan, con degradados listos para empezar. Un efecto al pulsar (onda, destello, brillo,
  chispas, reflejo o rebote) se reproduce sobre la tecla en el pad cada vez que la pulsas.
- **Tablero de sonidos:** una tecla puede reproducir un archivo de sonido de tu Mac (MP3,
  M4A, WAV, AIFF, CAF o FLAC) con su propio volumen, y un anillo alrededor de la tecla
  muestra cuánto lleva. **Nueva página → Tablero de sonidos** crea de una vez una página
  de teclas de sonido con una tecla para detener.
- **Las imágenes nunca se estiran:** las teclas son cuadradas, así que una imagen ancha o
  alta abre un editor de encuadre donde la mueves y la acercas para elegir la parte que
  muestra la tecla, o la muestras completa. Funciona igual con GIF y Lottie.
- **Carpetas:** cualquier tecla puede ser una carpeta con 11 teclas más, y puedes poner
  carpetas dentro de carpetas. La tecla 1 de una carpeta siempre te lleva atrás.
- **Páginas:** todas las que quieras, con tecla «Volver» y página inicial.
- **Páginas que se abren con apps (perfiles):** vincula una página a apps y el pad cambia
  a ella solo, mientras la app está abierta o mientras está al frente, y vuelve cuando la
  app ya no está.
- **Acciones:** abrir una app, web o carpeta, y una web en el navegador que elijas, en una
  pestaña o ventana nueva, o volver a la pestaña donde ya está abierta; atajos de teclado; escribir texto;
  reproducir/pausar, volumen y otras teclas multimedia; reproducir sonidos; comandos de terminal; AppleScript;
  cambiar de página; brillo de las pantallas del Mac (la integrada y las externas por
  DDC/CI) y del pad; pausas entre acciones. Varias acciones por tecla, en orden.
- **OBS Studio:** iniciar y detener la transmisión, la grabación y la cámara virtual,
  cambiar de escena y silenciar micrófonos directamente por el servidor WebSocket de OBS,
  aunque OBS esté en segundo plano y sin configurar atajos en OBS.
- **Teclas en vivo:** una tecla puede mostrar algo que va cambiando y redibujarse sola:
  la hora y la fecha, el uso de CPU, GPU y memoria, la batería, el volumen y el
  micrófono, lo que suena en Música o Spotify, si OBS está en vivo o grabando, o la
  salida de un comando. Como texto, o como un medidor con el número, el último minuto
  como una línea y una barra que se pone ámbar y roja.
- **Macros:** graba lo que haces con el teclado y el mouse (teclas, clics, arrastres,
  desplazamiento), edita los pasos y las esperas, y reprodúcelo desde una tecla una vez,
  varias veces, mientras mantienes la tecla, o encendido y apagado con cada pulsación.
- **Configurador:** arrastra teclas para intercambiarlas, suelta imágenes sobre ellas,
  graba atajos (una sola tecla, o los modificadores izquierdo y derecho por separado) o
  elígelos en un teclado en pantalla, y prueba las acciones antes de guardar. En inglés y español, claro y oscuro.
- **Asistentes de IA (MCP):** Claude, Cursor, VS Code o cualquier app MCP de tu Mac puede
  leer y cambiar tu configuración si lo permites. Desactivado por defecto.
- **Servicio:** arranca al iniciar sesión, se reconecta solo después de dormir el Mac o
  desconectar el pad, y recarga la configuración en cuanto cambia.

## Requisitos

- macOS. Probado en macOS 27.2 con Apple Silicon; en Mac con Intel debería funcionar,
  pero no se ha probado.
- [Homebrew](https://brew.sh) y Python 3.11 o superior (`brew install python@3.14`).
- Si falta `libusb`, el instalador lo instala con Homebrew.

## Instalación

Descarga el zip de la [última versión](../../releases/latest) y descomprímelo, o clona el
repositorio. Luego, en Terminal:

```bash
cd displaypad-mac
./install.sh
```

El instalador:

- copia el programa a `~/Library/Application Support/DisplayPadMac/`;
- prepara su entorno de Python;
- registra un servicio que arranca al iniciar sesión y se reinicia si falla
  (`~/Library/LaunchAgents/com.displaypadmac.agent.plist`);
- agrega la app **DisplayPad** a Aplicaciones. Abre el configurador.

Vuelve a ejecutar `./install.sh` para actualizar. Tu configuración se conserva.

### Permisos

macOS pide dos permisos para **Python**. El instalador muestra la ruta del `Python.app`
que los necesita.

- **Monitoreo de entrada:** sin él, el servicio no puede activar el DisplayPad.
- **Accesibilidad:** lo necesitan las acciones de atajo, texto, teclas multimedia y macro,
  y para grabar atajos que usa macOS.

Si macOS no lo pide, abre *Ajustes del Sistema → Privacidad y seguridad*, abre la
sección, pulsa **+** y elige ese `Python.app`. Después pulsa **Restart service**
(Reiniciar servicio) en el configurador.

### Desinstalar

```bash
./uninstall.sh
```

Agrega `--all` para borrar también tu configuración e imágenes.

## El configurador

Ábrelo con la app **DisplayPad** (Aplicaciones, Launchpad o Spotlight), con la tecla
**⚙️ Configure** del pad o con `python -m displaypad_mac configure`.

El idioma por defecto es inglés: cámbialo a español en **Settings → Language**.

![El configurador: las 12 teclas de una página a la izquierda y el editor de la tecla 1 a la derecha](docs/configurator-keys.png)


- **Páginas:** pestañas arriba. Crea, renombra y elimina páginas, marca la página inicial
  (★) o muéstrala en el pad.
- **Páginas listas para apps:** **+ Página** y **+ Página de app** pueden empezar con una
  página vacía o con los 9 a 11 atajos más usados de una app popular:
  - **Navegadores:** Google Chrome, Microsoft Edge, Brave, Safari.
  - **Foto, video y sonido:** Photoshop, Illustrator, Premiere Pro, After Effects,
    Lightroom Classic, DaVinci Resolve, Final Cut Pro, Logic Pro, Blender, Audacity.
  - **Trabajo y chat:** Excel, Word, PowerPoint, Outlook, Slack, Discord, Zoom, Microsoft
    Teams.
  - **Más:** Spotify, Figma, VS Code, Xcode, Obsidian.
  - **OBS Studio:** en vivo, grabar, pausar, micrófono, cámara virtual y escenas 1 a 5,
    con la acción OBS (ver el editor de teclas más abajo). Se queda mientras OBS está
    abierto, así la usas desde tu juego u otra app.

  Las apps que tienes salen primero. La página aparece mientras la app está al frente, su
  tecla 12 vuelve atrás y cada tecla es un atajo normal que puedes cambiar. Al vincular una página a una de estas apps en **Abrir con apps…** también se
  ofrece añadir sus atajos en las teclas libres, sin reemplazar nada. Los atajos se envían
  por posición de tecla y evitan las teclas de puntuación, así que funcionan también con
  otras distribuciones de teclado.
- **Abrir con apps…:** elige las apps que muestran la página actual en el pad, como un
  perfil de Base Camp, y cuándo:
  - **Mientras la app está abierta:** la página aparece cuando la app se abre y se va
    cuando la cierras.
  - **Mientras la app está al frente:** la página aparece cada vez que pasas a la app y
    se va cuando cambias a otra.

  Cuando la página se va, el pad vuelve a lo que mostraba antes, salvo que lo hayas
  cambiado a otra página mientras tanto. El configurador muestra dos pads: **Páginas**, a
  las que vas tú, y debajo **⚡ Páginas de apps**, las vinculadas, cada uno con sus
  pestañas (con el nombre de la app cuando el de la página no lo dice). Haz clic en una
  tecla de cualquiera de los dos para editar esa página; arrastra una tecla al otro pad
  para moverla allí. Los nombres de las apps se comparan sin el año, así que una página vinculada a
  "Adobe Photoshop" sigue funcionando cuando llega "Adobe Photoshop 2027". Nada cambia
  hasta que pulsas **Guardar**.
- **Teclas:** haz clic en una para editarla. Arrastra una tecla sobre otra para
  intercambiarlas, o suelta una imagen o un archivo de sonido sobre ella. Copia y pega teclas entre páginas.
- **El editor de la tecla:** la vista previa y el **Nombre** de la tecla quedan arriba; lo
  demás va en pestañas: **Estilo** (ícono, tamaño, fondo y efecto al pulsar), **Acciones** (lo que hace la
  tecla; la pestaña muestra cuántas tiene), **Carpeta** y **En vivo**. La barra de pestañas queda a la
  vista al desplazarte, y el editor recuerda la pestaña en la que estabas al elegir otra
  tecla.
- **Carpetas:** en la pestaña **Carpeta**, **Convertir esta tecla en carpeta** y luego
  **Abrir carpeta ›** (o doble clic en la tecla). Dentro, la tecla 1 es una tecla
  **Volver** fija y la ruta de arriba (`inicio › Trabajo`) te lleva hacia arriba. Para
  mover una tecla a una carpeta, arrástrala y mantenla sobre la carpeta hasta que se abra,
  y suéltala donde quieras. Igual con **Volver**, un paso de la ruta o la pestaña de una
  página; si la sueltas justo encima, va a la primera tecla libre de ahí. En el pad, al
  pulsar una tecla carpeta se abre.
- **Estilo:** emoji, imagen o solo texto; tamaño del ícono y colores. El selector de emojis
  tiene tus emojis recientes y un grupo sugerido; **Ver todos los emojis** abre todos los
  que tiene tu Mac (unos 1.900), por grupos. Busca por nombre en español o inglés, con o
  sin tildes, y elige un tono de piel. Los nombres vienen del propio macOS y el navegador
  los ordena y agrupa, así que no se descarga nada y todo lo que ofrece el selector, el pad
  lo puede dibujar.
  Marca **Ocultar el nombre en la tecla** (debajo del nombre) para conservar el nombre sin
  dibujarlo. En **Fondo** elige **Liso**, **Degradado**, **En movimiento** u **Olas** (ver
  [Fondos y efectos al pulsar](#fondos-y-efectos-al-pulsar)); en **Al pulsar** elige un
  efecto y **▶ Probar** para verlo en la vista previa.
  La vista previa es exactamente lo que dibuja el pad.
- **Ajustar encuadre:** al añadir una imagen o animación que no es cuadrada, se abre una
  ventana donde la arrastras y la acercas o alejas (control, rueda del mouse, pellizco en
  el trackpad, o flechas y + / −) dentro de un cuadrado del tamaño de la tecla. **Imagen
  completa** la muestra entera con el color de la tecla alrededor; **Llenar la tecla**
  cubre la tecla con su centro. La imagen mantiene sus proporciones y el archivo original
  no cambia, así que puedes volver a encuadrarla con **Ajustar encuadre…** en **Imagen**,
  dentro de la pestaña Estilo.
- **Acciones:** varias por tecla, en orden. **Grabar** captura las teclas que pulses: una
  combinación como ⌘⇧4, una sola tecla como F13 o un modificador solo, y distingue la
  izquierda de la derecha (⌘ derecho se guarda como `rcmd`). Mientras graba, macOS y las
  demás apps no reaccionan a las teclas, así que los atajos del sistema como ⌘⇧4,
  ⌘Espacio, ⌘Tab o ⌘Q se graban completos en vez de ejecutarse. El teclado vuelve en
  cuanto sueltas las teclas, al hacer clic en otro sitio o a los 30 segundos. **Teclado…**
  abre un teclado en pantalla para elegir las teclas con el mouse, por ejemplo las del
  teclado numérico si el tuyo no lo tiene. **Mantener las teclas pulsadas mientras
  mantienes la tecla del pad** sirve para apps que reaccionan a una tecla mantenida, como
  el dictado de pulsar para hablar. **▶ Probar** ejecuta las acciones y muestra la salida o el error de los comandos
  de terminal y AppleScript.
- **Webs:** cuando una acción **Abrir** tiene una dirección web, puedes elegir el
  **Navegador** (el predeterminado del Mac o cualquiera instalado), abrirla en **Una pestaña
  nueva** (lo normal) o **Una ventana nueva**, y marcar **Si ya está abierta, ir a su
  pestaña**. Con eso, una tecla para `https://web.whatsapp.com` trae la pestaña de WhatsApp
  que ya tienes en vez de abrir otra: cuenta una pestaña cuya dirección empiece por la de la
  tecla, con lo que siga después, sin importar `http`/`https` ni `www.`. Safari, Chrome,
  Edge, Brave y Vivaldi pueden hacerlo todo; los demás navegadores (Firefox, Arc, Opera)
  abren la dirección como cualquier enlace. La primera vez, macOS pregunta si DisplayPad
  puede controlar el navegador. Si escribes una dirección sin más, como
  `web.whatsapp.com`, se le añade `https://`.
- **Macros:** agrega una acción **Macro (teclado y mouse)** y pulsa **● Grabar…**. Elige
  qué grabar (el teclado; los clics, arrastres y desplazamiento del mouse; y el movimiento
  del puntero si lo necesitas) y pulsa **Empezar a grabar**: tienes 3 segundos para
  cambiar a tu app. Haz lo que debe hacer la macro y luego pulsa cualquier tecla del
  DisplayPad (o **Detener** en el configurador). **Editar pasos…** muestra cada paso:
  cambia teclas, botones, posiciones y esperas, agrega o mueve pasos, o pon la misma
  espera en todo. **Reproducción** la reproduce una vez, varias veces, mientras mantienes
  la tecla del pad o de una pulsación a la siguiente; **Esperas** mantiene las grabadas,
  usa una espera fija o ninguna. **▶ Probar** la reproduce una vez a los 3 segundos, y
  mientras una macro se reproduce aparece un aviso con **Detener**.
- **OBS Studio:** agrega una acción **OBS Studio** y elige qué hace: iniciar o detener la
  transmisión, la grabación o la cámara virtual, pausar la grabación, cambiar a una
  escena, ir a la escena siguiente o anterior, silenciar o activar micrófonos, el modo
  estudio, la transición o guardar el búfer de repetición. Una escena es su nombre, o `#1`
  para la primera escena de la lista **Escenas** de OBS, `#2` para la segunda, etc., así
  una página sigue funcionando si renombras escenas. Deja la fuente de audio vacía para
  silenciar todos los micrófonos a la vez. El editor muestra tus escenas y fuentes y dice
  si OBS responde. En modo estudio, las teclas de escena cambian la vista previa. Primero
  configura la conexión en **Ajustes → OBS**.
- **En vivo:** elige lo que muestra la tecla (ver [Teclas en vivo](#teclas-en-vivo)). Para
  un número (CPU, memoria, batería…) elige **Texto** o **Medidor**. Los valores que puedes
  usar en el **Nombre** de la tecla, como `{time}` o `{value}`, son botones que los añaden
  donde está el cursor; el reloj tiene formatos rápidos. Las vistas previas de los dos
  pads se actualizan mientras las miras.
- **Guardar** (⌘S) revisa todo antes y te dice qué tecla tiene un problema. La versión
  anterior queda en `config.json.previous`.

Si otra cosa cambia la configuración con el configurador abierto (un asistente de IA, o
tú editando `config.json`), la página se recarga sola. Si tienes cambios sin guardar, te
pregunta qué versión conservar.

### Ajustes

La pestaña **Ajustes** aplica los cambios al momento:

- **Idioma:** English (por defecto) o Español.
- **Apariencia:** igual que macOS, clara u oscura.
- **DisplayPad:** brillo de las teclas, si una tecla se oscurece al pulsarla y las esquinas de
  las teclas. Las pantallas del pad son cuadradas, así que el servicio dibuja esquinas
  redondeadas en cada imagen, como las muestra el configurador (12 px por defecto; 0 las deja
  cuadradas).
- **OBS:** la conexión con OBS Studio para las teclas de OBS. En OBS, elige
  **Herramientas → Ajustes del servidor WebSocket**, marca **Habilitar servidor WebSocket**,
  pulsa **Mostrar información de conexión** y copia la **Contraseña del servidor** en
  **Contraseña**. **Guardar y conectar** la guarda y muestra la versión y las escenas de
  OBS, o por qué no se puede conectar. El puerto es 4455 salvo que lo hayas cambiado en OBS.
  La contraseña se guarda en `obs.json` junto a la configuración, legible solo por ti, y no
  se vuelve a mostrar en el configurador ni a los asistentes de IA.
- **Asistentes de IA (MCP):** ver abajo.
- **Acerca de:** versión, estado del servicio y de los permisos, y dónde están la
  configuración y el registro.

![La pestaña de Ajustes: idioma, apariencia, brillo y esquinas de las teclas del DisplayPad, y la conexión con OBS](docs/configurator-settings.png)

## Asistentes de IA (MCP)

DisplayPad for Mac incluye un servidor [Model Context Protocol](https://modelcontextprotocol.io).
Si lo permites, un asistente de IA de tu Mac puede ver tus páginas y teclas, crear nuevas,
buscar las apps que tienes instaladas, agregar imágenes y ver cómo quedan. Puedes pedirle
cosas como *«Agrega una página con mis apps de reuniones»* o *«Haz una tecla que me silencie
en Zoom»*.

1. Abre DisplayPad → **Ajustes** → **Asistentes de IA** y marca **Permitir que los
   asistentes de IA se conecten**.
2. Conecta tu asistente. La pestaña de Ajustes muestra estos ejemplos con tus propias rutas
   y un botón **Copiar**.

**Claude Code:**

```bash
claude mcp add --scope user displaypad -- "$HOME/Library/Application Support/DisplayPadMac/displaypad-mcp"
```

**Claude Desktop:** *Ajustes → Desarrollador → Editar configuración*, agrega la entrada y
reinicia Claude. Cambia `TU_USUARIO` por tu nombre de usuario de macOS:

```json
{
  "mcpServers": {
    "displaypad": {
      "command": "/Users/TU_USUARIO/Library/Application Support/DisplayPadMac/displaypad-mcp"
    }
  }
}
```

**Otras apps:**

- Apps que arrancan un programa local (stdio): usa el programa `displaypad-mcp` de arriba.
  Lee la clave de acceso por su cuenta.
- Apps que se conectan a una dirección (Streamable HTTP): usa `http://127.0.0.1:8765/mcp`
  y envía la clave de acceso de Ajustes en la cabecera `Authorization: Bearer <clave>`.

El servidor solo escucha en este Mac, así que los asistentes que funcionan en la nube y no
pueden llegar a `127.0.0.1` no podrán conectarse.

| Herramienta | Qué hace |
|---|---|
| `get_status` | Conexión, página actual, permisos |
| `get_reference` | Todos los campos de tecla y acciones, con ejemplos |
| `get_config`, `list_pages`, `get_key` | Leer la configuración |
| `set_key`, `clear_key` | Cambiar o vaciar una tecla |
| `create_page`, `rename_page`, `delete_page` | Gestionar páginas (los enlaces a una página renombrada o eliminada se actualizan) |
| `show_page` | Cambiar la página que muestra el pad |
| `link_page_to_apps` | Hacer que una página se abra sola con apps (abiertas o al frente) |
| `list_app_presets`, `add_app_preset` | Páginas listas con los atajos de apps populares y controles de OBS: crear una o añadir sus teclas a una página |
| `get_obs_info` | Si OBS responde, con sus escenas y fuentes de audio |
| `update_settings` | Brillo, oscurecer al pulsar, idioma, apariencia, página inicial |
| `list_apps` | Apps instaladas, para las acciones «abrir» y las páginas que se abren con apps |
| `list_browsers` | Los navegadores del Mac y el predeterminado, para las acciones «abrir» con una dirección web |
| `upload_image` | Agregar una imagen o animación desde un archivo o base64 |
| `upload_sound`, `list_sounds` | Agregar un sonido para teclas de sonido, o ver los ya agregados y los del Mac |
| `preview_page` | Imagen de una página tal como la dibuja el pad, con las teclas en vivo |
| `test_actions` | Ejecutar acciones al momento (solo si lo permites, ver abajo) |

**Seguridad**

- El servidor está apagado hasta que lo enciendes, solo escucha en `127.0.0.1`, exige la
  clave de acceso en cada petición y rechaza peticiones de páginas web.
- **Nueva clave** en Ajustes reemplaza la clave de acceso; los asistentes conectados dejan
  de funcionar hasta que les des la nueva (el programa `displaypad-mcp` la toma solo).
- Los asistentes guardan acciones en las teclas, y esas acciones se ejecutan cuando pulsas
  la tecla. Conecta solo asistentes de confianza y revisa las teclas nuevas que ejecutan
  comandos de terminal o AppleScript.
- **Permitir que los asistentes ejecuten acciones al momento** está desactivado por defecto.
  Mientras lo esté, `test_actions` no ejecuta nada, y un asistente no puede añadir una
  tecla en vivo que ejecute un comando nuevo (sí cualquier otro tipo de tecla en vivo).

## Animaciones (GIF y Lottie)

En **Imagen** puedes subir o arrastrar, además de fotos:

- **GIF animado**, WebP animado o PNG animado (APNG).
- **Lottie:** `.json`, `.lottie` (dotLottie) o `.tgs` (stickers de Telegram).

El DisplayPad no guarda animaciones: muestra la última imagen que recibió en cada tecla,
así que el servicio le envía los cuadros uno a uno. Medido en el pad:

- **Unas 52 imágenes por segundo en total** (unos 18 ms cada una), repartidas entre las
  teclas animadas de la página que se ve.
- Una tecla animada va a la velocidad del archivo: hasta 50 cuadros por segundo un GIF,
  25 un Lottie. Dos teclas Lottie caben a velocidad completa.
- Si las teclas animadas piden más de lo que el pad acepta, se saltan cuadros: cada
  animación conserva su velocidad real, pero se ve con menos fluidez.
- Mientras mantienes pulsada una tecla animada, se queda quieta y oscurecida (una tecla con
  efecto al pulsar reproduce su efecto y sigue moviéndose).
- Con el pad al límite, el servicio usa un 4 % de CPU.

Lo que subes se guarda en `icons/` como WebP animado, con el lado corto a 204 px como
máximo (para que el tamaño del ícono llegue a 200 %) y el largo a 408 px (para poder
encuadrar una animación ancha), y con 180 cuadros como máximo (si hay más, se quitan
cuadros intermedios). Los Lottie se dibujan con rlottie a 25 cuadros por segundo. Algunas
funciones de After Effects (expresiones, efectos, capas de texto) pueden no dibujarse; si
un Lottie sale sin movimiento, el configurador te avisa: expórtalo como GIF.

## Fondos y efectos al pulsar

En la pestaña **Estilo** del editor de la tecla, **Fondo** tiene cuatro estilos:

- **Liso:** un solo color (lo de siempre).
- **Degradado:** dos o tres colores que se funden a lo largo de la tecla. **Dirección** lo
  gira (la flecha muestra hacia dónde va).
- **En movimiento:** los colores del degradado no dejan de fluir en esa dirección.
- **Olas:** franjas onduladas de los colores que ruedan por la tecla.

Elige uno de los degradados listos (Atardecer, Océano, Morado, Aurora, Fuego, Menta,
Caramelo, Neón, Durazno, Noche, Azul real) o tus propios colores; **+** agrega un tercer
color. **En movimiento** y **Olas** tienen **Velocidad** (lenta, normal, rápida). Se
reproducen en el pad como una animación, unas 15 imágenes por segundo cada una, y comparten
la velocidad del pad con las demás teclas animadas de la página (ver
[Animaciones](#animaciones-gif-y-lottie)), así que una página llena de teclas en movimiento
se mueve con menos fluidez. Con una imagen animada encima, las dos se reproducen juntas
(la velocidad del fondo se ajusta un poco para que se repitan a la vez).
Los medidores, y las teclas en vivo que se ponen ámbar o rojas, mantienen un color liso.

**Al pulsar** define un **efecto al pulsar**, que se reproduce sobre la tecla en el pad cada
vez que la pulsas, en lugar de oscurecerla:

| Efecto | Qué hace |
|---|---|
| Onda | Un anillo se abre desde el centro |
| Destello | La tecla se ilumina y se apaga |
| Brillo | Se ilumina el borde de la tecla |
| Chispas | Un destello y estrellitas que salen volando |
| Reflejo | Una franja de luz cruza la tecla |
| Rebote | La tecla se hunde y vuelve a salir |

Todos menos Rebote tienen color (blanco por defecto). El efecto se reproduce aunque
**Oscurecer la tecla mientras está presionada** esté desactivado en Ajustes. Una tecla que
abre una página o carpeta cambia al instante, así que su efecto se corta.

## Tablero de sonidos

Una tecla puede reproducir un sonido en tu Mac. Agrega una acción **Reproducir un sonido**
(en **Sonido**, en la lista de acciones) y dale un sonido:

- **Elegir archivo…** toma uno de tu Mac; también puedes soltar un archivo de sonido sobre
  la acción, o directamente sobre cualquier tecla del pad (una tecla sin aspecto toma el
  nombre del sonido y 🔊).
- **Elegir un sonido…** reutiliza un sonido que ya agregaste, o uno de los sonidos del
  propio Mac (Glass, Hero, Ping, Pop…).
- **Archivo en este Mac** enlaza un archivo esté donde esté (`~/Music/intro.mp3`).

Los archivos que eliges se copian a la carpeta `sounds` de DisplayPad, así la tecla sigue
funcionando aunque muevas o borres el original. Sirven MP3, M4A/AAC, WAV, AIFF, CAF y FLAC,
hasta 50 MB. **▶ Escuchar** lo reproduce en el Mac y **■ Detener** lo para.

Cada sonido tiene un **Volumen** (una parte del volumen del Mac) y una opción para cuando
pulsas la tecla otra vez mientras todavía suena: **Volver a empezar** (la opción normal),
**Detenerlo** o **Sonar otra copia encima**. Mientras un sonido suena, un anillo alrededor
de la tecla se va llenando, así ves qué está sonando y cuánto falta. La acción **Detener
todos los sonidos** lo para todo.

Los sonidos salen por la salida de sonido del Mac (la elegida en **Ajustes del Sistema →
Sonido**) y siguen sonando aunque cambies de página.

**Nueva página → Tablero de sonidos** arma una página completa de una vez: elige hasta 10
archivos de sonido (o ninguno, para empezar con 10 sonidos del Mac) y cada uno tiene una
tecla con su nombre, un fondo degradado y una onda al pulsar; la tecla 11 detiene todos los
sonidos y la 12 vuelve atrás.

## Teclas en vivo

Una tecla en vivo muestra un dato en lugar de un nombre fijo, y el servicio la redibuja
sola en el pad, solo cuando cambia lo que muestra. En el configurador, abre la pestaña
**En vivo** de la tecla; a mano, añade `"live"` a la tecla (ver
[Campos de la tecla](#editar-la-configuración-a-mano)).

| `source` | Qué muestra | Valores para el nombre | Se lee cada |
|---|---|---|---|
| `clock` | Hora y fecha | `{time}` (14:05), `{time12}` (2:05), `{ampm}`, `{seconds}`, `{weekday}`, `{day}`, `{month}`, `{year}`, `{date}` (vie 20 nov) | segundo |
| `cpu` | Uso de CPU, todos los núcleos | `{value}` | 2 s |
| `gpu` | Uso de GPU, como el Historial de la GPU del Monitor de Actividad | `{value}` | 2 s |
| `ram` | Memoria usada, como la cuenta el Monitor de Actividad | `{value}` (%), `{used}` (12.5 GB), `{total}` | 2 s |
| `battery` | Carga de la batería | `{value}`, `{state}` (cargando, con batería…) | 30 s |
| `volume` | Volumen de salida | `{value}`, `{state}` (silenciado) | 2 s |
| `mic` | Nivel de entrada del micrófono | `{value}`, `{state}` (silenciado) | 2 s |
| `music` | Lo que suena en Música o Spotify | `{title}`, `{artist}`, `{app}`, `{state}` | 3 s |
| `obs` | Transmisión y grabación de OBS Studio | `{status}` (EN VIVO · REC, Fuera del aire), `{scene}`, `{stream_time}`, `{record_time}` | 2 s |
| `command` | La salida de un comando de terminal | `{output}` (su primera línea), `{value}` (el primer número) | `every` segundos |

- **Texto** (por defecto) dibuja el **Nombre** de la tecla con los valores en su lugar,
  como `"{weekday} {day} {time}"`. Sin nombre muestra el dato solo (`{time}`,
  `CPU {value}%`, `{title}`…).
- **Medidor** (`"style": "meter"`, para CPU, GPU, memoria, batería, volumen, micrófono y
  comandos) dibuja el nombre como título, el número grande, el último minuto como una
  línea y una barra. La barra se pone ámbar al 70 % y roja al 90 %; la memoria sigue en
  cambio la presión de memoria de macOS, la batería se pone ámbar al 20 % y roja al
  10 % si no está cargando, y los medidores de volumen y micrófono se ponen grises
  mientras están silenciados. Se usan los colores de la tecla para el fondo y el texto.
- **Alerta:** las teclas de texto se ponen ámbar o rojas cuando el dato requiere atención
  (OBS en vivo o grabando, el micrófono silenciado, el sonido silenciado, CPU o GPU altas,
  la batería baja, un comando que falla). `"alert": false` lo desactiva.
- **Comandos:** se ejecutan con `zsh -l` cada `every` segundos (de 2 a 3600, 10 por
  defecto) y se detienen a los 10 segundos. Un medidor usa el primer número que imprime
  el comando, de 0 a 100. Un comando solo se ejecuta una vez guardada la tecla, y la vista
  previa del configurador muestra «guarda la tecla para ejecutar su comando» hasta
  entonces.
- **Lo que suena:** solo se consulta una app que ya está abierta, así que una tecla en
  vivo nunca abre Música ni Spotify. La primera vez, macOS pregunta si DisplayPad puede
  controlar la app; si dijiste que no, la tecla lo indica y puedes permitirlo en **Ajustes
  del Sistema → Privacidad y seguridad → Automatización**.
- **OBS** usa la conexión de **Ajustes → OBS** y solo se consulta mientras OBS está abierto.

Los datos solo se leen mientras una tecla en vivo está en el pad o abierta en el
configurador, cada fuente una vez para todas las teclas que la muestran. Las teclas en vivo
comparten con las animaciones las ≈ 52 imágenes por segundo del pad, pero una tecla en vivo
solo envía una imagen cuando cambia: un reloj una vez por minuto (una por segundo con
`{seconds}`), un medidor cada 2 segundos. Mientras mantienes pulsada una tecla en vivo se
queda quieta y oscurecida.

## Editar la configuración a mano

También puedes editar `~/Library/Application Support/DisplayPadMac/config.json`. **Se
recarga en cuanto lo guardas.** Las teclas van del 1 al 12: del 1 al 6 en la fila de arriba
y del 7 al 12 en la de abajo. [`config.example.json`](config.example.json) es un ejemplo
completo.

```json
{
  "language": "es",
  "theme": "system",
  "brightness": 80,
  "press_feedback": true,
  "corner_radius": 12,
  "mcp": {"enabled": false, "allow_run": false},
  "start_page": "inicio",
  "pages": {
    "inicio": {
      "keys": {
        "1": {"emoji": "📧", "label": "Outlook", "color": "#0B3A66",
              "action": {"type": "open", "target": "Microsoft Outlook"}},
        "2": {"image": "icons/logo.png", "label": "Captura", "hide_label": true,
              "actions": [{"type": "shortcut", "keys": "cmd+shift+4"}]}
      }
    }
  }
}
```

`corner_radius` redondea las esquinas de todas las imágenes de las teclas, en píxeles de la
cara de 102 píxeles: `0` es cuadrada, `12` es el valor por defecto, `51` es redonda.

Un reloj en vivo y un medidor de CPU:

```json
"3": {"label": "{weekday} {day}\n{time}", "color": "#1C1C24", "live": {"source": "clock"}},
"4": {"label": "CPU", "live": {"source": "cpu", "style": "meter"},
      "actions": [{"type": "open", "target": "Activity Monitor"}]}
```

**Páginas que se abren con apps:** una página puede tener `"apps"`, los nombres del `.app`
de cada app como los lista el configurador, y `"when"`: `"open"` (lo normal: se muestra
mientras una de ellas está abierta) o `"front"` (se muestra mientras una está al frente).
Por ejemplo: `"Photoshop": {"apps": ["Adobe Photoshop 2026"], "when": "front", "keys": {...}}`.
El servicio revisa las apps abiertas cada segundo y la app al frente cada 0,4 segundos, y
no necesita ningún permiso más para ello.

**Campos de cada tecla** (todos opcionales)

| Campo | Qué es |
|---|---|
| `emoji` | Un emoji, dibujado a color |
| `image` | Ruta a un PNG, JPG, GIF o WebP animado, relativa a la carpeta de la configuración (pon las imágenes en `icons/`). Los Lottie se convierten al subirlos en el configurador |
| `crop` | Solo imágenes. `[izquierda, arriba, derecha, abajo]`: la parte de la imagen que muestra la tecla, en fracciones de su ancho y alto (`[0.25, 0, 0.75, 1]` es el cuadrado central de una imagen 2:1). Los valores menores que 0 o mayores que 1 alejan la imagen y ahí se ve el color de la tecla (`[0, -0.5, 1, 1.5]` muestra completa una imagen 2:1). Nunca se estira: si el área no es cuadrada en píxeles, la imagen se centra en ella. Sin `crop`, el centro de la imagen cubre la tecla o, con texto o `fill: false`, se muestra la imagen completa. El configurador lo escribe por ti |
| `fill` | Solo imágenes. `true` (por defecto) hace que la imagen cubra toda la tecla si no se dibuja texto; `false` deja un margen |
| `icon_scale` | Tamaño del emoji o la imagen en %, de 30 a 200 (100 es el normal) |
| `label` | Texto. Se achica y parte en líneas para caber |
| `hide_label` | `true` conserva el texto sin dibujarlo |
| `color` | Color de fondo, por ejemplo `#1C1C24` |
| `text_color` | Color del texto |
| `background` | Un [fondo degradado](#fondos-y-efectos-al-pulsar): `{"style": "waves", "colors": ["#FC5C7D", "#6A82FB"]}`. `style`: `gradient`, `animated` (en movimiento), `waves` (olas) o `solid`; `colors`: 2 o 3; `angle`: grados, 0 es hacia arriba y 90 hacia la derecha (por defecto 135, olas 180); `speed`: de 0.25 a 4 para `animated` y `waves` (por defecto 1). Los medidores y las alertas siguen usando `color` |
| `press_effect` | Se reproduce sobre la tecla al pulsarla: `{"style": "ripple", "color": "#FFFFFF"}`. `style`: `ripple` (onda), `flash` (destello), `glow` (brillo), `sparkle` (chispas), `shine` (reflejo) o `bounce` (rebote); `color` es opcional |
| `action` / `actions` | Una acción, o una lista que se ejecuta en orden |
| `folder` | Convierte la tecla en carpeta: `{"keys": {"2": {...}, "3": {...}}}`, con las teclas 2 a 12 (la 1 es su tecla Volver). Una carpeta puede tener carpetas. Sus propias acciones, si tiene, se ejecutan antes de abrirla |
| `live` | La convierte en [tecla en vivo](#teclas-en-vivo): `{"source": "cpu", "style": "meter"}`. `source` es obligatorio; `style` es `text` (por defecto) o `meter`; `alert`: `false` mantiene los colores; una tecla `command` lleva además `command` y `every` (segundos). El `label` es el texto, con valores como `{time}` en su lugar |

**Acciones**

| `type` | Campos | Ejemplo |
|---|---|---|
| `open` | `target`: app, URL o carpeta. Para direcciones web: `browser` (el nombre de la app; por defecto, el navegador predeterminado), `new`: `"tab"` (por defecto) o `"window"`, `reuse_tab`: `true` va a la pestaña que ya la muestra | `"Microsoft Excel"`, `"~/Documents"`, `{"type": "open", "target": "https://web.whatsapp.com", "browser": "Google Chrome", "reuse_tab": true}` |
| `shortcut` | `keys`; `hold`: `true` las mantiene pulsadas mientras mantienes la tecla del pad | `"cmd+shift+4"`, `"f5"`, `"rcmd"`, `"ctrl+rshift"` |
| `text` | `text` (`\n` pulsa Enter) | `"Saludos cordiales,\n"` |
| `media` | `key` | `play_pause`, `next`, `previous`, `volume_up`, `volume_down`, `mute`, `brightness_up`, `brightness_down` |
| `shell` | `command` | `"say listo"` |
| `applescript` | `script` | `"display notification \"Hola\""` |
| `page` | `page`: nombre de página, o `back` | `"mas"` |
| `screen_brightness` | `value`: un nivel o `"+10"` / `"-10"`; `display`: `all`, `builtin` o `external` | `{"value": "-10", "display": "all"}` |
| `brightness` | `value`: brillo del propio pad, un nivel o `"+10"` / `"-10"` | `"+20"` |
| `delay` | `ms`: espera entre acciones | `250` |
| `macro` | `steps`; `play`: `once`, `repeat` (con `times`), `while_held` o `toggle`; `delays`: `recorded`, `fixed` (con `delay_ms`) o `none` | ver abajo |
| `configurator` | ninguno: abre el configurador | |
| `obs` | `do`: `stream`, `record`, `pause`, `scene` (con `scene`), `next_scene`, `previous_scene`, `mute` (con `source`, vacío para todos los micrófonos), `virtualcam`, `studio`, `transition`, `replay` | `{"do": "scene", "scene": "#2"}` |
| `sound` | `file`: en la carpeta de configuración (`sounds/...`) o en cualquier parte del Mac; `volume`: 0 a 100 (100 si no se indica); `play` al pulsar otra vez mientras suena: `restart` (normal), `toggle` u `overlap` | `{"file": "sounds/aplauso-1a2b3c.mp3", "volume": 80}` |
| `stop_sounds` | ninguno: detiene todos los sonidos | |

`screen_brightness` cambia la pantalla del MacBook (como F1/F2) y los monitores externos
por DDC/CI (activa DDC/CI en el menú del monitor si no responde).

`obs` habla con OBS Studio 28 o posterior por su servidor WebSocket (protocolo 5), con la
conexión de **Ajustes → OBS**. `stream`, `record`, `pause`, `virtualcam` y `studio` se
encienden y apagan con cada pulsación. Una `scene` es el nombre de una escena o `"#N"`, la
escena N desde arriba en la lista **Escenas** de OBS; `next_scene` y `previous_scene`
siguen esa lista y dan la vuelta. En modo estudio los cambios de escena van a la vista
previa y `transition` la pasa al programa.

Modificadores de `shortcut`: `cmd`, `shift`, `ctrl`, `alt`/`option`, `fn` (los de la
izquierda) y `rcmd`, `rshift`, `rctrl`, `ralt` (los de la derecha). Teclas: letras, números,
`f1` a `f20`, `return`, `tab`, `space`, `esc`, `delete`, `forwarddelete`, flechas (`up`,
`down`, `left`, `right`), `home`, `end`, `pageup`, `pagedown`, `help`, `section` (§), el
teclado numérico (`kp0` a `kp9`, `kpdecimal`, `kpplus`, `kpminus`, `kpmultiply`,
`kpdivide`, `kpequals`, `kpenter`, `kpclear`) y signos.

Un atajo también puede ser una sola tecla (`"f13"`) o modificadores solos (`"rcmd"`), para
apps que empiezan a escuchar cuando pulsas una tecla. Añade `"hold": true` para mantener
las teclas pulsadas mientras mantienes la tecla del pad; se sueltan cuando la sueltas
(como mucho a los 10 minutos). Sin esto, las teclas se pulsan y se sueltan enseguida.

```json
{"type": "shortcut", "keys": "rcmd", "hold": true}
```

Una macro es una lista de pasos que se reproducen en orden. El configurador los graba por
ti, pero también puedes escribirlos:

| Paso | Campos |
|---|---|
| `keys` | `keys`: un atajo completo, pulsado y soltado (`"cmd+c"`) |
| `key_down`, `key_up` | `key`: una tecla o modificador (`"rcmd"`, `"a"`) |
| `text` | `text`: se escribe tal cual |
| `click` | `button` (`left`, `right`, `middle`, `back`, `forward`), `count` (2 es doble clic), `x`, `y` |
| `mouse_down`, `mouse_up` | `button`, `x`, `y` |
| `move` | `x`, `y` (arrastra si hay un botón presionado) |
| `scroll` | `dy`, `dx` en píxeles (`dy` positivo desplaza hacia arriba), `x`, `y` |
| `wait` | `ms` |

`x` e `y` son puntos de pantalla desde la esquina superior izquierda de la pantalla
principal; si los omites, se usa donde esté el puntero. Pulsar la tecla otra vez mientras
una macro se reproduce no hace nada, salvo detener una `toggle`. Las teclas o botones que
una macro tenga presionados se sueltan cuando termina o se detiene.

```json
{"type": "macro", "play": "repeat", "times": 3, "steps": [
  {"do": "keys", "keys": "cmd+a"}, {"do": "wait", "ms": 100},
  {"do": "text", "text": "Hola"}, {"do": "click", "x": 640, "y": 400}]}
```

## Comandos útiles

Ejecútalos desde la carpeta instalada:

```bash
cd ~/Library/Application\ Support/DisplayPadMac
```

| Para… | Comando |
|---|---|
| Abrir el configurador | `.venv/bin/python -m displaypad_mac configure` |
| Dibujar las páginas como PNG, sin el dispositivo | `.venv/bin/python -m displaypad_mac preview --config config.json` |
| Ver y pedir los permisos | `.venv/bin/python -m displaypad_mac permissions` |
| Reiniciar el servicio | `launchctl kickstart -k gui/$(id -u)/com.displaypadmac.agent` |
| Ver el registro en vivo | `tail -f ~/Library/Logs/DisplayPadMac.log` |
| Probar el hardware (detén el servicio antes) | `.venv/bin/python -m displaypad_mac test` |

## Solución de problemas

- **`Cannot open DisplayPad IF0: kIOReturnNotPermitted`** en el registro: falta el permiso
  de Monitoreo de entrada para Python.
- **Los atajos, el texto o las teclas multimedia no hacen nada:** falta el permiso de
  Accesibilidad para Python.
- **Dejó de funcionar después de `brew upgrade`:** Homebrew cambió el binario de Python.
  Vuelve a ejecutar `./install.sh` y da los permisos al nuevo `Python.app`.
- **Las teclas quedan negras después de dormir el Mac o desconectar el pad:** el servicio
  se reconecta solo en unos 2 segundos. Si no lo hace, reinícialo.
- **La app DisplayPad dice que el servicio no responde:** revisa el registro. Si otro
  programa usa el puerto 8765, el configurador no arranca (el pad sigue funcionando).
- **Pantalla − / + no cambia el monitor externo:** activa DDC/CI en el menú del monitor.
  Algunos adaptadores y docks USB-C no dejan pasar DDC.
- **Una animación va a saltos:** las teclas animadas de esa página (también cuentan los
  fondos en movimiento y las olas) piden más de las ≈ 52 imágenes por segundo que acepta el pad. Deja menos teclas animadas en esa página o
  usa GIF con menos cuadros por segundo.
- **Una tecla de sonido no suena:** revisa el volumen del Mac y la salida elegida en
  **Ajustes del Sistema → Sonido**, y el **Volumen** de la tecla. **▶ Escuchar** en la acción
  avisa si falta el archivo. Los altavoces Bluetooth pueden comerse el primer instante de un
  sonido corto.
- **Un asistente de IA no se conecta:** revisa que **Permitir que los asistentes de IA se
  conecten** esté activado y que el servicio esté en marcha. Un `401` significa que la clave
  de acceso es incorrecta o se reemplazó.
- **Las teclas de OBS no hacen nada:** **Ajustes → OBS → Probar conexión** dice por qué.
  OBS debe estar abierto con **Herramientas → Ajustes del servidor WebSocket → Habilitar
  servidor WebSocket** activado, y la contraseña debe ser la de **Mostrar información de
  conexión**.
- **Una tecla de una web abre una pestaña nueva en vez de ir a la que está abierta:** el
  botón **Probar** de la acción dice por qué. Casi siempre macOS preguntó si DisplayPad
  puede controlar el navegador y se rechazó: permítelo en **Ajustes del Sistema →
  Privacidad y seguridad → Automatización**. La tecla solo busca en el navegador que abre
  (el predeterminado salvo que elijas otro), y la dirección de la pestaña debe empezar por
  la de la tecla.
- **Una tecla «Lo que suena» dice que lo permitas en Ajustes:** macOS preguntó si
  DisplayPad puede controlar Música o Spotify y se rechazó. Permítelo en **Ajustes del
  Sistema → Privacidad y seguridad → Automatización**.
- **Una tecla en vivo con comando muestra un guion o un error:** la vista previa muestra el
  error del comando; pruébalo en Terminal con `zsh -lc '...'`. Los comandos que tardan más
  de 10 segundos se detienen.
- **`Another DisplayPadMac instance is already running`:** solo un programa puede usar el
  DisplayPad a la vez. Detén el servicio antes de usar `test`.

## Cómo funciona

El instalador de Windows (BaseCamp 1.9.10) **no trae ningún driver de kernel**: no tiene
archivos `.sys` ni `.inf`. Es una app Electron/.NET cuyo `DisplayPadSDK.dll` le habla al
dispositivo por la API HID estándar de Windows. macOS ya ve el DisplayPad como un
dispositivo HID, así que solo faltaba el programa que le habla.

El dispositivo tiene tres interfaces USB:

| Interfaz | Qué es | Cómo se usa en macOS |
|---|---|---|
| IF0 | Teclado HID (macOS lo controla) | IOKit, apertura compartida, un solo `SET_REPORT` |
| IF1 | Datos de imagen (macOS no le asigna driver) | `libusb` la reclama; endpoint OUT `0x02` |
| IF3 | HID de fabricante `0xFF00`, 64 bytes | `hidapi`: comandos, confirmaciones y pulsaciones |

**Por qué el driver de Linux se cuelga en Mac:** el firmware no atiende ningún comando en
IF3 hasta que recibe el reporte de salida 3 = `[0x03, 0x01]` en IF0 («modo de eventos»).
En Linux se envía separando IF0 del kernel, y en macOS eso requiere root. Aquí se envía
abriendo IF0 en modo compartido con IOKit, que no necesita root, solo el permiso de
Monitoreo de entrada.

Cada imagen de tecla es una transferencia BGR de 102 × 102 y 31.744 bytes por IF1, unos
18 ms.

## Hecho con IA

Este proyecto se escribió con **Claude Code**, el asistente de programación con IA de
Anthropic: el driver, el servicio, el configurador, el servidor MCP, el instalador y este
README. Una persona dirigió el trabajo, decidió qué construir y probó cada función en un
DisplayPad real con macOS. Revisa el código como harías con cualquier proyecto de código
abierto antes de depender de él.

## Créditos

- Protocolo USB y secuencia de envío de imágenes:
  [oss-mountain-displaypad](https://github.com/AnnikenYT/oss-mountain-displaypad) de
  AnnikenToGo (MIT). Reimplementado en Python en `displaypad_mac/driver.py`.
- La forma de activar el pad se entendió primero gracias a
  [BaseCamp-Linux](https://github.com/ramisotti13-eng/BaseCamp-Linux) (solo consultado,
  sin copiar código).
- Animaciones Lottie: [rlottie](https://github.com/Samsung/rlottie) mediante
  [rlottie-python](https://github.com/laggykiller/rlottie-python) (LGPL 2.1).
- La parte de macOS (activación por IOKit, reclamo de IF1 con libusb, el servicio, las
  acciones, el brillo de las pantallas, el configurador y el servidor MCP) es nueva y se
  verificó en el hardware.

Detalles y textos de las licencias: [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

## Licencia

[MIT](LICENSE). Sin relación con Mountain ni con 360 Service Agency GmbH, que no lo
respaldan ni le dan soporte. Mountain y DisplayPad son marcas de sus dueños.
