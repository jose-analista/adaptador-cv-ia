"""Único punto de contacto con la IA.

La configuración (proveedor, modelo, clave) se puede pasar en cada llamada con
un objeto Config, así la app puede cambiar de modelo en vivo. Si no pasas nada,
se usa la configuración de las variables de entorno (ver al final).
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
    proveedor: str = "ollama"  # "ollama" u "openai" (API compatible con OpenAI)
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
        base_url=os.getenv("LLM_BASE_URL", "http://localhost:11434"),
        api_key=os.getenv("LLM_API_KEY", ""),
        num_ctx=int(os.getenv("LLM_NUM_CTX", "4096")),
        timeout=int(os.getenv("LLM_TIMEOUT", "180")),
    )


CONFIG_POR_DEFECTO = config_desde_entorno()


def modelos_ollama(base_url="http://localhost:11434"):
    """Lista los modelos instalados en Ollama (vacía si no responde)."""
    try:
        r = requests.get(f"{base_url}/api/tags", timeout=3)
        r.raise_for_status()
        return sorted(m["name"] for m in r.json().get("models", []))
    except Exception:
        return []


def generar(prompt, como_json=False, config=None):
    """Envía un prompt al modelo y devuelve el texto de la respuesta."""
    cfg = config or CONFIG_POR_DEFECTO
    try:
        if cfg.proveedor == "ollama":
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
            r = requests.post(f"{cfg.base_url}/api/generate", json=cuerpo, timeout=cfg.timeout)
            r.raise_for_status()
            return r.json()["response"]

        # API compatible con OpenAI (Groq, OpenRouter, etc.)
        if not cfg.api_key:
            raise LLMError("Falta la API key del proveedor.")
        cuerpo = {
            "model": cfg.modelo,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.2,
            "max_tokens": cfg.max_tokens,
        }
        if como_json:
            cuerpo["response_format"] = {"type": "json_object"}
        r = requests.post(
            f"{cfg.base_url}/chat/completions",
            json=cuerpo,
            headers={"Authorization": f"Bearer {cfg.api_key}"},
            timeout=cfg.timeout,
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]

    except requests.ConnectionError:
        raise LLMError(
            "No pude conectar con el proveedor. Si usas Ollama, ¿está corriendo? "
            "Prueba 'ollama ps' o 'ollama serve'."
        )
    except requests.Timeout:
        raise LLMError("El modelo tardó demasiado en responder (sube el tiempo máximo).")
    except requests.HTTPError as e:
        codigo = e.response.status_code if e.response is not None else "?"
        detalle = e.response.text[:200] if e.response is not None else ""
        if codigo in (401, 403):
            raise LLMError("La API key no es válida o no tiene permiso.")
        if codigo == 404 and cfg.proveedor == "ollama":
            raise LLMError(f"Ollama no tiene el modelo '{cfg.modelo}'. Descárgalo con: ollama pull {cfg.modelo}")
        raise LLMError(f"El proveedor devolvió el error {codigo}: {detalle}")
    except (KeyError, ValueError) as e:
        raise LLMError(f"Respuesta inesperada del proveedor: {e}")


def _extraer_json(texto):
    """Intenta obtener un objeto JSON del texto, aunque venga con relleno."""
    texto = texto.strip()
    try:
        return json.loads(texto)
    except json.JSONDecodeError:
        pass
    m = re.search(r"\{.*\}", texto, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            return None
    return None


def generar_json(prompt, claves, reintentos=3, config=None):
    """Pide JSON, lo valida (que tenga las claves) y reintenta si falla."""
    aviso = ""
    for _ in range(reintentos):
        texto = generar(prompt + aviso, como_json=True, config=config)
        datos = _extraer_json(texto)
        if isinstance(datos, dict) and all(c in datos for c in claves):
            return datos
        aviso = (
            "\n\nIMPORTANTE: tu respuesta anterior no fue válida. "
            f"Responde SOLO con un JSON que tenga las claves: {', '.join(claves)}."
        )
    raise LLMError("El modelo no devolvió un JSON válido después de varios intentos.")


# Variables de entorno opcionales (valores por defecto al abrir la app):
#   LLM_PROVEEDOR, LLM_MODELO, LLM_BASE_URL, LLM_API_KEY, LLM_NUM_CTX, LLM_TIMEOUT