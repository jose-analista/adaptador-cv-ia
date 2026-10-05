import os
import re
import time

import streamlit as st
from dotenv import load_dotenv

from core.extractor import extraer_requisitos
from core.lector import CVError, leer_cv
from llm_client import (
    CONFIG_POR_DEFECTO,
    Config,
    LLMError,
    generar,
    modelos_ollama,
    modelos_groq,
)

load_dotenv()

# Límite de caracteres de la oferta: más bajo en local para proteger modelos pequeños
MAX_OFERTA_LOCAL = 5000
MAX_OFERTA_EXTERNO = 12000

# Modelos preferidos en Groq (se elige el primero que exista en tu lista)
PREFERIDOS_GROQ = [
    "gpt-oss-120b",
    "llama-3.3-70b",
    "gpt-oss-20b",
    "llama-3.1-8b",
]

PROVEEDORES = {
    "Ollama (local)": {
        "proveedor": "ollama",
        "base_url": "http://localhost:11434",
    },
    "Groq": {
        "proveedor": "openai",
        "base_url": "https://api.groq.com/openai/v1",
        "env_key": "GROQ_API_KEY",
    },
    "OpenRouter": {
        "proveedor": "openai",
        "base_url": "https://openrouter.ai/api/v1",
        "env_key": "OPENROUTER_API_KEY",
        "modelo_defecto": "google/gemini-3.8-flash",
    },
}

st.set_page_config(page_title="Adaptador de CV", page_icon="📄")


# ---------- Utilidades ----------

@st.cache_data(ttl=120, show_spinner=False)
def _modelos_ollama(base_url):
    return modelos_ollama(base_url)


@st.cache_data(ttl=600, show_spinner=False)
def _modelos_groq(api_key, base_url):
    return modelos_groq(api_key, base_url)


def _indice_preferido(modelos, actual):
    """Índice del modelo por defecto: el actual, luego los preferidos, luego el primero."""
    if actual in modelos:
        return modelos.index(actual)
    for pref in PREFERIDOS_GROQ:
        for i, m in enumerate(modelos):
            if pref in m.lower():
                return i
    return 0


def _es_local(cfg):
    return cfg.proveedor == "ollama" and (
        "localhost" in cfg.base_url or "127.0.0.1" in cfg.base_url
    )


def _lineas(texto):
    return [l.strip() for l in texto.splitlines() if l.strip()]


def _sin_duplicados(items):
    """Quita repetidos exactos y los que ya están contenidos en otro más completo.

    Ejemplo: "GCP" se descarta si existe "Experiencia en arquitectura de GCP".
    Compara por palabras completas, así "Java" no se confunde con "JavaScript".
    """
    limpios, vistos = [], set()
    for it in items:
        it = it.strip()
        if it and it.lower() not in vistos:
            vistos.add(it.lower())
            limpios.append(it)

    resultado = []
    for it in limpios:
        patron = r"(?<!\w)" + re.escape(it.lower()) + r"(?!\w)"
        contenido = any(
            otro is not it and len(otro) > len(it) and re.search(patron, otro.lower())
            for otro in limpios
        )
        if not contenido:
            resultado.append(it)
    return resultado


# ---------- Barra lateral ----------

def configurar_modelo():
    """Barra lateral para elegir proveedor y modelo. Devuelve un Config."""
    base = CONFIG_POR_DEFECTO
    with st.sidebar:
        st.header("⚙️ Modelo de IA")
        nombre = st.selectbox("Proveedor", list(PROVEEDORES))
        p = PROVEEDORES[nombre]

        if p["proveedor"] == "ollama":
            base_url = st.text_input("Dirección de Ollama", p["base_url"])
            instalados = _modelos_ollama(base_url)
            if instalados:
                indice = instalados.index(base.modelo) if base.modelo in instalados else 0
                modelo = st.selectbox("Modelo instalado", instalados, index=indice)
            else:
                st.warning("No encontré modelos. ¿Ollama está corriendo?")
                modelo = st.text_input("Nombre del modelo", base.modelo)
            api_key = ""
            timeout_defecto = 600
        else:
            base_url = p["base_url"]
            api_key = os.getenv(p["env_key"], os.getenv("LLM_API_KEY", ""))
            timeout_defecto = 120

            if api_key:
                st.caption("🔑 API key cargada desde .env")
            else:
                api_key = st.text_input(
                    "API key",
                    type="password",
                    help=f"No encontré {p['env_key']} en .env. Solo se guarda en esta sesión.",
                )

            if nombre == "Groq":
                modelos = _modelos_groq(api_key, base_url) if api_key.strip() else []
                if modelos:
                    indice = _indice_preferido(modelos, base.modelo)
                    modelo = st.selectbox("Modelo disponible en Groq", modelos, index=indice)
                    if st.button("🔄 Actualizar modelos"):
                        _modelos_groq.clear()
                        st.rerun()
                else:
                    st.warning("No pude obtener los modelos de Groq. Revisa GROQ_API_KEY en tu .env.")
                    modelo = st.text_input("Nombre del modelo", value="openai/gpt-oss-20b")
            else:
                modelo = st.text_input(
                    "Nombre del modelo",
                    value=p.get("modelo_defecto", base.modelo),
                    help="Escríbelo tal como aparece en el catálogo del proveedor.",
                )

        timeout = st.number_input("Tiempo máximo (segundos)", 30, 1800, timeout_defecto, step=30)
        cfg = Config(
            proveedor=p["proveedor"],
            modelo=modelo.strip(),
            base_url=base_url,
            api_key=api_key.strip(),
            timeout=int(timeout),
        )

        if st.button("Probar conexión", disabled=not cfg.modelo):
            try:
                inicio = time.perf_counter()
                with st.spinner("Probando..."):
                    generar("Responde solo: ok", config=cfg)
                st.success(f"Respondió en {time.perf_counter() - inicio:.1f} s")
            except LLMError as e:
                st.error(str(e))

        if not _es_local(cfg):
            st.caption("⚠️ El texto que analices se enviará a este proveedor externo.")
    return cfg


cfg = configurar_modelo()

st.title("📄 Adaptador de CV a ofertas")
st.caption(f"Modelo: {cfg.modelo or 'sin elegir'} ({'local' if cfg.proveedor == 'ollama' else 'externo'})")


# ---------- Funciones con caché ----------

@st.cache_data(show_spinner=False)
def _leer(contenido, nombre):
    return leer_cv(contenido, nombre)


@st.cache_data(show_spinner=False)
def _extraer(oferta, proveedor, modelo, base_url, timeout, _api_key):
    # La clave lleva guion bajo para que no entre en la llave del caché
    c = Config(proveedor=proveedor, modelo=modelo, base_url=base_url, api_key=_api_key, timeout=timeout)
    return extraer_requisitos(oferta, config=c)


# ---------- Entradas ----------

col1, col2 = st.columns(2)
with col1:
    archivo = st.file_uploader("Sube tu CV", type=["pdf", "docx"])
with col2:
    oferta = st.text_area("Pega la oferta laboral", height=200)

if archivo:
    try:
        texto_cv = _leer(archivo.getvalue(), archivo.name)
    except CVError as e:
        st.session_state.pop("texto_cv", None)
        st.error(str(e))
    else:
        # Se guarda para los siguientes pasos (comparador y generador)
        st.session_state["texto_cv"] = texto_cv
        with st.expander(f"Texto extraído del CV ({len(texto_cv)} caracteres)"):
            st.text(texto_cv)
else:
    st.session_state.pop("texto_cv", None)

max_oferta = MAX_OFERTA_LOCAL if _es_local(cfg) else MAX_OFERTA_EXTERNO
oferta = oferta.strip()
if len(oferta) > max_oferta:
    st.warning(f"La oferta es muy larga; uso solo los primeros {max_oferta} caracteres.")
    oferta = oferta[:max_oferta]

if st.button("Extraer requisitos de la oferta", disabled=not (oferta and cfg.modelo)):
    try:
        with st.spinner("Analizando la oferta..."):
            resultado = _extraer(
                oferta, cfg.proveedor, cfg.modelo, cfg.base_url, cfg.timeout, cfg.api_key
            )
        # Copia con duplicados eliminados (no modifica el resultado cacheado)
        st.session_state["requisitos"] = {
            **resultado,
            "obligatorios": _sin_duplicados(resultado["obligatorios"]),
            "deseables": _sin_duplicados(resultado["deseables"]),
        }
        st.session_state["oferta_analizada"] = oferta
    except LLMError as e:
        st.error(str(e))


# ---------- Requisitos ----------

req = st.session_state.get("requisitos")
if req:
    if st.session_state.get("oferta_analizada") != oferta:
        st.info("La oferta cambió desde el último análisis. Vuelve a extraer los requisitos.")

    st.subheader(f"Requisitos: {req['puesto'] or 'puesto sin nombre'}")
    st.caption("Revisa y corrige: el modelo puede equivocarse. Un requisito por línea.")
    c1, c2 = st.columns(2)
    with c1:
        obligatorios = st.text_area("Obligatorios", "\n".join(req["obligatorios"]), height=180)
    with c2:
        deseables = st.text_area("Deseables", "\n".join(req["deseables"]), height=180)

    # Esto es lo que usará el siguiente paso (Comparador)
    st.session_state["requisitos_final"] = {
        "puesto": req["puesto"],
        "obligatorios": _lineas(obligatorios),
        "deseables": _lineas(deseables),
    }