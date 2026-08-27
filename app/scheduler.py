import asyncio

from app.connectors.base import HypervisorConnector
from app.database import record_health_check

CHECK_INTERVAL_SECONDS = 60


async def run_health_check_loop(connectors: dict[str, HypervisorConnector]) -> None:
    loop = asyncio.get_event_loop()
    while True:
        for name, connector in connectors.items():
            try:
                reachable = await loop.run_in_executor(None, connector.health_check)
            except Exception:
                reachable = False
            record_health_check(hypervisor=name, reachable=reachable)
        await asyncio.sleep(CHECK_INTERVAL_SECONDS)