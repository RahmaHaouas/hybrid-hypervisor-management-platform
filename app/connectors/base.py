from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum


class VMState(str, Enum):
    RUNNING = "running"
    STOPPED = "stopped"
    SUSPENDED = "suspended"
    UNKNOWN = "unknown"


@dataclass
class VMInfo:
    id: str
    name: str
    state: VMState
    hypervisor: str
    cpu_count: int | None = None
    memory_mb: int | None = None
    ip_address: str | None = None


class HypervisorConnector(ABC):
    @abstractmethod
    def list_vms(self) -> list[VMInfo]:
        raise NotImplementedError

    @abstractmethod
    def start_vm(self, vm_id: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    def stop_vm(self, vm_id: str) -> bool:
        raise NotImplementedError
    
    def create_vm(self, name: str, **kwargs) -> bool:
        raise NotImplementedError(f"create_vm non implémenté pour {self.__class__.__name__}")

    @abstractmethod
    def health_check(self) -> bool:
        raise NotImplementedError