"""HT-06 CA-08: regularización del código institucional de convenios históricos.

Conciliación explícita y transaccional, invocada solo por el procedimiento
autorizado de `backend.cli.regularizar_codigos_convenio`. Las consultas HTTP no
la llaman: el código normal se asigna al formalizar (RN-01).

La política de año es una definición técnica provisional; su validación
institucional corresponde al Product Owner.
"""

import logging
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from backend.models.convenio import Convenio
from backend.models.enums import EstadoProcesoFirmasConvenio
from backend.models.usuario import Usuario
from backend.services.bitacora import describir_accion_automatica
from backend.services.codigo_convenio import asignar_codigo
from backend.services.convenios import filtro_convenio_formalizado
from backend.services.vigencia import ZONA_HORARIA_DOMINIO

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CodigoRegularizado:
    convenio_id: int
    codigo: str
    anio: int


@dataclass(frozen=True)
class ResultadoRegularizacion:
    asignados: tuple[CodigoRegularizado, ...]
    sin_fecha_confiable: tuple[int, ...]
    simulado: bool


def instante_de_formalizacion(convenio: Convenio) -> datetime | None:
    """Instante verificable en que se formalizó el convenio, o None.

    Solo se aceptan marcas que escribe `formalizar()`, porque son las únicas
    que evidencian una formalización real:

    - `activado_en` es la marca directa del convenio.
    - `completado_en` del proceso de firmas COMPLETADO es el respaldo para los
      convenios formalizados antes de que HU-20 agregara `activado_en`. Es
      también la respuesta a cuál firma representa la culminación del proceso:
      no una de las siete, sino el cierre del proceso que las reúne.

    `fecha_firma` queda deliberadamente fuera: durante la elaboración se puede
    diligenciar a mano (ver `convenio_esta_formalizado`), así que su presencia
    no distingue una formalización real de un dato tecleado. Un convenio sin
    ninguna de las dos marcas no recibe un año inventado: se reporta.
    """
    if convenio.activado_en is not None:
        return convenio.activado_en
    completados = [
        proceso.completado_en
        for proceso in convenio.procesos_firmas
        if proceso.estado == EstadoProcesoFirmasConvenio.COMPLETADO.value
        and proceso.completado_en is not None
    ]
    return max(completados) if completados else None


def anio_de_formalizacion(convenio: Convenio) -> int | None:
    """Año calendario de la formalización en la zona del dominio (RN-05)."""
    instante = instante_de_formalizacion(convenio)
    if instante is None:
        return None
    return instante.astimezone(ZONA_HORARIA_DOMINIO).year


def regularizar_codigos(
    db: Session,
    *,
    anio_politica: int | None = None,
    originador: Usuario | None = None,
    simular: bool = False,
) -> ResultadoRegularizacion:
    """Asigna el código a los convenios formalizados que no lo tienen.

    Posee la transacción: confirma todo o revierte todo. Es idempotente, porque
    solo mira los convenios con `codigo` nulo; repetirla no asigna nada y nunca
    sobrescribe un código existente (RN-13).

    `anio_politica` fuerza el año para todos los candidatos, para cuando el PO
    decida una política distinta a la del año real de formalización. Con él, los
    convenios sin fecha verificable sí reciben código, porque el año lo decide
    la política y no un dato dudoso.

    `simular` calcula los códigos que se asignarían, bajo los mismos candados,
    y revierte: no deja códigos, ni consecutivos consumidos, ni auditoría.
    """
    asignados: list[CodigoRegularizado] = []
    sin_fecha_confiable: list[int] = []
    try:
        if not simular:
            # HT-09, CA-03: la ejecución es automática y conserva al usuario que
            # la autorizó, cuando se conoce, sin inventar uno si no existe
            # (RN-07). No se declara etapa ni versión: una misma ejecución toca
            # convenios con etapas y versiones distintas.
            describir_accion_automatica(
                db,
                "Regularizó el código institucional de convenios formalizados",
                evento="CODIGO_REGULARIZADO",
                originador=originador,
            )
        # Se bloquea en orden de id, igual que la conciliación de estados, para
        # que ambas operaciones tomen los candados en el mismo orden.
        candidatos = db.scalars(
            select(Convenio)
            .where(Convenio.codigo.is_(None))
            .where(filtro_convenio_formalizado())
            .order_by(Convenio.id)
            .options(selectinload(Convenio.procesos_firmas))
            .execution_options(populate_existing=True)
            .with_for_update(of=Convenio)
        ).all()
        # El código se asigna en orden cronológico de formalización para que el
        # consecutivo de cada año siga la historia real y no los ids. Los que no
        # tienen instante verificable van al final, en orden de id, de modo que
        # el resultado sea el mismo en cada ejecución. Se separan en dos listas
        # en lugar de ordenar con un instante centinela: comparar fechas con
        # zona contra `datetime.min` desborda si la zona del dominio llegara a
        # tener desplazamiento positivo.
        con_instante = [c for c in candidatos if instante_de_formalizacion(c)]
        sin_instante = [c for c in candidatos if not instante_de_formalizacion(c)]
        con_instante.sort(key=lambda c: (instante_de_formalizacion(c), c.id))
        sin_instante.sort(key=lambda c: c.id)
        for convenio in [*con_instante, *sin_instante]:
            anio = anio_politica or anio_de_formalizacion(convenio)
            if anio is None:
                sin_fecha_confiable.append(convenio.id)
                continue
            codigo = asignar_codigo(db, convenio, anio)
            asignados.append(CodigoRegularizado(convenio.id, codigo, anio))
        if simular:
            db.rollback()
        else:
            db.commit()
    except Exception:
        db.rollback()
        raise

    # Solo se anuncia lo ya confirmado.
    for asignado in asignados:
        logger.info(
            "codigo_regularizado convenio_id=%s codigo=%s anio=%s simulado=%s",
            asignado.convenio_id,
            asignado.codigo,
            asignado.anio,
            simular,
        )
    for convenio_id in sin_fecha_confiable:
        logger.warning(
            "anomalia=SIN_FECHA_DE_FORMALIZACION_VERIFICABLE convenio_id=%s "
            "accion=revisar_manualmente",
            convenio_id,
        )
    return ResultadoRegularizacion(
        asignados=tuple(asignados),
        sin_fecha_confiable=tuple(sin_fecha_confiable),
        simulado=simular,
    )
