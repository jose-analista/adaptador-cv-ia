"""
Único punto de contacto con la IA.

Soporta:
- Ollama local
- Groq
- OpenRouter
- Otros proveedores compatibles con la API de OpenAI

Los modelos de proveedores externos se consultan dinámicamente
desde su endpoint /models para evitar depender de nombres antiguos.
"""

import json
import os
import re
from dataclasses import dataclass

import requests


class LLMError(Exception):
    """Error al hablar con el modelo."""


@dataclass(frozen=True)
class Config:
    proveedor: str = "ollama"
    modelo: str = "qwen2.5:3b"
    base_url: str = "http://localhost:11434"
    api_key: str = ""
    num_ctx: int = 4096
    max_tokens: int = 800
    timeout: int = 180


def config_desde_entorno():
    return Config(
        proveedor=os.getenv("LLM_PROVEEDOR", "ollama"),
        modelo=os.getenv("LLM_MODELO", "qwen2.5:3b"),
        base_url=os.getenv(
            "LLM_BASE_URL",
            "http://localhost:11434",
        ),
        api_key=os.getenv("LLM_API_KEY", ""),
        num_ctx=int(os.getenv("LLM_NUM_CTX", "4096")),
        max_tokens=int(os.getenv("LLM_MAX_TOKENS", "800")),
        timeout=int(os.getenv("LLM_TIMEOUT", "180")),
    )


CONFIG_POR_DEFECTO = config_desde_entorno()


# ============================================================
# OLLAMA
# ============================================================

def modelos_ollama(base_url="http://localhost:11434"):
    """
    Lista los modelos instalados en Ollama.
    Devuelve [] si Ollama no responde.
    """

    base_url = base_url.rstrip("/")

    try:
        r = requests.get(
            f"{base_url}/api/tags",
            timeout=3,
        )

        r.raise_for_status()

        modelos = r.json().get("models", [])

        return sorted(
            m["name"]
            for m in modelos
            if m.get("name")
        )

    except Exception:
        return []


# ============================================================
# PROVEEDORES COMPATIBLES CON OPENAI
# ============================================================

def modelos_openai_compatible(api_key, base_url):
    """
    Obtiene dinámicamente los modelos disponibles de un proveedor
    compatible con la API de OpenAI.

    Funciona con Groq, OpenRouter y otros proveedores que expongan:

        GET /models
    """

    if not api_key:
        return []

    base_url = base_url.rstrip("/")

    try:
        r = requests.get(
            f"{base_url}/models",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            timeout=10,
        )

        r.raise_for_status()

        datos = r.json()

        modelos = datos.get("data", [])

        resultado = []

        for modelo in modelos:
            modelo_id = modelo.get("id")

            if modelo_id:
                resultado.append(modelo_id)

        return sorted(set(resultado))

    except requests.HTTPError:
        return []

    except requests.RequestException:
        return []

    except (ValueError, TypeError):
        return []


def modelos_groq(
    api_key,
    base_url="https://api.groq.com/openai/v1",
):
    """
    Obtiene los modelos actuales disponibles en Groq.

    No mantiene una lista fija para evitar errores cuando Groq
    depreca o agrega modelos.
    """

    return modelos_openai_compatible(
        api_key,
        base_url,
    )


def modelos_openrouter(
    api_key,
    base_url="https://openrouter.ai/api/v1",
):
    """
    Obtiene dinámicamente los modelos disponibles en OpenRouter.
    """

    return modelos_openai_compatible(
        api_key,
        base_url,
    )


# ============================================================
# VALIDACIÓN DE MODELO
# ============================================================

def modelo_disponible(
    modelo,
    api_key,
    base_url,
):
    """
    Comprueba si un modelo concreto existe y es accesible
    mediante GET /models/{modelo}.
    """

    if not modelo or not api_key:
        return False

    base_url = base_url.rstrip("/")

    try:
        r = requests.get(
            f"{base_url}/models/{modelo}",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            timeout=10,
        )

        return r.ok

    except requests.RequestException:
        return False


# ============================================================
# GENERAR
# ============================================================

def generar(prompt, como_json=False, config=None):
    """
    Envía un prompt al modelo y devuelve el texto.
    """

    cfg = config or CONFIG_POR_DEFECTO

    if not cfg.modelo:
        raise LLMError("No se ha seleccionado ningún modelo.")

    try:

        # ====================================================
        # OLLAMA
        # ====================================================

        if cfg.proveedor == "ollama":

            base_url = cfg.base_url.rstrip("/")

            cuerpo = {
                "model": cfg.modelo,
                "prompt": prompt,
                "stream": False,
                "keep_alive": "30m",
                "options": {
                    "num_ctx": cfg.num_ctx,
                    "num_predict": cfg.max_tokens,
                    "temperature": 0.2,
                },
            }

            if como_json:
                cuerpo["format"] = "json"

            r = requests.post(
                f"{base_url}/api/generate",
                json=cuerpo,
                timeout=cfg.timeout,
            )

            r.raise_for_status()

            datos = r.json()

            if "response" not in datos:
                raise LLMError(
                    "Ollama respondió, pero no entregó texto."
                )

            return datos["response"]

        # ====================================================
        # OPENAI COMPATIBLE
        # Groq / OpenRouter / etc.
        # ====================================================

        if cfg.proveedor == "openai":

            if not cfg.api_key:
                raise LLMError(
                    "Falta la API key del proveedor."
                )

            base_url = cfg.base_url.rstrip("/")

            cuerpo = {
                "model": cfg.modelo,
                "messages": [
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ],
                "temperature": 0.2,
                "max_tokens": cfg.max_tokens,
            }

            if como_json:
                cuerpo["response_format"] = {
                    "type": "json_object"
                }

            r = requests.post(
                f"{base_url}/chat/completions",
                json=cuerpo,
                headers={
                    "Authorization": f"Bearer {cfg.api_key}",
                    "Content-Type": "application/json",
                },
                timeout=cfg.timeout,
            )

            r.raise_for_status()

            datos = r.json()

            return datos["choices"][0]["message"]["content"]

        raise LLMError(
            f"Proveedor no soportado: {cfg.proveedor}"
        )

    except requests.ConnectionError:
        raise LLMError(
            "No pude conectar con el proveedor. "
            "Si usas Ollama, comprueba que esté ejecutándose."
        )

    except requests.Timeout:
        raise LLMError(
            "El modelo tardó demasiado en responder. "
            "Puedes aumentar el tiempo máximo."
        )

    except requests.HTTPError as e:

        codigo = (
            e.response.status_code
            if e.response is not None
            else "?"
        )

        detalle = (
            e.response.text[:500]
            if e.response is not None
            else ""
        )

        if codigo == 401:
            raise LLMError(
                "La API key no es válida."
            )

        if codigo == 403:
            raise LLMError(
                "La API key es válida, pero no tiene "
                "permiso para utilizar este modelo."
            )

        if codigo == 404:

            if cfg.proveedor == "ollama":
                raise LLMError(
                    f"Ollama no tiene el modelo "
                    f"'{cfg.modelo}'.\n\n"
                    f"Puedes instalarlo con:\n"
                    f"ollama pull {cfg.modelo}"
                )

            raise LLMError(
                f"El modelo '{cfg.modelo}' ya no está "
                f"disponible o no tienes acceso a él.\n\n"
                f"Actualiza la lista de modelos disponibles "
                f"y selecciona uno nuevo."
            )

        raise LLMError(
            f"El proveedor devolvió el error "
            f"{codigo}: {detalle}"
        )

    except (KeyError, ValueError, TypeError) as e:
        raise LLMError(
            f"Respuesta inesperada del proveedor: {e}"
        )


# ============================================================
# JSON
# ============================================================

def _extraer_json(texto):
    """
    Intenta obtener un objeto JSON del texto,
    aunque el modelo incluya texto adicional.
    """

    texto = texto.strip()

    try:
        return json.loads(texto)

    except json.JSONDecodeError:
        pass

    m = re.search(
        r"\{.*\}",
        texto,
        re.DOTALL,
    )

    if m:

        try:
            return json.loads(m.group(0))

        except json.JSONDecodeError:
            return None

    return None


def generar_json(
    prompt,
    claves,
    reintentos=3,
    config=None,
):
    """
    Pide JSON al modelo, lo valida y reintenta
    si la respuesta no contiene las claves requeridas.
    """

    aviso = ""

    for _ in range(reintentos):

        texto = generar(
            prompt + aviso,
            como_json=True,
            config=config,
        )

        datos = _extraer_json(texto)

        if (
            isinstance(datos, dict)
            and all(
                clave in datos
                for clave in claves
            )
        ):
            return datos

        aviso = (
            "\n\nIMPORTANTE: tu respuesta anterior "
            "no fue válida.\n"
            "Responde SOLO con un JSON válido "
            "que tenga las claves: "
            f"{', '.join(claves)}."
        )

    raise LLMError(
        "El modelo no devolvió un JSON válido "
        "después de varios intentos."
    )