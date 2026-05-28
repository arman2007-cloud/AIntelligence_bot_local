from pydantic import BaseModel, Field, field_validator
from urllib.parse import urlparse

class CandidateSchema(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    job_title: str = Field(..., min_length=2, max_length=120)
    company: str = Field(default="Not specified", max_length=100)
    location: str = Field(default="Unknown", max_length=80)
    url: str = Field(...)
    score: int = Field(..., ge=0, le=100)

    @field_validator('url')
    @classmethod
    def strict_linkedin_only(cls, v):
        """CANDADO 1: Solo perfiles personales de LinkedIn permitidos."""
        if not v.startswith('http'):
            v = f"https://{v}"
            
        parsed = urlparse(v)
        
        # Si no es LinkedIn o es una página de empresa/empleo, se bloquea.
        if 'linkedin.com' not in parsed.netloc or '/in/' not in parsed.path:
            raise ValueError('Operación cancelada: La URL debe ser un perfil personal de LinkedIn (/in/)')
            
        return f"https://www.linkedin.com{parsed.path.rstrip('/')}"

    @field_validator('name')
    @classmethod
    def no_noise_names(cls, v):
        """CANDADO 2: Bloquea perfiles anónimos o nombres basura."""
        noise = ['linkedin member', 'usuario de linkedin', 'unknown', 'n/a', 'perfil de linkedin']
        if v.lower().strip() in noise:
            raise ValueError(f'El nombre "{v}" es basura/ruido, no es una persona real')
        return v.strip()