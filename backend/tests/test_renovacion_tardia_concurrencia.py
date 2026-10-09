from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from threading import Barrier
from uuid import uuid4

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from backend.cli.conciliar_convenios import main
from backend.core.roles import CodigoRol, TipoUsuario
from backend.models.auditoria import Auditoria
from backend.models.convenio import Convenio
from backend.models.enums import EstadoSolicitud, TipoSolicitante
from backend.models.historial_etapa import HistorialEtapa
from backend.models.rol import Rol
from backend.models.solicitud_convenio import SolicitudConvenio
from backend.models.transicion_estado_convenio import TransicionEstadoConvenio
from backend.models.usuario import Usuario
from backend.models.version_convenio import VersionConvenio
from backend.schemas.convenio import ConvenioCrear
from backend.services.ciclo_vida_convenios import conciliar_estados
from backend.services.convenios import (
    ConvenioDuplicado,
    ConvenioNoEditable,
    ServicioConvenios,
)
from backend.services.renovaciones import ServicioRenovaciones

HOY = date(2026, 10, 8)


@pytest.fixture
def origen_confirmado(db_engine):
    with Session(db_engine, expire_on_commit=False) as db:
        rol = db.scalar(select(Rol).where(Rol.codigo == CodigoRol.GESTOR_ORI.value))
        usuario = Usuario(
            correo=f"tardia-{uuid4().hex}@example.com",
            hash_contrasena="sin-login",
            nombre_completo="Gestor concurrente",
            rol=rol,
            tipo_usuario=TipoUsuario.INTERNO.value,
        )
        db.add(usuario)
        db.flush()
        solicitud = SolicitudConvenio(
            consecutivo=f"SOL-{uuid4().hex}",
            solicitante_id=usuario.id,
            tipo_solicitante=TipoSolicitante.INTERNO.value,
            estado=EstadoSolicitud.APROBADA.value,
        )
        db.add(solicitud)
        db.commit()
        convenio = ServicioConvenios(db).crear(
            ConvenioCrear(
                solicitud_id=solicitud.id,
                objeto="Convenio para renovación concurrente",
                fecha_vencimiento=HOY - timedelta(days=1),
            ),
            usuario,
        )
        convenio.estado = "FINALIZADO"
        db.commit()
        ids = convenio.id, usuario.id
    try:
        yield ids
    finally:
        with Session(db_engine) as db:
            convenios = list(
                db.scalars(select(Convenio.id).where(Convenio.creado_por_id == ids[1]))
            )
            for modelo in (TransicionEstadoConvenio, VersionConvenio, HistorialEtapa):
                db.execute(delete(modelo).where(modelo.convenio_id.in_(convenios)))
            db.execute(delete(Auditoria).where(Auditoria.usuario_id == ids[1]))
            db.execute(delete(Convenio).where(Convenio.convenio_origen_id == ids[0]))
            db.execute(delete(Convenio).where(Convenio.id == ids[0]))
            db.execute(
                delete(SolicitudConvenio).where(
                    SolicitudConvenio.solicitante_id == ids[1]
                )
            )
            db.execute(delete(Usuario).where(Usuario.id == ids[1]))
            db.commit()


def test_dos_renovaciones_tardias_solo_crean_un_hijo(db_engine, origen_confirmado):
    origen_id, usuario_id = origen_confirmado
    barrera = Barrier(2)

    def iniciar(_):
        with Session(db_engine) as db:
            usuario = db.get(Usuario, usuario_id)
            barrera.wait(timeout=10)
            try:
                ServicioRenovaciones(db).iniciar_renovacion(origen_id, usuario)
                return "CREADA"
            except (ConvenioDuplicado, ConvenioNoEditable):
                return "CONFLICTO"

    with ThreadPoolExecutor(max_workers=2) as ejecutor:
        assert sorted(ejecutor.map(iniciar, range(2))) == ["CONFLICTO", "CREADA"]
    with Session(db_engine) as db:
        assert db.get(Convenio, origen_id).estado == "FINALIZADO"
        assert (
            db.scalar(
                select(func.count())
                .select_from(Convenio)
                .where(
                    Convenio.convenio_origen_id == origen_id,
                    Convenio.estado == "EN_TRAMITE",
                )
            )
            == 1
        )
        assert (
            db.scalar(
                select(func.count())
                .select_from(SolicitudConvenio)
                .where(SolicitudConvenio.solicitante_id == usuario_id)
            )
            == 2
        )


def test_conciliar_y_renovar_concurrentemente_conserva_padre_e_hijo(
    db_engine, origen_confirmado
):
    origen_id, usuario_id = origen_confirmado
    with Session(db_engine) as db:
        db.get(Convenio, origen_id).estado = "POR_VENCER"
        db.commit()
    barrera = Barrier(2)

    def ejecutar(tipo):
        with Session(db_engine) as db:
            usuario = db.get(Usuario, usuario_id)
            barrera.wait(timeout=10)
            if tipo == "conciliar":
                conciliar_estados(db, HOY)
            else:
                ServicioRenovaciones(db).iniciar_renovacion(origen_id, usuario)

    with ThreadPoolExecutor(max_workers=2) as ejecutor:
        list(ejecutor.map(ejecutar, ["conciliar", "renovar"]))
    with Session(db_engine) as db:
        assert db.get(Convenio, origen_id).estado == "FINALIZADO"
        hijos = db.scalars(
            select(Convenio).where(Convenio.convenio_origen_id == origen_id)
        ).all()
        assert len(hijos) == 1
        assert hijos[0].estado == "EN_TRAMITE"
        assert hijos[0].solicitud.solicitante_id == usuario_id
        assert (
            db.scalar(
                select(func.count())
                .select_from(TransicionEstadoConvenio)
                .where(TransicionEstadoConvenio.convenio_id == origen_id)
            )
            == 1
        )


def test_cli_real_simula_ejecuta_y_repite_sin_duplicar(db_engine, origen_confirmado):
    origen_id, _ = origen_confirmado
    with Session(db_engine) as db:
        db.get(Convenio, origen_id).estado = "VIGENTE"
        db.commit()
    assert main(["--simular", "--fecha-referencia", HOY.isoformat()]) == 0
    with Session(db_engine) as db:
        assert db.get(Convenio, origen_id).estado == "VIGENTE"
        assert not db.scalars(select(TransicionEstadoConvenio)).all()
    for _ in range(2):
        assert main(["--fecha-referencia", HOY.isoformat()]) == 0
    with Session(db_engine) as db:
        assert db.get(Convenio, origen_id).estado == "FINALIZADO"
        assert (
            db.scalar(
                select(func.count())
                .select_from(TransicionEstadoConvenio)
                .where(TransicionEstadoConvenio.convenio_id == origen_id)
            )
            == 1
        )
