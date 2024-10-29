from typing import Optional
from pydantic import BaseModel
from datetime import datetime

class LoginStatus(BaseModel):
    success: bool
    message: str
    error_details: Optional[str] = None

class EventStatus(BaseModel):
    name: str
    location: str
    event_date: str
    registration_start: str
    registration_end: str
    status: str
    last_checked: str
