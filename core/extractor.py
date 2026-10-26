from llm_client import generar_json, CONFIG_POR_DEFECTO

PROMPT = """Eres un analista de selección de personal. Lee la oferta laboral y extrae sus requisitos.

Responde SOLO con un JSON con estas claves:
- "puesto": nombre del puesto (texto)
- "obligatorios": lista de requisitos imprescindibles
- "deseables": lista de requisitos que se valoran pero no son imprescindibles

Reglas:
- Cada requisito debe ser corto (2 a 6 palabras).
- No inventes nada que no esté en la oferta.
- Si no hay deseables, usa una lista vacía.

Oferta:
\"\"\"
{oferta}
\"\"\"
"""


def _lista_de_textos(valor):
    """Asegura que el valor sea una lista de textos limpios."""
    if not isinstance(valor, list):
        return []
    return [str(x).strip() for x in valor if str(x).strip()]


def extraer_requisitos(texto_cv: str, texto_oferta: str) -> dict:
    prompt = f"""
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
    
    # ✅ CORRECTO: Usar generar_json pasando el objeto CONFIG_POR_DEFECTO
    return generar_json(
        prompt=prompt,
        claves=["empresa", "puesto", "match_score", "puntos_fuertes"],
        config=CONFIG_POR_DEFECTO 
    )