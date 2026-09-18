from collections.abc import Callable
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.core.roles import CodigoRol, TipoUsuario
from backend.models.aliado import Aliado
from backend.models.contacto_aliado import ContactoAliado
from backend.models.convenio import Convenio
from backend.models.enums import (
    AlcanceConvenio,
    EstadoConvenio,
    EstadoSolicitud,
    TipoAliado,
    TipoSolicitante,
)
from backend.models.solicitud_convenio import SolicitudConvenio
from backend.models.usuario import Usuario
from backend.schemas.aliado import DatosContraparteSolicitud
from backend.services.aliados import ConflictoAliado, resolver_aliado_para_convenio


@pytest.fixture
def crear_aliado(db: Session) -> Callable[..., Aliado]:
    def _crear(**cambios) -> Aliado:
        datos = {
            "nombre": "Universidad aliada",
            "tipo": TipoAliado.UNIVERSIDAD.value,
            "identificacion": f"ALI-{uuid4().hex}",
            "correo": "contacto@aliada.example",
            "activo": True,
        }
        datos.update(cambios)
        aliado = Aliado(**datos)
        db.add(aliado)
        db.commit()
        return aliado

    return _crear


@pytest.fixture
def crear_solicitud(db: Session, crear_usuario) -> Callable[..., SolicitudConvenio]:
    def _crear(solicitante: Usuario | None = None, **cambios) -> SolicitudConvenio:
        usuario = solicitante or crear_usuario()
        datos = {
            "consecutivo": f"SOL-{uuid4().hex}",
            "tipo_solicitante": TipoSolicitante.INTERNO.value,
            "solicitante_id": usuario.id,
            "objeto": "Solicitud de cooperación académica",
            "estado": EstadoSolicitud.APROBADA.value,
        }
        datos.update(cambios)
        solicitud = SolicitudConvenio(**datos)
        db.add(solicitud)
        db.commit()
        return solicitud

    return _crear


def _crear_convenio(
    db: Session,
    solicitud: SolicitudConvenio,
    usuario: Usuario,
    aliado: Aliado | None = None,
    estado: EstadoConvenio = EstadoConvenio.EN_TRAMITE,
) -> Convenio:
    convenio = Convenio(
        solicitud_id=solicitud.id,
        aliado_id=aliado.id if aliado else None,
        estado=estado.value,
        objeto="Cooperación internacional",
        alcance=AlcanceConvenio.INSTITUCIONAL.value,
        creado_por_id=usuario.id,
    )
    db.add(convenio)
    db.commit()
    return convenio


def _autenticar(client, crear_usuario, entrar_como, rol: CodigoRol) -> Usuario:
    usuario = crear_usuario(
        rol,
        TipoUsuario.EXTERNO if rol == CodigoRol.SOLICITANTE_EXTERNO else TipoUsuario.INTERNO,
    )
    entrar_como(usuario)
    return usuario


def _payload_convenio(solicitud_id: int, aliado_id: int | None = None) -> dict:
    return {
        "solicitud_id": solicitud_id,
        "aliado_id": aliado_id,
        "objeto": "Convenio de movilidad académica",
        "alcance": "INSTITUCIONAL",
    }


# HU04 CA-01 a CA-05: conversión automática y trazabilidad de correo.
def test_hu04_ca01_en_tramite_no_crea_ni_asocia_aliado(
    db, crear_usuario, crear_solicitud
) -> None:
    usuario = crear_usuario()
    solicitud = crear_solicitud(usuario)
    convenio = _crear_convenio(db, solicitud, usuario)

    resultado = resolver_aliado_para_convenio(
        db,
        convenio,
        DatosContraparteSolicitud(
            identificacion="NUEVA-1",
            nombre="Entidad propuesta",
            tipo=TipoAliado.UNIVERSIDAD,
            correo="nuevo@example.com",
        ),
    )

    assert resultado is None
    assert convenio.aliado_id is None
    assert solicitud.aliado_id is None
    assert db.scalar(select(Aliado).where(Aliado.identificacion == "NUEVA-1")) is None


def test_hu04_ca02_ca03_ca04_vigente_crea_y_reutiliza_por_identificacion(
    db, crear_usuario, crear_solicitud
) -> None:
    usuario = crear_usuario()
    datos = DatosContraparteSolicitud(
        identificacion="NIT-COMPARTIDO",
        nombre="Empresa compartida",
        tipo=TipoAliado.EMPRESA,
        sector_economico="Tecnología",
        correo="uno@example.com",
    )
    solicitud_1 = crear_solicitud(usuario)
    convenio_1 = _crear_convenio(db, solicitud_1, usuario, estado=EstadoConvenio.VIGENTE)
    aliado_1 = resolver_aliado_para_convenio(db, convenio_1, datos)
    db.commit()
    solicitud_2 = crear_solicitud(usuario)
    convenio_2 = _crear_convenio(db, solicitud_2, usuario, estado=EstadoConvenio.VIGENTE)
    aliado_2 = resolver_aliado_para_convenio(db, convenio_2, datos)
    db.commit()

    assert aliado_1 is not None and aliado_2 is not None
    assert aliado_1.id == aliado_2.id
    assert convenio_1.aliado_id == aliado_1.id == solicitud_1.aliado_id
    assert convenio_2.aliado_id == aliado_1.id == solicitud_2.aliado_id
    assert len(db.scalars(select(Aliado).where(Aliado.identificacion == "NIT-COMPARTIDO")).all()) == 1


def test_hu04_ca05_correo_distinto_no_duplica_aliado_y_conserva_contactos(
    db, crear_usuario, crear_solicitud, crear_aliado
) -> None:
    usuario = crear_usuario()
    aliado = crear_aliado(identificacion="NIT-CORREO", correo="anterior@example.com")
    solicitud = crear_solicitud(usuario)
    convenio = _crear_convenio(db, solicitud, usuario, estado=EstadoConvenio.VIGENTE)

    resultado = resolver_aliado_para_convenio(
        db,
        convenio,
        DatosContraparteSolicitud(
            identificacion="NIT-CORREO",
            nombre="Universidad aliada",
            tipo=TipoAliado.UNIVERSIDAD,
            correo="nuevo@example.com",
        ),
    )
    db.commit()

    assert resultado is not None and resultado.id == aliado.id
    assert resultado.correo == "nuevo@example.com"
    correos = set(db.scalars(select(ContactoAliado.correo).where(ContactoAliado.aliado_id == aliado.id)))
    assert correos == {"anterior@example.com", "nuevo@example.com"}


def test_hu04_aliado_inactivo_no_se_reactiva_al_formalizar(
    db, crear_usuario, crear_solicitud, crear_aliado
) -> None:
    usuario = crear_usuario()
    aliado = crear_aliado(identificacion="INACTIVO-1", activo=False)
    solicitud = crear_solicitud(usuario)
    convenio = _crear_convenio(db, solicitud, usuario, estado=EstadoConvenio.VIGENTE)
    with pytest.raises(ConflictoAliado, match="reactivarse"):
        resolver_aliado_para_convenio(
            db,
            convenio,
            DatosContraparteSolicitud(
                identificacion=aliado.identificacion,
                nombre=aliado.nombre,
                tipo=TipoAliado.UNIVERSIDAD,
            ),
        )
    assert aliado.activo is False
    assert convenio.aliado_id is None


# HU04 CA-06 a CA-12: gestión, permisos, estado e integridad.
@pytest.mark.parametrize(
    "rol",
    [CodigoRol.ADMINISTRADOR_ORI, CodigoRol.GESTOR_ORI, CodigoRol.REVISOR_ORI],
)
def test_hu04_ca06_roles_autorizados_consultan(
    rol, client, crear_usuario, entrar_como
) -> None:
    _autenticar(client, crear_usuario, entrar_como, rol)
    assert client.get("/api/aliados").status_code == 200


def test_hu04_ca07_ca12_revisor_no_edita_y_gestor_si(
    client, crear_usuario, entrar_como, crear_aliado
) -> None:
    aliado = crear_aliado()
    _autenticar(client, crear_usuario, entrar_como, CodigoRol.REVISOR_ORI)
    assert client.patch(f"/api/aliados/{aliado.id}", json={"ciudad": "Cali"}).status_code == 403
    _autenticar(client, crear_usuario, entrar_como, CodigoRol.GESTOR_ORI)
    respuesta = client.patch(f"/api/aliados/{aliado.id}", json={"ciudad": "Cali"})
    assert respuesta.status_code == 200
    assert respuesta.json()["ciudad"] == "Cali"


def test_hu04_ca08_ca09_ca10_inactivar_segun_estado_y_reactivar(
    db, client, crear_usuario, entrar_como, crear_aliado, crear_solicitud
) -> None:
    gestor = _autenticar(client, crear_usuario, entrar_como, CodigoRol.GESTOR_ORI)
    aliado = crear_aliado()
    solicitud = crear_solicitud(gestor)
    convenio = _crear_convenio(db, solicitud, gestor, aliado, EstadoConvenio.VIGENTE)
    assert client.patch(f"/api/aliados/{aliado.id}/estado", json={"activo": False}).status_code == 409
    convenio.estado = EstadoConvenio.VENCIDO.value
    db.commit()
    inactivar = client.patch(f"/api/aliados/{aliado.id}/estado", json={"activo": False})
    assert inactivar.status_code == 200 and inactivar.json()["activo"] is False
    reactivar = client.patch(f"/api/aliados/{aliado.id}/estado", json={"activo": True})
    assert reactivar.status_code == 200 and reactivar.json()["activo"] is True


def test_hu04_por_vencer_bloquea_y_finalizado_no_bloquea(
    db, client, crear_usuario, entrar_como, crear_aliado, crear_solicitud
) -> None:
    gestor = _autenticar(client, crear_usuario, entrar_como, CodigoRol.GESTOR_ORI)
    aliado = crear_aliado()
    convenio = _crear_convenio(db, crear_solicitud(gestor), gestor, aliado, EstadoConvenio.POR_VENCER)
    assert client.patch(f"/api/aliados/{aliado.id}/estado", json={"activo": False}).status_code == 409
    convenio.estado = EstadoConvenio.FINALIZADO.value
    db.commit()
    assert client.patch(f"/api/aliados/{aliado.id}/estado", json={"activo": False}).status_code == 200


def test_hu04_ca11_identificacion_unica_y_no_editable(
    db, client, crear_usuario, entrar_como, crear_aliado
) -> None:
    aliado = crear_aliado(identificacion="UNICA-1")
    db.add(Aliado(nombre="Duplicado", tipo=TipoAliado.COLEGIO.value, identificacion="UNICA-1"))
    with pytest.raises(IntegrityError):
        db.flush()
    db.rollback()
    _autenticar(client, crear_usuario, entrar_como, CodigoRol.GESTOR_ORI)
    assert client.patch(f"/api/aliados/{aliado.id}", json={"identificacion": "OTRA"}).status_code == 422


def test_hu04_rutas_sin_sesion_responden_401(client) -> None:
    client.cookies.clear()
    assert client.get("/api/aliados").status_code == 401
    assert client.patch("/api/aliados/1", json={"nombre": "X"}).status_code == 401
    assert client.patch("/api/aliados/1/estado", json={"activo": False}).status_code == 401


# HU05 CA-01 a CA-08: perfil consolidado, filtrado y errores.
def test_hu05_perfil_devuelve_todos_y_solo_convenios_del_aliado(
    db, client, crear_usuario, entrar_como, crear_aliado, crear_solicitud
) -> None:
    revisor = _autenticar(client, crear_usuario, entrar_como, CodigoRol.REVISOR_ORI)
    aliado = crear_aliado()
    otro = crear_aliado()
    propios = {
        _crear_convenio(db, crear_solicitud(revisor), revisor, aliado, EstadoConvenio.VIGENTE).id,
        _crear_convenio(db, crear_solicitud(revisor), revisor, aliado, EstadoConvenio.FINALIZADO).id,
    }
    ajeno = _crear_convenio(db, crear_solicitud(revisor), revisor, otro).id

    respuesta = client.get(f"/api/aliados/{aliado.id}")
    assert respuesta.status_code == 200
    ids = {item["id"] for item in respuesta.json()["convenios"]}
    assert ids == propios and ajeno not in ids


def test_hu05_aliado_sin_convenios_e_inactivo_sigue_consultable(
    client, crear_usuario, entrar_como, crear_aliado
) -> None:
    _autenticar(client, crear_usuario, entrar_como, CodigoRol.REVISOR_ORI)
    aliado = crear_aliado(activo=False)
    respuesta = client.get(f"/api/aliados/{aliado.id}")
    assert respuesta.status_code == 200
    assert respuesta.json()["activo"] is False
    assert respuesta.json()["convenios"] == []


def test_hu05_404_403_y_401(client, crear_usuario, entrar_como) -> None:
    _autenticar(client, crear_usuario, entrar_como, CodigoRol.REVISOR_ORI)
    assert client.get("/api/aliados/999999999").status_code == 404
    _autenticar(client, crear_usuario, entrar_como, CodigoRol.SOLICITANTE_INTERNO)
    assert client.get("/api/aliados/1").status_code == 403
    client.cookies.clear()
    assert client.get("/api/aliados/1").status_code == 401


# HU06 CA-01 a CA-08: registro, consulta, edición y permisos.
def test_hu06_ca01_ca03_ca04_ca06_crea_desde_sesion_sin_aliado(
    client, crear_usuario, entrar_como, crear_solicitud
) -> None:
    gestor = _autenticar(client, crear_usuario, entrar_como, CodigoRol.GESTOR_ORI)
    solicitud = crear_solicitud(gestor)
    respuesta = client.post("/api/convenios", json=_payload_convenio(solicitud.id))
    assert respuesta.status_code == 201
    cuerpo = respuesta.json()
    assert cuerpo["id"] > 0
    assert cuerpo["aliado_id"] is None
    assert cuerpo["estado"] == EstadoConvenio.EN_TRAMITE
    assert cuerpo["creado_por_id"] == gestor.id
    assert cuerpo["creado_por"]["id"] == gestor.id
    assert cuerpo["creado_en"]
    assert client.get(f"/api/convenios/{cuerpo['id']}").status_code == 200


def test_hu06_ca02_ca07_aliado_activo_valido_inexistente_e_inactivo_rechazados(
    client, crear_usuario, entrar_como, crear_solicitud, crear_aliado
) -> None:
    gestor = _autenticar(client, crear_usuario, entrar_como, CodigoRol.GESTOR_ORI)
    activo = crear_aliado()
    inactivo = crear_aliado(activo=False)
    correcta = client.post("/api/convenios", json=_payload_convenio(crear_solicitud(gestor).id, activo.id))
    inexistente = client.post("/api/convenios", json=_payload_convenio(crear_solicitud(gestor).id, 999999999))
    rechazada = client.post("/api/convenios", json=_payload_convenio(crear_solicitud(gestor).id, inactivo.id))
    assert correcta.status_code == 201
    assert inexistente.status_code == 422
    assert rechazada.status_code == 422


def test_hu06_ca04_rechaza_estado_y_creado_por_del_cliente(
    client, crear_usuario, entrar_como, crear_solicitud
) -> None:
    gestor = _autenticar(client, crear_usuario, entrar_como, CodigoRol.GESTOR_ORI)
    solicitud = crear_solicitud(gestor)
    datos = {**_payload_convenio(solicitud.id), "estado": "VIGENTE", "creado_por_id": 999}
    assert client.post("/api/convenios", json=datos).status_code == 422


def test_hu06_ca05_solicitud_unica(client, crear_usuario, entrar_como, crear_solicitud) -> None:
    gestor = _autenticar(client, crear_usuario, entrar_como, CodigoRol.GESTOR_ORI)
    solicitud = crear_solicitud(gestor)
    assert client.post("/api/convenios", json=_payload_convenio(solicitud.id)).status_code == 201
    assert client.post("/api/convenios", json=_payload_convenio(solicitud.id)).status_code == 409


def test_hu06_patch_parcial_y_campos_inmutables(
    client, crear_usuario, entrar_como, crear_solicitud
) -> None:
    gestor = _autenticar(client, crear_usuario, entrar_como, CodigoRol.GESTOR_ORI)
    solicitud = crear_solicitud(gestor)
    creado = client.post("/api/convenios", json=_payload_convenio(solicitud.id)).json()
    respuesta = client.patch(f"/api/convenios/{creado['id']}", json={"objeto": "Objeto actualizado"})
    assert respuesta.status_code == 200 and respuesta.json()["objeto"] == "Objeto actualizado"
    for campo, valor in [("estado", "VIGENTE"), ("solicitud_id", 1), ("creado_por_id", 1), ("id", 1), ("creado_en", "2026-01-01")]:
        assert client.patch(f"/api/convenios/{creado['id']}", json={campo: valor}).status_code == 422


@pytest.mark.parametrize(
    ("rol", "lectura", "escritura"),
    [
        (CodigoRol.REVISOR_ORI, 200, 403),
        (CodigoRol.GESTOR_ORI, 200, 201),
        (CodigoRol.SOLICITANTE_INTERNO, 403, 403),
        (CodigoRol.SOLICITANTE_EXTERNO, 403, 403),
    ],
)
def test_hu06_ca08_permisos_por_rol(
    rol, lectura, escritura, db, client, crear_usuario, entrar_como, crear_solicitud
) -> None:
    autor = crear_usuario(CodigoRol.GESTOR_ORI)
    existente = _crear_convenio(db, crear_solicitud(autor), autor)
    actor = _autenticar(client, crear_usuario, entrar_como, rol)
    assert client.get(f"/api/convenios/{existente.id}").status_code == lectura
    solicitud = crear_solicitud(actor)
    assert client.post("/api/convenios", json=_payload_convenio(solicitud.id)).status_code == escritura
    assert client.patch(f"/api/convenios/{existente.id}", json={"objeto": "Cambio"}).status_code == (200 if rol == CodigoRol.GESTOR_ORI else 403)


def test_hu06_rutas_sin_sesion_responden_401(client) -> None:
    client.cookies.clear()
    assert client.post("/api/convenios", json=_payload_convenio(1)).status_code == 401
    assert client.get("/api/convenios/1").status_code == 401
    assert client.patch("/api/convenios/1", json={"objeto": "X"}).status_code == 401
