from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.core.roles import CodigoRol, TipoUsuario
from backend.core.security import verificar_contrasena
from backend.core.unidades_organizacionales import TipoUnidad
from backend.models.unidad_organizacional import UnidadOrganizacional
from backend.models.usuario import Usuario
from backend.schemas.usuario import UsuarioActualizar
from backend.services.sesiones import RepositorioSesionesMemoria
from backend.services.usuarios import ServicioUsuarios


def _datos_usuario(
    correo: str | None = None,
    rol: CodigoRol = CodigoRol.GESTOR_ORI,
    tipo_usuario: TipoUsuario = TipoUsuario.INTERNO,
) -> dict[str, object]:
    return {
        "correo": correo or f"nuevo-{uuid4().hex}@example.com",
        "contrasena": "ClaveNueva123!",
        "nombre_completo": "Usuario nuevo",
        "rol": rol.value,
        "tipo_usuario": tipo_usuario.value,
        "documento_identidad": "123456789",
        "telefono": "3001234567",
        "cargo": "Profesional",
    }


def _autenticar_admin(client: TestClient, crear_usuario, entrar_como):
    admin = crear_usuario(CodigoRol.ADMINISTRADOR_ORI)
    entrar_como(admin)
    return admin


def test_listar_y_obtener_usuario(
    client: TestClient,
    crear_usuario,
    entrar_como,
) -> None:
    admin = _autenticar_admin(client, crear_usuario, entrar_como)
    otro = crear_usuario()

    listado = client.get("/api/usuarios")
    detalle = client.get(f"/api/usuarios/{otro.id}")

    assert listado.status_code == 200
    assert {usuario["id"] for usuario in listado.json()} >= {admin.id, otro.id}
    assert detalle.status_code == 200
    assert detalle.json()["correo"] == otro.correo


@pytest.mark.parametrize(
    ("rol", "tipo"),
    [
        (CodigoRol.GESTOR_ORI, TipoUsuario.INTERNO),
        (CodigoRol.REVISOR_ORI, TipoUsuario.INTERNO),
        (CodigoRol.SOLICITANTE_INTERNO, TipoUsuario.INTERNO),
        (CodigoRol.SOLICITANTE_EXTERNO, TipoUsuario.EXTERNO),
    ],
)
def test_usuarios_sin_permisos_no_acceden_a_endpoints_administrativos(
    rol: CodigoRol,
    tipo: TipoUsuario,
    client: TestClient,
    crear_usuario,
    entrar_como,
) -> None:
    objetivo = crear_usuario(CodigoRol.ADMINISTRADOR_ORI)
    actor = crear_usuario(rol, tipo)
    entrar_como(actor)

    respuestas = [
        client.get("/api/usuarios"),
        client.get(f"/api/usuarios/{objetivo.id}"),
        client.post("/api/usuarios", json=_datos_usuario()),
        client.patch(
            f"/api/usuarios/{objetivo.id}",
            json={"nombre_completo": "Cambio no autorizado"},
        ),
        client.patch(
            f"/api/usuarios/{objetivo.id}/rol",
            json={"rol": CodigoRol.GESTOR_ORI.value},
        ),
        client.patch(
            f"/api/usuarios/{objetivo.id}/estado",
            json={"activo": False},
        ),
    ]

    assert all(respuesta.status_code == 403 for respuesta in respuestas)


def test_listado_y_detalle_incluyen_usuarios_ori_y_solicitantes(
    client: TestClient,
    crear_usuario,
    entrar_como,
) -> None:
    admin = _autenticar_admin(client, crear_usuario, entrar_como)
    gestor = crear_usuario()
    solicitante_interno = crear_usuario(
        CodigoRol.SOLICITANTE_INTERNO,
        TipoUsuario.INTERNO,
    )
    solicitante_externo = crear_usuario(
        CodigoRol.SOLICITANTE_EXTERNO,
        TipoUsuario.EXTERNO,
    )

    listado = client.get("/api/usuarios")

    assert listado.status_code == 200
    ids = {usuario["id"] for usuario in listado.json()}
    assert ids >= {
        admin.id,
        gestor.id,
        solicitante_interno.id,
        solicitante_externo.id,
    }
    for solicitante in (solicitante_interno, solicitante_externo):
        detalle = client.get(f"/api/usuarios/{solicitante.id}")
        assert detalle.status_code == 200
        assert detalle.json()["id"] == solicitante.id


@pytest.mark.parametrize(
    ("rol", "tipo"),
    [
        (CodigoRol.SOLICITANTE_INTERNO, TipoUsuario.INTERNO),
        (CodigoRol.SOLICITANTE_EXTERNO, TipoUsuario.EXTERNO),
    ],
)
def test_admin_edita_datos_generales_de_solicitantes(
    rol: CodigoRol,
    tipo: TipoUsuario,
    client: TestClient,
    crear_usuario,
    entrar_como,
    db: Session,
) -> None:
    _autenticar_admin(client, crear_usuario, entrar_como)
    solicitante = crear_usuario(rol, tipo)

    respuesta = client.patch(
        f"/api/usuarios/{solicitante.id}",
        json={
            "nombre_completo": "Solicitante actualizado",
            "telefono": "3151234567",
            "cargo": "Representante",
        },
    )

    assert respuesta.status_code == 200
    assert respuesta.json()["nombre_completo"] == "Solicitante actualizado"
    assert respuesta.json()["telefono"] == "3151234567"
    assert respuesta.json()["cargo"] == "Representante"
    db.refresh(solicitante)
    assert solicitante.nombre_completo == "Solicitante actualizado"
    assert solicitante.telefono == "3151234567"


@pytest.mark.parametrize(
    ("rol", "tipo"),
    [
        (CodigoRol.SOLICITANTE_INTERNO, TipoUsuario.INTERNO),
        (CodigoRol.SOLICITANTE_EXTERNO, TipoUsuario.EXTERNO),
    ],
)
def test_admin_desactiva_y_reactiva_solicitantes_e_invalida_sesiones(
    rol: CodigoRol,
    tipo: TipoUsuario,
    client: TestClient,
    crear_usuario,
    entrar_como,
    sesiones: RepositorioSesionesMemoria,
) -> None:
    admin = crear_usuario(CodigoRol.ADMINISTRADOR_ORI)
    solicitante = crear_usuario(rol, tipo)
    token_solicitante = entrar_como(solicitante)
    entrar_como(admin)

    desactivar = client.patch(
        f"/api/usuarios/{solicitante.id}/estado",
        json={"activo": False},
    )
    reactivar = client.patch(
        f"/api/usuarios/{solicitante.id}/estado",
        json={"activo": True},
    )

    assert desactivar.status_code == 200
    assert desactivar.json()["activo"] is False
    assert sesiones.obtener_por_token(token_solicitante) is None
    assert reactivar.status_code == 200
    assert reactivar.json()["activo"] is True


@pytest.mark.parametrize(
    ("rol_actual", "tipo"),
    [
        (CodigoRol.SOLICITANTE_INTERNO, TipoUsuario.INTERNO),
        (CodigoRol.SOLICITANTE_EXTERNO, TipoUsuario.EXTERNO),
    ],
)
@pytest.mark.parametrize(
    "rol_destino",
    [CodigoRol.ADMINISTRADOR_ORI, CodigoRol.GESTOR_ORI, CodigoRol.REVISOR_ORI],
)
def test_admin_no_puede_cambiar_rol_de_solicitantes(
    rol_actual: CodigoRol,
    tipo: TipoUsuario,
    rol_destino: CodigoRol,
    client: TestClient,
    crear_usuario,
    entrar_como,
    db: Session,
) -> None:
    _autenticar_admin(client, crear_usuario, entrar_como)
    solicitante = crear_usuario(rol_actual, tipo)

    respuesta = client.patch(
        f"/api/usuarios/{solicitante.id}/rol",
        json={"rol": rol_destino.value},
    )

    assert respuesta.status_code == 422
    assert respuesta.json()["detail"] == (
        "El rol de los solicitantes no se administra desde este módulo"
    )
    db.refresh(solicitante)
    assert solicitante.rol.codigo == rol_actual


@pytest.mark.parametrize(
    ("campo", "valor", "mensaje"),
    [
        (
            "correo",
            "otro-dominio@example.com",
            "El correo de los solicitantes no se administra desde este módulo",
        ),
        (
            "contrasena",
            "ClaveDistinta123!",
            "La contraseña de los solicitantes se gestiona mediante recuperación de acceso",
        ),
    ],
)
def test_edicion_solicitante_bloquea_correo_y_contrasena(
    campo: str,
    valor: str,
    mensaje: str,
    client: TestClient,
    crear_usuario,
    entrar_como,
    db: Session,
) -> None:
    _autenticar_admin(client, crear_usuario, entrar_como)
    solicitante = crear_usuario(
        CodigoRol.SOLICITANTE_INTERNO,
        TipoUsuario.INTERNO,
        correo="solicitante@usbcali.edu.co",
    )
    correo_anterior = solicitante.correo
    hash_anterior = solicitante.hash_contrasena

    respuesta = client.patch(
        f"/api/usuarios/{solicitante.id}",
        json={campo: valor},
    )

    assert respuesta.status_code == 422
    assert respuesta.json()["detail"] == mensaje
    db.refresh(solicitante)
    assert solicitante.correo == correo_anterior
    assert solicitante.hash_contrasena == hash_anterior


@pytest.mark.parametrize(
    ("campo", "valor"),
    [
        ("documento_identidad", "DOC-NUEVO"),
        ("entidad_externa", "Entidad nueva"),
    ],
)
def test_solicitante_interno_rechaza_campos_de_solicitante_externo(
    campo: str,
    valor: str,
    client: TestClient,
    crear_usuario,
    entrar_como,
    db: Session,
) -> None:
    _autenticar_admin(client, crear_usuario, entrar_como)
    solicitante = crear_usuario(
        CodigoRol.SOLICITANTE_INTERNO,
        TipoUsuario.INTERNO,
    )
    solicitante.documento_identidad = "DOC-LEGACY"
    solicitante.entidad_externa = "Entidad legacy"
    db.commit()

    respuesta = client.patch(
        f"/api/usuarios/{solicitante.id}",
        json={campo: valor},
    )

    assert respuesta.status_code == 422
    assert campo in respuesta.json()["detail"]
    db.refresh(solicitante)
    assert solicitante.documento_identidad == "DOC-LEGACY"
    assert solicitante.entidad_externa == "Entidad legacy"


def test_solicitante_externo_rechaza_unidad_organizacional(
    client: TestClient,
    crear_usuario,
    entrar_como,
    db: Session,
) -> None:
    _autenticar_admin(client, crear_usuario, entrar_como)
    unidad = UnidadOrganizacional(
        codigo=f"USR-{uuid4().hex}",
        nombre="Unidad legacy solicitante externo",
        tipo=TipoUnidad.FACULTAD.value,
        activa=True,
    )
    db.add(unidad)
    db.commit()
    solicitante = crear_usuario(
        CodigoRol.SOLICITANTE_EXTERNO,
        TipoUsuario.EXTERNO,
    )
    solicitante.unidad_organizacional_id = unidad.id
    db.commit()

    respuesta = client.patch(
        f"/api/usuarios/{solicitante.id}",
        json={"unidad_organizacional_id": None},
    )

    assert respuesta.status_code == 422
    assert "unidad_organizacional_id" in respuesta.json()["detail"]
    db.refresh(solicitante)
    assert solicitante.unidad_organizacional_id == unidad.id


def test_crear_usuario_y_no_exponer_hash(
    client: TestClient,
    crear_usuario,
    entrar_como,
) -> None:
    _autenticar_admin(client, crear_usuario, entrar_como)

    respuesta = client.post("/api/usuarios", json=_datos_usuario())

    assert respuesta.status_code == 201
    cuerpo = respuesta.json()
    assert cuerpo["rol"]["codigo"] == CodigoRol.GESTOR_ORI
    assert cuerpo["tipo_usuario"] == TipoUsuario.INTERNO
    assert cuerpo["activo"] is True
    serializado = respuesta.text
    assert "hash_contrasena" not in serializado
    assert "contrasena" not in serializado


@pytest.mark.parametrize(
    "campo",
    ["correo", "contrasena", "nombre_completo", "rol"],
)
def test_creacion_rechaza_campos_obligatorios_ausentes(
    campo: str,
    client: TestClient,
    crear_usuario,
    entrar_como,
) -> None:
    _autenticar_admin(client, crear_usuario, entrar_como)
    datos = _datos_usuario()
    del datos[campo]

    respuesta = client.post("/api/usuarios", json=datos)

    assert respuesta.status_code == 422


@pytest.mark.parametrize(
    "contrasena",
    [
        "Corta1!",
        "clavesegura123!",
        "CLAVESEGURA123!",
        "ClaveSegura!",
        "ClaveSegura123",
        "Clave Segura123",
    ],
)
def test_creacion_exige_politica_completa_contrasena(
    client: TestClient,
    crear_usuario,
    entrar_como,
    contrasena: str,
) -> None:
    _autenticar_admin(client, crear_usuario, entrar_como)
    datos = {**_datos_usuario(), "contrasena": contrasena}

    assert client.post("/api/usuarios", json=datos).status_code == 422


def test_password_creado_permite_login(
    client: TestClient,
    crear_usuario,
    entrar_como,
) -> None:
    _autenticar_admin(client, crear_usuario, entrar_como)
    datos = _datos_usuario("creado-login@example.com")
    assert client.post("/api/usuarios", json=datos).status_code == 201
    client.cookies.clear()

    login = client.post(
        "/api/auth/login",
        json={"correo": datos["correo"], "contrasena": datos["contrasena"]},
    )

    assert login.status_code == 200


def test_editar_datos_y_contrasena(
    client: TestClient,
    crear_usuario,
    entrar_como,
) -> None:
    _autenticar_admin(client, crear_usuario, entrar_como)
    usuario = crear_usuario(correo="editar@example.com")

    respuesta = client.patch(
        f"/api/usuarios/{usuario.id}",
        json={
            "correo": "editado@example.com",
            "contrasena": "ClaveEditada123!",
            "telefono": "3110000000",
            "entidad_externa": "Entidad",
        },
    )

    assert respuesta.status_code == 200
    assert respuesta.json()["telefono"] == "3110000000"
    client.cookies.clear()
    login = client.post(
        "/api/auth/login",
        json={
            "correo": "editado@example.com",
            "contrasena": "ClaveEditada123!",
        },
    )
    assert login.status_code == 200


def test_cambio_contrasena_debil_no_actualiza_usuario(
    client: TestClient,
    crear_usuario,
    entrar_como,
    db: Session,
) -> None:
    _autenticar_admin(client, crear_usuario, entrar_como)
    usuario = crear_usuario(correo="debil-edicion@example.com")
    hash_anterior = usuario.hash_contrasena
    telefono_anterior = usuario.telefono

    respuesta = client.patch(
        f"/api/usuarios/{usuario.id}",
        json={"contrasena": "clavesegura123!", "telefono": "3110000000"},
    )

    assert respuesta.status_code == 422
    db.refresh(usuario)
    assert usuario.hash_contrasena == hash_anterior
    assert usuario.telefono == telefono_anterior


def test_contrasena_igual_rechaza_todo_el_patch_y_conserva_sesion(
    client: TestClient,
    crear_usuario,
    entrar_como,
    sesiones: RepositorioSesionesMemoria,
    db: Session,
) -> None:
    admin = crear_usuario(CodigoRol.ADMINISTRADOR_ORI)
    usuario = crear_usuario(correo="misma-clave@example.com")
    token_usuario = entrar_como(usuario)
    hash_anterior = usuario.hash_contrasena
    telefono_anterior = usuario.telefono
    entrar_como(admin)

    respuesta = client.patch(
        f"/api/usuarios/{usuario.id}",
        json={"telefono": "3110000000", "contrasena": "ClaveSegura123!"},
    )

    assert respuesta.status_code == 409
    assert respuesta.json()["detail"] == (
        "La nueva contraseña debe ser diferente a la actual"
    )
    db.refresh(usuario)
    assert usuario.hash_contrasena == hash_anterior
    assert usuario.telefono == telefono_anterior
    assert verificar_contrasena("ClaveSegura123!", usuario.hash_contrasena)
    assert sesiones.obtener_por_token(token_usuario) is not None
    client.cookies.set("session_id", token_usuario)
    assert client.get("/api/auth/me").status_code == 200
    client.cookies.clear()
    assert client.post(
        "/api/auth/login",
        json={"correo": usuario.correo, "contrasena": "ClaveSegura123!"},
    ).status_code == 200


def test_cambio_contrasena_invalida_sesion_y_credencial_anterior(
    client: TestClient,
    crear_usuario,
    entrar_como,
    sesiones: RepositorioSesionesMemoria,
) -> None:
    admin = crear_usuario(CodigoRol.ADMINISTRADOR_ORI)
    usuario = crear_usuario(correo="cambio-clave@example.com")
    token_usuario = entrar_como(usuario)
    entrar_como(admin)

    respuesta = client.patch(
        f"/api/usuarios/{usuario.id}",
        json={"contrasena": "ClaveDistinta123!"},
    )

    assert respuesta.status_code == 200
    assert sesiones.obtener_por_token(token_usuario) is None
    client.cookies.set("session_id", token_usuario)
    assert client.get("/api/auth/me").status_code == 401
    client.cookies.clear()
    assert client.post(
        "/api/auth/login",
        json={"correo": usuario.correo, "contrasena": "ClaveSegura123!"},
    ).status_code == 401
    assert client.post(
        "/api/auth/login",
        json={"correo": usuario.correo, "contrasena": "ClaveDistinta123!"},
    ).status_code == 200


def test_cambio_contrasena_invalida_todas_las_sesiones(
    client: TestClient,
    crear_usuario,
    entrar_como,
    sesiones: RepositorioSesionesMemoria,
) -> None:
    admin = crear_usuario(CodigoRol.ADMINISTRADOR_ORI)
    usuario = crear_usuario()
    primer_token = entrar_como(usuario)
    segundo_token = entrar_como(usuario)
    entrar_como(admin)

    respuesta = client.patch(
        f"/api/usuarios/{usuario.id}",
        json={"contrasena": "ClaveDistinta123!"},
    )

    assert respuesta.status_code == 200
    assert sesiones.obtener_por_token(primer_token) is None
    assert sesiones.obtener_por_token(segundo_token) is None


def test_admin_cambia_su_contrasena_e_invalida_su_sesion(
    client: TestClient,
    crear_usuario,
    entrar_como,
    sesiones: RepositorioSesionesMemoria,
) -> None:
    admin = crear_usuario(CodigoRol.ADMINISTRADOR_ORI)
    token = entrar_como(admin)

    respuesta = client.patch(
        f"/api/usuarios/{admin.id}",
        json={"contrasena": "ClaveDistinta123!"},
    )

    assert respuesta.status_code == 200
    assert sesiones.obtener_por_token(token) is None
    assert client.get("/api/auth/me").status_code == 401
    client.cookies.clear()
    assert client.post(
        "/api/auth/login",
        json={"correo": admin.correo, "contrasena": "ClaveDistinta123!"},
    ).status_code == 200


def test_fallo_al_guardar_contrasena_conserva_sesiones(
    client: TestClient,
    crear_usuario,
    entrar_como,
    sesiones: RepositorioSesionesMemoria,
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    usuario = crear_usuario()
    token = entrar_como(usuario)
    hash_anterior = usuario.hash_contrasena

    def fallar_commit() -> None:
        raise RuntimeError("Fallo de persistencia simulado")

    with monkeypatch.context() as parche:
        parche.setattr(db, "commit", fallar_commit)
        with pytest.raises(RuntimeError, match="Fallo de persistencia simulado"):
            ServicioUsuarios(db, sesiones).actualizar(
                usuario.id,
                UsuarioActualizar(contrasena="ClaveDistinta123!"),
            )

    db.rollback()
    db.refresh(usuario)
    assert usuario.hash_contrasena == hash_anterior
    assert sesiones.obtener_por_token(token) is not None
    assert client.get("/api/auth/me").status_code == 200


def test_edicion_parcial_conserva_campos_no_enviados(
    client: TestClient,
    crear_usuario,
    entrar_como,
) -> None:
    _autenticar_admin(client, crear_usuario, entrar_como)
    usuario = crear_usuario(correo="parcial@example.com")
    datos_antes = client.get(f"/api/usuarios/{usuario.id}").json()

    respuesta = client.patch(
        f"/api/usuarios/{usuario.id}",
        json={"cargo": "Coordinador"},
    )

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["cargo"] == "Coordinador"
    for campo in (
        "correo",
        "nombre_completo",
        "documento_identidad",
        "telefono",
        "tipo_usuario",
        "entidad_externa",
        "activo",
        "rol",
        "unidad_organizacional_id",
    ):
        assert cuerpo[campo] == datos_antes[campo]


def test_edicion_general_rechaza_rol_estado_y_tipo(
    client: TestClient,
    crear_usuario,
    entrar_como,
) -> None:
    _autenticar_admin(client, crear_usuario, entrar_como)
    usuario = crear_usuario()

    respuesta = client.patch(
        f"/api/usuarios/{usuario.id}",
        json={
            "rol": CodigoRol.ADMINISTRADOR_ORI.value,
            "activo": False,
            "tipo_usuario": TipoUsuario.EXTERNO.value,
        },
    )

    assert respuesta.status_code == 422


def test_cambiar_rol_persistido(
    client: TestClient,
    crear_usuario,
    entrar_como,
) -> None:
    _autenticar_admin(client, crear_usuario, entrar_como)
    usuario = crear_usuario(CodigoRol.GESTOR_ORI)

    respuesta = client.patch(
        f"/api/usuarios/{usuario.id}/rol",
        json={"rol": CodigoRol.REVISOR_ORI.value},
    )

    assert respuesta.status_code == 200
    assert respuesta.json()["rol"]["codigo"] == CodigoRol.REVISOR_ORI
    assert client.get(f"/api/usuarios/{usuario.id}").json()["rol"]["codigo"] == (
        CodigoRol.REVISOR_ORI
    )


def test_cambio_de_rol_aplica_a_sesion_existente(
    client: TestClient,
    crear_usuario,
    entrar_como,
) -> None:
    admin = crear_usuario(CodigoRol.ADMINISTRADOR_ORI)
    usuario = crear_usuario(CodigoRol.GESTOR_ORI)
    token_usuario = entrar_como(usuario)
    assert client.get("/api/usuarios").status_code == 403

    token_admin = entrar_como(admin)
    respuesta = client.patch(
        f"/api/usuarios/{usuario.id}/rol",
        json={"rol": CodigoRol.ADMINISTRADOR_ORI.value},
    )
    assert respuesta.status_code == 200

    client.cookies.set("session_id", token_usuario)
    assert client.get("/api/usuarios").status_code == 200

    client.cookies.set("session_id", token_admin)
    respuesta = client.patch(
        f"/api/usuarios/{usuario.id}/rol",
        json={"rol": CodigoRol.GESTOR_ORI.value},
    )
    assert respuesta.status_code == 200

    client.cookies.set("session_id", token_usuario)
    assert client.get("/api/usuarios").status_code == 403


def test_cambiar_estado_invalida_sesiones(
    client: TestClient,
    crear_usuario,
    entrar_como,
    sesiones: RepositorioSesionesMemoria,
) -> None:
    admin = crear_usuario(CodigoRol.ADMINISTRADOR_ORI)
    usuario = crear_usuario()
    token_usuario = entrar_como(usuario)
    entrar_como(admin)

    respuesta = client.patch(
        f"/api/usuarios/{usuario.id}/estado",
        json={"activo": False},
    )

    assert respuesta.status_code == 200
    assert respuesta.json()["activo"] is False
    assert sesiones.obtener_por_token(token_usuario) is None
    client.cookies.clear()
    login = client.post(
        "/api/auth/login",
        json={"correo": usuario.correo, "contrasena": "ClaveSegura123!"},
    )
    assert login.status_code == 403
    assert login.cookies.get("session_id") is None


def test_desactivar_usuario_ya_inactivo_responde_409(
    client: TestClient,
    crear_usuario,
    entrar_como,
) -> None:
    _autenticar_admin(client, crear_usuario, entrar_como)
    usuario = crear_usuario()

    primera = client.patch(
        f"/api/usuarios/{usuario.id}/estado",
        json={"activo": False},
    )
    segunda = client.patch(
        f"/api/usuarios/{usuario.id}/estado",
        json={"activo": False},
    )

    assert primera.status_code == 200
    assert segunda.status_code == 409
    assert segunda.json()["detail"] == "El usuario ya se encuentra inactivo"
    assert client.get(f"/api/usuarios/{usuario.id}").json()["activo"] is False


def test_correo_duplicado_responde_409(
    client: TestClient,
    crear_usuario,
    entrar_como,
) -> None:
    _autenticar_admin(client, crear_usuario, entrar_como)
    existente = crear_usuario(correo="duplicado@example.com")

    crear = client.post(
        "/api/usuarios",
        json=_datos_usuario(existente.correo),
    )
    otro = crear_usuario()
    editar = client.patch(
        f"/api/usuarios/{otro.id}",
        json={"correo": existente.correo},
    )

    assert crear.status_code == 409
    assert editar.status_code == 409
    assert crear.json()["detail"] == "Ya existe un usuario con ese correo"
    assert editar.json()["detail"] == "Ya existe un usuario con ese correo"


def test_usuario_inexistente_responde_404(
    client: TestClient,
    crear_usuario,
    entrar_como,
) -> None:
    _autenticar_admin(client, crear_usuario, entrar_como)

    assert client.get("/api/usuarios/2147483647").status_code == 404
    assert (
        client.patch(
            "/api/usuarios/2147483647/estado",
            json={"activo": False},
        ).status_code
        == 404
    )


def test_rol_inexistente_e_incompatibilidad_responden_422(
    client: TestClient,
    crear_usuario,
    entrar_como,
) -> None:
    _autenticar_admin(client, crear_usuario, entrar_como)

    inexistente = client.post(
        "/api/usuarios",
        json={**_datos_usuario(), "rol": "ROL_INEXISTENTE"},
    )
    incompatible = client.post(
        "/api/usuarios",
        json=_datos_usuario(
            rol=CodigoRol.SOLICITANTE_EXTERNO,
            tipo_usuario=TipoUsuario.INTERNO,
        ),
    )
    invitado = client.post(
        "/api/usuarios",
        json={**_datos_usuario(), "rol": "INVITADO"},
    )

    assert inexistente.status_code == 422
    assert incompatible.status_code == 422
    assert invitado.status_code == 422


def test_unidad_inexistente_responde_422(
    client: TestClient,
    crear_usuario,
    entrar_como,
) -> None:
    _autenticar_admin(client, crear_usuario, entrar_como)
    datos = {**_datos_usuario(), "unidad_organizacional_id": 2147483647}

    assert client.post("/api/usuarios", json=datos).status_code == 422


def test_admin_no_puede_cambiar_su_rol_ni_desactivarse(
    client: TestClient,
    crear_usuario,
    entrar_como,
) -> None:
    admin = _autenticar_admin(client, crear_usuario, entrar_como)

    rol = client.patch(
        f"/api/usuarios/{admin.id}/rol",
        json={"rol": CodigoRol.GESTOR_ORI.value},
    )
    estado = client.patch(
        f"/api/usuarios/{admin.id}/estado",
        json={"activo": False},
    )

    assert rol.status_code == 409
    assert estado.status_code == 409


def test_administracion_rechaza_creacion_de_usuario_externo(
    client: TestClient,
    crear_usuario,
    entrar_como,
) -> None:
    _autenticar_admin(client, crear_usuario, entrar_como)

    respuesta = client.post(
        "/api/usuarios",
        json=_datos_usuario(
            rol=CodigoRol.SOLICITANTE_EXTERNO,
            tipo_usuario=TipoUsuario.EXTERNO,
        ),
    )

    assert respuesta.status_code == 422
    assert respuesta.json()["detail"] == (
        "El módulo administrativo solo permite crear usuarios internos"
    )


def test_usuario_desactivado_conserva_identidad_y_ultimo_acceso(
    client: TestClient,
    crear_usuario,
    entrar_como,
    db: Session,
) -> None:
    admin = crear_usuario(CodigoRol.ADMINISTRADOR_ORI)
    usuario = crear_usuario(correo="trazabilidad@example.com")

    login = client.post(
        "/api/auth/login",
        json={"correo": usuario.correo, "contrasena": "ClaveSegura123!"},
    )
    assert login.status_code == 200

    entrar_como(admin)
    antes = client.get(f"/api/usuarios/{usuario.id}").json()
    assert antes["ultimo_acceso"] is not None

    desactivar = client.patch(
        f"/api/usuarios/{usuario.id}/estado",
        json={"activo": False},
    )
    despues = client.get(f"/api/usuarios/{usuario.id}")

    assert desactivar.status_code == 200
    assert despues.status_code == 200
    cuerpo = despues.json()
    assert cuerpo["id"] == antes["id"]
    assert cuerpo["correo"] == antes["correo"]
    assert cuerpo["activo"] is False
    assert cuerpo["ultimo_acceso"] == antes["ultimo_acceso"]
    persistido = db.get(Usuario, usuario.id)
    assert persistido is not None
    assert persistido.id == antes["id"]
    assert client.delete(f"/api/usuarios/{usuario.id}").status_code == 405
