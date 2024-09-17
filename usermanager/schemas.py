# mpi_src/usermanager/schemas.py

from pydantic import BaseModel, EmailStr, Field
from typing import Optional, Dict, Any

class UserCreateSchema(BaseModel):
    email: EmailStr
    password: str

class PaymentInitiateSchema(BaseModel):
    email: EmailStr
    amount: int = Field(..., gt=0)  # Amount must be greater than 0

class PaymentCallbackSchema(BaseModel):
    event: str
    data: Dict[str, Any]


class CreateUserSchema(BaseModel):
    email: EmailStr
    password: str
    profile: str = 'default'

class UpdateUserSchema(BaseModel):
    email: EmailStr
    password: str
    profile: str

class TopUpUserSchema(BaseModel):
    email: EmailStr
    days_to_add: int = Field(..., gt=0)
