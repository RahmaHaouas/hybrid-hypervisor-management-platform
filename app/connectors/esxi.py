import logging
import re

import ssl

from pyVim.connect import SmartConnect, Disconnect
from pyVmomi import vim

from app.connectors.base import HypervisorConnector, VMInfo, VMState

_STATE_MAP = {
    vim.VirtualMachinePowerState.poweredOn: VMState.RUNNING,
    vim.VirtualMachinePowerState.poweredOff: VMState.STOPPED,
    vim.VirtualMachinePowerState.suspended: VMState.SUSPENDED,
}

logger = logging.getLogger(__name__)

_NAME_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")


class ESXiConnector(HypervisorConnector):
    def __init__(self, host: str, user: str, password: str):
        self.host = host
        self.user = user
        self.password = password
        self._ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS)
        self._ssl_context.verify_mode = ssl.CERT_NONE

    def _connect(self):
        return SmartConnect(
            host=self.host,
            user=self.user,
            pwd=self.password,
            sslContext=self._ssl_context,
        )

    def health_check(self) -> bool:
        try:
            si = self._connect()
            Disconnect(si)
            return True
        except Exception:
            return False

    def list_vms(self) -> list[VMInfo]:
        si = self._connect()
        try:
            content = si.RetrieveContent()
            container = content.viewManager.CreateContainerView(
                content.rootFolder, [vim.VirtualMachine], True
            )
            vms = []
            for vm in container.view:
                summary = vm.summary
                vms.append(
                    VMInfo(
                        id=summary.config.instanceUuid or vm._moId,
                        name=summary.config.name,
                        state=_STATE_MAP.get(summary.runtime.powerState, VMState.UNKNOWN),
                        hypervisor="esxi",
                        cpu_count=summary.config.numCpu,
                        memory_mb=summary.config.memorySizeMB,
                        ip_address=summary.guest.ipAddress if summary.guest else None,
                    )
                )
            container.Destroy()
            return vms
        finally:
            Disconnect(si)

    def _find_vm(self, si, vm_id: str):
        content = si.RetrieveContent()
        container = content.viewManager.CreateContainerView(
            content.rootFolder, [vim.VirtualMachine], True
        )
        try:
            for vm in container.view:
                if vm.summary.config.instanceUuid == vm_id or vm._moId == vm_id:
                    return vm
        finally:
            container.Destroy()
        return None

    def start_vm(self, vm_id: str) -> bool:
        si = self._connect()
        try:
            vm = self._find_vm(si, vm_id)
            if vm is None:
                return False
            vm.PowerOnVM_Task()
            return True
        except vim.fault.RestrictedVersion:
                return False
        finally:
            Disconnect(si)
            
    

    def stop_vm(self, vm_id: str) -> bool:
        si = self._connect()
        try:
            vm = self._find_vm(si, vm_id)
            if vm is None:
                return False
            vm.PowerOffVM_Task()
            return True
        except vim.fault.RestrictedVersion:
                return False
        finally:
            Disconnect(si)
            
    def create_vm(
        self,
        name: str,
        ram_mb: int = 512,
        vcpus: int = 1,
        datastore: str = "datastore1",
    ) -> bool:
        if not _NAME_PATTERN.match(name):
            raise ValueError(
                "Nom de VM invalide : lettres, chiffres, tirets et underscores uniquement"
            )

        si = self._connect()
        try:
            content = si.RetrieveContent()
            datacenter = content.rootFolder.childEntity[0]
            vm_folder = datacenter.vmFolder
            resource_pool = datacenter.hostFolder.childEntity[0].resourcePool

            vmx_file = vim.vm.FileInfo(
                logDirectory=None,
                snapshotDirectory=None,
                suspendDirectory=None,
                vmPathName=f"[{datastore}]",
            )

            config = vim.vm.ConfigSpec(
                name=name,
                memoryMB=ram_mb,
                numCPUs=vcpus,
                files=vmx_file,
                guestId="otherGuest64",
                version="vmx-19",
            )

            task = vm_folder.CreateVM_Task(config=config, pool=resource_pool)
            return True
        except vim.fault.RestrictedVersion:
            logger.warning("Création de VM ESXi bloquée par restriction de licence")
            raise NotImplementedError(
                "Création de VM non disponible sur cet hôte ESXi : licence gratuite/standalone restreinte (vCenter requis)."
        )
        except Exception:
            logger.exception("Échec de la création de VM ESXi '%s'", name)
            return False
        finally:
            Disconnect(si)