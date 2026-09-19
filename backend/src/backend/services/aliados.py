from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from backend.models.aliado import Aliado
from backend.models.contacto_aliado import ContactoAliado
from backend.models.convenio import Convenio
from backend.models.enums import EstadoConvenio, TipoAliado, TipoIdentificacion
from backend.models.pais import Pais
from backend.models.solicitud_convenio import SolicitudConvenio
from backend.schemas.aliado import (
    AliadoActualizar,
    AliadoAdministracion,
    AliadoCorregirIdentificacion,
)


class ErrorAliado(Exception):
    pass


class AliadoNoEncontrado(ErrorAliado):
    pass


class ConflictoAliado(ErrorAliado):
    pass


class ReferenciaAliadoInvalida(ErrorAliado):
    pass


@dataclass(frozen=True)
class FiltrosAliado:
    buscar: str | None = None
    tipo: TipoAliado | None = None
    activo: bool | None = None
    limite: int = 20
    desplazamiento: int = 0


def _validar_sector(tipo: str, sector: str | None) -> None:
    if tipo == TipoAliado.EMPRESA and not sector:
        raise ReferenciaAliadoInvalida(
            "sector_economico es obligatorio para un aliado EMPRESA"
        )


class ServicioAliados:
    def __init__(self, db: Session):
        self.db = db

    def listar(self, filtros: FiltrosAliado) -> tuple[Sequence[Aliado], int]:
        condiciones = []
        if filtros.buscar:
            patron = f"%{filtros.buscar.strip()}%"
            condiciones.append(
                or_(Aliado.nombre.ilike(patron), Aliado.identificacion.ilike(patron))
            )
        if filtros.tipo is not None:
            condiciones.append(Aliado.tipo == filtros.tipo.value)
        if filtros.activo is not None:
            condiciones.append(Aliado.activo == filtros.activo)
        total = self.db.scalar(
            select(func.count()).select_from(Aliado).where(*condiciones)
        ) or 0
        items = self.db.scalars(
            select(Aliado)
            .where(*condiciones)
            .order_by(Aliado.nombre, Aliado.id)
            .limit(filtros.limite)
            .offset(filtros.desplazamiento)
        ).all()
        return items, total

    def obtener(self, aliado_id: int, *, perfil: bool = False) -> Aliado:
        consulta = select(Aliado).where(Aliado.id == aliado_id)
        if perfil:
            consulta = consulta.options(
                selectinload(Aliado.convenios).selectinload(Convenio.tipo_convenio)
            )
        aliado = self.db.scalar(consulta)
        if aliado is None:
            raise AliadoNoEncontrado("Aliado no encontrado")
        return aliado

    def actualizar(self, aliado_id: int, datos: AliadoActualizar) -> Aliado:
        aliado = self.obtener(aliado_id)
        cambios = datos.model_dump(exclude_unset=True)
        tipo = cambios.get("tipo", aliado.tipo)
        tipo_valor = tipo.value if isinstance(tipo, TipoAliado) else tipo
        sector = cambios.get("sector_economico", aliado.sector_economico)
        _validar_sector(tipo_valor, sector)
        pais_id = cambios.get("pais_id")
        if pais_id is not None and self.db.get(Pais, pais_id) is None:
            raise ReferenciaAliadoInvalida("El país seleccionado no existe")
        for campo, valor in cambios.items():
            setattr(aliado, campo, valor.value if isinstance(valor, TipoAliado) else valor)
        self.db.commit()
        self.db.refresh(aliado)
        return aliado

    def cambiar_estado(self, aliado_id: int, activo: bool) -> Aliado:
        aliado = self.obtener(aliado_id)
        if aliado.activo == activo:
            estado = "activo" if activo else "inactivo"
            raise ConflictoAliado(f"El aliado ya se encuentra {estado}")
        if not activo:
            bloquea = self.db.scalar(
                select(Convenio.id).where(
                    Convenio.aliado_id == aliado_id,
                    Convenio.estado.in_(
                        [EstadoConvenio.VIGENTE.value, EstadoConvenio.POR_VENCER.value]
                    ),
                ).limit(1)
            )
            if bloquea is not None:
                raise ConflictoAliado(
                    "No se puede inactivar un aliado con convenios VIGENTE o POR_VENCER"
                )
        aliado.activo = activo
        self.db.commit()
        self.db.refresh(aliado)
        return aliado

    def corregir_identificacion(
        self, aliado_id: int, datos: AliadoCorregirIdentificacion
    ) -> Aliado:
        aliado = self.obtener(aliado_id)
        duplicado = self.db.scalar(select(Aliado.id).where(
            Aliado.tipo_identificacion == datos.tipo_identificacion.value,
            Aliado.identificacion == datos.identificacion,
            Aliado.id != aliado_id,
        ))
        if duplicado is not None:
            raise ConflictoAliado("Ya existe un aliado con ese tipo y documento")
        aliado.tipo_identificacion = datos.tipo_identificacion.value
        aliado.identificacion = datos.identificacion
        self.db.commit()
        self.db.refresh(aliado)
        return aliado

    def actualizar_administracion(
        self, aliado_id: int, datos: AliadoAdministracion
    ) -> Aliado:
        aliado = self.obtener(aliado_id)
        cambios = datos.model_dump(exclude_unset=True)
        tipo = cambios.get("tipo", aliado.tipo)
        if tipo is None or ("nombre" in cambios and cambios["nombre"] is None):
            raise ReferenciaAliadoInvalida("Nombre y tipo del aliado son obligatorios")
        tipo_valor = tipo.value if isinstance(tipo, TipoAliado) else tipo
        sector = cambios.get("sector_economico", aliado.sector_economico)
        _validar_sector(tipo_valor, sector.strip() if sector else None)
        pais_id = cambios.get("pais_id")
        if pais_id is not None and self.db.get(Pais, pais_id) is None:
            raise ReferenciaAliadoInvalida("El país seleccionado no existe")
        duplicado = self.db.scalar(select(Aliado.id).where(
            Aliado.tipo_identificacion == datos.tipo_identificacion.value,
            Aliado.identificacion == datos.identificacion,
            Aliado.id != aliado_id,
        ))
        if duplicado is not None:
            raise ConflictoAliado("Ya existe un aliado con ese tipo y documento")
        for campo, valor in cambios.items():
            setattr(
                aliado, campo,
                valor.value if isinstance(valor, (TipoAliado, TipoIdentificacion)) else valor,
            )
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ConflictoAliado("Ya existe un aliado con ese tipo y documento") from exc
        self.db.refresh(aliado)
        return aliado


def _registrar_correo(db: Session, aliado: Aliado, correo: str | None) -> None:
    if not correo:
        return
    correos = {correo}
    if aliado.correo:
        correos.add(aliado.correo)
    existentes = set(
        db.scalars(
            select(ContactoAliado.correo).where(
                ContactoAliado.aliado_id == aliado.id,
                ContactoAliado.correo.in_(correos),
            )
        ).all()
    )
    for valor in correos - existentes:
        db.add(
            ContactoAliado(
                aliado_id=aliado.id,
                nombre=aliado.nombre,
                correo=valor,
                es_principal=valor == correo,
            )
        )
    aliado.correo = correo


def _buscar_por_identificacion(db: Session, solicitud: SolicitudConvenio) -> Aliado | None:
    tipo = solicitud.tipo_identificacion_aliado_propuesto
    identificacion = (solicitud.identificacion_aliado_propuesto or "").strip()
    if not tipo or not identificacion:
        return None
    return db.scalar(select(Aliado).where(
        Aliado.tipo_identificacion == tipo,
        Aliado.identificacion == identificacion,
    ))


def resolver_aliado_existente_para_solicitud(
    db: Session, solicitud: SolicitudConvenio
) -> Aliado | None:
    """Reconoce la contraparte persistida sin crear un aliado."""
    aliado = _buscar_por_identificacion(db, solicitud)
    solicitud.aliado_id = aliado.id if aliado is not None else None
    db.flush()
    return aliado


def resolver_aliado_para_convenio(db: Session, convenio: Convenio) -> Aliado | None:
    """Asocia la contraparte persistida solo al formalizar el convenio."""
    if convenio.estado != EstadoConvenio.VIGENTE:
        return None
    solicitud = convenio.solicitud
    aliado = db.get(Aliado, solicitud.aliado_id) if solicitud.aliado_id else None
    if solicitud.aliado_id and aliado is None:
        raise ReferenciaAliadoInvalida("El aliado de la solicitud no existe")
    if aliado is None:
        aliado = _buscar_por_identificacion(db, solicitud)
    if aliado is not None and not aliado.activo:
        raise ConflictoAliado(
            "El aliado está inactivo; debe reactivarse antes de asociarlo"
        )
    if aliado is None:
        nombre = (solicitud.nombre_aliado_propuesto or "").strip()
        identificacion = (solicitud.identificacion_aliado_propuesto or "").strip()
        tipo_identificacion = solicitud.tipo_identificacion_aliado_propuesto
        tipo = solicitud.tipo_aliado_propuesto
        if not nombre or not identificacion or not tipo_identificacion or not tipo:
            raise ReferenciaAliadoInvalida("Faltan datos persistidos de la contraparte")
        if tipo_identificacion not in TipoIdentificacion or tipo not in TipoAliado:
            raise ReferenciaAliadoInvalida("Tipo de contraparte o documento inválido")
        sector = (solicitud.sector_economico_aliado_propuesto or "").strip() or None
        _validar_sector(tipo, sector)
        aliado = Aliado(
            nombre=nombre, tipo=tipo, tipo_identificacion=tipo_identificacion,
            identificacion=identificacion, sector_economico=sector,
            correo=(solicitud.correo_aliado_propuesto or "").strip() or None,
        )
        db.add(aliado)
        db.flush()
    _registrar_correo(db, aliado, (solicitud.correo_aliado_propuesto or "").strip() or None)
    convenio.aliado_id = aliado.id
    solicitud.aliado_id = aliado.id
    db.flush()
    return aliado
