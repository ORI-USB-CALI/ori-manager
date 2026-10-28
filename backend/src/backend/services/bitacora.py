from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum

from sqlalchemy import event, insert, inspect
from sqlalchemy.orm import Session, SessionTransaction, UOWTransaction, object_session
from sqlalchemy.sql.elements import ClauseElement

from backend.models.actividad_convenio import ActividadConvenio
from backend.models.aliado import Aliado
from backend.models.auditoria import Auditoria
from backend.models.borrador_convenio import BorradorConvenio
from backend.models.contacto_aliado import ContactoAliado
from backend.models.convenio import Convenio
from backend.models.decision_no_renovacion import DecisionNoRenovacion
from backend.models.documento import Documento
from backend.models.enums import AccionAuditoria, EjecucionAuditoria
from backend.models.evaluacion_convenio import EvaluacionConvenio
from backend.models.firma_convenio import FirmaConvenio
from backend.models.observacion_revision import ObservacionRevision
from backend.models.proceso_firmas_convenio import ProcesoFirmasConvenio
from backend.models.revision_convenio import RevisionConvenio
from backend.models.rol import Rol
from backend.models.solicitud_convenio import SolicitudConvenio
from backend.models.usuario import Usuario

CLAVE_ACTOR = "bitacora_actor"
CLAVE_ACCION = "bitacora_accion"
CLAVE_INSERTADOS = "bitacora_insertados"
CLAVE_CAMBIOS_AUTOMATICOS = "bitacora_cambios_automaticos"

# Columnas que cambian por mantenimiento interno y no aportan a la trazabilidad.
CAMPOS_TECNICOS = frozenset({"id", "creado_en", "actualizado_en", "ultimo_acceso"})

# Se registra que cambiaron, pero su valor nunca se guarda en la bitácora.
CAMPOS_SENSIBLES = frozenset({"hash_contrasena", "token_hash", "firma_png"})

ENTIDADES_AUDITADAS: dict[type, str] = {
    **{
        modelo: modelo.__tablename__
        for modelo in (
            Aliado,
            ContactoAliado,
            Usuario,
            Rol,
            Convenio,
            RevisionConvenio,
            ObservacionRevision,
            Documento,
            ProcesoFirmasConvenio,
            FirmaConvenio,
            DecisionNoRenovacion,
            EvaluacionConvenio,
            ActividadConvenio,
            # HT-13: el contenido es JSON, así que _sin_texto_legible ya
            # evita guardar su valor; solo se registra que cambió.
            BorradorConvenio,
        )
    },
    # Nombre con el que la bitácora registró las solicitudes desde HU-07.
    SolicitudConvenio: "solicitud",
}


@dataclass(frozen=True)
class Actor:
    # HT-09, CA-03: nulos únicamente para procesos automáticos sin usuario
    # originador. No se usa un usuario ficticio para representarlos (RN-07).
    usuario_id: int | None
    rol: str | None


@dataclass(frozen=True)
class Accion:
    actor: Actor
    descripcion: str
    instante: datetime | None = None
    # HT-09, CA-01/CA-05: identifica estructuradamente la acción de negocio,
    # independiente del texto libre de `descripcion`.
    evento: str | None = None
    etapa: str | None = None
    version: int | None = None
    # HT-09, CA-02/CA-03: HUMANA o AUTOMATICA. Nulo en los registros previos
    # a HT-09 (nunca se completa retroactivamente, CA-07).
    ejecucion: str | None = None
    # Asignación de negocio verificable, independiente del originador.
    responsable_id: int | None = None


def _actor_de(usuario: Usuario) -> Actor:
    return Actor(usuario_id=usuario.id, rol=usuario.rol.codigo)


def asignar_actor(db: Session, usuario: Usuario) -> None:
    """Atribuye los cambios que se guarden en esta sesión al usuario autenticado,
    con el rol que tiene en este momento."""
    db.info[CLAVE_ACTOR] = _actor_de(usuario)


def describir_accion(
    db: Session,
    usuario: Usuario,
    descripcion: str,
    *,
    instante: datetime | None = None,
    evento: str | None = None,
    etapa: str | None = None,
    version: int | None = None,
    responsable_id: int | None = None,
) -> None:
    """Atribuye al usuario los cambios de la transacción en curso y los acompaña
    con la acción de negocio que los origina. Si se indica el instante, los
    registros llevan esa misma fecha y hora, por ejemplo la de una decisión que
    también queda guardada en su propia entidad.

    `evento`, `etapa` y `version` identifican estructuradamente la acción de
    negocio (HT-09, CA-01 y CA-05). `responsable_id` es el responsable de
    negocio de la operación cuando exista (CA-04); no confundir con el
    usuario que origina la acción."""
    db.info[CLAVE_ACCION] = Accion(
        _actor_de(usuario),
        descripcion,
        instante,
        evento,
        etapa,
        version,
        EjecucionAuditoria.HUMANA.value,
        responsable_id,
    )


def describir_accion_automatica(
    db: Session,
    descripcion: str,
    *,
    instante: datetime | None = None,
    evento: str | None = None,
    etapa: str | None = None,
    version: int | None = None,
    originador: Usuario | None = None,
    responsable_id: int | None = None,
) -> None:
    """Declara la ejecución automática, conservando un originador si se conoce.

    Sin originador explícito, no hereda al usuario de la sesión ni inventa uno.
    La naturaleza de ejecución es independiente de quién inició el proceso.
    """
    actor = _actor_de(originador) if originador is not None else Actor(None, None)
    db.info[CLAVE_ACCION] = Accion(
        actor,
        descripcion,
        instante,
        evento,
        etapa,
        version,
        EjecucionAuditoria.AUTOMATICA.value,
        responsable_id,
    )


def describir_cambios_automaticos(db: Session, objeto: object, *campos: str) -> None:
    """Asocia efectos derivados a un objeto y a su próxima modificación.

    Se captura la acción humana antes del flush, sin cambiar el contexto global
    de la sesión. Se registra su evento humano y sus efectos por campo, con el
    mismo originador e instante. No genera filas si no hubo cambios reales.
    """
    accion = db.info.get(CLAVE_ACCION)
    if accion is None or accion.ejecucion != EjecucionAuditoria.HUMANA.value:
        raise ValueError("Los efectos derivados requieren una acción humana descrita")
    if not inspect(objeto).persistent or object_session(objeto) is not db:
        raise ValueError("Los efectos derivados requieren un objeto persistido de esta sesión")
    if not campos or not set(campos) <= set(inspect(objeto).mapper.column_attrs.keys()):
        raise ValueError("Los efectos automáticos deben identificar columnas del objeto")
    marcas = db.info.setdefault(CLAVE_CAMBIOS_AUTOMATICOS, {})
    previa = marcas.get(objeto)
    if previa is not None and previa[0] != accion:
        raise ValueError("Confirme con flush los efectos previos antes de cambiar su acción")
    marcas[objeto] = (accion, frozenset(campos) | (previa[1] if previa else frozenset()))


def _a_texto(valor: object) -> str | None:
    if valor is None:
        return None
    if isinstance(valor, Enum):
        return str(valor.value)
    if isinstance(valor, (date, datetime)):
        return valor.isoformat()
    return str(valor)


def _sin_texto_legible(valor: object) -> bool:
    return isinstance(valor, (bytes, dict, list))


def _registro_id(objeto: object) -> int:
    (identificador,) = inspect(objeto).mapper.primary_key_from_instance(objeto)
    return identificador


def _fila(
    actor: Actor,
    contexto: str | None,
    instante: datetime | None,
    entidad: str,
    registro_id: int,
    accion: AccionAuditoria,
    campo: str | None = None,
    anterior: object = None,
    nuevo: object = None,
    *,
    evento: str | None = None,
    etapa: str | None = None,
    version: int | None = None,
    ejecucion: str | None = None,
    responsable_id: int | None = None,
) -> dict[str, object]:
    fila: dict[str, object] = {
        "usuario_id": actor.usuario_id,
        "rol": actor.rol,
        "entidad": entidad,
        "registro_id": registro_id,
        "accion": accion.value,
        "campo": campo,
        "valor_anterior": _a_texto(anterior),
        "valor_nuevo": _a_texto(nuevo),
        "contexto": contexto,
        "evento": evento,
        "etapa": etapa,
        "version": version,
        "ejecucion": ejecucion,
        "responsable_id": responsable_id,
    }
    # Sin instante, la fecha la asigna la base al insertar.
    if instante is not None:
        fila["fecha_hora"] = instante
    return fila


def _filas_de_modificacion(
    objeto: object,
    entidad: str,
    actor: Actor,
    contexto: str | None,
    instante: datetime | None,
    accion: Accion | None,
    campos_automaticos: frozenset[str] = frozenset(),
) -> list[dict[str, object]]:
    estado = inspect(objeto)
    registro_id = _registro_id(objeto)
    filas = []
    for atributo in estado.mapper.column_attrs:
        campo = atributo.key
        if campo in CAMPOS_TECNICOS:
            continue
        historia = estado.attrs[campo].history
        if not historia.has_changes():
            continue
        anterior = historia.deleted[0] if historia.deleted else None
        nuevo = historia.added[0] if historia.added else None
        # Un valor calculado por la base (por ejemplo, now()) no tiene texto que
        # registrar, y reasignar el mismo valor no es una modificación.
        if isinstance(nuevo, ClauseElement) or anterior == nuevo:
            continue
        # Binarios y documentos JSON no tienen una representación legible: queda
        # el registro de que cambiaron, sin su contenido.
        if (
            campo in CAMPOS_SENSIBLES
            or _sin_texto_legible(anterior)
            or _sin_texto_legible(nuevo)
        ):
            anterior = nuevo = None
        filas.append(
            _fila(
                actor,
                contexto,
                instante,
                entidad,
                registro_id,
                AccionAuditoria.UPDATE,
                campo,
                anterior,
                nuevo,
                evento=accion.evento if accion else None,
                etapa=accion.etapa if accion else None,
                version=accion.version if accion else None,
                ejecucion=(EjecucionAuditoria.AUTOMATICA.value
                           if campo in campos_automaticos else _ejecucion(accion)),
                responsable_id=accion.responsable_id if accion else None,
            )
        )
    return filas


def _ejecucion(accion: Accion | None) -> str | None:
    # Compatibilidad HU-18: las mutaciones autenticadas directas tienen naturaleza
    # humana por defecto. Los efectos automáticos se declaran por su semántica,
    # nunca por el simple hecho de ejecutarse en el backend.
    if accion is None:
        return EjecucionAuditoria.HUMANA.value
    return accion.ejecucion


@event.listens_for(Session, "after_flush")
def _registrar_cambios(session: Session, _flush_context: UOWTransaction) -> None:
    # En after_flush los objetos nuevos ya tienen id y la sesión aún conserva el
    # historial de cada atributo, así que se puede reconstruir el cambio completo.
    accion = session.info.get(CLAVE_ACCION)
    actor = accion.actor if accion else session.info.get(CLAVE_ACTOR)
    if actor is None:
        return
    contexto = accion.descripcion if accion else None
    instante = accion.instante if accion else None
    evento = accion.evento if accion else None
    etapa = accion.etapa if accion else None
    version = accion.version if accion else None
    ejecucion = _ejecucion(accion)
    responsable_id = accion.responsable_id if accion else None
    # Lo que se completa de un registro en la misma transacción que lo crea es
    # parte de su creación: su inserción ya lo representa.
    insertados = session.info.setdefault(CLAVE_INSERTADOS, set())
    derivados = session.info.pop(CLAVE_CAMBIOS_AUTOMATICOS, {})

    filas: list[dict[str, object]] = []
    for objeto in session.new:
        entidad = ENTIDADES_AUDITADAS.get(type(objeto))
        if entidad is not None:
            registro_id = _registro_id(objeto)
            insertados.add((entidad, registro_id))
            filas.append(
                _fila(
                    actor,
                    contexto,
                    instante,
                    entidad,
                    registro_id,
                    AccionAuditoria.INSERT,
                    evento=evento,
                    etapa=etapa,
                    version=version,
                    ejecucion=ejecucion,
                    responsable_id=responsable_id,
                )
            )
    for objeto in session.dirty:
        entidad = ENTIDADES_AUDITADAS.get(type(objeto))
        if entidad is not None and (entidad, _registro_id(objeto)) not in insertados:
            accion_objeto, campos = derivados.get(objeto, (accion, frozenset()))
            actor_objeto = accion_objeto.actor if accion_objeto else actor
            contexto_objeto = accion_objeto.descripcion if accion_objeto else contexto
            instante_objeto = accion_objeto.instante if accion_objeto else instante
            modificaciones = _filas_de_modificacion(
                objeto, entidad, actor_objeto, contexto_objeto, instante_objeto,
                accion_objeto, campos,
            )
            if modificaciones and campos:
                # Evento humano de radicar, separado de los efectos automáticos.
                filas.append(_fila(
                    actor_objeto, contexto_objeto, instante_objeto, entidad,
                    _registro_id(objeto), AccionAuditoria.UPDATE,
                    evento=accion_objeto.evento, etapa=accion_objeto.etapa,
                    version=accion_objeto.version, ejecucion=accion_objeto.ejecucion,
                    responsable_id=accion_objeto.responsable_id,
                ))
            filas.extend(modificaciones)
    for objeto in session.deleted:
        entidad = ENTIDADES_AUDITADAS.get(type(objeto))
        if entidad is not None:
            filas.append(
                _fila(
                    actor,
                    contexto,
                    instante,
                    entidad,
                    _registro_id(objeto),
                    AccionAuditoria.DELETE,
                    evento=evento,
                    etapa=etapa,
                    version=version,
                    ejecucion=ejecucion,
                    responsable_id=responsable_id,
                )
            )

    if filas:
        # Inserción directa en la misma transacción: no pasa por la sesión, así que
        # no vuelve a disparar este evento.
        session.connection().execute(insert(Auditoria.__table__), filas)


@event.listens_for(Session, "after_transaction_end")
def _cerrar_transaccion(session: Session, transaccion: SessionTransaction) -> None:
    # Una acción descrita vale solo para la transacción en la que se declaró: al
    # confirmarse o revertirse, los cambios siguientes no la heredan.
    if transaccion.parent is None:
        session.info.pop(CLAVE_ACCION, None)
        session.info.pop(CLAVE_INSERTADOS, None)
        session.info.pop(CLAVE_CAMBIOS_AUTOMATICOS, None)
