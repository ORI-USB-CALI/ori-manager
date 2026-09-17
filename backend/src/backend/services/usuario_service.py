from fastapi import HTTPException
from sqlalchemy.orm import Session
from pwdlib import PasswordHash
from backend.models.usuario import Usuario
from backend.models.rol import Rol
from backend.schemas.usuario import UsuarioCrear, UsuarioActualizar, UsuarioCambiarRol

password_hash = PasswordHash.recommended()

def listar_usuarios(db: Session):
    return db.query(Usuario).all()

def obtener_usuario(db: Session, usuario_id: int) -> Usuario:
    usuario = db.query(Usuario).filter(Usuario.id == usuario_id).first()
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return usuario

def crear_usuario(db: Session, user_in: UsuarioCrear):
    if db.query(Usuario).filter(Usuario.correo == user_in.correo).first():
        raise HTTPException(status_code=400, detail="El correo ya existe")
    
    rol = db.query(Rol).filter(Rol.codigo == user_in.rol).first()
    if not rol:
        raise HTTPException(status_code=400, detail="Rol no valido")

    nuevo_usuario = Usuario(
        correo=user_in.correo,
        hash_contrasena=password_hash.hash(user_in.contrasena),
        nombre_completo=user_in.nombre_completo,
        documento_identidad=user_in.documento_identidad,
        telefono=user_in.telefono,
        cargo=user_in.cargo,
        rol_id=rol.id,
    )
    db.add(nuevo_usuario)
    db.commit()
    db.refresh(nuevo_usuario)
    return nuevo_usuario

def editar_usuario(db: Session, usuario_id: int, user_in: UsuarioActualizar):
    usuario = db.query(Usuario).filter(Usuario.id == usuario_id).first()
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    update_data = user_in.model_dump(exclude_unset=True, exclude_none=True)
    for key, value in update_data.items():
        setattr(usuario, key, value)
        
    db.commit()
    db.refresh(usuario)
    return usuario

def cambiar_rol(db: Session, usuario_id: int, rol_in: UsuarioCambiarRol):
    usuario = db.query(Usuario).filter(Usuario.id == usuario_id).first()
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
        
    rol = db.query(Rol).filter(Rol.codigo == rol_in.rol).first()
    if not rol:
        raise HTTPException(status_code=400, detail="Rol no valido")
        
    usuario.rol_id = rol.id
    db.commit()
    db.refresh(usuario)
    return usuario

def desactivar_usuario(db: Session, usuario_id: int):
    usuario = db.query(Usuario).filter(Usuario.id == usuario_id).first()
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    if not usuario.activo:
        raise HTTPException(status_code=400, detail="El usuario ya esta inactivo")
        
    usuario.desactivar()
    db.commit()
    db.refresh(usuario)
    return usuario