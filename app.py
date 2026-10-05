import os
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
MAX_OFERTA = 5000  # caracteres; protege el contexto de modelos pequeños

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
        "modelos": [
            "google/gemini-3.8-flash",
        ],
    },
}

st.set_page_config(page_title="Adaptador de CV", page_icon="📄")


def configurar_modelo():
    """Barra lateral para elegir proveedor y modelo. Devuelve un Config."""
    base = CONFIG_POR_DEFECTO
    with st.sidebar:
        st.header("⚙️ Modelo de IA")
        nombre = st.selectbox("Proveedor", list(PROVEEDORES))
        p = PROVEEDORES[nombre]

        if p["proveedor"] == "ollama":
            base_url = st.text_input("Dirección de Ollama", p["base_url"])
            instalados = modelos_ollama(base_url)
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
        

            if api_key:
                st.caption("🔑 API key cargada desde .env")
            else:
                api_key = st.text_input(
                    "API key",
                    type="password",
                    help=f"No encontré {p['env_key']} en .env. Solo se guarda en esta sesión.",
                )
            timeout_defecto = 120

            if nombre == "Groq":
                modelos = modelos_groq(api_key, base_url) if api_key.strip() else []
                if modelos:
                    indice = modelos.index(base.modelo) if base.modelo in modelos else 0
                    modelo = st.selectbox("Modelo disponible en Groq", modelos, index=indice)
                else:
                    st.warning("No pude obtener los modelos de Groq. Comprueba la API key.")
                    modelo = st.text_input("Nombre del modelo", value="openai/gpt-oss-20b")
            elif p.get("modelos"):
                modelo = st.selectbox("Modelo", p["modelos"])
            else:
                modelo = st.text_input("Nombre del modelo", value=base.modelo)

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

        local = cfg.proveedor == "ollama" and ("localhost" in base_url or "127.0.0.1" in base_url)
        if not local:
            st.caption("⚠️ El texto que analices se enviará a este proveedor externo.")
    return cfg


cfg = configurar_modelo()

st.title("📄 Adaptador de CV a ofertas")
st.caption(f"Modelo: {cfg.modelo or 'sin elegir'} ({'local' if cfg.proveedor == 'ollama' else 'externo'})")


@st.cache_data(show_spinner=False)
def _leer(contenido, nombre):
    return leer_cv(contenido, nombre)


@st.cache_data(show_spinner=False)
def _extraer(oferta, proveedor, modelo, base_url, timeout, _api_key):
    # La clave lleva guion bajo para que no entre en la llave del caché
    c = Config(proveedor=proveedor, modelo=modelo, base_url=base_url, api_key=_api_key, timeout=timeout)
    return extraer_requisitos(oferta, config=c)


def _lineas(texto):
    return [l.strip() for l in texto.splitlines() if l.strip()]


col1, col2 = st.columns(2)
with col1:
    archivo = st.file_uploader("Sube tu CV", type=["pdf", "docx"])
with col2:
    oferta = st.text_area("Pega la oferta laboral", height=200)

if archivo:
    try:
        texto_cv = _leer(archivo.getvalue(), archivo.name)
    except CVError as e:
        st.error(str(e))
    else:
        with st.expander(f"Texto extraído del CV ({len(texto_cv)} caracteres)"):
            st.text(texto_cv)

oferta = oferta.strip()
if len(oferta) > MAX_OFERTA:
    st.warning(f"La oferta es muy larga; uso solo los primeros {MAX_OFERTA} caracteres.")
    oferta = oferta[:MAX_OFERTA]

if st.button("Extraer requisitos de la oferta", disabled=not (oferta and cfg.modelo)):
    try:
        with st.spinner("Analizando la oferta..."):
            st.session_state["requisitos"] = _extraer(
                oferta, cfg.proveedor, cfg.modelo, cfg.base_url, cfg.timeout, cfg.api_key
            )
            st.session_state["oferta_analizada"] = oferta
    except LLMError as e:
        st.error(str(e))

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