import io

import pdfplumber
from docx import Document


class CVError(Exception):
    """No se pudo leer el CV."""


def _leer_docx(contenido):
    doc = Document(io.BytesIO(contenido))
    partes = [p.text for p in doc.paragraphs]
    # Muchos CVs usan tablas para el diseño: también hay que leerlas
    for tabla in doc.tables:
        for fila in tabla.rows:
            for celda in fila.cells:
                partes.append(celda.text)
    return "\n".join(partes)


def _leer_pdf(contenido):
    with pdfplumber.open(io.BytesIO(contenido)) as pdf:
        return "\n".join(p.extract_text() or "" for p in pdf.pages)


def leer_cv(contenido, nombre):
    """Recibe los bytes del archivo y su nombre. Devuelve el texto del CV."""
    try:
        if nombre.lower().endswith(".pdf"):
            texto = _leer_pdf(contenido)
        else:
            texto = _leer_docx(contenido)
    except Exception as e:
        raise CVError(
            "No pude leer el archivo. ¿Está dañado o protegido con contraseña?"
        ) from e

    texto = texto.strip()
    if not texto:
        raise CVError(
            "No encontré texto en el archivo. Si es un PDF escaneado "
            "(una imagen), necesitaría OCR."
        )
    return texto