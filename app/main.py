import os

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException

from app.connectors.base import HypervisorConnector
from app.connectors.esxi import ESXiConnector
from app.connectors.hyperv import HyperVConnector
from app.connectors.kvm import KVMConnector
from app.connectors.openstack import OpenStackConnector
from app.models import ActionResult, HypervisorHealth, VMResponse

load_dotenv()

app = FastAPI(
    title="Hybrid Hypervisor Management Platform",
    description="API unifiée pour administrer ESXi, Hyper-V, KVM et OpenStack",
    version="0.1.0",
)


def _build_connectors() -> dict[str, HypervisorConnector]:
    connectors: dict[str, HypervisorConnector] = {}

    if os.getenv("ESXI_HOST"):
        connectors["esxi"] = ESXiConnector(
            host=os.environ["ESXI_HOST"],
            user=os.environ["ESXI_USER"],
            password=os.environ["ESXI_PASSWORD"],
        )

    if os.getenv("HYPERV_HOST"):
        connectors["hyperv"] = HyperVConnector(
            host=os.environ["HYPERV_HOST"],
            user=os.environ["HYPERV_USER"],
            password=os.environ["HYPERV_PASSWORD"],
        )

    if os.getenv("KVM_HOST"):
        connectors["kvm"] = KVMConnector(
            host=os.environ["KVM_HOST"],
            user=os.environ["KVM_USER"],
            password=os.environ["KVM_PASSWORD"],
        )

    if os.getenv("OPENSTACK_AUTH_URL"):
        connectors["openstack"] = OpenStackConnector(
            auth_url=os.environ["OPENSTACK_AUTH_URL"],
            username=os.environ["OPENSTACK_USER"],
            password=os.environ["OPENSTACK_PASSWORD"],
            project_name=os.getenv("OPENSTACK_PROJECT", "admin"),
        )

    return connectors


CONNECTORS = _build_connectors()


def _get_connector(hypervisor: str) -> HypervisorConnector:
    connector = CONNECTORS.get(hypervisor)
    if connector is None:
        raise HTTPException(
            status_code=404,
            detail=f"Hyperviseur '{hypervisor}' inconnu ou non configuré. "
                    f"Disponibles : {list(CONNECTORS.keys())}",
        )
    return connector


@app.get("/hypervisors", response_model=list[HypervisorHealth])
def list_hypervisors():
    results = []
    for name, connector in CONNECTORS.items():
        results.append(HypervisorHealth(hypervisor=name, reachable=connector.health_check()))
    return results


@app.get("/vms", response_model=list[VMResponse])
def list_all_vms():
    all_vms = []
    for name, connector in CONNECTORS.items():
        try:
            all_vms.extend(connector.list_vms())
        except Exception:
            continue
    return all_vms


@app.get("/vms/{hypervisor}", response_model=list[VMResponse])
def list_vms_for_hypervisor(hypervisor: str):
    connector = _get_connector(hypervisor)
    try:
        return connector.list_vms()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@app.post("/vms/{hypervisor}/{vm_id}/start", response_model=ActionResult)
def start_vm(hypervisor: str, vm_id: str):
    connector = _get_connector(hypervisor)
    success = connector.start_vm(vm_id)
    return ActionResult(success=success, hypervisor=hypervisor, vm_id=vm_id, action="start")


@app.post("/vms/{hypervisor}/{vm_id}/stop", response_model=ActionResult)
def stop_vm(hypervisor: str, vm_id: str):
    connector = _get_connector(hypervisor)
    success = connector.stop_vm(vm_id)
    return ActionResult(success=success, hypervisor=hypervisor, vm_id=vm_id, action="stop")