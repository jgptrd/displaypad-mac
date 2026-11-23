"""Messages the user can see (errors shown in the configurator), in English or Spanish.

The code is written in English; t("English text {x}", x=...) looks the text up in
the Spanish table when the language is "es". The language comes from config.json
("language"), or DISPLAYPAD_LANG for child processes. A thread can force a
language with `override("en")` (the MCP server always answers in English).
"""

import os
import threading
from contextlib import contextmanager

LANGS = ("en", "es")
_local = threading.local()
_lang = os.environ.get("DISPLAYPAD_LANG") if os.environ.get("DISPLAYPAD_LANG") in LANGS else "en"


def set_language(lang: str):
    global _lang
    _lang = lang if lang in LANGS else "en"


def language() -> str:
    return getattr(_local, "lang", None) or _lang


@contextmanager
def override(lang: str):
    old = getattr(_local, "lang", None)
    _local.lang = lang
    try:
        yield
    finally:
        _local.lang = old


def t(msg: str, **kw) -> str:
    text = ES.get(msg, msg) if language() == "es" else msg
    return text.format(**kw) if kw else text


ES = {
    "that picture is not part of the configuration": "esa imagen no forma parte de la configuración",
    "picture not found: {path}": "no se encontró la imagen: {path}",
    # actions.py
    "unknown action type '{kind}'": "tipo de acción desconocido '{kind}'",
    "the '{kind}' action is missing '{field}'": "a la acción '{kind}' le falta '{field}'",
    "hold must be true or false": "hold debe ser true o false",
    "held down for 1 second": "mantenida 1 segundo",
    "invalid shortcut “{keys}”: use modifiers (cmd, shift, ctrl, alt, fn; rcmd, rshift, rctrl, ralt for the right ones) and one key, or a single key, e.g. cmd+shift+4, f5, rcmd":
        "atajo inválido «{keys}»: usa modificadores (cmd, shift, ctrl, alt, fn; rcmd, rshift, rctrl, ralt para los de la derecha) y una tecla, o una sola tecla, p. ej. cmd+shift+4, f5, rcmd",
    "unknown media key '{key}'": "tecla multimedia desconocida '{key}'",
    "the page '{page}' does not exist": "la página '{page}' no existe",
    "brightness must be a number (50) or a change (+10 / -10)": "el brillo debe ser un número (50) o un cambio (+10 / -10)",
    "display must be all, builtin or external": "pantalla debe ser all, builtin o external",
    "the wait must be a number of milliseconds": "la espera debe ser un número de milisegundos",
    "stopped: it took more than 30 seconds": "se detuvo: tardó más de 30 segundos",
    "ended with code {code}": "terminó con código {code}",
    "the Accessibility permission is needed to control the keyboard": "falta el permiso de Accesibilidad para controlar el teclado",
    "no compatible display was found": "no se encontró ninguna pantalla compatible",
    # macro.py
    "each step must be an object like {\"do\": \"click\"}": "cada paso debe ser un objeto como {\"do\": \"click\"}",
    "unknown step “{do}”": "paso desconocido «{do}»",
    "unknown key “{key}”": "tecla desconocida «{key}»",
    "invalid shortcut “{keys}”": "atajo inválido «{keys}»",
    "the text is empty": "el texto está vacío",
    "dx and dy must be whole numbers": "dx y dy deben ser números enteros",
    "x and y must be numbers": "x e y deben ser números",
    "unknown mouse button “{button}” (use left, right, middle, back or forward)":
        "botón del ratón desconocido «{button}» (usa left, right, middle, back o forward)",
    "count must be 1, 2 or 3": "count debe ser 1, 2 o 3",
    "the macro has no steps yet: record it or add steps": "la macro aún no tiene pasos: grábala o añade pasos",
    "a macro can have up to {n} steps": "una macro puede tener hasta {n} pasos",
    "macro step {n}: {problem}": "paso {n} de la macro: {problem}",
    "the macro only waits: add a step that does something": "la macro solo espera: añade un paso que haga algo",
    "play must be once, repeat, while_held or toggle": "play debe ser once, repeat, while_held o toggle",
    "times must be a whole number from 1 to 1000": "times debe ser un número entero del 1 al 1000",
    "delays must be recorded, fixed or none": "delays debe ser recorded, fixed o none",
    "delay_ms must be a number of milliseconds from 0 to 10000": "delay_ms debe ser un número de milisegundos del 0 al 10000",
    "a recording is already running": "ya hay una grabación en curso",
    "the Input Monitoring permission is needed to record": "falta el permiso de Monitoreo de entrada para grabar",
    "could not start recording: allow Input Monitoring for DisplayPad, then restart it":
        "no se pudo empezar a grabar: permite el Monitoreo de entrada para DisplayPad y reinícialo",
    "stopped after {seconds} s": "detenida a los {seconds} s",
    "played {steps} steps in {seconds} s": "reprodujo {steps} pasos en {seconds} s",
    # keycapture.py
    "the Accessibility permission is needed to record shortcuts from the whole Mac":
        "falta el permiso de Accesibilidad para grabar atajos de todo el Mac",
    # daemon.py
    "the configuration must be a JSON object": "la configuración debe ser un objeto JSON",
    "at least one page is needed": "se necesita al menos una página",
    "there is a page without a name": "hay una página sin nombre",
    "page '{page}': key '{key}' must be from 1 to 12": "página '{page}': la tecla '{key}' debe ser del 1 al 12",
    "page '{page}', key {key}: the key must be an object": "página '{page}', tecla {key}: la tecla debe ser un objeto",
    "page '{page}', key {key}: the icon size must be a number from 30 to 200":
        "página '{page}', tecla {key}: el tamaño del ícono debe ser un número entre 30 y 200",
    "page '{page}', key {key}: hide_label must be true or false": "página '{page}', tecla {key}: hide_label debe ser true o false",
    "page '{page}', key {key}: crop must be [left, top, right, bottom] as fractions of the picture, with right > left and bottom > top":
        "página '{page}', tecla {key}: crop debe ser [izquierda, arriba, derecha, abajo] en fracciones de la imagen, con derecha > izquierda y abajo > arriba",
    "page '{page}', key {key}: {error}": "página '{page}', tecla {key}: {error}",
    "page '{page}': keys must be an object like {{\"2\": {{...}}}}":
        "página '{page}': keys debe ser un objeto como {{\"2\": {{...}}}}",
    "page '{page}': key 1 of a folder is its back key; use keys 2 to 12":
        "página '{page}': la tecla 1 de una carpeta es la de volver; usa las teclas 2 a 12",
    "page '{page}', key {key}: folder must be an object with its keys, like {{\"keys\": {{...}}}}":
        "página '{page}', tecla {key}: folder debe ser un objeto con sus teclas, como {{\"keys\": {{...}}}}",
    "page '{page}': page names cannot contain “/”": "página '{page}': los nombres de página no pueden llevar «/»",
    "page '{page}': the page must be an object like {{\"keys\": {{...}}}}":
        "página '{page}': la página debe ser un objeto como {{\"keys\": {{...}}}}",
    "the start page '{page}' does not exist": "la página inicial '{page}' no existe",
    "language must be one of: {values}": "language debe ser uno de: {values}",
    "theme must be one of: {values}": "theme debe ser uno de: {values}",
    "brightness must be a number from 0 to 100": "brightness debe ser un número del 0 al 100",
    "corner_radius must be a number from 0 to {max}": "corner_radius debe ser un número del 0 al {max}",
    "page '{page}': apps must be a list of app names": "página '{page}': apps debe ser una lista de nombres de apps",
    "page '{page}': when must be \"open\" or \"front\"": "página '{page}': when debe ser \"open\" o \"front\"",
    "mcp must be an object with true/false values": "mcp debe ser un objeto con valores true/false",
    "{path}: invalid JSON at line {line}, column {col}: {msg}": "{path}: JSON inválido en la línea {line}, columna {col}: {msg}",
    "the configuration was changed somewhere else (for example by an AI assistant); load it again before saving":
        "la configuración cambió en otro lugar (por ejemplo, la cambió un asistente de IA); vuelve a cargarla antes de guardar",
    # web.py
    "file too large (12 MB max)": "archivo demasiado grande (máximo 12 MB)",
    "invalid key: open the configurator from the DisplayPad app": "clave inválida: abre el configurador desde la app DisplayPad",
    "could not read config.json: {error}": "no se pudo leer config.json: {error}",
    "the file is not a valid image or animation (use PNG, JPG, GIF, WebP or Lottie .json / .lottie / .tgs)":
        "el archivo no es una imagen ni una animación válida (usa PNG, JPG, GIF, WebP o Lottie .json / .lottie / .tgs)",
    "unknown setting '{name}'": "ajuste desconocido '{name}'",
    # anim.py
    "the .lottie file is too large": "el archivo .lottie es demasiado grande",
    "the .lottie file is damaged": "el archivo .lottie está dañado",
    "the .lottie file contains no animation": "el archivo .lottie no contiene ninguna animación",
    "the .tgs file is damaged": "el archivo .tgs está dañado",
    "the animation is too large": "la animación es demasiado grande",
    "the .lottie file does not contain a valid Lottie animation": "el archivo .lottie no contiene una animación Lottie válida",
    "the JSON file cannot be read: {error}": "el archivo JSON no se puede leer: {error}",
    "that JSON is not a Lottie animation (it has no “layers” and “op”)":
        "ese JSON no es una animación Lottie (le faltan «layers» y «op»)",
    "the Lottie animation is empty": "la animación Lottie está vacía",
    "this Lottie animation was drawn without movement: it may use features the Lottie reader does not support. Try exporting it as a GIF.":
        "esta animación Lottie se dibujó sin movimiento: puede usar funciones que el lector de Lottie no admite. "
        "Prueba exportarla como GIF.",
    "the animation took more than {seconds} s to prepare": "la animación tardó más de {seconds} s en prepararse",
    "the Lottie animation could not be drawn (it may use features the pad does not support)":
        "no se pudo dibujar la animación Lottie (puede usar funciones que el pad no admite)",
    "the Lottie component is missing: run install.sh again": "falta el componente para Lottie: vuelve a ejecutar install.sh",
    # obs.py
    "the OBS port must be a number from 1 to 65535": "el puerto de OBS debe ser un número de 1 a 65535",
    "OBS asks for a password: copy it from OBS (Tools › WebSocket Server Settings › Show Connect Info) into DisplayPad's Settings › OBS":
        "OBS pide una contraseña: cópiala de OBS (Herramientas › Ajustes del servidor WebSocket › Mostrar información de conexión) en Ajustes › OBS de DisplayPad",
    "OBS did not accept the password: copy it again from OBS (Tools › WebSocket Server Settings › Show Connect Info) into DisplayPad's Settings › OBS":
        "OBS no aceptó la contraseña: cópiala de nuevo de OBS (Herramientas › Ajustes del servidor WebSocket › Mostrar información de conexión) en Ajustes › OBS de DisplayPad",
    "OBS: {error}": "OBS: {error}",
    "the request failed (code {code})": "la petición falló (código {code})",
    "OBS is not reachable at {host}:{port}. Is OBS open, with its WebSocket server on (Tools › WebSocket Server Settings › Enable WebSocket server)?":
        "No se puede conectar con OBS en {host}:{port}. ¿Está OBS abierto, con su servidor WebSocket activado (Herramientas › Ajustes del servidor WebSocket › Habilitar servidor WebSocket)?",
    "lost the connection to OBS: {error}": "se perdió la conexión con OBS: {error}",
    "unknown OBS command '{do}'; use one of: {values}": "orden de OBS desconocida '{do}'; usa una de: {values}",
    "the OBS scene is missing: its name, or #1 for the first one in the list":
        "falta la escena de OBS: su nombre, o #1 para la primera de la lista",
    "the OBS {field} must be text": "en OBS, {field} debe ser texto",
    "OBS has {n} scenes, not {i}": "OBS tiene {n} escenas, no {i}",
    "OBS has no scene called “{name}”": "OBS no tiene ninguna escena llamada «{name}»",
    "OBS has no scenes": "OBS no tiene escenas",
    "OBS has no microphone source": "OBS no tiene ninguna fuente de micrófono",
    "on": "activado", "off": "desactivado", "done": "hecho", "muted": "silenciado", "unmuted": "con sonido",
    # live.py
    "Battery": "Batería", "Volume": "Volumen", "Mic": "Micro",
    'live must be an object like {"source": "cpu"}': 'live debe ser un objeto como {"source": "cpu"}',
    "unknown live source '{source}'; use one of: {values}": "fuente en vivo desconocida '{source}'; usa una de: {values}",
    'the live style must be "text" or "meter"': 'el estilo en vivo debe ser "text" o "meter"',
    "a meter needs a number: use it with {values}": "un medidor necesita un número: úsalo con {values}",
    "alert must be true or false": "alert debe ser true o false",
    "a live command key needs the command to run": "una tecla en vivo con comando necesita el comando que ejecutará",
    "the command is too long (at most {n} characters)": "el comando es demasiado largo (como máximo {n} caracteres)",
    "every must be a number of seconds from {min} to {max}": "every debe ser un número de segundos de {min} a {max}",
    "this Mac does not report GPU use": "este Mac no informa el uso de la GPU",
    "this Mac has no battery": "este Mac no tiene batería",
    "charged": "cargada", "charging": "cargando", "on battery": "con batería",
    "this sound output has no volume control": "esta salida de sonido no tiene control de volumen",
    "no microphone": "sin micrófono",
    "allow it in Settings › Privacy › Automation": "permítelo en Ajustes › Privacidad › Automatización",
    "playing": "sonando", "paused": "en pausa",
    "OBS closed": "OBS cerrado", "No connection": "Sin conexión", "LIVE": "EN VIVO", "PAUSED": "EN PAUSA",
    "Off air": "Fuera del aire",
    "took more than {seconds} s": "tardó más de {seconds} s",
    "save the key to run its command": "guarda la tecla para ejecutar su comando",
    "cannot read it now": "no se puede leer ahora",
    # render.py: backgrounds and press effects
    'background must be an object like {"style": "gradient", "colors": ["#FF5F6D", "#FFC371"]}':
        'background debe ser un objeto como {"style": "gradient", "colors": ["#FF5F6D", "#FFC371"]}',
    "the background style must be one of: {values}": "el estilo del fondo debe ser uno de: {values}",
    'the background needs 2 or 3 colors, like ["#FF5F6D", "#FFC371"]':
        'el fondo necesita 2 o 3 colores, como ["#FF5F6D", "#FFC371"]',
    "the background angle must be a number of degrees from 0 to 360":
        "el ángulo del fondo debe ser un número de grados de 0 a 360",
    "the background speed must be a number from {min} to {max}":
        "la velocidad del fondo debe ser un número de {min} a {max}",
    'press_effect must be an object like {"style": "ripple"}': 'press_effect debe ser un objeto como {"style": "ripple"}',
    "the press effect must be one of: {values}": "el efecto al pulsar debe ser uno de: {values}",
    'the press effect color must be a color like "#FFFFFF"': 'el color del efecto al pulsar debe ser un color como "#FFFFFF"',
    "this key has no press effect": "esta tecla no tiene efecto al pulsar",
    # sound.py: sound keys
    "the sound must be an MP3, M4A, WAV, AIFF, CAF or FLAC file":
        "el sonido debe ser un archivo MP3, M4A, WAV, AIFF, CAF o FLAC",
    "the sound volume must be a number from 0 to 100": "el volumen del sonido debe ser un número de 0 a 100",
    "the sound's play must be one of: {values}": "el «play» del sonido debe ser uno de: {values}",
    "sound file not found: {path}": "no se encontró el archivo de sonido: {path}",
    "the sound is too large (50 MB max)": "el sonido es demasiado grande (máximo 50 MB)",
    "the file is not a sound macOS can play (use MP3, M4A, WAV, AIFF, CAF or FLAC)":
        "el archivo no es un sonido que macOS pueda reproducir (usa MP3, M4A, WAV, AIFF, CAF o FLAC)",
    "playing {name} ({seconds} s)": "reproduciendo {name} ({seconds} s)",
    "stopped {name}": "se detuvo {name}",
    "stopped {n} sound(s)": "se detuvieron {n} sonido(s)",
    # browsers.py: web addresses in a chosen browser
    "browser must be the name of a browser app, such as Safari or Google Chrome":
        "browser debe ser el nombre de un navegador, como Safari o Google Chrome",
    "new must be tab or window": "new debe ser tab o window",
    "reuse_tab must be true or false": "reuse_tab debe ser true o false",
    "could not open {url}": "no se pudo abrir {url}",
    "{browser} is not installed, so the default browser opened it":
        "{browser} no está instalado, así que lo abrió el navegador predeterminado",
    "{browser} can't be asked for its tabs or a new window, so it opened the address the way it opens links":
        "a {browser} no se le pueden pedir sus pestañas ni una ventana nueva, así que abrió la dirección como abre los enlaces",
    "went to the {browser} tab already showing it": "fue a la pestaña de {browser} que ya la mostraba",
    "opened in a new {browser} window": "se abrió en una ventana nueva de {browser}",
    "opened in {browser}": "se abrió en {browser}",
    "to find open tabs or make windows, allow DisplayPad to control {browser} in System Settings > Privacy & Security > Automation":
        "para encontrar pestañas abiertas o abrir ventanas, permite que DisplayPad controle {browser} en Ajustes del Sistema > Privacidad y seguridad > Automatización",
    # the floating pad
    "the floating pad needs a shortcut or a mouse button": "el pad flotante necesita un atajo o un botón del mouse",
    "'{part}' can't be used in the floating pad's shortcut: use ⌘, ⌥, ⌃ or ⇧ and then one key or mouse button":
        "'{part}' no se puede usar en el atajo del pad flotante: usa ⌘, ⌥, ⌃ o ⇧ y luego una tecla o un botón del mouse",
    "the floating pad's shortcut needs a key or a mouse button after the modifiers":
        "el atajo del pad flotante necesita una tecla o un botón del mouse después de los modificadores",
    "unknown key '{key}' in the floating pad's shortcut": "tecla desconocida '{key}' en el atajo del pad flotante",
    "the floating pad's shortcut needs ⌘, ⌃, ⌥ or ⇧ with that key (F-keys can be alone)":
        "el atajo del pad flotante necesita ⌘, ⌃, ⌥ o ⇧ con esa tecla (las teclas F pueden ir solas)",
    "macOS doesn't allow shortcuts with only ⌥ or ⌥⇧: add ⌘ or ⌃": "macOS no permite atajos solo con ⌥ o ⌥⇧: agrega ⌘ o ⌃",
    'popup must be an object like {"enabled": true, "trigger": "cmd+middle_click"}':
        'popup debe ser un objeto como {"enabled": true, "trigger": "cmd+middle_click"}',
    "popup: unknown setting '{name}'": "popup: ajuste desconocido '{name}'",
    "popup.enabled must be true or false": "popup.enabled debe ser true o false",
    "floating pad: {error}": "pad flotante: {error}",
    "{name} must be an object": "{name} debe ser un objeto",
    "that key is not on the pad any more": "esa tecla ya no está en el pad",
    "macOS didn't let DisplayPad watch the mouse buttons (Input Monitoring)":
        "macOS no dejó que DisplayPad vea los botones del mouse (Monitoreo de entrada)",
}
