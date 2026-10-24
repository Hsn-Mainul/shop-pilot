"""Real execution for the 'scheduled_job' automation kind (FR-AUTO-01), run on
a timer via Celery beat instead of in-request like the event-triggered rules
in app/services/automation_engine.py.
"""
from app.core.celery_app import celery_app
from app.db.session import SessionLocal
from app.models.automation import AutomationKind, AutomationRule
from app.services.automation_engine import ACTION_HANDLERS


@celery_app.task
def run_scheduled_jobs() -> dict:
    db = SessionLocal()
    try:
        rules = (
            db.query(AutomationRule)
            .filter(AutomationRule.kind == AutomationKind.SCHEDULED_JOB, AutomationRule.is_active.is_(True))
            .all()
        )
        ran = 0
        for rule in rules:
            handler = ACTION_HANDLERS.get(rule.action)
            rule.run_count += 1
            if handler is None:
                rule.failure_count += 1
                db.add(rule)
                continue
            try:
                handler(db, rule, {})
                ran += 1
            except Exception:
                rule.failure_count += 1
            db.add(rule)
        db.commit()
        return {"rules_considered": len(rules), "rules_ran": ran}
    finally:
        db.close()


celery_app.conf.beat_schedule = {
    "run-scheduled-automation-jobs-every-5-minutes": {
        "task": "app.tasks.automation_tasks.run_scheduled_jobs",
        "schedule": 300.0,
    },
    "dispatch-due-campaigns-every-minute": {
        "task": "app.tasks.campaign_tasks.dispatch_due_campaigns",
        "schedule": 60.0,
    },
}
