#!/bin/bash
# Va a la carpeta del proyecto (la misma donde está este script)
cd "$(dirname "$0")" || exit 1

# Si no existe el entorno virtual, lo crea e instala las dependencias
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
else
    source .venv/bin/activate
fi

# Inicia Streamlit
#streamlit run app.py

# Inicia Streamlit sin abrir el navegador
streamlit run app.py --server.headless true
