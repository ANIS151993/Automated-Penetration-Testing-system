from datetime import datetime

from pydantic import BaseModel


class InventoryHostRead(BaseModel):
    target: str
    operations: list[str]
    last_validated_at: datetime
    os_guess: str | None = None


class InventoryServiceRead(BaseModel):
    target: str
    port: int
    protocol: str
    operations: list[str]
    last_validated_at: datetime
    service_name: str | None = None
    details: str | None = None


class InventoryRead(BaseModel):
    hosts: list[InventoryHostRead]
    services: list[InventoryServiceRead]
