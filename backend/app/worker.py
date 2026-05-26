import time
from datetime import datetime, timezone

from sqlalchemy import select

from .config import get_settings
from .database import Base, SessionLocal, engine
from .migrations import apply_lightweight_migrations
from .models import ResearchEvent, ResearchRun, RunStatus
from .research_graph import ResearchGraphRunner, add_event


def claim_next_run():
    db = SessionLocal()
    try:
        run = db.scalar(
            select(ResearchRun)
            .where(ResearchRun.status == RunStatus.queued.value)
            .order_by(ResearchRun.approved_at.asc().nulls_last(), ResearchRun.created_at.asc())
            .with_for_update(skip_locked=True)
        )
        if run is None:
            db.rollback()
            return None
        run.status = RunStatus.running.value
        run.started_at = datetime.now(timezone.utc)
        db.commit()
        run_id = run.id
        return run_id
    finally:
        db.close()


def mark_failed(run_id, message: str) -> None:
    db = SessionLocal()
    try:
        run = db.get(ResearchRun, run_id)
        if run is not None:
            run.status = RunStatus.failed.value
            run.error_message = message
            run.completed_at = datetime.now(timezone.utc)
            db.commit()
            add_event(db, run.id, "run_failed", "Research failed", message)
    finally:
        db.close()


def process_run(run_id) -> None:
    settings = get_settings()
    db = SessionLocal()
    try:
        ResearchGraphRunner(db, settings).run(run_id)
    except Exception as exc:
        db.rollback()
        try:
            add_event(db, run_id, "run_failed", "Research failed", str(exc))
            run = db.get(ResearchRun, run_id)
            if run is not None:
                run.status = RunStatus.failed.value
                run.error_message = str(exc)
                run.completed_at = datetime.now(timezone.utc)
                db.commit()
        except Exception:
            mark_failed(run_id, str(exc))
    finally:
        db.close()


def main() -> None:
    settings = get_settings()
    Base.metadata.create_all(bind=engine)
    apply_lightweight_migrations(engine)
    print("Research worker started")
    while True:
        run_id = claim_next_run()
        if run_id is None:
            time.sleep(settings.worker_poll_interval_seconds)
            continue
        process_run(run_id)


if __name__ == "__main__":
    main()
