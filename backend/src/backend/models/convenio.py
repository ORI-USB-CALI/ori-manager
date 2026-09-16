from datetime import datetime

from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from backend.db.base import Base
from backend.models.enums import EstadoConvenio

# Tabla minima: solo lo necesario para HU-04 (gestion de aliados).
# El resto de columnas del MER (codigo, solicitud_id, tipo_convenio_id,
# etapa_actual_id, etc.) se agregan via migraciones futuras cuando
# existan las HU/tablas correspondientes.


class Convenio(Base):
    __tablename__ = "convenio"

    id: Mapped[int] = mapped_column(primary_key=True)
    aliado_id: Mapped[int | None] = mapped_column(ForeignKey("aliado.id"))
    estado: Mapped[EstadoConvenio] = mapped_column(
        SAEnum(EstadoConvenio, name="estado_convenio"),
        nullable=False,
        default=EstadoConvenio.EN_TRAMITE,
    )
    creado_en: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
    actualizado_en: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now(), nullable=False
    )
