import openstack

from app.connectors.base import HypervisorConnector, VMInfo, VMState

_STATE_MAP = {
    "ACTIVE": VMState.RUNNING,
    "SHUTOFF": VMState.STOPPED,
    "SUSPENDED": VMState.SUSPENDED,
    "PAUSED": VMState.SUSPENDED,
}


class OpenStackConnector(HypervisorConnector):
    def __init__(self, auth_url: str, username: str, password: str,
                 project_name: str = "admin", user_domain: str = "Default",
                 project_domain: str = "Default"):
        self._conn_kwargs = dict(
            auth_url=auth_url,
            username=username,
            password=password,
            project_name=project_name,
            user_domain_name=user_domain,
            project_domain_name=project_domain,
        )

    def _connect(self):
        return openstack.connect(**self._conn_kwargs)

    def health_check(self) -> bool:
        try:
            conn = self._connect()
            list(conn.identity.services())
            return True
        except Exception:
            return False

    def list_vms(self) -> list[VMInfo]:
        conn = self._connect()
        vms = []
        for server in conn.compute.servers():
            ip = None
            for addresses in (server.addresses or {}).values():
                if addresses:
                    ip = addresses[0].get("addr")
                    break
            vms.append(
                VMInfo(
                    id=server.id,
                    name=server.name,
                    state=_STATE_MAP.get(server.status, VMState.UNKNOWN),
                    hypervisor="openstack",
                    cpu_count=server.flavor.get("vcpus") if server.flavor else None,
                    memory_mb=server.flavor.get("ram") if server.flavor else None,
                    ip_address=ip,
                )
            )
        return vms

    def start_vm(self, vm_id: str) -> bool:
        try:
            conn = self._connect()
            conn.compute.start_server(vm_id)
            return True
        except Exception:
            return False

    def stop_vm(self, vm_id: str) -> bool:
        try:
            conn = self._connect()
            conn.compute.stop_server(vm_id)
            return True
        except Exception:
            return False