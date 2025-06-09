from pydantic import BaseModel, EmailStr

class UsuarioLogin(BaseModel):
    email: EmailStr
    password: str