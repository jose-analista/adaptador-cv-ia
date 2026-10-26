import os
import streamlit as st
from dotenv import load_dotenv

from core.extractor import extraer_requisitos
from core.lector import CVError, leer_cv
from core.db import JobDB
from llm_client import (
    Config,
    CONFIG_POR_DEFECTO,
    generar,
    generar_json,
    LLMError,
    modelos_ollama,
    modelos_groq,
)

load_dotenv()

# Inicializar la base de datos
db = JobDB()

st.set_page_config(page_title="AutoPostulador IA", layout="centered")
st.title("🚀 AutoPostulador con IA y SQLite")

# ==========================================================
# 0. CONFIGURACIÓN DEL MODELO (Restaurado)
# ==========================================================
st.sidebar.header("⚙️ Configuración de IA")

PROVEEDORES = {
    "Ollama (Local)": {
        "proveedor": "ollama",
        "base_url": "http://localhost:11434",
        "env_key": "",
    },
    "Groq (Rápido en la nube)": {
        "proveedor": "openai",
        "base_url": "https://api.groq.com/openai/v1",
        "env_key": "GROQ_API_KEY",
    },
}

proveedor_seleccionado = st.sidebar.selectbox(
    "Proveedor", 
    list(PROVEEDORES.keys()),
    index=1 # Por defecto Groq para evitar timeouts
)

config_prov = PROVEEDORES[proveedor_seleccionado]

# Obtener API Key (del .env o del input del usuario)
api_key = os.getenv(config_prov["env_key"], "")
if config_prov["proveedor"] == "openai" and not api_key:
    api_key = st.sidebar.text_input("API Key de Groq/OpenRouter", type="password")

# Cargar modelos disponibles dinámicamente
with st.sidebar:
    with st.spinner("Cargando modelos..."):
        if config_prov["proveedor"] == "ollama":
            modelos_disponibles = modelos_ollama(config_prov["base_url"])
            if not modelos_disponibles:
                st.warning("No se detectó Ollama. ¿Está corriendo?")
                modelos_disponibles = ["qwen2.5:3b", "llama3.2:3b"] # Fallback
        else:
            modelos_disponibles = modelos_groq(api_key, config_prov["base_url"])
            # Fallback a modelos conocidos de Groq si la API falla o está vacía
            if not modelos_disponibles:
                modelos_disponibles = ["llama-3.1-8b-8192", "llama-3.3-70b-versatile", "mixtral-8x7b-32768"]

modelo_seleccionado = st.sidebar.selectbox("Modelo", modelos_disponibles)

# Crear el objeto Config dinámico para esta sesión
config_actual = Config(
    proveedor=config_prov["proveedor"],
    modelo=modelo_seleccionado,
    base_url=config_prov["base_url"],
    api_key=api_key,
    num_ctx=4096,
    max_tokens=800,
    timeout=120 # 120 segundos es más que suficiente para Groq
)

st.sidebar.success(f"✅ Usando: {modelo_seleccionado}")

# ==========================================================
# 1. ENTRADA DE DATOS
# ==========================================================
st.subheader("1. Sube tu CV y la Oferta")
col1, col2 = st.columns(2)

with col1:
    archivo_cv = st.file_uploader("Sube tu CV", type=["pdf", "docx", "txt"])
    cv_nombre = archivo_cv.name if archivo_cv else "cv_desconocido.pdf"

with col2:
    url_oferta = st.text_input("URL de la oferta (Opcional)", "https://linkedin.com/jobs/...")
    texto_oferta = st.text_area("Pega la descripción de la oferta aquí", height=200)

# ==========================================================
# 2. PROCESAMIENTO
# ==========================================================
if "datos_procesados" not in st.session_state:
    st.session_state.datos_procesados = None

if st.button("🧠 Analizar y Generar Carta"):
    if not archivo_cv or not texto_oferta:
        st.warning("Por favor, sube un CV y pega una oferta de trabajo.")
    else:
        with st.spinner(f"Analizando con {modelo_seleccionado}..."):
            try:
                # 1. Leer CV
                texto_cv = leer_cv(archivo_cv.read(), archivo_cv.name)
                
                # 2. Extraer requisitos (usando config_actual)
                prompt_extraccion = f"""
                Analiza el siguiente CV y la oferta de trabajo.
                Responde ÚNICAMENTE con un objeto JSON válido con este formato exacto:
                {{
                  "empresa": "Nombre de la empresa",
                  "puesto": "Título del puesto",
                  "match_score": 75,
                  "puntos_fuertes": ["Experiencia en Python", "Gestión de equipos"]
                }}
                CV: {texto_cv[:1500]}
                OFERTA: {texto_oferta[:1500]}
                """
                
                datos_extraccion = generar_json(
                    prompt=prompt_extraccion,
                    claves=["empresa", "puesto", "match_score", "puntos_fuertes"],
                    config=config_actual # ← AQUÍ USAMOS LA CONFIG DINÁMICA
                )
                
                empresa_extraida = datos_extraccion.get("empresa", "Empresa no identificada")
                puesto_extraido = datos_extraccion.get("puesto", "Puesto no identificado")
                puntuacion_match = datos_extraccion.get("match_score", 0)
                
                # 3. Generar carta (usando config_actual)
                prompt_carta = f"""
                Escribe una carta de presentación profesional y persuasiva para el puesto de {puesto_extraido} en {empresa_extraida}. 
                Destaca estos puntos fuertes de mi CV: {', '.join(datos_extraccion.get('puntos_fuertes', []))}. 
                La oferta menciona estos requisitos: {texto_oferta[:800]}...
                """
                
                carta_generada = generar(
                    prompt=prompt_carta,
                    config=config_actual # ← AQUÍ TAMBIÉN
                )
                
                # 4. Guardar en sesión
                st.session_state.datos_procesados = {
                    "empresa": empresa_extraida,
                    "puesto": puesto_extraido,
                    "score": puntuacion_match,
                    "carta": carta_generada,
                    "cv_nombre": cv_nombre,
                    "url": url_oferta
                }
                
                st.success("¡Análisis y generación completados!")
                
            except CVError as e:
                st.error(f"Error al leer el CV: {e}")
            except LLMError as e:
                st.error(f"Error con el modelo de IA: {e}")
            except Exception as e:
                st.error(f"Error inesperado: {e}")

# ==========================================================
# 3. VISUALIZACIÓN Y GUARDADO
# ==========================================================
if st.session_state.datos_procesados:
    datos = st.session_state.datos_procesados
    
    st.divider()
    st.subheader(f"📄 Resultado para: {datos['puesto']} en {datos['empresa']}")
    
    st.metric(label="Compatibilidad (Match Score)", value=f"{datos['score']}/100")
    st.progress(min(datos['score'], 100) / 100) # min() evita errores si el score es > 100
    
    st.text_area("Carta de Presentación Generada", value=datos['carta'], height=300)
    
    st.divider()
    
    if st.button("💾 Guardar Postulación en Base de Datos (SQLite)"):
        db.guardar_postulacion(
            empresa=datos['empresa'],
            puesto=datos['puesto'],
            url=datos['url'],
            cv_nombre=datos['cv_nombre'],
            score=datos['score'],
            cover_letter=datos['carta']
        )
        st.success("✅ ¡Postulación guardada exitosamente en `aplicaciones.db`!")
        
        st.subheader("📜 Historial Reciente")
        historial = db.obtener_historial(limite=3)
        for h in historial:
            st.write(f"- **{h['puesto']}** en {h['empresa']} (Score: {h['match_score']}) - {h['estado']}")