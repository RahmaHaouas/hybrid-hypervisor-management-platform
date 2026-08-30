from pydantic import BaseModel

from app.connectors.base import VMState


class VMResponse(BaseModel):
    id: str
    name: str
    state: VMState
    hypervisor: str
    cpu_count: int | None = None
    memory_mb: int | None = None
    ip_address: str | None = None


class HypervisorHealth(BaseModel):
    hypervisor: str
    reachable: bool


class ActionResult(BaseModel):
    success: bool
    hypervisor: str
    vm_id: str
    action: str
    
class UptimePoint(BaseModel):
    hypervisor: str
    reachable: bool
    checked_at: str


class ActivityEntry(BaseModel):
    username: str
    hypervisor: str
    vm_id: str
    action: str
    success: bool
    performed_at: str
    
class VMCreateRequest(BaseModel):
    name: str
    image: str | None = None
    flavor: str | None = None
    network: str | None = None