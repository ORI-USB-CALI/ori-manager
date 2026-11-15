"""Identidad jurídica congelada y excepción inicial compartidas por HT-16."""

import json
from hashlib import sha256

from sqlalchemy import select
from sqlalchemy.orm import Session, object_session

from backend.models.aliado import Aliado
from backend.models.auditoria import Auditoria
from backend.models.convenio import Convenio
from backend.models.revision_convenio import RevisionConvenio
from backend.models.version_convenio import VersionConvenio

CAMPOS_IDENTIDAD_ALIADO = (
    "nombre", "tipo", "tipo_identificacion", "identificacion", "digito_verificacion",
)


def identidad_aliado(convenio: Convenio) -> dict[str, object] | None:
    if convenio.aliado_id is None:
        return None
    db = object_session(convenio)
    aliado = convenio.aliado if db is None else db.scalar(
        select(Aliado).where(Aliado.id == convenio.aliado_id)
        .execution_options(populate_existing=True).with_for_update(read=True)
    )
    return {campo: getattr(aliado, campo) for campo in CAMPOS_IDENTIDAD_ALIADO} if aliado else None


def huella_identidad(identidad: dict[str, object] | None) -> str:
    return sha256(json.dumps(identidad, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def asignacion_inicial_auditada(db: Session, convenio: Convenio) -> bool:
    cambios = list(db.scalars(select(Auditoria).where(
        Auditoria.entidad == "convenio", Auditoria.registro_id == convenio.id,
        Auditoria.campo == "aliado_id", Auditoria.version == convenio.version_actual,
        Auditoria.etapa == "REVISION_CONTRAPARTE",
    )))
    identidad = db.scalar(select(Auditoria).where(
        Auditoria.entidad == "convenio", Auditoria.registro_id == convenio.id,
        Auditoria.campo == "aliado_identidad_sha256",
        Auditoria.evento == "CONTRAPARTE_ASIGNADA",
        Auditoria.version == convenio.version_actual,
        Auditoria.etapa == "REVISION_CONTRAPARTE",
    ).order_by(Auditoria.id.desc()).limit(1))
    return (
        len(cambios) == 1
        and cambios[0].evento == "CONTRAPARTE_ASIGNADA"
        and cambios[0].valor_anterior is None
        and cambios[0].valor_nuevo == str(convenio.aliado_id)
        and identidad is not None
        and identidad.valor_nuevo == huella_identidad(identidad_aliado(convenio))
    )


def identidad_autorizada_para_revision(
    db: Session, convenio: Convenio, version: VersionConvenio,
) -> bool:
    """Valida versión y ambos avales; retiene FOR SHARE del aliado hasta terminar.

    El llamador bloquea primero convenio/revisión/invitación para serializar
    decisiones y recuperación. Nunca devuelve datos de identidad al cliente.
    """
    actual = identidad_aliado(convenio)
    if actual is None or version.convenio_id != convenio.id or version.numero != convenio.version_actual:
        return False
    segunda = db.scalar(select(RevisionConvenio).where(
        RevisionConvenio.convenio_id == convenio.id,
        RevisionConvenio.tipo == "JURIDICA", RevisionConvenio.instancia_juridica == 2,
        RevisionConvenio.estado == "RESUELTA", RevisionConvenio.resultado == "APROBADA",
        RevisionConvenio.version_resultado_id == version.id,
    ).order_by(RevisionConvenio.numero_ronda.desc()).limit(1))
    if segunda is None or segunda.numero_ronda is None:
        return False
    primera = db.scalar(select(RevisionConvenio).where(
        RevisionConvenio.convenio_id == convenio.id,
        RevisionConvenio.tipo == "JURIDICA", RevisionConvenio.instancia_juridica == 1,
        RevisionConvenio.numero_ronda == segunda.numero_ronda,
        RevisionConvenio.estado == "RESUELTA", RevisionConvenio.resultado == "APROBADA",
        RevisionConvenio.version_resultado_id == version.id,
        RevisionConvenio.resuelta_por_id != segunda.resuelta_por_id,
    ))
    if primera is None:
        return False
    congelados = (version.snapshot_metadata, primera.snapshot_datos, segunda.snapshot_datos)
    if all(
        dato and dato.get("aliado_id") == convenio.aliado_id
        and "aliado_identidad" in dato and dato["aliado_identidad"] == actual
        for dato in congelados
    ):
        return True
    return (
        convenio.origen == "MANUAL_ORI"
        and all(
            dato and "aliado_id" in dato and dato["aliado_id"] is None
            and "aliado_identidad" in dato and dato["aliado_identidad"] is None
            for dato in congelados
        )
        and asignacion_inicial_auditada(db, convenio)
    )
