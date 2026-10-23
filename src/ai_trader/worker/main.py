import argparse
import time
from datetime import UTC, datetime

from sqlalchemy.dialects.postgresql import insert as postgres_insert

from ai_trader.config import get_settings
from ai_trader.infrastructure.database import SessionFactory
from ai_trader.infrastructure.models import WorkerHeartbeatModel


def heartbeat(worker_name: str = "primary") -> None:
    now = datetime.now(UTC)
    with SessionFactory.begin() as session:
        if session.bind and session.bind.dialect.name == "postgresql":
            statement = postgres_insert(WorkerHeartbeatModel).values(
                worker_name=worker_name, last_seen_at=now
            )
            session.execute(
                statement.on_conflict_do_update(
                    index_elements=[WorkerHeartbeatModel.worker_name],
                    set_={"last_seen_at": now},
                )
            )
        else:
            model = session.get(WorkerHeartbeatModel, worker_name)
            if model is None:
                session.add(WorkerHeartbeatModel(worker_name=worker_name, last_seen_at=now))
            else:
                model.last_seen_at = now


def run(once: bool = False) -> None:
    interval = get_settings().worker_heartbeat_seconds
    while True:
        heartbeat()
        if once:
            return
        time.sleep(interval)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the AI-Trader background worker")
    parser.add_argument("--once", action="store_true", help="write one heartbeat and exit")
    args = parser.parse_args()
    run(once=args.once)


if __name__ == "__main__":
    main()

