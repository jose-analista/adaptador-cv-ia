from llm_client import generar_json

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


def extraer_requisitos(oferta, config=None):
    """Devuelve {'puesto': str, 'obligatorios': [..], 'deseables': [..]}."""
    datos = generar_json(
        PROMPT.format(oferta=oferta.strip()),
        claves=["obligatorios", "deseables"],
        config=config,
    )
    return {
        "puesto": str(datos.get("puesto", "")).strip(),
        "obligatorios": _lista_de_textos(datos["obligatorios"]),
        "deseables": _lista_de_textos(datos["deseables"]),
    }