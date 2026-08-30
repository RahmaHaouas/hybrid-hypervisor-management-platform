import logging
import re

import winrm

from app.connectors.base import HypervisorConnector, VMInfo, VMState

logger = logging.getLogger(__name__)

_STATE_MAP = {
    "Running": VMState.RUNNING,
    "Off": VMState.STOPPED,
    "Saved": VMState.SUSPENDED,
    "Paused": VMState.SUSPENDED,
}

_NAME_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")

_TEMPLATE_VHDX = r"C:\Users\Public\Documents\Hyper-V\Virtual hard disks\test-vm-hyperv.vhdx"
_VHD_DIR = r"C:\Users\Public\Documents\Hyper-V\Virtual hard disks"
_SWITCH_NAME = "vSwitch-External"


class HyperVConnector(HypervisorConnector):
    def __init__(self, host: str, user: str, password: str):
        self.host = host
        self.user = user
        self.password = password

    def _run_ps(self, script: str) -> str:
        session = winrm.Session(self.host, auth=(self.user, self.password), transport="ntlm")
        result = session.run_ps(script)
        if result.status_code != 0:
            raise RuntimeError(result.std_err.decode(errors="ignore"))
        return result.std_out.decode(errors="ignore")

    def health_check(self) -> bool:
        try:
            self._run_ps("Get-VM | Select-Object -First 1")
            return True
        except Exception:
            return False

    def list_vms(self) -> list[VMInfo]:
        script = (
            "Get-VM | Select-Object Id, Name, State, ProcessorCount, MemoryAssigned "
            "| ConvertTo-Csv -NoTypeInformation"
        )
        raw = self._run_ps(script)
        lines = [l for l in raw.strip().splitlines() if l.strip()]
        vms = []
        if len(lines) <= 1:
            return vms
        for line in lines[1:]:
            fields = [f.strip('"') for f in line.split(",")]
            vm_id, name, state, cpu_count, memory_bytes = fields
            vms.append(
                VMInfo(
                    id=vm_id,
                    name=name,
                    state=_STATE_MAP.get(state, VMState.UNKNOWN),
                    hypervisor="hyperv",
                    cpu_count=int(cpu_count) if cpu_count else None,
                    memory_mb=int(int(memory_bytes) / 1_048_576) if memory_bytes else None,
                )
            )
        return vms

    def start_vm(self, vm_id: str) -> bool:
        try:
            self._run_ps(f"Start-VM -Id '{vm_id}'")
            return True
        except RuntimeError:
            return False

    def stop_vm(self, vm_id: str) -> bool:
        try:
            self._run_ps(f"Stop-VM -Id '{vm_id}' -Force")
            return True
        except RuntimeError:
            return False

    def create_vm(
        self,
        name: str,
        ram_mb: int = 512,
        vcpus: int = 1,
    ) -> bool:
        if not _NAME_PATTERN.match(name):
            raise ValueError(
                "Nom de VM invalide : lettres, chiffres, tirets et underscores uniquement"
            )

        new_vhd_path = f"{_VHD_DIR}\\{name}.vhdx"
        ram_bytes = ram_mb * 1_048_576

        script = (
            f"Copy-Item -Path '{_TEMPLATE_VHDX}' -Destination '{new_vhd_path}' -ErrorAction Stop; "
            f"New-VM -Name '{name}' -MemoryStartupBytes {ram_bytes} -VHDPath '{new_vhd_path}' -Generation 1 -SwitchName '{_SWITCH_NAME}' -ErrorAction Stop; "
            f"Set-VMProcessor -VMName '{name}' -Count {vcpus} -ErrorAction Stop; "
            f"Start-VM -Name '{name}' -ErrorAction Stop"
        )

        try:
            self._run_ps(script)
            return True
        except RuntimeError:
            logger.exception("Échec de la création de VM Hyper-V '%s'", name)
            return False