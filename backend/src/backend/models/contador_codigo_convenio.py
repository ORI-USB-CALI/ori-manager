from __future__ import annotations

from sqlalchemy import CheckConstraint, Integer, text
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.base import Base


class ContadorCodigoConvenio(Base):
    """Consecutivo anual del código institucional del convenio (HT-06).

    Una fila por año calendario. El consecutivo es compartido por todos los
    convenios, sin importar tipo, alcance u origen (RN-07), y se reinicia al
    cambiar de año.

    Existe como tabla propia porque el consecutivo necesita su propio candado:
    `formalizar()` ya bloquea la fila del convenio, pero dos convenios
    distintos no se bloquean entre sí y comparten esta secuencia (RN-11).
    Tampoco se usa una secuencia de PostgreSQL, que exigiría crearla en tiempo
    de ejecución y por tanto privilegios DDL para el usuario de la aplicación.
    """

    __tablename__ = "contador_codigo_convenio"
    __table_args__ = (
        CheckConstraint(
            "ultimo_consecutivo >= 0",
            name="ck_contador_codigo_convenio_consecutivo",
        ),
    )

    # El año es la clave: no es un identificador generado, se recibe.
    anio: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    # Último consecutivo entregado. 0 significa que el año aún no entregó ninguno.
    ultimo_consecutivo: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
