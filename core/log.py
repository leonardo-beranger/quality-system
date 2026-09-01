"""Auditoría — arma las filas de `log_actividad` para cada cambio hecho por la app.

`log_actividad` tiene una fila por COLUMNA alterada (no por registro): tabla,
registro_id, accion ('INSERT'/'UPDATE'/'DELETE'), columna, valor_anterior,
valor_nuevo, usuario, fecha. Las funciones de acá devuelven listas de
(sql, params) en el mismo formato que `db.run_transaction_safe` espera, para
que el INSERT/UPDATE/DELETE real y su rastro de auditoría se graben en la
MISMA transacción — si uno falla, el otro tampoco queda grabado.

No escriben nada por sí solas: cada página arma sus operaciones normales,
les agrega lo que devuelven estas funciones, y manda todo junto a
`run_transaction_safe`.
"""

from __future__ import annotations

from .auth import usuario_actual
from .config import TABLES

T_LOG = TABLES["activity_log"]

_SQL_INSERT_LOG = f"""
    INSERT INTO {T_LOG} (tabla, registro_id, accion, columna, valor_anterior, valor_nuevo, usuario)
    VALUES (:tabla, :registro_id, :accion, :columna, :valor_anterior, :valor_nuevo, :usuario)
"""


def _usuario_log() -> str:
    """Nombre de quien está haciendo el cambio, para grabar en `usuario`.

    Se guarda el NOMBRE (no el id): así el log queda legible aunque el
    usuario sea desactivado/renombrado después — es historial, no debe
    depender de que la fila de quality_agent siga igual.
    """
    usuario = usuario_actual()
    return usuario["name"] if usuario else "desconocido"


def _valor_texto(valor) -> str | None:
    """Normaliza un valor cualquiera (None, NaN de pandas, número, string) a texto o None."""
    if valor is None:
        return None
    texto = str(valor).strip()
    if not texto or texto.lower() == "nan":
        return None
    return texto


def _fila_log(tabla: str, registro_id, accion: str, columna: str, anterior: str | None, nuevo: str | None) -> tuple[str, dict]:
    return (
        _SQL_INSERT_LOG,
        {
            "tabla": tabla,
            "registro_id": str(registro_id),
            "accion": accion,
            "columna": columna,
            "valor_anterior": anterior,
            "valor_nuevo": nuevo,
            "usuario": _usuario_log(),
        },
    )


def log_insert(tabla: str, registro_id, valores: dict) -> list[tuple[str, dict]]:
    """Una fila de log por columna con valor no vacío — `valor_anterior` queda NULL."""
    operaciones = []
    for columna, valor in valores.items():
        nuevo = _valor_texto(valor)
        if nuevo is None:
            continue
        operaciones.append(_fila_log(tabla, registro_id, "INSERT", columna, None, nuevo))
    return operaciones


def log_update(tabla: str, registro_id, anteriores: dict, nuevos: dict) -> list[tuple[str, dict]]:
    """Una fila de log SOLO para las columnas cuyo valor realmente cambió."""
    operaciones = []
    for columna, nuevo_valor in nuevos.items():
        anterior_texto = _valor_texto(anteriores.get(columna))
        nuevo_texto = _valor_texto(nuevo_valor)
        if anterior_texto == nuevo_texto:
            continue
        operaciones.append(_fila_log(tabla, registro_id, "UPDATE", columna, anterior_texto, nuevo_texto))
    return operaciones


def log_delete(tabla: str, registro_id, valores: dict) -> list[tuple[str, dict]]:
    """Una fila de log por columna con valor no vacío — `valor_nuevo` queda NULL."""
    operaciones = []
    for columna, valor in valores.items():
        anterior = _valor_texto(valor)
        if anterior is None:
            continue
        operaciones.append(_fila_log(tabla, registro_id, "DELETE", columna, anterior, None))
    return operaciones
