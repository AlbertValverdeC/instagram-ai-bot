# Reels Automatizados — Documento Conceptual

## Formato: Reel-Podcast (2 pantallas: Portada + Podcast)

**Objetivo:** Generar Reels de Instagram 100% automatizados con dos estados
visuales claros — una portada de impacto y una pantalla de podcast con la
imagen de fondo, voz narrando y subtítulos con formato visual propio.

---

## 1. Qué es un Reel TechTokio

Un vídeo vertical de **35-50 segundos** con dos actos:

1. **PORTADA (3-4s):** Imagen de portada a pantalla completa con título
   grande superpuesto. Impacto máximo. El thumbnail del Reel.
2. **PODCAST (30-45s):** La imagen pasa a ser fondo (oscurecida/blur),
   la voz empieza a narrar y los subtítulos ocupan el centro con
   formato visual de reel-podcast.

**Referencia:** El formato que usan cuentas como @visualpolitik, @playground
o clips de podcast en Spotify — imagen de fondo + subs estilizados +
indicador visual de audio.

### PANTALLA 1: PORTADA (0-3 segundos)

La portada es lo primero que se ve y funciona como thumbnail.
Tiene que parar el scroll en seco.

```
┌────────────────────────────────┐
│                                │
│                                │
│   ┌────────────────────────┐   │
│   │                        │   │
│   │                        │   │
│   │    IMAGEN COVER IA     │   │  Imagen generada (1080x1920)
│   │    a pantalla completa │   │  Ocupa TODO el frame
│   │                        │   │  Con Ken Burns zoom-in suave
│   │                        │   │
│   │                        │   │
│   └────────────────────────┘   │
│                                │
│                                │  Overlay gradiente oscuro
│   ░░░░░░░░░░░░░░░░░░░░░░░░   │  (bottom 40%: negro 0%→80%)
│   ░░░░░░░░░░░░░░░░░░░░░░░░   │  Para que el texto se lea
│                                │
│                                │
│   SAMSUNG LEE                  │  TÍTULO: 2-4 palabras
│   TU MENTE                     │  Space Grotesk Bold 72-88pt
│                                │  Blanco, sombra suave
│   La IA que sabe lo que        │  SUBTÍTULO: 1 línea
│   quieres antes que tú         │  Space Grotesk 36pt, 80% opacidad
│                                │
│   ⚡ TechTokio                 │  Branding: logo + nombre
│                                │  Esquina inferior, 60% opacidad
│                                │
└────────────────────────────────┘
```

**Animación:**
- La imagen tiene un Ken Burns zoom-in lento (1.0x → 1.05x en 3s)
- El título aparece con fade-in rápido (0.3s) o scale-up (0.9x → 1.0x)
- Al final de los 3s: transición a Pantalla 2

**Por qué funciona:**
- Es lo que Instagram usa como thumbnail → tiene que ser bonito y legible
- El título grande con imagen de fondo = el formato más scrollstopper
- Solo dura 3s → no aburre, engancha y pasa al contenido

### PANTALLA 2: PODCAST (3s hasta el final)

La imagen de portada se queda pero pasa a ser fondo decorativo.
La voz arranca y los subtítulos toman el protagonismo.

```
┌────────────────────────────────┐
│                                │
│   ┌────────────────────────┐   │
│   │ ░░░░░░░░░░░░░░░░░░░░░ │   │  FONDO: misma imagen de portada
│   │ ░░ IMAGEN COVER ░░░░░ │   │  PERO con:
│   │ ░░ (blur gaussiano ░░ │   │  - Blur gaussiano (radius 20-30)
│   │ ░░  + oscurecida)  ░░ │   │  - Overlay negro al 50-60%
│   │ ░░░░░░░░░░░░░░░░░░░░░ │   │  - Ken Burns zoom MUY lento continuo
│   │ ░░░░░░░░░░░░░░░░░░░░░ │   │
│   │ ░░░░░░░░░░░░░░░░░░░░░ │   │  Efecto: se intuye la imagen
│   │ ░░░░░░░░░░░░░░░░░░░░░ │   │  pero no distrae del texto
│   └────────────────────────┘   │
│                                │
│                                │
│   ⚡ TechTokio                 │  BRANDING SUPERIOR
│   ──────────────────           │  Logo + línea accent (persistente)
│                                │
│                                │
│                                │
│   Samsung acaba de             │
│   lanzar una IA que            │  SUBTÍTULOS CENTRALES
│   ██████ lo que                │  El bloque principal del reel
│   necesitas antes de           │  (ver detalle abajo)
│   que lo pidas                 │
│                                │
│                                │
│                                │
│   ▁▂▃▅▇█▇▅▃▂▁▂▃▅▇█▇▅▃▂▁     │  WAVEFORM
│                                │  Sincronizada con audio
│   ──────────────────           │  Color accent del template
│          @techtokio            │
│                                │
└────────────────────────────────┘
```

### Formato de subtítulos "reel-podcast"

Esto es lo que marca la diferencia visual. Los subtítulos no son
un bloque de texto plano — tienen un formato visual que grita
"esto es un podcast/narración".

**Estilo: palabra activa resaltada (highlight boxing)**

```
┌──────────────────────────────┐
│                              │
│   Samsung acaba de           │  ← texto blanco normal
│   lanzar una IA que          │
│   ████████████ lo que        │  ← palabra actual: fondo accent
│   necesitas antes de         │     color (caja redondeada detrás)
│   que lo pidas               │     como un "highlight marker"
│                              │
└──────────────────────────────┘
```

Palabra a palabra, el highlight se mueve — como un karaoke pero
con una caja de color detrás de la palabra activa en vez de
solo cambiar el color del texto.

**Características del formato de subtítulos:**
- Fuente: Space Grotesk Bold, 44-48pt
- Color base: blanco puro (#FFFFFF)
- Highlight: caja redondeada detrás de la palabra actual
  - Background: accent color del template (cyan, purple, etc.)
  - Texto dentro del highlight: blanco o negro (el que contraste más)
  - Border radius: 8px
  - Padding: 6px horizontal, 4px vertical
- Máximo 5-6 palabras por línea, 4-5 líneas visibles
- Centrado en pantalla, zona Y=900-1300
- Salto de bloque cada ~15 palabras (fade-out viejo, fade-in nuevo)
- El bloque entero aparece con fade rápido (0.2s) y desaparece igual

**Alternativa: highlight por color (más simple)**

Si la caja resulta compleja de implementar con ASS/FFmpeg:
- Palabra actual → color accent (cyan/purple)
- Resto de palabras → blanco al 60% opacidad
- Palabra ya dicha → blanco al 100%
- Efecto más sutil pero igualmente efectivo

### La transición Portada → Podcast

Este momento es clave. Tiene que sentirse fluido, no un corte brusco.

```
Segundo 0.0 ──── Portada: imagen nítida + título grande
    │
    │  Ken Burns zoom continuo (no se para)
    │
Segundo 2.5 ──── Título hace fade-out (0.3s)
    │
Segundo 2.8 ──── Imagen empieza blur transition (0.5s)
    │              (gaussiano de 0 → 25 progresivo)
    │              + oscurecimiento de 0% → 55%
    │
Segundo 3.0 ──── Voz arranca
    │              Branding superior aparece (fade-in 0.3s)
    │              Waveform aparece (fade-in 0.3s)
    │
Segundo 3.3 ──── Primer bloque de subtítulos aparece (fade-in 0.2s)
    │
    │  ... narración continua ...
    │
Segundo ~40 ──── Último subtítulo: CTA
    │              Waveform fade-out
    │              Pantalla: logo grande + @techtokio
    │
Segundo ~43 ──── Fin
```

**Lo importante:** el zoom de la imagen NUNCA para. La portada y
el modo podcast comparten la misma imagen en movimiento — solo
cambia que se aplica blur + oscuro + se superponen los subs.
Esto da continuidad visual.

### Desglose temporal de un Reel de 42 segundos

```
0-3s    PORTADA       Imagen full + título grande + branding
                      Ken Burns zoom-in suave
                      Sin audio de voz (puede haber sfx de intro)

3-3.5s  TRANSICIÓN    Título fade-out → imagen blur + darken
                      Branding + waveform fade-in

3.5-38s PODCAST       Imagen blurred de fondo con zoom continuo
                      Voz narrando (4-5 segmentos temáticos)
                      Subtítulos con highlight word-by-word
                      Waveform animada abajo
                      Bloques de subs cambian cada ~8 segundos

38-42s  CTA/CIERRE    Voz: frase CTA
                      Subs: última frase
                      Waveform fade-out
                      Logo + handle quedan solos
```

### Elementos que dan vida (vs. vídeo plano)

| Elemento | Qué hace | Pantalla |
|----------|----------|----------|
| **Ken Burns zoom continuo** | Imagen nunca está quieta | Ambas |
| **Blur transition** | Portada → podcast de forma fluida | Transición |
| **Highlight boxing** | Caja accent detrás de palabra actual | Podcast |
| **Waveform animada** | Señal visual de "esto es audio" | Podcast |
| **Fade de bloques de subs** | Renueva el texto cada ~8s | Podcast |
| **Branding persistente** | Logo + handle siempre visibles | Podcast |

**Duración target:** 35-45 segundos (sweet spot para retention en Reels).

---

## 2. De dónde sale cada pieza

El pipeline de carruseles ya genera TODO el contenido necesario.
No hace falta una segunda llamada a OpenAI para el Reel.

### Datos de entrada (ya existen)

```
topic = {
    "topic": "Samsung lanza IA que anticipa tus deseos en el Galaxy S26",
    "key_points": ["...", "...", "...", "...", "...", "..."],
    "virality_score": 8.5
}

content = {
    "slides": [
        {"type": "cover", "title": "...", "subtitle": "..."},
        {"type": "content", "number": 1, "title": "...", "body": "..."},
        {"type": "content", "number": 2, "title": "...", "body": "..."},
        {"type": "content", "number": 3, "title": "...", "body": "..."},
        {"type": "content", "number": 4, "title": "...", "body": "..."},
        {"type": "content", "number": 5, "title": "...", "body": "..."},
        {"type": "content", "number": 6, "title": "...", "body": "..."},
        {"type": "cta", "title": "...", "body": "..."}
    ],
    "caption": "...",
    "alt_text": "..."
}
```

### Qué genera cada módulo nuevo

| Pieza del Reel | Fuente | Módulo nuevo |
|----------------|--------|-------------|
| Guión de voz | `content.slides` (ya existe) | `reel_script_generator.py` |
| Audio narración | Guión de voz | `voiceover.py` |
| Slides 9:16 | Templates existentes (adaptados) | `reel_designer.py` |
| Subtítulos | Guión + timestamps del TTS | `voiceover.py` (output) |
| Vídeo final | Slides + audio + subs | `reel_composer.py` |

---

## 3. Guión de voz (reel_script_generator.py)

### El problema

Los bodies de los slides del carrusel tienen 38-65 palabras cada uno.
Si leemos los 6 slides + cover + CTA, son ~350-500 palabras.
A ~150 palabras/minuto (ritmo natural en español), eso son 2-3 minutos.
**Demasiado largo para un Reel.**

### La solución

Generar un **guión condensado** de ~100-120 palabras (~40-50 segundos)
que cubra el cover + los 3-4 puntos más importantes + CTA.

### Dos opciones de implementación

#### Opción A: LLM resume los slides (1 llamada extra a OpenAI)

```python
def generate_reel_script(content: dict, topic: dict) -> ReelScript:
    """
    Prompt a GPT-4o-mini para condensar los slides en un guión
    narrable de 100-120 palabras.
    """
```

**Prompt conceptual:**
```
Eres locutor de noticias tech para Reels de Instagram.

SLIDES DEL CARRUSEL:
{slides_json}

Genera contenido para un Reel vertical de 35-50 segundos.
El Reel tiene 2 pantallas: una PORTADA (3s, sin voz) y un PODCAST
(el resto, con voz narrando + subtítulos).

Genera:
1. cover_title: Título de portada. 2-4 palabras. IMPACTO MÁXIMO.
   Debe incluir el nombre/marca principal del topic.
   Ejemplo: "VISION PRO 2 ES REAL", "SAMSUNG LEE TU MENTE"
2. cover_subtitle: 1 frase corta de contexto (8-15 palabras).
   Ejemplo: "Apple reinventa las gafas con M5 y mitad de peso"
3. narration: Texto continuo de 100-130 palabras para narrar por voz.
   Empieza directo con el gancho, NO con "hola" ni presentaciones.
   Fluye como un locutor de noticias contando algo interesante.
   Termina con CTA corto: "sígueme para más", "guarda este reel", etc.

Reglas de la narración:
- Tono directo, conversacional, como si hablaras a un amigo informado.
- No uses "en este vídeo" ni meta-referencias al formato.
- Texto corrido, sin marcas de segmento (los subtítulos se generan aparte).
- Cubre 3-4 key points principales, no los 6 (hay que condensar).
- No inventes datos fuera de KEY POINTS/CONTEXT.

Responde JSON exacto:
{
    "cover_title": "SAMSUNG LEE TU MENTE",
    "cover_subtitle": "La IA que sabe lo que quieres antes que tú",
    "narration": "Samsung acaba de lanzar una IA que sabe lo que quieres antes que tú. El Galaxy S26 integra un modelo que aprende de tus patrones de uso y anticipa acciones. Lo más impactante es que reduce un cincuenta por ciento el tiempo que pasas configurando tu móvil. El sistema analiza cómo usas cada app y prepara todo antes de que lo pidas. Ya está disponible en Europa y se espera que el resto de fabricantes copien la idea antes de fin de año. Sígueme para enterarte de las noticias tech más importantes cada día.",
    "total_words": 118
}
```

**Ventaja:** Guión fluido y natural, bien condensado.
**Coste:** 1 llamada extra a GPT-4o-mini (~$0.001 por Reel).

#### Opción B: Extraer mecánicamente del contenido existente (0 llamadas extra)

```python
def generate_reel_script(content: dict, topic: dict) -> ReelScript:
    """
    Extrae hook del cover.subtitle + primeras frases de los 4 mejores
    slides + CTA.body. Sin llamada a LLM.
    """
```

Lógica:
1. Hook = `cover.title` + primera frase de `cover.subtitle`
2. Seleccionar los 4 slides con body más corto (mejor ritmo)
3. De cada body, tomar solo la primera oración
4. CTA = `cta.body` cortado a 15 palabras

**Ventaja:** Cero coste, cero latencia extra.
**Desventaja:** Resultado más mecánico, puede sonar cortado.

### Recomendación: Opción A

El coste es despreciable ($0.001) y la diferencia de calidad es grande.
Un guión que suena a "locución" retiene mucho más que frases sueltas cortadas.

### Output del módulo

```python
@dataclass
class ReelScript:
    cover_title: str         # Título para la portada (2-4 palabras, GRANDE)
    cover_subtitle: str      # Subtítulo portada (1 línea de contexto)
    narration: str           # Texto continuo completo para TTS
    word_count: int          # Para validar duración (~100-130)
```

**Nota importante:** El guión ahora es MÁS simple. Solo necesita:
1. El título grande de la portada (cover_title)
2. El subtítulo de la portada (cover_subtitle)
3. Un texto corrido de narración (narration) — que va directo al TTS

Ya no hay "screen_modes" ni segmentos separados. La pantalla de
podcast solo tiene subtítulos que fluyen con la voz. No hay cambios
de layout durante la narración — la imagen de fondo está fija (blur)
y los subs se van renovando. Mucho más limpio.

---

## 4. Voiceover (voiceover.py)

### Motor de TTS

| Motor | Calidad | Latencia | Coste/Reel | Voces ES |
|-------|---------|----------|-----------|----------|
| **OpenAI TTS (tts-1-hd)** | Muy buena | ~3-5s | ~$0.03 | Sí (alloy, nova, shimmer) |
| OpenAI TTS (tts-1) | Buena | ~2-3s | ~$0.015 | Sí |
| ElevenLabs | Excelente | ~5-8s | ~$0.02 (Creator plan) | Sí, clonables |
| Google Cloud TTS | Buena | ~2s | Free tier 1M chars/mes | Sí |
| Edge TTS (gratis) | Decente | ~1s | $0 | Sí (es-ES-AlvaroNeural) |

### Recomendación: OpenAI TTS (tts-1-hd)

- Ya tenemos `OPENAI_API_KEY` configurada.
- Calidad/precio muy bueno: ~$0.03 por Reel de 120 palabras.
- Voces recomendadas para TechTokio:
  - `nova` — voz femenina neutra, buen ritmo
  - `onyx` — voz masculina grave, tono informativo
  - `alloy` — voz neutra, versátil
- Velocidad configurable (`speed: 1.0-1.15` para ritmo dinámico).

### Flujo del módulo

```python
def generate_voiceover(script: ReelScript, voice: str = "nova") -> VoiceoverResult:
    """
    1. Envía script.full_text a OpenAI TTS
    2. Recibe audio MP3/WAV
    3. Calcula timestamps por segmento (ver sección subtítulos)
    4. Retorna audio + timestamps
    """
```

### Output

```python
@dataclass
class VoiceoverResult:
    audio_path: Path                    # output/reel_voice.mp3
    duration_seconds: float             # Duración real del audio
    segment_timestamps: list[tuple]     # [(start_s, end_s, text), ...]
```

### Cálculo de timestamps para subtítulos

OpenAI TTS no devuelve timestamps palabra a palabra.
Dos estrategias:

#### Estrategia 1: Estimación proporcional (simple, sin dependencia extra)

```python
def estimate_timestamps(script: ReelScript, total_duration: float):
    """
    Asigna tiempos proporcionalmente por número de palabras.
    Cada segmento = (words_in_segment / total_words) * total_duration
    """
```

Precisión: ~85-90%. Suficiente para subtítulos por frase.

#### Estrategia 2: Whisper alignment (preciso, 1 llamada extra)

```python
def align_timestamps(audio_path: Path, script: ReelScript):
    """
    Pasa el audio por Whisper (local o API) para obtener
    timestamps palabra a palabra.
    """
```

Precisión: ~98%. Necesario solo si queremos subtítulos palabra-a-palabra
con highlight (estilo karaoke).

### Recomendación: Estrategia 2 (Whisper) desde el principio

El formato reel-podcast necesita subtítulos con highlight palabra a palabra
para tener el aspecto "vivo". La estimación proporcional se queda corta
visualmente — el desfase se nota y rompe la ilusión de sincronía.

Whisper es gratis (se ejecuta local con `openai-whisper` o vía API ~$0.006/min).
Con un audio de 40-50 segundos, es instantáneo y da timestamps por palabra.

```python
def align_with_whisper(audio_path: Path) -> list[WordTimestamp]:
    """
    Usa Whisper (local o API) para extraer timestamps palabra a palabra.
    Retorna lista de (word, start_s, end_s).
    """
```

Esto alimenta directamente los subtítulos ASS con highlight por palabra.

---

## 5. Diseño visual del Reel-Podcast (reel_designer.py)

**Principio: 2 pantallas, 1 imagen. Simplicidad que retiene.**

Pillow genera solo 2 frames base. FFmpeg hace todo lo demás
(zoom, blur, transición, waveform, subtítulos).

### Qué genera Pillow: 2 frames

#### Frame 1: PORTADA

```python
def render_cover_frame(
    cover_image: Path,       # Imagen IA generada (ya existe)
    title: str,              # "SAMSUNG LEE TU MENTE"
    subtitle: str,           # "La IA que sabe lo que quieres antes que tú"
    template: dict,          # Colores del template activo
) -> Path:
    """
    1. Escalar cover_image a 1080x1920 (crop-to-fill)
    2. Gradiente oscuro en bottom 40% (para leer el texto)
    3. Título en grande (72-88pt Bold, blanco, sombra)
    4. Subtítulo debajo (36pt, 80% opacidad)
    5. Logo TechTokio en esquina inferior
    → output/reel_frame_cover.png
    """
```

#### Frame 2: FONDO PODCAST

```python
def render_podcast_frame(
    cover_image: Path,       # Misma imagen de portada
    template: dict,          # Colores del template activo
) -> Path:
    """
    1. Escalar cover_image a 1080x1920 (crop-to-fill)
    2. Blur gaussiano (radius 25)
    3. Overlay negro al 55% opacidad
    4. Header branding: "TechTokio" + línea accent
    5. Zona de waveform: placeholder vacío (FFmpeg lo llena)
    6. Handle @techtokio abajo
    → output/reel_frame_podcast.png
    """
```

**Eso es todo lo que Pillow hace.** El resto es FFmpeg:
- Ken Burns zoom
- Transición blur (cover → podcast)
- Waveform overlay
- Subtítulos con highlight

### Templates de color (reutilizan los del carrusel)

Cada template define los colores de todas las capas:

```python
REEL_TEMPLATES = {
    "dark_blue": {
        "bg_gradient": ("#0a0e1a", "#0d1b2a"),    # Fondo
        "accent": "#00d4ff",                        # Waveform + highlights
        "text_primary": "#ffffff",                  # Títulos
        "text_secondary": "#a0b4c8",               # Subtítulos
        "progress_bar": "#00d4ff",                  # Barra progreso
        "waveform_color": "0x00d4ff",              # Para FFmpeg showwaves
    },
    "dark_purple": {
        "bg_gradient": ("#0f0a1a", "#1a0d2e"),
        "accent": "#b366ff",
        "text_primary": "#ffffff",
        "text_secondary": "#c4a8d8",
        "progress_bar": "#b366ff",
        "waveform_color": "0xb366ff",
    },
    # ... dark_green, midnight, editorial_black
}
```

### Qué genera Pillow vs qué genera FFmpeg

| Elemento | Generado por | Por qué |
|----------|-------------|---------|
| Frame portada (imagen + título + gradiente) | **Pillow** | 1 PNG estático |
| Frame podcast (imagen blur + oscuro + branding) | **Pillow** | 1 PNG estático |
| **Ken Burns zoom (ambos frames)** | **FFmpeg** | zoompan filter |
| **Transición portada → podcast (blur progresivo)** | **FFmpeg** | xfade / blend |
| **Waveform animada** | **FFmpeg** | showwaves sobre audio |
| **Subtítulos con highlight** | **FFmpeg** | ASS con override tags |
| **Audio mix (voz + BGM)** | **FFmpeg** | amix + volume + afade |

**Flujo simplificado:**
1. Pillow genera **2 PNGs** (portada + fondo podcast)
2. FFmpeg anima ambos con zoom, transiciona, superpone waveform + subs + audio
3. Output: 1 MP4 listo para publicar

---

## 6. Composición de vídeo (reel_composer.py)

### Herramienta: FFmpeg (vía subprocess)

FFmpeg directo es la mejor opción: rápido, sin dependencias Python pesadas,
y tiene TODOS los filtros que necesitamos (showwaves, zoompan, xfade,
drawtext, overlay con timing, amix).

### Pipeline completo de FFmpeg

```
┌─────────────────────────────────────────────────────────────┐
│                    PIPELINE FFmpeg                           │
│                                                             │
│  INPUTS:                                                    │
│  ├── reel_frame_cover.png    (portada: imagen + título)     │
│  ├── reel_frame_podcast.png  (fondo: imagen blur + brand)   │
│  ├── voice.mp3               (narración TTS)                │
│  ├── bgm.mp3                 (música de fondo)              │
│  └── subs.ass                (subtítulos con timestamps)    │
│                                                             │
│  PASO 1: Portada animada (3s)                               │
│  ┌───────────────────────────────────────────────┐          │
│  │  reel_frame_cover.png                         │          │
│  │  + zoompan 1.0x → 1.05x en 3s (Ken Burns)    │          │
│  │  = segment_cover.mp4 (3s, sin audio)          │          │
│  └───────────────────────────────────────────────┘          │
│                                                             │
│  PASO 2: Fondo podcast animado (duración del audio)         │
│  ┌───────────────────────────────────────────────┐          │
│  │  reel_frame_podcast.png                       │          │
│  │  + zoompan MUY lento 1.0x → 1.03x            │          │
│  │  = segment_podcast.mp4 (38-47s, sin audio)    │          │
│  └───────────────────────────────────────────────┘          │
│                                                             │
│  PASO 3: Transición portada → podcast                       │
│  ┌───────────────────────────────────────────────┐          │
│  │  xfade entre segment_cover y segment_podcast  │          │
│  │  Tipo: fadeblack o smoothleft (0.5s)          │          │
│  │  = video_base.mp4 (vídeo continuo)            │          │
│  └───────────────────────────────────────────────┘          │
│                                                             │
│  PASO 4: Overlay waveform animada                           │
│  ┌───────────────────────────────────────────────┐          │
│  │  showwaves=s=1000x60:mode=cline:colors=accent │          │
│  │  Posición: centrado en Y≈1350 (zona baja)     │          │
│  │  Solo activo desde segundo 3 (modo podcast)    │          │
│  │  Sincronizado con voice.mp3                   │          │
│  └───────────────────────────────────────────────┘          │
│                                                             │
│  PASO 5: Burn subtítulos ASS                                │
│  ┌───────────────────────────────────────────────┐          │
│  │  ass filter con fuente Space Grotesk Bold     │          │
│  │  Posición: zona central (Y≈750-1150)          │          │
│  │  Texto blanco + outline negro (3px)           │          │
│  │  Palabra activa: caja accent detrás (o color) │          │
│  │  Solo activo desde segundo 3                   │          │
│  └───────────────────────────────────────────────┘          │
│                                                             │
│  PASO 6: Mix audio                                          │
│  ┌───────────────────────────────────────────────┐          │
│  │  3s silencio (portada) + voice.mp3            │          │
│  │  + bgm.mp3 (vol 0.15, fade-in 1s, fade-out)  │          │
│  │  bgm empieza desde segundo 0 (bajo en portada)│          │
│  │  Codec: AAC 48kHz stereo                      │          │
│  └───────────────────────────────────────────────┘          │
│                                                             │
│  OUTPUT:                                                    │
│  └── reel_final.mp4 (H.264, AAC, 1080x1920, 38-50s)       │
│      Tamaño estimado: 8-15MB                                │
└─────────────────────────────────────────────────────────────┘
```

**Nota sobre el audio en la portada (0-3s):**
La portada no tiene voz, pero SÍ puede tener un sfx de intro sutil
(whoosh, click tech, etc.) + la BGM que ya suena muy baja.
Esto da contexto de "algo está por empezar".
El sfx es opcional — un único archivo en `assets/sfx/intro.mp3`.

### Waveform animada (audiograma) — el detalle clave

FFmpeg tiene un filtro nativo `showwaves` que genera una visualización
de audio en tiempo real. Es lo que usan los audiogramas de podcast.

```bash
# Generar waveform como vídeo overlay
ffmpeg -i voice.mp3 \
  -filter_complex "
    [0:a]showwaves=s=1000x80:mode=cline:rate=30:colors=0x00d4ff[wv];
    [1:v][wv]overlay=40:1120
  " \
  -c:v libx264 output.mp4
```

Modos de waveform disponibles:

| Modo | Aspecto | Recomendación |
|------|---------|--------------|
| `cline` | Línea centrada (sube y baja) | Elegante, minimalista |
| `p2p` | Punto a punto | Más "técnico" |
| `line` | Línea desde base | Clásico podcast |

**Recomendación:** `cline` — aspecto limpio, se integra bien con
diseño dark y accent colors.

### Subtítulos con highlight de palabra actual

Para que los subs no sean planos, usamos ASS con override tags:

```ass
{\c&H00d4ff&}Samsung{\c&HFFFFFF&} acaba de lanzar una IA
```

Esto hace que "Samsung" aparezca en cyan (accent) y el resto en blanco.
El highlight se mueve palabra a palabra conforme avanza la narración.

Con timestamps estimados por proporción de palabras:
- Frase de 10 palabras en 5 segundos → 0.5s por palabra
- Cada 0.5s, el highlight avanza a la siguiente palabra
- Se genera un evento ASS por cada "ventana" de highlight

### Música de fondo

- 5-10 tracks royalty-free en `assets/music/` (LoFi/ambient/tech)
- Rotación aleatoria (como los templates de carrusel)
- Volumen: 15% respecto a la voz
- Fade-in 1s al inicio, fade-out 2s al final

```bash
# Mix audio en FFmpeg
ffmpeg -i voice.mp3 -i bgm.mp3 \
  -filter_complex "
    [1:a]volume=0.15,afade=t=in:d=1,afade=t=out:st=38:d=2[bg];
    [0:a][bg]amix=inputs=2:duration=first[out]
  " \
  -map "[out]" mixed_audio.mp3
```

---

## 7. Publicación de Reels (ampliar publisher.py)

### Instagram Graph API — Reels

La Graph API soporta Reels nativamente:

```python
# Paso 1: Crear container de Reel
POST /{ig-user-id}/media
{
    "media_type": "REELS",
    "video_url": "https://tu-cdn.com/output/reel_final.mp4",
    "caption": "...",
    "share_to_feed": "true",
    "access_token": "..."
}

# Paso 2: Esperar a que el container esté FINISHED
GET /{container-id}?fields=status_code

# Paso 3: Publicar
POST /{ig-user-id}/media_publish
{
    "creation_id": "{container-id}",
    "access_token": "..."
}
```

### Requisitos del vídeo

| Spec | Valor |
|------|-------|
| Formato | MP4 (H.264 + AAC) |
| Resolución | 1080x1920 (9:16) |
| FPS | 30 |
| Duración | 3-90 segundos |
| Tamaño máx | 1GB (recomendado <50MB) |
| Audio | AAC, 48kHz |

### Hosting del vídeo

Mismo sistema que las imágenes:
1. `PUBLIC_IMAGE_BASE_URL` → servir el MP4 desde el mismo CDN/ngrok
2. Fallback: no aplica Imgur (solo imágenes) → necesita hosting propio

**Nota:** El vídeo debe estar accesible públicamente para que Meta lo descargue.
Misma infra que ya se usa para las imágenes del carrusel.

### Cambios en publisher.py

```python
def publish_reel(video_path: Path, content: dict, strategy: dict) -> str:
    """
    Publish flow para Reels:
    1. Resolver URL pública del vídeo
    2. Crear Reel container (media_type=REELS)
    3. Esperar FINISHED
    4. Publicar
    """
```

Reutiliza toda la lógica de retry, error classification y rate limiting
que ya existe.

---

## 8. Integración en el pipeline

### Opción: Pipeline unificado (1 topic → 1 carrusel + 1 Reel)

```
main_pipeline.py (ampliado):

  RESEARCH  ─────────────────────────►  topic
                                          │
  CONTENT   ─────────────────────────►  content (slides + caption)
                                          │
                    ┌─────────────────────┴──────────────────────┐
                    │                                            │
              CAROUSEL PATH                               REEL PATH
                    │                                            │
              carousel_designer.create()               reel_script_generator
              → 8 PNGs (1080x1350)                     → ReelScript (100-120 words)
                    │                                            │
                    │                                     voiceover.generate()
                    │                                     → audio.mp3 + timestamps
                    │                                            │
                    │                                     reel_designer.create()
                    │                                     → 8 PNGs (1080x1920)
                    │                                            │
                    │                                     reel_composer.compose()
                    │                                     → reel_final.mp4
                    │                                            │
              ENGAGEMENT                                  ENGAGEMENT
              (mismos hashtags)                           (mismos hashtags)
                    │                                            │
              publisher.publish()                         publisher.publish_reel()
              → carousel en feed                          → reel en feed + reels tab
                    │                                            │
                    └─────────────────────┬──────────────────────┘
                                          │
                                     POST STORE
                                    (registro único)
```

### Configuración

Nuevas variables en `config/settings.py`:

```python
# --- Reels ---
REEL_ENABLED = os.getenv("REEL_ENABLED", "false").lower() in {"1", "true", "yes"}
REEL_WIDTH = 1080
REEL_HEIGHT = 1920
REEL_TTS_VOICE = os.getenv("REEL_TTS_VOICE", "nova")          # nova|onyx|alloy|shimmer
REEL_TTS_SPEED = float(os.getenv("REEL_TTS_SPEED", "1.1"))    # 1.0-1.25
REEL_TTS_MODEL = os.getenv("REEL_TTS_MODEL", "tts-1-hd")      # tts-1|tts-1-hd
REEL_BGM_VOLUME = float(os.getenv("REEL_BGM_VOLUME", "0.15"))  # 0.0-1.0
REEL_TRANSITION = os.getenv("REEL_TRANSITION", "zoom")          # cut|zoom|crossfade
REEL_MAX_DURATION = int(os.getenv("REEL_MAX_DURATION", "50"))   # segundos
REEL_SCRIPT_WORDS = int(os.getenv("REEL_SCRIPT_WORDS", "120")) # target palabras
MUSIC_DIR = ASSETS_DIR / "music"
```

### Nuevos argumentos CLI

```bash
python main_pipeline.py --reel              # Genera carrusel + reel
python main_pipeline.py --reel-only         # Solo el reel (sin carrusel)
python main_pipeline.py --reel --dry-run    # Preview sin publicar
```

### Scheduler

Ampliar el scheduler para soportar tipo de publicación:

```python
# En la queue del scheduler
{
    "date": "2026-03-01",
    "time": "08:30",
    "type": "carousel",          # carousel | reel | both
    "topic": null,
    "template": null
}
```

Ejemplo de configuración semanal optimizada:

```
Lunes:    08:30 carrusel + 13:00 reel + 20:30 carrusel
Martes:   08:30 reel + 13:00 carrusel + 20:30 reel
Miércoles: 08:30 carrusel + 13:00 reel + 20:30 carrusel
...
```

Esto da: **~3 carruseles + ~3 reels al día, alternando.**

---

## 9. Coste por Reel

| Componente | Coste |
|-----------|-------|
| Research | $0 (ya se hizo para el carrusel) |
| Content generation | $0 (reutiliza content del carrusel) |
| Guión de voz (GPT-4o-mini) | ~$0.001 |
| TTS (OpenAI tts-1-hd, ~120 palabras) | ~$0.03 |
| Whisper alignment (API, ~50s audio) | ~$0.006 |
| Diseño frames (Pillow) | $0 |
| Composición vídeo (FFmpeg) | $0 |
| **Total por Reel** | **~$0.037** |
| **90 Reels/mes (3/día)** | **~$3.33/mes** |

---

## 10. Dependencias nuevas

### Sistema

```bash
# FFmpeg (necesario para composición de vídeo)
brew install ffmpeg        # macOS
apt install ffmpeg         # Linux/Docker
```

### Python

```
openai-whisper     # Timestamps palabra a palabra (local, gratis)
                   # Alternativa: Whisper API ($0.006/min, sin instalar modelo)
                   # pip install openai-whisper (requiere ~1GB de modelo small)

# Ya instalados:
# openai           → TTS + script generation
# Pillow           → Frame rendering

# FFmpeg se llama via subprocess (sin wrapper Python).
```

---

## 11. Estructura de archivos nuevos

```
modules/
  reel_script_generator.py   # cover_title + cover_subtitle + narration via LLM
  voiceover.py               # TTS (OpenAI) + Whisper alignment → timestamps
  reel_designer.py           # Pillow: render_cover_frame() + render_podcast_frame()
  reel_composer.py           # FFmpeg: 2 frames + audio + waveform + subs → MP4

assets/
  music/                     # 5-10 tracks BGM royalty-free
    lofi_tech_01.mp3
    ambient_dark_02.mp3
    ...
  sfx/                       # Sonidos de intro (opcionales)
    intro_whoosh.mp3

config/
  settings.py                # + variables REEL_*
  reel_templates.py          # 5 templates de color para reels (mapeados del carrusel)

output/
  reel_frame_cover.png       # Frame portada (Pillow)
  reel_frame_podcast.png     # Frame fondo podcast (Pillow)
  reel_voice.mp3             # Audio TTS
  reel_subs.ass              # Subtítulos con timestamps
  reel_final.mp4             # Vídeo final
```

---

## 12. Fases de implementación

### Fase 1 — Reel-podcast funcional (~12h)

El modelo de 2 pantallas simplifica mucho la implementación.
Pillow genera 2 imágenes, FFmpeg hace el resto.

**Script + Voz (3h)**
- [ ] `reel_script_generator.py` — cover_title + cover_subtitle + narration
- [ ] `voiceover.py` — OpenAI TTS (tts-1-hd)
- [ ] `voiceover.py` — Whisper alignment → timestamps palabra a palabra
- [ ] Config vars en `settings.py` (REEL_*)

**Frames con Pillow (2h)**
- [ ] `reel_designer.py` — `render_cover_frame()`: imagen + título + gradiente
- [ ] `reel_designer.py` — `render_podcast_frame()`: imagen blur + branding
- [ ] `config/reel_templates.py` — 5 templates de color (mapeados del carrusel)

**Composición FFmpeg (5h)**
- [ ] `reel_composer.py` — Ken Burns zoom sobre ambos frames
- [ ] `reel_composer.py` — Transición portada → podcast (xfade 0.5s)
- [ ] `reel_composer.py` — Waveform overlay (showwaves sincronizado)
- [ ] `reel_composer.py` — Subtítulos ASS con highlight por palabra
- [ ] `reel_composer.py` — Audio: 3s silencio/sfx + voz + BGM con fades

**Publicación (2h)**
- [ ] Ampliar `publisher.py` con `publish_reel()` (media_type=REELS)
- [ ] Ampliar `main_pipeline.py` con `--reel` / `--reel-only`

**Resultado:** Reels con formato podcast visual — portada impactante,
transición fluida a modo podcast, waveform, subs con highlight, BGM.

### Fase 2 — Pulido + Integración (~6h)

- [ ] Scheduler: soporte para tipo `reel` / `both` en la queue
- [ ] Dashboard: preview de Reel (thumbnail + player)
- [ ] Dashboard: controles de voz/template/velocidad
- [ ] `post_store.py`: campo `media_format` (carousel/reel)
- [ ] Métricas: plays, likes, shares diferenciados para Reels
- [ ] Rotación de voz TTS (nova/onyx/alloy por día de la semana)
- [ ] Librería de 5-10 tracks BGM + 2-3 sfx de intro en `assets/`

**Resultado:** Sistema completo, 100% operado desde el dashboard.

---

## 13. Ejemplo de ejecución completa

```
$ python main_pipeline.py --reel --dry-run --topic "Apple lanza Vision Pro 2"

📡 STEP 1: Research — Using focused topic...
✓ Topic: Apple lanza Vision Pro 2 con chip M5 y menor peso

✍️  STEP 2: Content — Generating carousel text...
✓ Generated 8 slides

🎬 STEP 3a: Reel Script — Generating voiceover script...
✓ Cover title: "VISION PRO 2 ES REAL"
  Cover subtitle: "Apple reinventa las gafas con M5 y mitad de peso"
  Narration: 122 words, estimated duration: ~48s

🔊 STEP 3b: Voiceover — Generating TTS + Whisper alignment...
✓ TTS: 46.1s, voice=nova, speed=1.1
✓ Whisper: 194 word timestamps aligned

🎨 STEP 3c: Reel Frames — Rendering with Pillow...
✓ 2 frames (1080x1920), template: dark_blue
  → reel_frame_cover.png   (imagen + título + gradiente)
  → reel_frame_podcast.png (imagen blur + branding)

🎥 STEP 3d: Reel Compose — FFmpeg building final video...
✓ Portada: 3s, Ken Burns zoom 1.0x→1.05x
✓ Transición: xfade fadeblack 0.5s
✓ Podcast: 46.1s, Ken Burns zoom 1.0x→1.03x
✓ Waveform: showwaves cline, color=0x00d4ff, Y=1350
✓ Subtitles: 194 words, highlight sync, ASS burned
✓ Audio: 3s silence + voice + bgm (lofi_tech_03.mp3 @ 15%)
✓ Output: 49.1s, 1080x1920, 30fps, 12.3MB
  → output/reel_final.mp4

📊 STEP 4: Engagement — Building strategy...
✓ Hashtags: 30 tags, day_type: weekday_carousel

🚫 STEP 5: Publish — SKIPPED (dry-run)
  Would publish: carousel + reel for same topic
```
