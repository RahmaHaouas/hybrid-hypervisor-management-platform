import winrm

from app.connectors.base import HypervisorConnector, VMInfo, VMState

_STATE_MAP = {
    "Running": VMState.RUNNING,
    "Off": VMState.STOPPED,
    "Saved": VMState.SUSPENDED,
    "Paused": VMState.SUSPENDED,
}


class HyperVConnector(HypervisorConnector):
    def __init__(self, host: str, user: str, password: str):
        self.session = winrm.Session(host, auth=(user, password), transport="ntlm")

    def _run_ps(self, script: str) -> str:
        result = self.session.run_ps(script)
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