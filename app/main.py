import os

from dotenv import load_dotenv

load_dotenv()

import asyncio
import contextlib

from fastapi import Depends, FastAPI, HTTPException
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.auth import create_access_token, decode_access_token, verify_password
from app.connectors.base import HypervisorConnector
from app.connectors.esxi import ESXiConnector
from app.connectors.hyperv import HyperVConnector
from app.connectors.kvm import KVMConnector
from app.connectors.openstack import OpenStackConnector
from app.database import get_activity_log, get_uptime_history, init_db, record_activity
from app.models import ActionResult, ActivityEntry, HypervisorHealth, UptimePoint, VMResponse
from app.scheduler import run_health_check_loop

ADMIN_USERNAME = os.environ["ADMIN_USERNAME"]
ADMIN_PASSWORD_HASH = os.environ["ADMIN_PASSWORD_HASH"]

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


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

init_db()


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(run_health_check_loop(CONNECTORS))
    yield
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task


app = FastAPI(
    title="Hybrid Hypervisor Management Platform",
    description="API unifiée pour administrer ESXi, Hyper-V, KVM et OpenStack",
    version="0.1.0",
    lifespan=lifespan,
)

app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
def serve_dashboard():
    return FileResponse("static/index.html")


def get_current_username(token: str = Depends(oauth2_scheme)) -> str:
    username = decode_access_token(token)
    if username is None:
        raise HTTPException(
            status_code=401,
            detail="Token invalide ou expiré",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return username


def _get_connector(hypervisor: str) -> HypervisorConnector:
    connector = CONNECTORS.get(hypervisor)
    if connector is None:
        raise HTTPException(
            status_code=404,
            detail=f"Hyperviseur '{hypervisor}' inconnu ou non configuré. "
                    f"Disponibles : {list(CONNECTORS.keys())}",
        )
    return connector


@app.post("/token")
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    if form_data.username != ADMIN_USERNAME:
        raise HTTPException(status_code=401, detail="Identifiants invalides")
    if not verify_password(form_data.password, ADMIN_PASSWORD_HASH):
        raise HTTPException(status_code=401, detail="Identifiants invalides")

    token = create_access_token(username=form_data.username)
    return {"access_token": token, "token_type": "bearer"}


@app.get("/hypervisors", response_model=list[HypervisorHealth])
def list_hypervisors(current_user: str = Depends(get_current_username)):
    results = []
    for name, connector in CONNECTORS.items():
        results.append(HypervisorHealth(hypervisor=name, reachable=connector.health_check()))
    return results


@app.get("/vms", response_model=list[VMResponse])
def list_all_vms(current_user: str = Depends(get_current_username)):
    all_vms = []
    for name, connector in CONNECTORS.items():
        try:
            all_vms.extend(connector.list_vms())
        except Exception:
            continue
    return all_vms


@app.get("/vms/{hypervisor}", response_model=list[VMResponse])
def list_vms_for_hypervisor(hypervisor: str, current_user: str = Depends(get_current_username)):
    connector = _get_connector(hypervisor)
    try:
        return connector.list_vms()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@app.post("/vms/{hypervisor}/{vm_id}/start", response_model=ActionResult)
def start_vm(hypervisor: str, vm_id: str, current_user: str = Depends(get_current_username)):
    connector = _get_connector(hypervisor)
    success = connector.start_vm(vm_id)
    record_activity(username=current_user, hypervisor=hypervisor, vm_id=vm_id, action="start", success=success)
    return ActionResult(success=success, hypervisor=hypervisor, vm_id=vm_id, action="start")


@app.post("/vms/{hypervisor}/{vm_id}/stop", response_model=ActionResult)
def stop_vm(hypervisor: str, vm_id: str, current_user: str = Depends(get_current_username)):
    connector = _get_connector(hypervisor)
    success = connector.stop_vm(vm_id)
    record_activity(username=current_user, hypervisor=hypervisor, vm_id=vm_id, action="stop", success=success)
    return ActionResult(success=success, hypervisor=hypervisor, vm_id=vm_id, action="stop")


@app.get("/uptime", response_model=list[UptimePoint])
def get_uptime(current_user: str = Depends(get_current_username)):
    return get_uptime_history()


@app.get("/activity-log", response_model=list[ActivityEntry])
def get_activity(current_user: str = Depends(get_current_username)):
    return get_activity_log()