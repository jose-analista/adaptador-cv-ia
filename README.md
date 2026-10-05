# 📄 Adaptador de CV a ofertas laborales

Herramienta en **Python + Streamlit** que ayuda a adaptar tu CV a una oferta de trabajo: lee tu CV, extrae los requisitos de la oferta con IA y los deja listos para compararlos con tus habilidades.

Funciona con **modelos open source locales** (Ollama) o **alojados** (Groq, OpenRouter), y puedes cambiar de modelo desde la propia app.

> 🚧 **Proyecto en desarrollo.** Mira la sección [Estado](#estado).

## Qué hace hoy

- Lee CVs en **PDF** y **Word (.docx)**, incluidas las tablas de Word.
- Extrae de la oferta el puesto, los requisitos **obligatorios** y los **deseables**.
- Te deja **corregir** los requisitos antes de seguir (los modelos pequeños se equivocan).
- Permite elegir **proveedor y modelo** desde la barra lateral, con un botón para probar la conexión.
- Guarda en caché los análisis para no repetir llamadas al modelo.

## Estado

- [x] Lector de CV (PDF y DOCX)
- [x] Extractor de requisitos con IA
- [x] Selector de proveedor y modelo
- [ ] Comparador: habilidades de la persona vs. requisitos de la oferta
- [ ] Generador del CV adaptado
- [ ] Exportación a PDF
- [ ] Perfil de habilidades guardado

## Requisitos

- Python 3.10 o superior
- Para usar IA local: [Ollama](https://ollama.com) y un modelo descargado
- Para usar IA alojada: una API key de [Groq](https://console.groq.com) u [OpenRouter](https://openrouter.ai)

## Instalación

```bash
git clone https://github.com/jose-analista/adaptador-cv-ia.git
cd adaptador-cv-ia

python3 -m venv .venv
source .venv/bin/activate        # En Windows: .venv\Scripts\activate

pip install -r requirements.txt
```

## Uso

```bash
streamlit run app.py
```

Se abre en `http://localhost:8501`. Si no quieres que se abra el navegador solo:

```bash
streamlit run app.py --server.headless true
```

### Opción A: IA local con Ollama

```bash
ollama pull qwen2.5:3b
```

En la app elige **Ollama (local)** y el modelo instalado. Con equipos de poca RAM (unos 4 GB libres) conviene un modelo de 3B parámetros o menos. En CPU puede ser lento, así que sube el tiempo máximo en la barra lateral.

### Opción B: IA alojada (Groq, OpenRouter)

En la app elige el proveedor y pega tu API key, o defínela antes de iniciar:

```bash
export GROQ_API_KEY=tu_clave
# o
export OPENROUTER_API_KEY=tu_clave
```

La clave solo se usa en la sesión y no se guarda en disco.

### Variables de entorno opcionales

Definen los valores por defecto al abrir la app:

| Variable | Qué controla |
|---|---|
| `LLM_PROVEEDOR` | `ollama` u `openai` (API compatible con OpenAI) |
| `LLM_MODELO` | Nombre del modelo |
| `LLM_BASE_URL` | Dirección del servicio |
| `LLM_API_KEY` | Clave de la API |
| `LLM_NUM_CTX` | Contexto para Ollama (por defecto 4096) |
| `LLM_TIMEOUT` | Tiempo máximo en segundos |

## Estructura

```
adaptador-cv-ia/
├── app.py            # Interfaz Streamlit
├── llm_client.py     # Único punto de contacto con la IA
├── db.py             # Almacenamiento local
├── core/
│   ├── lector.py     # Lee CVs en PDF y DOCX
│   ├── extractor.py  # Extrae requisitos de la oferta
│   ├── comparador.py # Compara perfil y requisitos (en desarrollo)
│   └── generador.py  # Genera el CV adaptado (en desarrollo)
└── requirements.txt
```

La IA está aislada detrás de `llm_client.py`: para cambiar de modelo o de proveedor no hace falta tocar el resto del código.

## Privacidad

- Con **Ollama local**, tus textos no salen de tu equipo.
- Con **Groq u OpenRouter**, el texto que analices se envía a ese proveedor. Revisa su política de datos antes de usar CVs reales de otras personas.
- No subas CVs reales ni archivos con claves a este repositorio.

## Limitaciones conocidas

- Los **PDF escaneados** (imágenes) no tienen texto y necesitan OCR antes de usarse.
- Los modelos pequeños pueden clasificar mal los requisitos o devolver JSON inválido; la app reintenta y te deja corregir el resultado.
- La IA puede equivocarse: revisa siempre lo que genere antes de usarlo en un CV real.

## Licencia

Pendiente de definir.
