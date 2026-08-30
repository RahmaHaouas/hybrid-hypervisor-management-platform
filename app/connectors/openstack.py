import logging
import re

import openstack

from app.connectors.base import HypervisorConnector, VMInfo, VMState

logger = logging.getLogger(__name__)

_STATE_MAP = {
    "ACTIVE": VMState.RUNNING,
    "SHUTOFF": VMState.STOPPED,
    "SUSPENDED": VMState.SUSPENDED,
    "PAUSED": VMState.SUSPENDED,
}

_NAME_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")


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

    def create_vm(
        self,
        name: str,
        image: str = "cirros-0.6.2-x86_64-disk",
        flavor: str = "m1.tiny",
        network: str = "private",
    ) -> bool:
        if not _NAME_PATTERN.match(name):
            raise ValueError(
                "Nom de VM invalide : lettres, chiffres, tirets et underscores uniquement"
            )

        try:
            conn = self._connect()

            image_obj = conn.compute.find_image(image)
            if image_obj is None:
                raise ValueError(f"Image introuvable : '{image}'")

            flavor_obj = conn.compute.find_flavor(flavor)
            if flavor_obj is None:
                raise ValueError(f"Flavor introuvable : '{flavor}'")

            network_obj = conn.network.find_network(network)
            if network_obj is None:
                raise ValueError(f"Réseau introuvable : '{network}'")

            conn.compute.create_server(
                name=name,
                image_id=image_obj.id,
                flavor_id=flavor_obj.id,
                networks=[{"uuid": network_obj.id}],
            )
            return True
        except ValueError:
            raise
        except Exception:
            logger.exception("Échec de la création de VM OpenStack '%s'", name)
            return False