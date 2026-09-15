from sqlalchemy.orm import Session

from backend.models.convenio import ESTADO_CONVENIO_INICIAL, Convenio
from backend.schemas.convenio import ConvenioCreate


def crear_convenio(db: Session, datos: ConvenioCreate) -> Convenio:
    convenio = Convenio(
        solicitud_id=datos.solicitud_id,
        aliado_id=datos.aliado_id,
        creado_por_id=datos.creado_por_id,
        estado=ESTADO_CONVENIO_INICIAL,
        codigo=datos.codigo,
        tipo_convenio_id=datos.tipo_convenio_id,
        etapa_actual_id=datos.etapa_actual_id,
        objeto=datos.objeto,
        alcance=datos.alcance,
        unidad_organizacional_id=datos.unidad_organizacional_id,
        implicacion_financiera=datos.implicacion_financiera,
        fecha_inicio=datos.fecha_inicio,
        fecha_vencimiento=datos.fecha_vencimiento,
        fecha_firma=datos.fecha_firma,
        duracion_meses=datos.duracion_meses,
        porcentaje_avance=datos.porcentaje_avance,
        convenio_origen_id=datos.convenio_origen_id,
        numero_renovacion=datos.numero_renovacion,
    )
    db.add(convenio)
    db.commit()
    db.refresh(convenio)
    return convenio


def obtener_convenio(db: Session, convenio_id: int) -> Convenio | None:
    """CA-06: consulta el registro base de un convenio por id."""
    return db.get(Convenio, convenio_id)
