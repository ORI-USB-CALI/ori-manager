from collections.abc import Callable
from datetime import date
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.core.roles import CodigoRol, TipoUsuario
from backend.models.actividad_utilizacion import ActividadUtilizacion
from backend.models.convenio import Convenio
from backend.models.enums import EstadoConvenio
from backend.models.usuario import Usuario
from backend.services.actividades_utilizacion import (
    ServicioActividadesUtilizacion,
)

ACTIVIDAD_EJEMPLO = {
    "fecha": "2026-09-15",
    "actividad": "Movilidad académica de dos estudiantes de Ingeniería",
    "descripcion": "Participación en intercambio académico durante el semestre 2026-2",
    "responsable": "Facultad de Ingeniería",
    "observaciones": "Estudiantes seleccionados por convocatoria interna",
}


def url_actividades(convenio_id: int) -> str:
    return f"/api/convenios/{convenio_id}/actividades-utilizacion"


@pytest.fixture
def crear_convenio_en_estado(
    db: Session, gestor: Usuario, crear_convenio
) -> Callable[..., Convenio]:
    def _crear(estado: EstadoConvenio = EstadoConvenio.VIGENTE) -> Convenio:
        convenio = crear_convenio(gestor, codigo=f"HU35-{uuid4().hex[:12]}")
        convenio.estado = estado.value
        db.commit()
        db.refresh(convenio)
        return convenio

    return _crear


# ---- CA-01: registrar una actividad -----------------------------------------


@pytest.mark.parametrize(
    "estado", [EstadoConvenio.VIGENTE, EstadoConvenio.POR_VENCER]
)
def test_ca01_registra_actividad_asociada_al_convenio(
    client, db: Session, gestor, crear_convenio_en_estado, estado
) -> None:
    convenio = crear_convenio_en_estado(estado)

    respuesta = client.post(url_actividades(convenio.id), json=ACTIVIDAD_EJEMPLO)

    assert respuesta.status_code == 201
    assert respuesta.json()["convenio_id"] == convenio.id
    guardada = db.get(ActividadUtilizacion, respuesta.json()["id"])
    assert guardada is not None
    assert guardada.convenio_id == convenio.id


# ---- CA-02: conservar la información registrada -----------------------------


def test_ca02_conserva_los_datos_registrados(
    client, db: Session, gestor, crear_convenio_en_estado
) -> None:
    convenio = crear_convenio_en_estado()

    cuerpo = client.post(
        url_actividades(convenio.id), json=ACTIVIDAD_EJEMPLO
    ).json()

    guardada = db.get(ActividadUtilizacion, cuerpo["id"])
    assert guardada.fecha == date(2026, 9, 15)
    assert guardada.actividad == ACTIVIDAD_EJEMPLO["actividad"]
    assert guardada.descripcion == ACTIVIDAD_EJEMPLO["descripcion"]
    assert guardada.responsable == ACTIVIDAD_EJEMPLO["responsable"]
    assert guardada.observaciones == ACTIVIDAD_EJEMPLO["observaciones"]
    assert guardada.registrado_por_id == gestor.id
    assert guardada.creado_en is not None
    assert cuerpo["registrado_por_id"] == gestor.id
    assert cuerpo["creado_en"] is not None


@pytest.mark.parametrize("observaciones", [None, "", "   "])
def test_ca02_observaciones_es_opcional(
    client, gestor, crear_convenio_en_estado, observaciones
) -> None:
    convenio = crear_convenio_en_estado()
    datos = {**ACTIVIDAD_EJEMPLO, "observaciones": observaciones}

    respuesta = client.post(url_actividades(convenio.id), json=datos)

    assert respuesta.status_code == 201
    assert respuesta.json()["observaciones"] is None


def test_ca02_observaciones_puede_omitirse(
    client, gestor, crear_convenio_en_estado
) -> None:
    convenio = crear_convenio_en_estado()
    datos = {k: v for k, v in ACTIVIDAD_EJEMPLO.items() if k != "observaciones"}

    respuesta = client.post(url_actividades(convenio.id), json=datos)

    assert respuesta.status_code == 201


@pytest.mark.parametrize(
    "campo", ["fecha", "actividad", "descripcion", "responsable"]
)
def test_ca02_rechaza_campos_obligatorios_faltantes(
    client, db: Session, gestor, crear_convenio_en_estado, campo
) -> None:
    convenio = crear_convenio_en_estado()
    datos = {k: v for k, v in ACTIVIDAD_EJEMPLO.items() if k != campo}

    respuesta = client.post(url_actividades(convenio.id), json=datos)

    assert respuesta.status_code == 422
    assert db.scalars(select(ActividadUtilizacion)).all() == []


@pytest.mark.parametrize("campo", ["actividad", "descripcion", "responsable"])
def test_ca02_rechaza_textos_obligatorios_vacios(
    client, gestor, crear_convenio_en_estado, campo
) -> None:
    convenio = crear_convenio_en_estado()
    datos = {**ACTIVIDAD_EJEMPLO, campo: "   "}

    respuesta = client.post(url_actividades(convenio.id), json=datos)

    assert respuesta.status_code == 422


# ---- CA-03: consultar actividades del convenio ------------------------------


def test_ca03_lista_actividades_del_convenio_ordenadas(
    client, gestor, crear_convenio_en_estado
) -> None:
    convenio = crear_convenio_en_estado()
    otro = crear_convenio_en_estado()
    antigua = client.post(
        url_actividades(convenio.id), json={**ACTIVIDAD_EJEMPLO, "fecha": "2026-03-01"}
    ).json()
    reciente = client.post(url_actividades(convenio.id), json=ACTIVIDAD_EJEMPLO).json()
    mismo_dia = client.post(url_actividades(convenio.id), json=ACTIVIDAD_EJEMPLO).json()
    client.post(url_actividades(otro.id), json=ACTIVIDAD_EJEMPLO)

    respuesta = client.get(url_actividades(convenio.id))

    assert respuesta.status_code == 200
    assert [item["id"] for item in respuesta.json()] == [
        mismo_dia["id"],
        reciente["id"],
        antigua["id"],
    ]
    assert respuesta.json()[1] == reciente


# ---- CA-04: restringir el registro ------------------------------------------


@pytest.mark.parametrize(
    ("codigo_rol", "tipo_usuario"),
    [
        (CodigoRol.REVISOR_ORI, TipoUsuario.INTERNO),
        (CodigoRol.SOLICITANTE_INTERNO, TipoUsuario.INTERNO),
        (CodigoRol.SOLICITANTE_EXTERNO, TipoUsuario.EXTERNO),
    ],
)
def test_ca04_rol_sin_permiso_no_puede_registrar(
    client,
    db: Session,
    crear_usuario,
    entrar_como,
    crear_convenio_en_estado,
    codigo_rol,
    tipo_usuario,
) -> None:
    convenio = crear_convenio_en_estado()
    entrar_como(crear_usuario(codigo_rol, tipo_usuario))

    respuesta = client.post(url_actividades(convenio.id), json=ACTIVIDAD_EJEMPLO)

    assert respuesta.status_code == 403
    assert db.scalars(select(ActividadUtilizacion)).all() == []


def test_ca04_sin_sesion_no_puede_registrar(
    client, gestor, crear_convenio_en_estado
) -> None:
    convenio = crear_convenio_en_estado()
    client.cookies.clear()

    respuesta = client.post(url_actividades(convenio.id), json=ACTIVIDAD_EJEMPLO)

    assert respuesta.status_code == 401


def test_ca04_administrador_puede_registrar(
    client, crear_usuario, entrar_como, crear_convenio_en_estado
) -> None:
    convenio = crear_convenio_en_estado()
    administrador = crear_usuario(CodigoRol.ADMINISTRADOR_ORI, TipoUsuario.INTERNO)
    entrar_como(administrador)

    respuesta = client.post(url_actividades(convenio.id), json=ACTIVIDAD_EJEMPLO)

    assert respuesta.status_code == 201
    assert respuesta.json()["registrado_por_id"] == administrador.id


@pytest.mark.parametrize(
    "estado",
    [
        EstadoConvenio.EN_TRAMITE,
        EstadoConvenio.VENCIDO,
        EstadoConvenio.RENOVADO,
        EstadoConvenio.FINALIZADO,
        EstadoConvenio.CANCELADO,
    ],
)
def test_ca04_rechaza_registro_en_convenio_no_activo(
    client, db: Session, gestor, crear_convenio_en_estado, estado
) -> None:
    convenio = crear_convenio_en_estado(estado)

    respuesta = client.post(url_actividades(convenio.id), json=ACTIVIDAD_EJEMPLO)

    assert respuesta.status_code == 409
    assert "vigentes o por vencer" in respuesta.json()["detail"]
    assert db.scalars(select(ActividadUtilizacion)).all() == []


def test_convenio_inexistente_responde_404(client, gestor) -> None:
    assert client.post(url_actividades(999_999), json=ACTIVIDAD_EJEMPLO).status_code == 404
    assert client.get(url_actividades(999_999)).status_code == 404


# ---- CA-05: disponibles para consumo externo --------------------------------


def test_ca05_convenio_sin_actividades_devuelve_lista_vacia(
    client, gestor, crear_convenio_en_estado
) -> None:
    convenio = crear_convenio_en_estado()

    respuesta = client.get(url_actividades(convenio.id))

    assert respuesta.status_code == 200
    assert respuesta.json() == []


def test_ca05_listado_refleja_registro_inmediatamente(
    client, gestor, crear_convenio_en_estado
) -> None:
    convenio = crear_convenio_en_estado()
    assert client.get(url_actividades(convenio.id)).json() == []

    creada = client.post(url_actividades(convenio.id), json=ACTIVIDAD_EJEMPLO).json()

    assert client.get(url_actividades(convenio.id)).json() == [creada]


def test_ca05_actividades_siguen_disponibles_si_el_convenio_deja_de_estar_activo(
    client, db: Session, gestor, crear_convenio_en_estado
) -> None:
    convenio = crear_convenio_en_estado()
    creada = client.post(url_actividades(convenio.id), json=ACTIVIDAD_EJEMPLO).json()
    convenio.estado = EstadoConvenio.VENCIDO.value
    db.commit()

    respuesta = client.get(url_actividades(convenio.id))

    assert respuesta.status_code == 200
    assert respuesta.json() == [creada]


def test_ca05_servicio_lista_actividades_sin_volver_a_registrarlas(
    client, db: Session, gestor, crear_convenio_en_estado
) -> None:
    convenio = crear_convenio_en_estado()
    creada = client.post(url_actividades(convenio.id), json=ACTIVIDAD_EJEMPLO).json()

    actividades = ServicioActividadesUtilizacion(db).listar(convenio.id, gestor)

    assert [actividad.id for actividad in actividades] == [creada["id"]]
    assert db.scalar(
        select(ActividadUtilizacion.id).where(
            ActividadUtilizacion.convenio_id == convenio.id
        )
    ) == creada["id"]


def test_ca05_renovacion_no_hereda_actividades_del_origen(
    client, db: Session, gestor, crear_convenio_en_estado
) -> None:
    origen = crear_convenio_en_estado()
    client.post(url_actividades(origen.id), json=ACTIVIDAD_EJEMPLO)
    renovacion = crear_convenio_en_estado()
    renovacion.convenio_origen_id = origen.id
    db.commit()

    assert len(client.get(url_actividades(origen.id)).json()) == 1
    assert client.get(url_actividades(renovacion.id)).json() == []
