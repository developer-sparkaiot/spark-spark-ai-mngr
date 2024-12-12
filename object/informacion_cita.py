from pydantic import BaseModel, EmailStr
from datetime import date, time
from typing import List

class InformacionCita(BaseModel):
    """
    Clase InformacionCita, permite la creación de los elementos para agendar una cita.
    """
    codigo:str
    nombre: str
    correo: EmailStr
    fecha: date
    hora: time
    modalidad:str
    
    @classmethod
    def from_row(cls, row: List[str]) -> 'InformacionCita':
        """
        Dada una lista de elementos, crea el objeto InformacionCita.
        
        Args:
            row (List[str]): Lista con los datos para realizar la agendación de la cita.
        
        Returns:
            InformacionCita: El objeto con los datos creados.
        """
        if len(row) != 5 or any(not field for field in row):
            raise ValueError("Faltan campos en los datos de la cita")
        
        try:
            fecha_validation = date.fromisoformat(row[2])
            hora_validation = time.fromisoformat(row[3])
        except ValueError as e:
            raise ValueError(f"Error al procesar fecha u hora: {e}")
        
        return cls(
            codigo="",
            nombre=row[0],
            correo=row[1],
            fecha=fecha_validation,
            hora=hora_validation,
            modalidad=row[4]
        )
    
    @classmethod
    def from_string(cls, cadena: str) -> 'InformacionCita':

        """
        Crea un objeto InformacionCita a partir de una cadena separada por comas.
        
        Args:
            cadena (str): Cadena con los datos de la cita, en formato CSV.
        
        Returns:
            InformacionCita: Objeto creado con los datos de la cadena.
        """
        try:
            campos = [campo.strip() for campo in cadena.split(",")]
            return cls.from_row(campos)
        except Exception as e:
            raise ValueError(f"Error al procesar la cadena: {e}")
    
    def to_dict(self) -> dict:
        """
        Transforma el objeto InformacionCita a un diccionario.
        
        Returns:
            dict: Diccionario con la información del cliente.
        """
        return {
            "codigo":self.codigo,
            "nombre": self.nombre,
            "correo": self.correo,
            "fecha": self.fecha.strftime('%d/%m/%Y'),
            "hora": self.hora.strftime('%H:%M:%S'),
            "modalidad": self.modalidad
        }
