from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from uuid import uuid4

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.core.roles import CodigoRol, TipoUsuario
from backend.models.convenio import Convenio
from backend.models.enums import EstadoObservacionRevision, OrigenObservacionRevision
from backend.models.etapa import Etapa
from backend.models.historial_etapa import HistorialEtapa
from backend.models.observacion_revision import ObservacionRevision
from backend.models.rol import Rol
from backend.models.solicitud_convenio import SolicitudConvenio
from backend.models.usuario import Usuario


def _cargar_migracion():
    ruta = (
        Path(__file__).parents[1]
        / "migrations/versions/e41c9a7b2d53_bloque_b_trazabilidad_observaciones.py"
    )
    spec = spec_from_file_location("migracion_bloque_b", ruta)
    assert spec is not None and spec.loader is not None
    migracion = module_from_spec(spec)
    spec.loader.exec_module(migracion)
    return migracion


@pytest.fixture
def infraestructura_bloque_b(db_engine):
    esquema = f"test_bloque_b_{uuid4().hex}"
    migracion = _cargar_migracion()
    with db_engine.connect() as conexion:
        transaccion = conexion.begin()
        sesion = None
        try:
            tablas_publicas = set(
                conexion.execute(
                    text(
                        "SELECT tablename FROM pg_tables "
                        "WHERE schemaname = 'public'"
                    )
                ).scalars()
            )
            conexion.execute(text(f'CREATE SCHEMA "{esquema}"'))
            conexion.execute(
                text(f'SET LOCAL search_path TO "{esquema}", public')
            )
            migracion.op = Operations(MigrationContext.configure(conexion))
            migracion.upgrade()
            sesion = Session(bind=conexion, expire_on_commit=False)
            yield {
                "conexion": conexion,
                "esquema": esquema,
                "migracion": migracion,
                "sesion": sesion,
                "tablas_publicas": tablas_publicas,
            }
        finally:
            if sesion is not None:
                sesion.close()
            transaccion.rollback()


def _crear_contexto(sesion: Session):
    rol = sesion.scalar(select(Rol).where(Rol.codigo == CodigoRol.GESTOR_ORI.value))
    assert rol is not None
    sufijo = uuid4().hex
    actor = Usuario(
        correo=f"actor-{sufijo}@example.com",
        hash_contrasena="hash",
        nombre_completo="Actor de prueba",
        rol_id=rol.id,
        tipo_usuario=TipoUsuario.INTERNO.value,
    )
    responsable = Usuario(
        correo=f"responsable-{sufijo}@example.com",
        hash_contrasena="hash",
        nombre_completo="Responsable de prueba",
        rol_id=rol.id,
        tipo_usuario=TipoUsuario.INTERNO.value,
    )
    sesion.add_all([actor, responsable])
    sesion.flush()

    solicitud = SolicitudConvenio(
        consecutivo=f"SOL-{sufijo}",
        tipo_solicitante="INTERNO",
        solicitante_id=actor.id,
        estado="BORRADOR",
    )
    etapa_origen = Etapa(
        orden=-((int(sufijo[:4], 16) % 14000) + 1),
        codigo=f"ORIGEN-{sufijo}",
        nombre=f"Origen {sufijo}",
    )
    etapa_destino = Etapa(
        orden=-((int(sufijo[4:8], 16) % 14000) + 15001),
        codigo=f"DESTINO-{sufijo}",
        nombre=f"Destino {sufijo}",
    )
    sesion.add_all([solicitud, etapa_origen, etapa_destino])
    sesion.flush()
    convenio = Convenio(
        solicitud_id=solicitud.id,
        creado_por_id=actor.id,
        estado="EN_TRAMITE",
    )
    sesion.add(convenio)
    sesion.flush()
    return convenio, etapa_origen, etapa_destino, actor, responsable


def test_historial_etapa_admite_campos_opcionales_y_relaciones(
    infraestructura_bloque_b,
):
    sesion = infraestructura_bloque_b["sesion"]
    convenio, origen, destino, actor, responsable = _crear_contexto(sesion)
    inicial = HistorialEtapa(
        convenio_id=convenio.id,
        etapa_origen_id=None,
        etapa_destino_id=destino.id,
        usuario_id=actor.id,
        responsable_id=None,
    )
    posterior = HistorialEtapa(
        convenio_id=convenio.id,
        etapa_origen_id=origen.id,
        etapa_destino_id=destino.id,
        usuario_id=actor.id,
        responsable_id=responsable.id,
    )
    sesion.add_all([inicial, posterior])
    sesion.flush()

    assert inicial.etapa_origen is None
    assert inicial.responsable is None
    assert inicial.convenio is convenio
    assert inicial.etapa_destino is destino
    assert inicial.usuario is actor
    assert posterior.etapa_origen is origen
    assert posterior.etapa_destino is destino
    assert posterior.usuario is actor
    assert posterior.responsable is responsable


def test_observacion_revision_acepta_origenes_y_default_pendiente(
    infraestructura_bloque_b,
):
    sesion = infraestructura_bloque_b["sesion"]
    convenio, _, destino, actor, _ = _crear_contexto(sesion)
    historial = HistorialEtapa(
        convenio_id=convenio.id,
        etapa_destino_id=destino.id,
        usuario_id=actor.id,
    )
    sesion.add(historial)
    sesion.flush()

    observaciones = [
        ObservacionRevision(
            convenio_id=convenio.id,
            historial_etapa_id=historial.id,
            origen=origen.value,
            registrada_por_id=actor.id,
            descripcion=f"Observación {origen.value}",
        )
        for origen in OrigenObservacionRevision
    ]
    sesion.add_all(observaciones)
    sesion.flush()

    assert {item.origen for item in observaciones} == {
        "REVISOR_ORI",
        "CONTRAPARTE",
        "REVISION_FINAL_ORI",
    }
    assert all(
        item.estado == EstadoObservacionRevision.PENDIENTE.value
        for item in observaciones
    )
    assert all(item.respuesta is None for item in observaciones)
    assert all(item.atendida_por_id is None for item in observaciones)
    assert all(item.fecha_atencion is None for item in observaciones)


@pytest.mark.parametrize(
    ("campo", "valor", "constraint"),
    [
        ("origen", "ORIGEN_INVALIDO", "ck_observacion_revision_origen"),
        ("estado", "ESTADO_INVALIDO", "ck_observacion_revision_estado"),
    ],
)
def test_observacion_revision_rechaza_catalogos_invalidos(
    infraestructura_bloque_b, campo, valor, constraint
):
    sesion = infraestructura_bloque_b["sesion"]
    convenio, _, destino, actor, _ = _crear_contexto(sesion)
    historial = HistorialEtapa(
        convenio_id=convenio.id,
        etapa_destino_id=destino.id,
        usuario_id=actor.id,
    )
    sesion.add(historial)
    sesion.flush()
    observacion = ObservacionRevision(
        convenio_id=convenio.id,
        historial_etapa_id=historial.id,
        origen=OrigenObservacionRevision.REVISOR_ORI.value,
        registrada_por_id=actor.id,
        descripcion="Observación inválida",
    )
    setattr(observacion, campo, valor)

    with pytest.raises(IntegrityError, match=constraint), sesion.begin_nested():
        sesion.add(observacion)
        sesion.flush()


def test_migracion_crea_solo_tablas_bloque_b_y_fks_esperadas(
    infraestructura_bloque_b,
):
    conexion = infraestructura_bloque_b["conexion"]
    esquema = infraestructura_bloque_b["esquema"]
    migracion = infraestructura_bloque_b["migracion"]
    sesion = infraestructura_bloque_b["sesion"]
    tablas_publicas = infraestructura_bloque_b["tablas_publicas"]

    tablas = set(
        conexion.execute(
            text(
                "SELECT tablename FROM pg_tables WHERE schemaname = :esquema"
            ),
            {"esquema": esquema},
        ).scalars()
    )
    assert tablas == {"historial_etapa", "observacion_revision"}

    eliminaciones = {
        (fila.tabla, fila.columna): fila.on_delete
        for fila in conexion.execute(
            text(
                """
                SELECT tabla.relname AS tabla,
                       columna.attname AS columna,
                       restriccion.confdeltype AS on_delete
                FROM pg_constraint AS restriccion
                JOIN pg_class AS tabla
                  ON tabla.oid = restriccion.conrelid
                JOIN pg_namespace AS esquema_tabla
                  ON esquema_tabla.oid = tabla.relnamespace
                JOIN LATERAL unnest(restriccion.conkey) AS clave(attnum)
                  ON true
                JOIN pg_attribute AS columna
                  ON columna.attrelid = tabla.oid
                 AND columna.attnum = clave.attnum
                WHERE restriccion.contype = 'f'
                  AND esquema_tabla.nspname = :esquema
                """
            ),
            {"esquema": esquema},
        )
    }
    assert eliminaciones[("historial_etapa", "convenio_id")] == "r"
    assert eliminaciones[("observacion_revision", "convenio_id")] == "c"
    assert eliminaciones[("observacion_revision", "historial_etapa_id")] == "r"
    for tabla, columna in (
        ("historial_etapa", "usuario_id"),
        ("historial_etapa", "responsable_id"),
        ("observacion_revision", "registrada_por_id"),
        ("observacion_revision", "responsable_id"),
        ("observacion_revision", "atendida_por_id"),
    ):
        assert eliminaciones[(tabla, columna)] == "r"

    sesion.close()
    migracion.downgrade()
    tablas_despues = set(
        conexion.execute(
            text(
                "SELECT tablename FROM pg_tables WHERE schemaname = :esquema"
            ),
            {"esquema": esquema},
        ).scalars()
    )
    assert tablas_despues == set()
    assert (
        set(
            conexion.execute(
                text(
                    "SELECT tablename FROM pg_tables "
                    "WHERE schemaname = 'public'"
                )
            ).scalars()
        )
        == tablas_publicas
    )
