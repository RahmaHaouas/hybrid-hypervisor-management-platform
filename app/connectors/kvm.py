import re
import time

import paramiko

import logging

from app.connectors.base import HypervisorConnector, VMInfo, VMState

logger = logging.getLogger(__name__)

_STATE_MAP = {
    "running": VMState.RUNNING,
    "shut off": VMState.STOPPED,
    "paused": VMState.SUSPENDED,
}

_NAME_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")


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
        except RuntimeError:
            pass

        time.sleep(5)

        state = self._get_vm_state(vm_id)
        if state == VMState.STOPPED:
            return True

        try:
            self._run_ssh(f"destroy {vm_id}")
            return True
        except RuntimeError:
            return False

    def create_vm(
        self,
        name: str,
        template_image: str = "/var/lib/libvirt/images/cirros.qcow2",
        ram_mb: int = 512,
        vcpus: int = 1,
    ) -> bool:
        if not _NAME_PATTERN.match(name):
            raise ValueError(
                "Nom de VM invalide : lettres, chiffres, tirets et underscores uniquement"
            )

        disk_path = f"/var/lib/libvirt/images/{name}.qcow2"
        commands = [
            f"cp {template_image} {disk_path}",
            f"virt-install --connect qemu:///system --name {name} "
            f"--memory {ram_mb} --vcpus {vcpus} --disk path={disk_path} "
            f"--network network=default "
            f"--import --os-variant generic --noautoconsole",
        ]
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            client.connect(self.host, username=self.user, password=self.password, timeout=10)
            for command in commands:
                _, stdout, stderr = client.exec_command(command)
                exit_status = stdout.channel.recv_exit_status()
                if exit_status != 0:
                    err = stderr.read().decode(errors="ignore")
                    raise RuntimeError(f"Commande échouée ({exit_status}): {err.strip()}")
            return True
        except Exception:
            logger.exception("Échec de la création de VM KVM '%s'", name)
            return False
        finally:
            client.close()

    def _get_vm_state(self, vm_id: str) -> VMState:
        raw = self._run_ssh("list --all")
        for line in raw.strip().splitlines()[2:]:
            parts = line.split(None, 2)
            if len(parts) >= 3 and parts[1] == vm_id:
                return _STATE_MAP.get(parts[2].strip(), VMState.UNKNOWN)
        return VMState.UNKNOWN