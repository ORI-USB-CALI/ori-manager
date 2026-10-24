from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum

from sqlalchemy import event, insert, inspect
from sqlalchemy.orm import Session, SessionTransaction, UOWTransaction
from sqlalchemy.sql.elements import ClauseElement

from backend.models.actividad_convenio import ActividadConvenio
from backend.models.aliado import Aliado
from backend.models.auditoria import Auditoria
from backend.models.borrador_convenio import BorradorConvenio
from backend.models.contacto_aliado import ContactoAliado
from backend.models.convenio import Convenio
from backend.models.decision_no_renovacion import DecisionNoRenovacion
from backend.models.documento import Documento
from backend.models.enums import AccionAuditoria
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
    usuario_id: int
    rol: str


@dataclass(frozen=True)
class Accion:
    actor: Actor
    descripcion: str
    instante: datetime | None = None
    # HT-09: contrato de evento de negocio, aún no persistido en `auditoria`
    # (llega con HT09-BE02, cuando existan las columnas). Se acepta desde ya
    # para que los servicios de HT-13 puedan empezar a declararlo.
    evento: str | None = None
    etapa: str | None = None
    version: int | None = None


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
) -> None:
    """Atribuye al usuario los cambios de la transacción en curso y los acompaña
    con la acción de negocio que los origina. Si se indica el instante, los
    registros llevan esa misma fecha y hora, por ejemplo la de una decisión que
    también queda guardada en su propia entidad.

    `evento`, `etapa` y `version` identifican estructuradamente la acción de
    negocio (HT-09, CA-01 y CA-05). Todavía no se persisten: las columnas se
    agregan en HT09-BE02."""
    db.info[CLAVE_ACCION] = Accion(
        _actor_de(usuario), descripcion, instante, evento, etapa, version
    )


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
            )
        )
    return filas


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
    # Lo que se completa de un registro en la misma transacción que lo crea es
    # parte de su creación: su inserción ya lo representa.
    insertados = session.info.setdefault(CLAVE_INSERTADOS, set())

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
                )
            )
    for objeto in session.dirty:
        entidad = ENTIDADES_AUDITADAS.get(type(objeto))
        if entidad is not None and (entidad, _registro_id(objeto)) not in insertados:
            filas.extend(
                _filas_de_modificacion(objeto, entidad, actor, contexto, instante)
            )
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
