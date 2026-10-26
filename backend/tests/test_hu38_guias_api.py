import pytest
from sqlalchemy import func, select

from backend.core.roles import CodigoRol, TipoUsuario
from backend.models.enums import CodigoGuia, EstadoGuia
from backend.models.estado_guia_usuario import EstadoGuiaUsuario
from backend.services.guias import ServicioGuias

URL_GUIAS = "/api/guias"
URL_ONBOARDING = f"{URL_GUIAS}/{CodigoGuia.ONBOARDING_INICIAL.value}"
URL_RADICACION = f"{URL_GUIAS}/{CodigoGuia.GUIA_RADICACION.value}"


@pytest.fixture
def solicitante(crear_usuario, entrar_como):
    usuario = crear_usuario(CodigoRol.SOLICITANTE_EXTERNO, TipoUsuario.EXTERNO)
    entrar_como(usuario)
    return usuario


def _guardar(client, url, estado, version=1):
    return client.put(url, json={"estado": estado, "version": version})


def _filas(db, usuario, guia=CodigoGuia.ONBOARDING_INICIAL):
    return db.scalar(
        select(func.count()).select_from(EstadoGuiaUsuario).where(
            EstadoGuiaUsuario.usuario_id == usuario.id,
            EstadoGuiaUsuario.guia == guia.value,
        )
    )


# --- Autenticación y acceso ---------------------------------------------------


@pytest.mark.parametrize(
    ("metodo", "url"),
    [("get", URL_GUIAS), ("get", URL_ONBOARDING), ("put", URL_ONBOARDING)],
)
def test_requiere_autenticacion(client, metodo, url):
    if metodo == "put":
        respuesta = _guardar(client, url, "COMPLETADO")
    else:
        respuesta = client.get(url)
    assert respuesta.status_code == 401


@pytest.mark.parametrize("rol", list(CodigoRol))
def test_cualquier_rol_autenticado_gestiona_sus_guias(
    client, crear_usuario, entrar_como, rol
):
    entrar_como(crear_usuario(rol))
    assert client.get(URL_ONBOARDING).status_code == 200
    assert _guardar(client, URL_ONBOARDING, "OMITIDO").status_code == 200


def test_guia_desconocida_se_rechaza(client, solicitante):
    assert client.get(f"{URL_GUIAS}/GUIA_INVENTADA").status_code == 422
    assert _guardar(client, f"{URL_GUIAS}/GUIA_INVENTADA", "COMPLETADO").status_code == 422


# --- Consulta (RN-03) ---------------------------------------------------------


def test_sin_registro_todas_las_guias_estan_pendientes(client, solicitante):
    respuesta = client.get(URL_GUIAS)

    assert respuesta.status_code == 200
    cuerpo = {guia["guia"]: guia for guia in respuesta.json()}
    assert set(cuerpo) == {guia.value for guia in CodigoGuia}
    for guia in cuerpo.values():
        assert guia["estado"] == EstadoGuia.PENDIENTE.value
        assert guia["version"] is None
        assert guia["actualizado_en"] is None


def test_consulta_una_guia_pendiente(client, solicitante):
    cuerpo = client.get(URL_ONBOARDING).json()
    assert cuerpo == {
        "guia": "ONBOARDING_INICIAL",
        "estado": "PENDIENTE",
        "version": None,
        "actualizado_en": None,
    }


# --- Actualización y transiciones (CA-07, CA-08, RN-04) -----------------------


@pytest.mark.parametrize("estado", ["COMPLETADO", "OMITIDO"])
def test_guarda_estado_final_desde_pendiente(client, db, solicitante, estado):
    respuesta = _guardar(client, URL_ONBOARDING, estado, version=2)

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["estado"] == estado
    assert cuerpo["version"] == 2
    assert cuerpo["actualizado_en"] is not None
    assert client.get(URL_ONBOARDING).json()["estado"] == estado
    assert _filas(db, solicitante) == 1


def test_no_admite_guardar_pendiente(client, solicitante):
    assert _guardar(client, URL_ONBOARDING, "PENDIENTE").status_code == 422


@pytest.mark.parametrize(
    "cuerpo",
    [
        {"estado": "COMPLETADO"},
        {"estado": "COMPLETADO", "version": 0},
        {"estado": "COMPLETADO", "version": 1, "usuario_id": 1},
        {"estado": "INVENTADO", "version": 1},
    ],
)
def test_cuerpo_invalido_se_rechaza(client, solicitante, cuerpo):
    assert client.put(URL_ONBOARDING, json=cuerpo).status_code == 422


def test_completar_una_guia_omitida_la_marca_completada(client, solicitante):
    _guardar(client, URL_ONBOARDING, "OMITIDO", version=1)

    cuerpo = _guardar(client, URL_ONBOARDING, "COMPLETADO", version=1).json()

    assert cuerpo["estado"] == "COMPLETADO"


def test_cerrar_una_reproduccion_no_modifica_una_guia_completada(client, db, solicitante):
    _guardar(client, URL_ONBOARDING, "COMPLETADO", version=1)

    respuesta = _guardar(client, URL_ONBOARDING, "OMITIDO", version=1)

    assert respuesta.status_code == 200
    assert respuesta.json()["estado"] == "COMPLETADO"
    assert _filas(db, solicitante) == 1


@pytest.mark.parametrize("estado", ["COMPLETADO", "OMITIDO"])
def test_repetir_el_mismo_estado_no_crea_registros(client, db, solicitante, estado):
    primero = _guardar(client, URL_ONBOARDING, estado).json()
    segundo = _guardar(client, URL_ONBOARDING, estado).json()

    assert segundo == primero
    assert _filas(db, solicitante) == 1


# --- Independencia y aislamiento (RN-05, RN-06, RN-07) ------------------------


def test_cada_guia_conserva_su_estado(client, solicitante):
    _guardar(client, URL_ONBOARDING, "COMPLETADO")
    _guardar(client, URL_RADICACION, "OMITIDO")

    cuerpo = {guia["guia"]: guia["estado"] for guia in client.get(URL_GUIAS).json()}

    assert cuerpo == {"ONBOARDING_INICIAL": "COMPLETADO", "GUIA_RADICACION": "OMITIDO"}


def test_un_usuario_no_ve_ni_modifica_el_estado_de_otro(
    client, crear_usuario, entrar_como
):
    primero = crear_usuario(CodigoRol.SOLICITANTE_EXTERNO, TipoUsuario.EXTERNO)
    segundo = crear_usuario(CodigoRol.SOLICITANTE_INTERNO, TipoUsuario.INTERNO)
    entrar_como(primero)
    _guardar(client, URL_ONBOARDING, "COMPLETADO")

    entrar_como(segundo)
    assert client.get(URL_ONBOARDING).json()["estado"] == "PENDIENTE"
    _guardar(client, URL_ONBOARDING, "OMITIDO")

    entrar_como(primero)
    assert client.get(URL_ONBOARDING).json()["estado"] == "COMPLETADO"


def test_el_estado_se_conserva_entre_sesiones(client, solicitante, entrar_como):
    _guardar(client, URL_ONBOARDING, "OMITIDO")

    entrar_como(solicitante)  # nueva sesión del mismo usuario

    assert client.get(URL_ONBOARDING).json()["estado"] == "OMITIDO"


# --- Concurrencia ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("guardado", "solicitado", "esperado"),
    [
        ("OMITIDO", "COMPLETADO", "COMPLETADO"),
        ("COMPLETADO", "OMITIDO", "COMPLETADO"),
    ],
)
def test_si_otra_peticion_registra_primero_se_aplica_la_transicion(
    db, crear_usuario, monkeypatch, guardado, solicitado, esperado
):
    usuario = crear_usuario(CodigoRol.SOLICITANTE_EXTERNO, TipoUsuario.EXTERNO)
    db.add(
        EstadoGuiaUsuario(
            usuario_id=usuario.id,
            guia=CodigoGuia.ONBOARDING_INICIAL.value,
            estado=guardado,
            version=1,
        )
    )
    db.commit()
    servicio = ServicioGuias(db)
    original = servicio._registro
    llamadas = []

    def _registro_tardio(*args, **kwargs):
        # La primera lectura no ve la fila: simula que la otra petición la
        # insertó justo después.
        llamadas.append(1)
        return None if len(llamadas) == 1 else original(*args, **kwargs)

    monkeypatch.setattr(servicio, "_registro", _registro_tardio)

    resultado = servicio.registrar(
        usuario, CodigoGuia.ONBOARDING_INICIAL, EstadoGuia(solicitado), 1
    )

    assert resultado.estado == esperado
    assert _filas(db, usuario) == 1
