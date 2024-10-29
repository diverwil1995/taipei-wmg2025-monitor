from pydantic import BaseModel
from typing import Optional, List

class LoginStatus(BaseModel):
    success: bool
    message: str
    cookies_saved: bool = False

class EventStatus(BaseModel):
    name: str
    location: str
    event_date: str
    registration_start: str
    registration_end: str
    status: str
    last_checked: str

class EventQuery(BaseModel):
    event_name: Optional[str] = None
    event_date: Optional[str] = None
