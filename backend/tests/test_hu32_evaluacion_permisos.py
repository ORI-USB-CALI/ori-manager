"""HU-32 / CA-09 — Autorización de la evaluación de convenios.

Matriz completa por endpoint: quién puede registrar, quién puede consultar y la
garantía de que un rechazo no modifica nada.
"""

import pytest
from sqlalchemy import func, select

from backend.core.roles import CodigoRol, TipoUsuario
from backend.models.auditoria import Auditoria
from backend.models.convenio import Convenio
from backend.models.evaluacion_convenio import EvaluacionConvenio

ROLES_AUTORIZADOS = [CodigoRol.ADMINISTRADOR_ORI, CodigoRol.GESTOR_ORI]

# Enumerados a mano: la matriz debe fallar si un rol gana el permiso por error.
ROLES_SIN_PERMISO = [
    (CodigoRol.REVISOR_ORI, TipoUsuario.INTERNO),
    (CodigoRol.SOLICITANTE_INTERNO, TipoUsuario.INTERNO),
    (CodigoRol.SOLICITANTE_EXTERNO, TipoUsuario.EXTERNO),
]

OBSERVACIONES = "Evaluación registrada por el rol autorizado."


def url(convenio_id: int) -> str:
    return f"/api/convenios/{convenio_id}/evaluacion"


def cuerpo(**cambios) -> dict:
    base = {
        "fue_funcional": True,
        "calificacion": 7,
        "observaciones": OBSERVACIONES,
    }
    return {**base, **cambios}


def conteos(db) -> dict:
    return {
        modelo.__tablename__: db.scalar(select(func.count()).select_from(modelo))
        for modelo in (EvaluacionConvenio, Auditoria, Convenio)
    }


def fila(db, convenio_id: int) -> dict:
    evaluacion = db.scalar(
        select(EvaluacionConvenio).where(
            EvaluacionConvenio.convenio_id == convenio_id
        )
    )
    db.refresh(evaluacion)
    return {
        col.name: getattr(evaluacion, col.name)
        for col in EvaluacionConvenio.__table__.columns
    }


@pytest.fixture
def finalizado(crear_usuario, crear_convenio_finalizado) -> Convenio:
    """Convenio evaluable cuyo autor no es el usuario autenticado del test."""
    return crear_convenio_finalizado(crear_usuario(CodigoRol.GESTOR_ORI))


# ---- Registro: roles habilitados -----------------------------------------


@pytest.mark.parametrize("rol", ROLES_AUTORIZADOS)
def test_roles_autorizados_pueden_registrar_la_evaluacion(
    client, crear_usuario, entrar_como, finalizado, rol
):
    usuario = crear_usuario(rol)
    entrar_como(usuario)

    respuesta = client.post(url(finalizado.id), json=cuerpo())

    assert respuesta.status_code == 201
    assert respuesta.json()["evaluado_por_id"] == usuario.id


# ---- Registro: roles sin permiso -----------------------------------------


@pytest.mark.parametrize(("rol", "tipo"), ROLES_SIN_PERMISO)
def test_roles_sin_permiso_no_pueden_registrar_ni_modificar_nada(
    db, client, crear_usuario, entrar_como, finalizado, rol, tipo
):
    entrar_como(crear_usuario(rol, tipo))
    antes = conteos(db)

    assert client.post(url(finalizado.id), json=cuerpo()).status_code == 403
    assert conteos(db) == antes


def test_sin_sesion_no_se_puede_registrar_ni_modificar_nada(db, client, finalizado):
    antes = conteos(db)

    assert client.post(url(finalizado.id), json=cuerpo()).status_code == 401
    assert conteos(db) == antes


def test_usuario_inactivo_no_puede_registrar(
    db, client, crear_usuario, entrar_como, finalizado
):
    entrar_como(crear_usuario(CodigoRol.GESTOR_ORI, activo=False))
    antes = conteos(db)

    assert client.post(url(finalizado.id), json=cuerpo()).status_code == 403
    assert conteos(db) == antes


@pytest.mark.parametrize(("rol", "tipo"), ROLES_SIN_PERMISO)
def test_roles_sin_permiso_no_pueden_sobrescribir_una_evaluacion_existente(
    db, client, crear_usuario, entrar_como, finalizado, rol, tipo
):
    entrar_como(crear_usuario(CodigoRol.GESTOR_ORI))
    assert client.post(url(finalizado.id), json=cuerpo()).status_code == 201
    sin_permiso = crear_usuario(rol, tipo)
    antes_fila = fila(db, finalizado.id)
    antes_conteos = conteos(db)

    entrar_como(sin_permiso)
    respuesta = client.post(
        url(finalizado.id),
        json=cuerpo(
            fue_funcional=False,
            calificacion=1,
            observaciones="Intento no autorizado de sobrescribir",
        ),
    )

    assert respuesta.status_code == 403
    assert conteos(db) == antes_conteos
    assert fila(db, finalizado.id) == antes_fila


# ---- Consulta: permiso más alcance operativo -----------------------------


@pytest.mark.parametrize("rol", ROLES_AUTORIZADOS)
def test_roles_autorizados_pueden_consultar_la_evaluacion(
    client, crear_usuario, entrar_como, finalizado, rol
):
    entrar_como(crear_usuario(rol))

    assert client.get(url(finalizado.id)).status_code == 200


def test_revisor_no_ve_la_evaluacion_de_un_convenio_finalizado(
    client, crear_usuario, entrar_como, finalizado
):
    """El revisor tiene convenios.ver, pero su alcance operativo se limita a la
    revisión jurídica: un convenio FINALIZADO queda fuera y responde 404."""
    entrar_como(crear_usuario(CodigoRol.REVISOR_ORI, TipoUsuario.INTERNO))

    assert client.get(url(finalizado.id)).status_code == 404


@pytest.mark.parametrize(
    ("rol", "tipo"),
    [
        (CodigoRol.SOLICITANTE_INTERNO, TipoUsuario.INTERNO),
        (CodigoRol.SOLICITANTE_EXTERNO, TipoUsuario.EXTERNO),
    ],
)
def test_solicitantes_no_pueden_consultar_la_evaluacion(
    client, crear_usuario, entrar_como, finalizado, rol, tipo
):
    entrar_como(crear_usuario(rol, tipo))

    assert client.get(url(finalizado.id)).status_code == 403


def test_sin_sesion_no_se_puede_consultar_la_evaluacion(client, finalizado):
    assert client.get(url(finalizado.id)).status_code == 401
