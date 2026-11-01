from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path
from secrets import token_hex

from sqlalchemy import exists, func, or_, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, selectinload

from backend.core.roles import TipoUsuario
from backend.core.unidades_organizacionales import TipoUnidad
from backend.core.validaciones import (
    normalizar_ciudad,
    normalizar_digito_verificacion_nit,
    normalizar_direccion,
    normalizar_identificacion,
    normalizar_telefono,
)
from backend.models.convenio import Convenio
from backend.models.documento import Documento
from backend.models.enums import (
    EntidadNotificacion,
    EstadoSolicitud,
    TipoAliado,
    TipoDocumentoSolicitud,
    TipoIdentificacion,
    TipoNotificacion,
)
from backend.models.pais import Pais
from backend.models.solicitud_convenio import SolicitudConvenio
from backend.models.solicitud_usuario import SolicitudUsuario
from backend.models.solicitud_version import (
    SolicitudVersion,
    solicitud_version_documento,
)
from backend.models.tipo_convenio import TipoConvenio
from backend.models.usuario import Usuario
from backend.schemas.solicitud import (
    DevolucionSolicitudLeer,
    HistorialSolicitudLeer,
    SolicitudActualizar,
    SolicitudCampos,
    SolicitudCrear,
    VersionSolicitudHistorialLeer,
)
from backend.services.bitacora import describir_accion, describir_cambios_automaticos
from backend.services.documentos import (
    EXTENSIONES_PERMITIDAS,
    TAMANO_MAXIMO_DOCUMENTO,
    TIPOS_DOCUMENTO_REPRESENTACION,
    TIPOS_MIME_PERMITIDOS,
    AlmacenDocumentos,
)
from backend.services.notificaciones import ServicioNotificaciones


class ErrorSolicitud(Exception):
    pass


class SolicitudNoEncontrada(ErrorSolicitud):
    pass


class SolicitudNoEditable(ErrorSolicitud):
    pass


class SolicitudIncompleta(ErrorSolicitud):
    def __init__(
        self, errores: dict[str, str], mensaje: str = "La solicitud está incompleta"
    ):
        super().__init__(mensaje)
        self.errores = errores


class DatosSolicitudInvalidos(SolicitudIncompleta):
    """HT-14 CA-06: errores de formato por campo, con el mismo 422 de radicación."""

    def __init__(self, errores: dict[str, str]):
        super().__init__(errores, "La solicitud tiene datos con formato inválido")


class DocumentoInvalido(ErrorSolicitud):
    pass


class ReferenciaSolicitudInvalida(ErrorSolicitud):
    pass


class SolicitudNoRevisable(ErrorSolicitud):
    pass


# HT-14: campos con reglas de formato (core/validaciones.py).
CAMPOS_TELEFONO = (
    "telefono_aliado_propuesto",
    "contacto_contraparte_telefono",
    "supervisor_usb_telefono",
    "supervisor_contraparte_telefono",
)
# (tipo, número, dígito de verificación) de cada identificación de la solicitud.
GRUPOS_IDENTIFICACION = (
    (
        "tipo_identificacion_aliado_propuesto",
        "identificacion_aliado_propuesto",
        "digito_verificacion_aliado_propuesto",
    ),
    (
        "solicitante_tipo_documento",
        "solicitante_documento",
        "solicitante_digito_verificacion",
    ),
)
CAMPOS_CON_FORMATO = frozenset(
    {
        *CAMPOS_TELEFONO,
        "ciudad_aliado_propuesto",
        "direccion_aliado_propuesto",
        "pais_aliado_propuesto_id",
        *(campo for grupo in GRUPOS_IDENTIFICACION for campo in grupo),
    }
)

# Campos que se guardan en cada versión radicada. El país se conserva por su
# nombre: el id no es legible y duplicaría el cambio al comparar versiones.
CAMPOS_VERSION = tuple(
    campo for campo in SolicitudCampos.model_fields if campo != "pais_aliado_propuesto_id"
)

ESTADOS_PENDIENTES_REVISION = frozenset(
    {EstadoSolicitud.RADICADA.value, EstadoSolicitud.EN_ESTUDIO.value}
)

ACCION_POR_DECISION = {
    EstadoSolicitud.APROBADA: "Aceptó la solicitud",
    EstadoSolicitud.RECHAZADA: "Rechazó la solicitud",
    EstadoSolicitud.DEVUELTA: "Devolvió la solicitud al Solicitante para corrección",
}


class ServicioSolicitudes:
    def __init__(self, db: Session, almacen: AlmacenDocumentos | None = None):
        self.db = db
        self.almacen = almacen

    def _almacen_requerido(self) -> AlmacenDocumentos:
        if self.almacen is None:
            raise RuntimeError("Esta operación requiere un almacén documental")
        return self.almacen

    @staticmethod
    def _snapshot(usuario: Usuario) -> dict[str, object | None]:
        unidad = usuario.unidad_organizacional
        unidad_nombre = None
        programa_nombre = None
        if unidad is not None and unidad.tipo == TipoUnidad.PROGRAMA:
            programa_nombre = unidad.nombre
            unidad_nombre = unidad.unidad_padre.nombre if unidad.unidad_padre else None
        elif unidad is not None:
            unidad_nombre = unidad.nombre
        return {
            "tipo_solicitante": usuario.tipo_usuario,
            "unidad_organizacional_id": usuario.unidad_organizacional_id,
            "solicitante_nombre": usuario.nombre_completo,
            "solicitante_correo": usuario.correo,
            "solicitante_documento": usuario.documento_identidad,
            "solicitante_cargo": usuario.cargo,
            "solicitante_entidad": usuario.entidad_externa,
            "solicitante_unidad": unidad_nombre,
            "solicitante_programa": programa_nombre,
        }

    def _consulta_visible(self, usuario: Usuario):
        return select(SolicitudConvenio).where(
            or_(
                SolicitudConvenio.solicitante_id == usuario.id,
                exists(
                    select(SolicitudUsuario.id).where(
                        SolicitudUsuario.solicitud_id == SolicitudConvenio.id,
                        SolicitudUsuario.usuario_id == usuario.id,
                    )
                ),
            )
        )

    def _cargar(
        self, solicitud_id: int, usuario: Usuario, *, bloquear: bool = False
    ) -> SolicitudConvenio:
        consulta = (
            self._consulta_visible(usuario)
            .where(SolicitudConvenio.id == solicitud_id)
            .options(selectinload(SolicitudConvenio.documentos))
        )
        if bloquear:
            consulta = consulta.with_for_update()
        solicitud = self.db.scalar(consulta)
        if solicitud is None:
            raise SolicitudNoEncontrada("Solicitud no encontrada")
        return solicitud

    def _cargar_editable(
        self, solicitud_id: int, usuario: Usuario, *, bloquear: bool = False
    ) -> SolicitudConvenio:
        solicitud = self._cargar(solicitud_id, usuario, bloquear=bloquear)
        if solicitud.solicitante_id != usuario.id:
            raise SolicitudNoEncontrada("Solicitud no encontrada")
        if solicitud.estado not in {
            EstadoSolicitud.BORRADOR.value,
            EstadoSolicitud.DEVUELTA.value,
        }:
            raise SolicitudNoEditable(
                "Solo se pueden modificar solicitudes en BORRADOR o DEVUELTA"
            )
        return solicitud

    def crear(self, datos: SolicitudCrear, usuario: Usuario) -> SolicitudConvenio:
        recibidos = self._valores(datos)
        valores = {**self._snapshot(usuario), **recibidos}
        ajustes, errores = self._validar_formatos(valores, set(recibidos))
        if errores:
            raise DatosSolicitudInvalidos(errores)
        valores.update(ajustes)
        solicitud = SolicitudConvenio(
            consecutivo=f"TEMP-{token_hex(12)}",
            solicitante_id=usuario.id,
            estado=EstadoSolicitud.BORRADOR.value,
            **valores,
        )
        self._validar_tipo_convenio(solicitud.tipo_convenio_id)
        self.db.add(solicitud)
        self.db.flush()
        solicitud.consecutivo = f"SOL-{solicitud.id:08d}"
        self.db.commit()
        return self.obtener(solicitud.id, usuario)

    @staticmethod
    def _valores(datos: SolicitudCrear | SolicitudActualizar) -> dict[str, object]:
        return {
            campo: valor.value if hasattr(valor, "value") else valor
            for campo, valor in datos.model_dump(exclude_unset=True).items()
        }

    def _validar_tipo_convenio(self, tipo_id: int | None) -> None:
        if tipo_id is None:
            return
        tipo = self.db.get(TipoConvenio, tipo_id)
        if tipo is None or not tipo.activo:
            raise ReferenciaSolicitudInvalida(
                "El tipo de convenio no existe o está inactivo"
            )

    def actualizar(
        self, solicitud_id: int, datos: SolicitudActualizar, usuario: Usuario
    ) -> SolicitudConvenio:
        solicitud = self._cargar_editable(solicitud_id, usuario, bloquear=True)
        cambios = self._valores(datos)
        self._validar_tipo_convenio(
            cambios.get("tipo_convenio_id", solicitud.tipo_convenio_id)
        )
        # Un PATCH puede traer solo una parte de una identificación: se valida
        # sobre la combinación de lo recibido con lo ya guardado.
        efectivos = {
            campo: getattr(solicitud, campo) for campo in CAMPOS_CON_FORMATO
        } | cambios
        ajustes, errores = self._validar_formatos(efectivos, set(cambios))
        if errores:
            raise DatosSolicitudInvalidos(errores)
        cambios.update(ajustes)
        for campo, valor in cambios.items():
            setattr(solicitud, campo, valor)
        self.db.commit()
        return self.obtener(solicitud.id, usuario)

    def _validar_formatos(
        self, valores: dict[str, object], campos: set[str]
    ) -> tuple[dict[str, object], dict[str, str]]:
        """HT-14. Valida los ``campos`` indicados sobre ``valores`` y devuelve
        los valores canónicos a guardar y los errores por campo.

        Los campos vacíos no se validan aquí: la obligatoriedad se exige solo
        al radicar (CA-05).
        """
        ajustes: dict[str, object] = {}
        errores: dict[str, str] = {}

        def aplicar(campo: str, regla, *argumentos) -> object:
            try:
                ajustes[campo] = regla(*argumentos)
            except ValueError as error:
                errores[campo] = str(error)
            return ajustes.get(campo)

        for campo in CAMPOS_TELEFONO:
            if campo in campos and valores.get(campo):
                aplicar(campo, normalizar_telefono, valores[campo])
        for campo, regla in (
            ("ciudad_aliado_propuesto", normalizar_ciudad),
            ("direccion_aliado_propuesto", normalizar_direccion),
        ):
            if campo in campos and valores.get(campo):
                aplicar(campo, regla, valores[campo])

        for campo_tipo, campo_numero, campo_dv in GRUPOS_IDENTIFICACION:
            if not campos.intersection((campo_tipo, campo_numero, campo_dv)):
                continue
            tipo = valores.get(campo_tipo)
            numero = valores.get(campo_numero)
            digito = valores.get(campo_dv)
            if tipo != TipoIdentificacion.NIT and digito:
                if campo_dv in campos:
                    errores[campo_dv] = "El dígito de verificación solo aplica a NIT"
                else:
                    # El tipo dejó de ser NIT: el DV ya no tiene sentido.
                    ajustes[campo_dv] = None
                digito = None
            base = (
                aplicar(campo_numero, normalizar_identificacion, TipoIdentificacion(tipo), numero)
                if tipo and numero
                else None
            )
            if base and digito:
                aplicar(campo_dv, normalizar_digito_verificacion_nit, base, digito)

        if "pais_aliado_propuesto_id" in campos:
            pais_id = valores.get("pais_aliado_propuesto_id")
            pais = self.db.get(Pais, pais_id) if pais_id is not None else None
            if pais_id is not None and pais is None:
                errores["pais_aliado_propuesto_id"] = "El país seleccionado no existe"
            else:
                # El nombre oficial se conserva para el historial y los
                # consumidores que leen el país como texto.
                ajustes["pais_aliado_propuesto"] = pais.nombre if pais else None
        return ajustes, errores

    def listar(self, usuario: Usuario) -> list[SolicitudConvenio]:
        return list(
            self.db.scalars(
                self._consulta_visible(usuario)
                .options(selectinload(SolicitudConvenio.documentos))
                .order_by(
                    SolicitudConvenio.creado_en.desc(), SolicitudConvenio.id.desc()
                )
            ).unique()
        )

    def obtener(self, solicitud_id: int, usuario: Usuario) -> SolicitudConvenio:
        return self._cargar(solicitud_id, usuario)

    def _consulta_recibidas(self):
        return (
            select(SolicitudConvenio)
            .where(SolicitudConvenio.estado != EstadoSolicitud.BORRADOR)
            .options(
                selectinload(SolicitudConvenio.documentos),
                selectinload(SolicitudConvenio.convenio).selectinload(
                    Convenio.etapa_actual
                ),
                selectinload(SolicitudConvenio.tipo_convenio),
                selectinload(SolicitudConvenio.decidida_por),
            )
        )

    def listar_recibidas(self) -> list[SolicitudConvenio]:
        return list(
            self.db.scalars(
                self._consulta_recibidas().order_by(
                    SolicitudConvenio.fecha_radicacion.desc(),
                    SolicitudConvenio.id.desc(),
                )
            ).unique()
        )

    def obtener_recibida(
        self, solicitud_id: int, *, bloquear: bool = False
    ) -> SolicitudConvenio:
        consulta = self._consulta_recibidas().where(
            SolicitudConvenio.id == solicitud_id
        )
        if bloquear:
            consulta = consulta.with_for_update()
        solicitud = self.db.scalar(consulta)
        if solicitud is None:
            raise SolicitudNoEncontrada("Solicitud recibida no encontrada")
        return solicitud

    def historial(self, solicitud: SolicitudConvenio) -> HistorialSolicitudLeer:
        """HT-02 CA-05: cada radicación con su devolución y la versión que la corrigió."""
        versiones = self.db.scalars(
            select(SolicitudVersion)
            .where(SolicitudVersion.solicitud_id == solicitud.id)
            .options(selectinload(SolicitudVersion.devuelta_por))
            .order_by(SolicitudVersion.numero)
        ).all()
        numeros = {version.numero for version in versiones}
        return HistorialSolicitudLeer(
            solicitud_id=solicitud.id,
            consecutivo=solicitud.consecutivo,
            estado=solicitud.estado,
            versiones=[
                VersionSolicitudHistorialLeer(
                    numero=version.numero,
                    radicada_en=version.radicada_en,
                    devolucion=None
                    if version.devuelta_en is None
                    else DevolucionSolicitudLeer(
                        observaciones=version.observaciones_devolucion,
                        devuelta_por_nombre=version.devuelta_por.nombre_completo,
                        devuelta_en=version.devuelta_en,
                        corregida_en_version=(
                            version.numero + 1
                            if version.numero + 1 in numeros
                            else None
                        ),
                    ),
                )
                for version in versiones
            ],
        )

    def _decidir(
        self, solicitud_id: int, actor: Usuario, estado: EstadoSolicitud
    ) -> SolicitudConvenio:
        solicitud = self.obtener_recibida(solicitud_id, bloquear=True)
        if solicitud.estado not in ESTADOS_PENDIENTES_REVISION:
            raise SolicitudNoRevisable(
                f"La solicitud está {solicitud.estado} y ya no admite decisión"
            )
        instante = datetime.now(UTC)
        describir_accion(
            self.db,
            actor,
            ACCION_POR_DECISION[estado],
            instante=instante,
            evento=f"SOLICITUD_{estado.value}",
            # El solicitante es titular de la solicitud, no responsable de la
            # decisión de ORI; no existe una asignación institucional verificable.
        )
        solicitud.estado = estado.value
        solicitud.decidida_por = actor
        solicitud.fecha_decision = instante
        return solicitud

    def aceptar(self, solicitud_id: int, actor: Usuario) -> SolicitudConvenio:
        self._decidir(solicitud_id, actor, EstadoSolicitud.APROBADA)
        self.db.commit()
        return self.obtener_recibida(solicitud_id)

    def rechazar(
        self, solicitud_id: int, motivo: str, actor: Usuario
    ) -> SolicitudConvenio:
        solicitud = self._decidir(solicitud_id, actor, EstadoSolicitud.RECHAZADA)
        solicitud.motivo_rechazo = motivo
        self.db.commit()
        return self.obtener_recibida(solicitud_id)

    def devolver(
        self, solicitud_id: int, observaciones: str, actor: Usuario
    ) -> SolicitudConvenio:
        solicitud = self._decidir(solicitud_id, actor, EstadoSolicitud.DEVUELTA)
        notificaciones = ServicioNotificaciones(self.db)
        try:
            solicitud.observaciones_devolucion = observaciones
            version = self.db.scalar(
                select(SolicitudVersion)
                .where(SolicitudVersion.solicitud_id == solicitud.id)
                .order_by(SolicitudVersion.numero.desc())
                .limit(1)
            )
            # Las solicitudes radicadas antes de HT-02 no tienen versión que marcar.
            if version is not None:
                version.observaciones_devolucion = observaciones
                version.devuelta_por_id = actor.id
                version.devuelta_en = solicitud.fecha_decision
            notificaciones.crear(
                solicitud.solicitante_id,
                TipoNotificacion.SOLICITUD_DEVUELTA,
                EntidadNotificacion.SOLICITUD,
                solicitud.id,
                f"Su solicitud {solicitud.consecutivo} fue devuelta con observaciones.",
            )
            self.db.commit()
        except SQLAlchemyError:
            self.db.rollback()
            raise
        notificaciones.avisar_tiempo_real()
        return self.obtener_recibida(solicitud_id)

    def obtener_contenido_documento_recibido(
        self, solicitud_id: int, documento_id: int
    ) -> tuple[Documento, bytes]:
        solicitud = self.obtener_recibida(solicitud_id)
        documento = next(
            (item for item in solicitud.documentos if item.id == documento_id), None
        )
        if documento is None:
            raise SolicitudNoEncontrada("Documento no encontrado")
        return documento, self._almacen_requerido().leer(
            documento.ruta_almacenamiento
        )

    def agregar_documento(
        self,
        solicitud_id: int,
        usuario: Usuario,
        tipo_documento: TipoDocumentoSolicitud,
        nombre: str,
        tipo_mime: str,
        contenido: bytes,
    ) -> Documento:
        solicitud = self._cargar_editable(solicitud_id, usuario, bloquear=True)
        nombre_seguro = Path(nombre.replace("\\", "/")).name.strip()
        extension = Path(nombre_seguro).suffix.lower()
        if not nombre_seguro or extension not in EXTENSIONES_PERMITIDAS:
            raise DocumentoInvalido("Extensión no permitida; use PDF, JPG, JPEG o PNG")
        if tipo_mime not in TIPOS_MIME_PERMITIDOS:
            raise DocumentoInvalido("Tipo de contenido no permitido")
        if not contenido:
            raise DocumentoInvalido("El documento está vacío")
        if len(contenido) > TAMANO_MAXIMO_DOCUMENTO:
            raise DocumentoInvalido("El documento supera el límite de 10 MB")
        clave = f"solicitudes/{solicitud.id}/{token_hex(20)}{extension}"
        documento = Documento(
            solicitud_id=solicitud.id,
            convenio_id=None,
            tipo=tipo_documento.value,
            nombre_archivo=nombre_seguro[:255],
            tipo_mime=tipo_mime,
            tamano_bytes=len(contenido),
            ruta_almacenamiento=clave,
            es_vigente=True,
            cargado_por_id=usuario.id,
        )
        almacen = self._almacen_requerido()
        almacen.guardar(clave, contenido)
        self.db.add(documento)
        try:
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            almacen.eliminar(clave)
            raise
        self.db.refresh(documento)
        return documento

    def eliminar_documento(
        self, solicitud_id: int, documento_id: int, usuario: Usuario
    ) -> None:
        solicitud = self._cargar_editable(solicitud_id, usuario, bloquear=True)
        documento = next(
            (item for item in solicitud.documentos if item.id == documento_id), None
        )
        if documento is None:
            raise SolicitudNoEncontrada("Documento no encontrado")
        if self._pertenece_a_version(documento):
            documento.es_vigente = False
            self.db.commit()
            self.db.expire(solicitud, ["documentos"])
            return
        clave = documento.ruta_almacenamiento
        self.db.delete(documento)
        self.db.commit()
        self.db.expire(solicitud, ["documentos"])
        self._almacen_requerido().eliminar(clave)

    def _pertenece_a_version(self, documento: Documento) -> bool:
        return bool(
            self.db.scalar(
                select(
                    exists().where(
                        solicitud_version_documento.c.documento_id == documento.id
                    )
                )
            )
        )

    @staticmethod
    def _datos_version(solicitud: SolicitudConvenio) -> dict[str, object]:
        datos: dict[str, object] = {}
        for campo in CAMPOS_VERSION:
            valor = getattr(solicitud, campo)
            datos[campo] = valor.isoformat() if isinstance(valor, date) else valor
        return datos

    def _registrar_version(
        self, solicitud: SolicitudConvenio, usuario: Usuario, instante: datetime
    ) -> None:
        ultimo = self.db.scalar(
            select(func.max(SolicitudVersion.numero)).where(
                SolicitudVersion.solicitud_id == solicitud.id
            )
        )
        self.db.add(
            SolicitudVersion(
                solicitud_id=solicitud.id,
                numero=(ultimo or 0) + 1,
                datos=self._datos_version(solicitud),
                radicada_por_id=usuario.id,
                radicada_en=instante,
                documentos=list(solicitud.documentos),
            )
        )

    def _errores_radicacion(
        self, solicitud: SolicitudConvenio, usuario: Usuario
    ) -> dict[str, str]:
        requeridos = (
            "nombre_aliado_propuesto",
            "tipo_identificacion_aliado_propuesto",
            "identificacion_aliado_propuesto",
            "tipo_aliado_propuesto",
            "correo_aliado_propuesto",
            "pais_aliado_propuesto_id",
            "ciudad_aliado_propuesto",
            "telefono_aliado_propuesto",
            "direccion_aliado_propuesto",
            "contacto_contraparte_nombre",
            "contacto_contraparte_cargo",
            "contacto_contraparte_telefono",
            "contacto_contraparte_correo",
            "tipo_convenio_id",
            "justificacion",
            "objeto",
            "actividades_por_parte",
            "metas_esperadas",
            "implicacion_financiera",
            "vigencia_estimada",
            "requisitos_renovacion",
            "supervisor_usb_nombre",
            "supervisor_usb_cargo",
            "supervisor_usb_telefono",
            "supervisor_usb_correo",
            "supervisor_contraparte_nombre",
            "supervisor_contraparte_cargo",
            "supervisor_contraparte_telefono",
            "supervisor_contraparte_correo",
        )
        errores = {
            campo: "Este campo es obligatorio"
            for campo in requeridos
            if not getattr(solicitud, campo)
        }
        if (
            solicitud.tipo_aliado_propuesto == TipoAliado.EMPRESA
            and not solicitud.sector_economico_aliado_propuesto
        ):
            errores["sector_economico_aliado_propuesto"] = (
                "Es obligatorio para una empresa"
            )
        if not solicitud.solicitante_nombre:
            errores["solicitante_nombre"] = "Este campo es obligatorio"
        if usuario.tipo_usuario == TipoUsuario.INTERNO:
            unidad = usuario.unidad_organizacional
            if unidad is None:
                if not (solicitud.solicitante_unidad or solicitud.solicitante_programa):
                    errores["solicitante_unidad"] = (
                        "Ingrese la Facultad, Dependencia, Programa o Unidad aplicable"
                    )
            elif unidad.tipo == TipoUnidad.PROGRAMA:
                if not solicitud.solicitante_programa:
                    errores["solicitante_programa"] = "Este campo es obligatorio"
                if unidad.unidad_padre is not None and not solicitud.solicitante_unidad:
                    errores["solicitante_unidad"] = "Este campo es obligatorio"
            elif not solicitud.solicitante_unidad:
                errores["solicitante_unidad"] = "Este campo es obligatorio"
            if not solicitud.solicitante_cargo:
                errores["solicitante_cargo"] = "Este campo es obligatorio"
        else:
            if not solicitud.solicitante_tipo_documento:
                errores["solicitante_tipo_documento"] = "Este campo es obligatorio"
            if not solicitud.solicitante_documento:
                errores["solicitante_documento"] = "Este campo es obligatorio"
            if (
                solicitud.solicitante_tipo_documento == TipoIdentificacion.NIT
                and not solicitud.solicitante_digito_verificacion
            ):
                errores["solicitante_digito_verificacion"] = "Este campo es obligatorio"
            if not solicitud.solicitante_entidad:
                errores["solicitante_entidad"] = "Este campo es obligatorio"
        if (
            solicitud.tipo_identificacion_aliado_propuesto == TipoIdentificacion.NIT
            and not solicitud.digito_verificacion_aliado_propuesto
        ):
            errores["digito_verificacion_aliado_propuesto"] = "Este campo es obligatorio"
        # RN-09 y RN-10: los valores guardados antes de HT-14 o en una solicitud
        # devuelta se revalidan al radicar, sin corregirlos automáticamente.
        _, errores_formato = self._validar_formatos(
            {campo: getattr(solicitud, campo) for campo in CAMPOS_CON_FORMATO},
            set(CAMPOS_CON_FORMATO),
        )
        for campo, mensaje in errores_formato.items():
            errores.setdefault(campo, mensaje)
        cargados = {item.tipo for item in solicitud.documentos}
        tipos_representacion = {
            tipo.value for tipo in TIPOS_DOCUMENTO_REPRESENTACION
        }
        if not cargados.intersection(tipos_representacion):
            errores["documentos.representacion_legal"] = (
                "Adjunte al menos un documento de representación legal aplicable"
            )
        for documento in solicitud.documentos:
            if not self._almacen_requerido().existe(documento.ruta_almacenamiento):
                errores[f"documentos.{documento.id}"] = (
                    "El archivo almacenado no está disponible"
                )
        return errores

    def radicar(self, solicitud_id: int, usuario: Usuario) -> SolicitudConvenio:
        solicitud = self._cargar_editable(solicitud_id, usuario, bloquear=True)
        errores = self._errores_radicacion(solicitud, usuario)
        if errores:
            raise SolicitudIncompleta(errores)
        instante = datetime.now(UTC)
        reradicacion = solicitud.estado == EstadoSolicitud.DEVUELTA.value
        describir_accion(
            self.db,
            usuario,
            "Volvió a radicar la solicitud corregida"
            if reradicacion
            else "Radicó la solicitud",
            instante=instante,
            evento="SOLICITUD_RERADICADA" if reradicacion else "SOLICITUD_RADICADA",
            responsable_id=solicitud.solicitante_id,
        )
        describir_cambios_automaticos(
            self.db, solicitud, "estado", "fecha_radicacion", "fecha_recibido_ori",
            "decidida_por_id", "fecha_decision",
        )
        solicitud.estado = EstadoSolicitud.RADICADA.value
        solicitud.fecha_radicacion = instante
        solicitud.fecha_recibido_ori = instante
        solicitud.decidida_por_id = None
        solicitud.fecha_decision = None
        notificaciones = ServicioNotificaciones(self.db)
        try:
            self._registrar_version(solicitud, usuario, instante)
            notificaciones.resolver(
                TipoNotificacion.SOLICITUD_DEVUELTA,
                EntidadNotificacion.SOLICITUD,
                solicitud.id,
            )
            self.db.commit()
        except SQLAlchemyError:
            self.db.rollback()
            raise
        notificaciones.avisar_tiempo_real()
        return self.obtener(solicitud.id, usuario)
