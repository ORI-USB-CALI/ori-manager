"""HT-15, Tarea 6: atomicidad, concurrencia e histórico (CA-06 y CA-02)."""

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from threading import Barrier
from uuid import uuid4

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from backend.core.roles import CodigoRol, TipoUsuario
from backend.models.auditoria import Auditoria
from backend.models.borrador_convenio import BorradorConvenio
from backend.models.convenio import Convenio
from backend.models.enums import ContextoVersionConvenio
from backend.models.historial_etapa import HistorialEtapa
from backend.models.revision_convenio import RevisionConvenio
from backend.models.rol import Rol
from backend.models.tipo_convenio import TipoConvenio
from backend.models.usuario import Usuario
from backend.models.version_convenio import VersionConvenio
from backend.schemas.convenio import ConvenioCrearManual, ConvenioElaboracionGuardar
from backend.services.convenios import (
    ConflictoBorradorConvenio,
    ConvenioNoEditable,
    ServicioConvenios,
)

DOCUMENTO_ELABORADO = {
    "type": "doc",
    "content": [
        {"type": "paragraph", "content": [{"type": "text", "text": "Cláusula original"}]},
    ],
}
DOCUMENTO_VACIO = {"type": "doc", "content": [{"type": "paragraph"}]}


@pytest.fixture
def tipo_marco(db) -> int:
    return db.scalar(select(TipoConvenio.id).where(TipoConvenio.codigo == "MARCO"))


@pytest.fixture
def convenio_manual(client, db, gestor, tipo_marco) -> Convenio:
    respuesta = client.post(
        "/api/convenios/manual",
        json={
            "objeto": "Cooperación académica",
            "alcance": "INSTITUCIONAL",
            "implicacion_financiera": "Sin costo para la Universidad",
            "duracion_meses": 24,
            "tipo_convenio_id": tipo_marco,
        },
    )
    assert respuesta.status_code == 201, respuesta.text
    return db.get(Convenio, respuesta.json()["id"])


def _con_parrafo(contenido: dict, texto: str) -> dict:
    nuevo = deepcopy(contenido)
    nuevo["content"].append(
        {"type": "paragraph", "content": [{"type": "text", "text": texto}]}
    )
    return nuevo


def _estado(db, convenio_id: int) -> dict:
    db.expire_all()
    convenio = db.get(Convenio, convenio_id)
    borrador = db.scalar(
        select(BorradorConvenio).where(BorradorConvenio.convenio_id == convenio_id)
    )
    return {
        "etapa": convenio.etapa_actual.codigo,
        "version_actual": convenio.version_actual,
        "versiones": db.scalar(
            select(func.count())
            .select_from(VersionConvenio)
            .where(VersionConvenio.convenio_id == convenio_id)
        ),
        "revisiones": db.scalar(
            select(func.count())
            .select_from(RevisionConvenio)
            .where(RevisionConvenio.convenio_id == convenio_id)
        ),
        "historial": db.scalar(
            select(func.count())
            .select_from(HistorialEtapa)
            .where(HistorialEtapa.convenio_id == convenio_id)
        ),
        "borrador_existe": borrador is not None,
        "borrador_revision": borrador.revision if borrador else None,
        "borrador_contenido": borrador.contenido if borrador else None,
    }


# ---- CA-06: un error en cualquier paso del envío no deja cambios parciales -----


def test_fallo_al_crear_la_version_no_deja_nada_y_conserva_el_borrador(
    db, gestor, convenio_listo, monkeypatch
) -> None:
    antes = _estado(db, convenio_listo.id)

    def fallar(*_args, **_kwargs):
        raise SQLAlchemyError("fallo simulado al crear la versión (snapshot)")

    monkeypatch.setattr(db, "flush", fallar)

    with pytest.raises(SQLAlchemyError):
        ServicioConvenios(db).finalizar_elaboracion(convenio_listo.id, gestor)

    # Este fallo ocurre antes del try/except de finalizar_elaboracion (la
    # creación de la versión es anterior a él), así que el servicio no revierte
    # por sí mismo: hace falta lo que haría la sesión de una petición real al
    # cerrarse con una excepción sin manejar.
    monkeypatch.undo()
    db.rollback()
    assert _estado(db, convenio_listo.id) == antes


def test_fallo_al_registrar_la_revision_revierte_version_y_etapa(
    db, gestor, convenio_listo, monkeypatch
) -> None:
    antes = _estado(db, convenio_listo.id)
    flush_real = db.flush
    llamadas = 0

    def fallar(*args, **kwargs):
        nonlocal llamadas
        llamadas += 1
        # La 1ª llamada es la de `_crear_version` (debe pasar); la 2ª es la que
        # deja el historial listo para enlazar la revisión nueva.
        if llamadas == 2:
            raise SQLAlchemyError("fallo simulado al crear la revisión")
        return flush_real(*args, **kwargs)

    monkeypatch.setattr(db, "flush", fallar)

    with pytest.raises(SQLAlchemyError):
        ServicioConvenios(db).finalizar_elaboracion(convenio_listo.id, gestor)

    assert _estado(db, convenio_listo.id) == antes


def test_fallo_al_cambiar_la_etapa_revierte_version_y_revision(
    db, gestor, convenio_listo, monkeypatch
) -> None:
    antes = _estado(db, convenio_listo.id)

    def fallar(*_args, **_kwargs):
        raise SQLAlchemyError("fallo simulado al cambiar la etapa")

    monkeypatch.setattr(db, "commit", fallar)

    with pytest.raises(SQLAlchemyError):
        ServicioConvenios(db).finalizar_elaboracion(convenio_listo.id, gestor)

    assert _estado(db, convenio_listo.id) == antes


# ---- CA-06: dos envíos simultáneos del mismo convenio --------------------------


@pytest.fixture
def convenio_listo_concurrente(db_engine):
    """Convenio manual, con metadata completa y borrador elaborado, construido
    con su propia conexión/transacción real (no la del fixture `db`, que
    aísla cada prueba en un rollback) para poder enviarlo desde dos hilos."""
    with Session(db_engine, expire_on_commit=False) as db:
        rol = db.scalar(select(Rol).where(Rol.codigo == CodigoRol.GESTOR_ORI.value))
        usuario = Usuario(
            correo=f"concurrente-{uuid4().hex}@example.com",
            hash_contrasena="sin-login",
            nombre_completo="Gestor concurrente",
            rol=rol,
            tipo_usuario=TipoUsuario.INTERNO.value,
        )
        db.add(usuario)
        db.flush()
        tipo = db.scalar(select(TipoConvenio).where(TipoConvenio.codigo == "MARCO"))
        convenio = ServicioConvenios(db).crear_manual(
            ConvenioCrearManual(
                objeto="Convenio para envío concurrente",
                alcance="INSTITUCIONAL",
                implicacion_financiera="Sin costo para la Universidad",
                duracion_meses=24,
                tipo_convenio_id=tipo.id,
            ),
            usuario,
        )
        borrador = ServicioConvenios(db)._borrador(convenio.id)
        borrador.contenido = deepcopy(DOCUMENTO_ELABORADO)
        db.commit()
        ids = convenio.id, usuario.id
    try:
        yield ids
    finally:
        with Session(db_engine) as db:
            for modelo in (RevisionConvenio, VersionConvenio, HistorialEtapa, BorradorConvenio):
                db.execute(delete(modelo).where(modelo.convenio_id == ids[0]))
            db.execute(delete(Auditoria).where(Auditoria.usuario_id == ids[1]))
            db.execute(delete(Convenio).where(Convenio.id == ids[0]))
            db.execute(delete(Usuario).where(Usuario.id == ids[1]))
            db.commit()


def test_dos_envios_simultaneos_solo_uno_crea_la_version(
    db_engine, convenio_listo_concurrente
) -> None:
    convenio_id, usuario_id = convenio_listo_concurrente
    barrera = Barrier(2)

    def enviar(_):
        with Session(db_engine) as db:
            usuario = db.get(Usuario, usuario_id)
            barrera.wait(timeout=10)
            try:
                ServicioConvenios(db).finalizar_elaboracion(convenio_id, usuario)
                return "CREADA"
            except ConvenioNoEditable:
                return "CONFLICTO"

    with ThreadPoolExecutor(max_workers=2) as ejecutor:
        assert sorted(ejecutor.map(enviar, range(2))) == ["CONFLICTO", "CREADA"]

    with Session(db_engine) as db:
        convenio = db.get(Convenio, convenio_id)
        assert convenio.etapa_actual.codigo == "REVISION_AVAL_JURIDICO"
        assert convenio.version_actual == 1
        assert (
            db.scalar(
                select(func.count())
                .select_from(VersionConvenio)
                .where(VersionConvenio.convenio_id == convenio_id)
            )
            == 1
        )
        assert (
            db.scalar(
                select(func.count())
                .select_from(RevisionConvenio)
                .where(RevisionConvenio.convenio_id == convenio_id)
            )
            == 1
        )


# ---- Concurrencia de guardados: confirmar con un convenio nuevo (revisión 1) ---


@pytest.fixture
def convenio_nuevo_concurrente(db_engine):
    """Convenio manual recién creado, sin enviar: su borrador nace en
    revisión 1 (`_crear_borrador_inicial`)."""
    with Session(db_engine, expire_on_commit=False) as db:
        rol = db.scalar(select(Rol).where(Rol.codigo == CodigoRol.GESTOR_ORI.value))
        usuario = Usuario(
            correo=f"guardado-{uuid4().hex}@example.com",
            hash_contrasena="sin-login",
            nombre_completo="Gestor concurrente",
            rol=rol,
            tipo_usuario=TipoUsuario.INTERNO.value,
        )
        db.add(usuario)
        db.flush()
        convenio = ServicioConvenios(db).crear_manual(
            ConvenioCrearManual(objeto="Convenio nuevo para guardado concurrente"),
            usuario,
        )
        db.commit()
        borrador = ServicioConvenios(db)._borrador(convenio.id)
        assert borrador.revision == 1
        ids = convenio.id, usuario.id
    try:
        yield ids
    finally:
        with Session(db_engine) as db:
            for modelo in (RevisionConvenio, VersionConvenio, HistorialEtapa, BorradorConvenio):
                db.execute(delete(modelo).where(modelo.convenio_id == ids[0]))
            db.execute(delete(Auditoria).where(Auditoria.usuario_id == ids[1]))
            db.execute(delete(Convenio).where(Convenio.id == ids[0]))
            db.execute(delete(Usuario).where(Usuario.id == ids[1]))
            db.commit()


def test_dos_guardados_con_la_misma_revision_inicial_solo_uno_sube_la_revision(
    db_engine, convenio_nuevo_concurrente
) -> None:
    convenio_id, usuario_id = convenio_nuevo_concurrente
    barrera = Barrier(2)

    def guardar(indice):
        with Session(db_engine) as db:
            usuario = db.get(Usuario, usuario_id)
            barrera.wait(timeout=10)
            try:
                ServicioConvenios(db).guardar_elaboracion(
                    convenio_id,
                    ConvenioElaboracionGuardar(
                        contenido=_con_parrafo(DOCUMENTO_ELABORADO, f"Hilo {indice}"),
                        expected_revision=1,
                    ),
                    usuario,
                )
                return "GUARDADO"
            except ConflictoBorradorConvenio:
                return "CONFLICTO"

    with ThreadPoolExecutor(max_workers=2) as ejecutor:
        resultados = sorted(ejecutor.map(guardar, range(2)))

    assert resultados == ["CONFLICTO", "GUARDADO"]

    with Session(db_engine) as db:
        borrador = db.scalar(
            select(BorradorConvenio).where(BorradorConvenio.convenio_id == convenio_id)
        )
        assert borrador.revision == 2


# ---- Histórico: V1 vacía y V2 conservan su numeración tras un nuevo ciclo ------


def test_version_historica_conserva_numeros_contenidos_y_referencias(
    client, db, gestor, revisor, convenio_manual, formalizar_version
) -> None:
    # V1 "vacía", como la creaba el sistema antes de HT-15 (RN-01/RN-02 no
    # existían): se formaliza directo sobre el documento vacío inicial.
    v1 = formalizar_version(
        convenio_manual, gestor, ContextoVersionConvenio.INICIALIZACION
    )
    assert v1.numero == 1
    assert v1.contenido == DOCUMENTO_VACIO

    # V2 histórica, con contenido real, también anterior a HT-15.
    db.add(
        BorradorConvenio(
            convenio_id=convenio_manual.id,
            contenido=deepcopy(DOCUMENTO_ELABORADO),
            revision=1,
            actualizado_por_id=gestor.id,
        )
    )
    db.commit()
    v2 = formalizar_version(
        convenio_manual, gestor, ContextoVersionConvenio.INICIALIZACION
    )
    assert v2.numero == 2
    assert v2.contenido == DOCUMENTO_ELABORADO

    v1_id, v2_id = v1.id, v2.id
    v1_contenido, v2_contenido = deepcopy(v1.contenido), deepcopy(v2.contenido)

    # Nuevo ciclo real: editar y reenviar debe crear V3 sin tocar V1 ni V2.
    nuevo_borrador = BorradorConvenio(
        convenio_id=convenio_manual.id,
        contenido=_con_parrafo(DOCUMENTO_ELABORADO, "Ciclo nuevo tras HT-15"),
        revision=1,
        actualizado_por_id=gestor.id,
    )
    db.add(nuevo_borrador)
    db.commit()

    ServicioConvenios(db).finalizar_elaboracion(convenio_manual.id, gestor)

    db.expire_all()
    v1_despues = db.get(VersionConvenio, v1_id)
    v2_despues = db.get(VersionConvenio, v2_id)
    assert (v1_despues.numero, v1_despues.contenido) == (1, v1_contenido)
    assert (v2_despues.numero, v2_despues.contenido) == (2, v2_contenido)
    assert v1_despues.contexto == ContextoVersionConvenio.INICIALIZACION.value
    assert v2_despues.contexto == ContextoVersionConvenio.INICIALIZACION.value
    v3 = db.scalar(
        select(VersionConvenio).where(
            VersionConvenio.convenio_id == convenio_manual.id,
            VersionConvenio.numero == 3,
        )
    )
    assert v3 is not None
    assert v3.contexto == ContextoVersionConvenio.FINALIZACION.value
    assert db.get(Convenio, convenio_manual.id).version_actual == 3
    # La revisión jurídica abierta por el nuevo ciclo referencia V3, no V1/V2.
    pendiente = db.scalar(
        select(RevisionConvenio).where(
            RevisionConvenio.convenio_id == convenio_manual.id,
            RevisionConvenio.estado == "PENDIENTE",
        )
    )
    assert pendiente.version_convenio_id == v3.id
