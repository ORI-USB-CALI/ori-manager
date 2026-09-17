from datetime import date, datetime

from sqlalchemy import (
    CheckConstraint,
    Date,
    ForeignKey,
    SmallInteger,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.base import Base

# Valores de convenio.estado segun el MER aprobado por el DBA (paquete
# "5. Convenio y trazabilidad"). No incluye RECHAZADO: ese valor
# pertenece a solicitud.estado, no a convenio.estado.
ESTADOS_CONVENIO: tuple[str, ...] = (
    "EN_TRAMITE",
    "VIGENTE",
    "POR_VENCER",
    "VENCIDO",
    "RENOVADO",
    "FINALIZADO",
    "CANCELADO",
)

# CA-04: el convenio no debe nacer ACTIVO/VIGENTE; nace en tramite.
ESTADO_CONVENIO_INICIAL = "EN_TRAMITE"

# Valores de convenio.alcance segun el MER.
ALCANCES_CONVENIO: tuple[str, ...] = ("PROGRAMA", "INSTITUCIONAL")


class Convenio(Base):
    """Tabla "convenio", con el esquema completo definido en el MER
    (paquete "5. Convenio y trazabilidad").

   
    """

    __tablename__ = "convenio"
    __table_args__ = (
        CheckConstraint(
            "estado IN ({})".format(
                ", ".join(f"'{estado}'" for estado in ESTADOS_CONVENIO)
            ),
            name="ck_convenio_estado_valido",
        ),
        CheckConstraint(
            "alcance IN ({})".format(
                ", ".join(f"'{alcance}'" for alcance in ALCANCES_CONVENIO)
            ),
            name="ck_convenio_alcance_valido",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    # No lo asigna HU-06 (ninguna CA lo exige); nullable hasta que exista
    # la logica de generacion del consecutivo institucional.
    codigo: Mapped[str | None] = mapped_column(String(40), unique=True, nullable=True)

    # RN-07 / MER: una solicitud origina a lo sumo un convenio (1:1).
    # Decision confirmada: obligatoria, no opcional.
    solicitud_id: Mapped[int] = mapped_column(
        ForeignKey("solicitud_convenio.id"),
        unique=True,
        nullable=False,
    )

    # CA-02/CA-03: puede no existir aliado previo al registrar el convenio.
    aliado_id: Mapped[int | None] = mapped_column(
        ForeignKey("aliado.id"),
        nullable=True,
    )

    # Fuera del alcance de HU-06 (pertenece a la elaboracion del convenio).
    tipo_convenio_id: Mapped[int | None] = mapped_column(
        ForeignKey("tipo_convenio.id"),
        nullable=True,
    )

    # Fuera del alcance de HU-06 (pertenece al flujo de las 7 etapas).
    etapa_actual_id: Mapped[int | None] = mapped_column(
        ForeignKey("etapa.id"),
        nullable=True,
    )

    # CA-04: estado inicial obligatorio, nunca ACTIVO/VIGENTE al crear.
    estado: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=ESTADO_CONVENIO_INICIAL,
        server_default=text(f"'{ESTADO_CONVENIO_INICIAL}'"),
    )

    objeto: Mapped[str | None] = mapped_column(Text, nullable=True)

    # MER nota 2: obligatorio en aplicacion solo cuando alcance=PROGRAMA;
    # no se valida aqui, es responsabilidad de la HU de elaboracion.
    alcance: Mapped[str | None] = mapped_column(String(20), nullable=True)

    unidad_organizacional_id: Mapped[int | None] = mapped_column(
        ForeignKey("unidad_organizacional.id"),
        nullable=True,
    )

    implicacion_financiera: Mapped[str | None] = mapped_column(Text, nullable=True)

    fecha_inicio: Mapped[date | None] = mapped_column(Date, nullable=True)
    fecha_vencimiento: Mapped[date | None] = mapped_column(Date, nullable=True)
    fecha_firma: Mapped[date | None] = mapped_column(Date, nullable=True)

    duracion_meses: Mapped[int | None] = mapped_column(nullable=True)
    porcentaje_avance: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)

    # Autorreferencia para renovaciones (RN-20); no la gestiona HU-06.
    convenio_origen_id: Mapped[int | None] = mapped_column(
        ForeignKey("convenio.id"),
        nullable=True,
    )
    numero_renovacion: Mapped[int | None] = mapped_column(
        SmallInteger, nullable=True
    )

    # CA-01: usuario responsable de la creacion.
    # MER regla 6: FK hacia usuario va con ON DELETE RESTRICT (no se
    # borran usuarios, se inactivan, para conservar trazabilidad).
    creado_por_id: Mapped[int] = mapped_column(
        ForeignKey("usuario.id", ondelete="RESTRICT"),
        nullable=False,
    )

    creado_en: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        nullable=False,
    )

    actualizado_en: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
