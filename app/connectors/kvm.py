import paramiko

from app.connectors.base import HypervisorConnector, VMInfo, VMState

_STATE_MAP = {
    "running": VMState.RUNNING,
    "shut off": VMState.STOPPED,
    "paused": VMState.SUSPENDED,
}


class KVMConnector(HypervisorConnector):
    def __init__(self, host: str, user: str, password: str):
        self.host = host
        self.user = user
        self.password = password

    def _run_ssh(self, command: str) -> str:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            client.connect(self.host, username=self.user, password=self.password, timeout=10)
            full_command = f"virsh --connect qemu:///system {command}"
            _, stdout, stderr = client.exec_command(full_command)
            err = stderr.read().decode(errors="ignore")
            out = stdout.read().decode(errors="ignore")
            if err.strip():
                raise RuntimeError(err.strip())
            return out
        finally:
            client.close()

    def health_check(self) -> bool:
        try:
            self._run_ssh("version")
            return True
        except Exception:
            return False

    def list_vms(self) -> list[VMInfo]:
        raw = self._run_ssh("list --all")
        vms = []
        lines = raw.strip().splitlines()
        for line in lines[2:]:
            parts = line.split(None, 2)
            if len(parts) < 3:
                continue
            vm_id, name, state = parts[0], parts[1], parts[2].strip()
            vms.append(
                VMInfo(
                    id=name,
                    name=name,
                    state=_STATE_MAP.get(state, VMState.UNKNOWN),
                    hypervisor="kvm",
                )
            )
        return vms

    def start_vm(self, vm_id: str) -> bool:
        try:
            self._run_ssh(f"start {vm_id}")
            return True
        except RuntimeError:
            return False

    def stop_vm(self, vm_id: str) -> bool:
        try:
            self._run_ssh(f"shutdown {vm_id}")
            return True
        except RuntimeError:
            return False