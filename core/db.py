# core/db.py
import sqlite3
from datetime import datetime
import json

class JobDB:
    def __init__(self, db_path="aplicaciones.db"):
        self.db_path = db_path
        self._init_db()

    def _get_conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Permite acceder por nombre de columna
        return conn

    def _init_db(self):
        with self._get_conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS postulaciones (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    fecha TEXT,
                    empresa TEXT,
                    puesto TEXT,
                    url_oferta TEXT,
                    nombre_cv TEXT,
                    match_score INTEGER,
                    cover_letter TEXT,
                    estado TEXT DEFAULT 'Pendiente'
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS cvs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nombre TEXT,
                    contenido TEXT,
                    fecha_creacion TEXT
                )
            """)

    def guardar_postulacion(self, empresa, puesto, url, cv_nombre, score, cover_letter):
        with self._get_conn() as conn:
            conn.execute("""
                INSERT INTO postulaciones (fecha, empresa, puesto, url_oferta, nombre_cv, match_score, cover_letter)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (datetime.now().isoformat(), empresa, puesto, url, cv_nombre, score, cover_letter))

    def obtener_historial(self, limite=10):
        with self._get_conn() as conn:
            cursor = conn.execute("SELECT * FROM postulaciones ORDER BY fecha DESC LIMIT ?", (limite,))
            return [dict(row) for row in cursor.fetchall()]