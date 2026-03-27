"""
APScheduler Adapter — Inbound Adapter for Scheduling
Triggers scraper execution on a schedule.
"""
from datetime import datetime
import logging
from typing import Callable, Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from application.domain.services.scraping_service import ScrapingService
from application.ports.outbound.scraping.scraper_port import ScraperPort

logger = logging.getLogger(__name__)


class APSchedulerAdapter:
    """Inbound adapter: triggers scraper execution via cron schedules"""

    def __init__(self):
        self.scheduler = BackgroundScheduler(timezone="America/Sao_Paulo")

    def remove_all_jobs(self):
        """Remove all scheduled jobs"""
        self.scheduler.remove_all_jobs()
        logger.info("All scheduler jobs removed")

    def remove_jobs_by_prefix(self, prefix: str):
        """Remove only jobs whose id starts with prefix."""
        removed = 0
        for job in self.scheduler.get_jobs():
            if job.id and job.id.startswith(prefix):
                self.scheduler.remove_job(job.id)
                removed += 1
        logger.info(f"Removed {removed} jobs with prefix '{prefix}'")

    def add_job(
        self,
        *,
        func: Callable,
        cron_expression: str,
        job_id: str,
        name: str,
        args: Optional[list] = None,
    ):
        """Schedule a generic callable from a cron expression."""
        parts = cron_expression.split()
        if len(parts) != 5:
            raise ValueError(f"Invalid cron expression: {cron_expression}")

        trigger = CronTrigger(
            minute=parts[0],
            hour=parts[1],
            day=parts[2],
            month=parts[3],
            day_of_week=parts[4],
        )

        self.scheduler.add_job(
            func=func,
            trigger=trigger,
            args=args or [],
            id=job_id,
            name=name,
            replace_existing=True,
        )
        logger.info(f"Scheduled {name} ({job_id}): {cron_expression}")

    def add_scraper_job(
        self,
        scraper: ScraperPort,
        cron_expression: str,
        name: str,
        scraping_service: ScrapingService,
        job_id: Optional[str] = None,
    ):
        """Schedule a scraper to run on a cron expression"""
        self.add_job(
            func=scraping_service.execute_scraper,
            cron_expression=cron_expression,
            args=[scraper],
            job_id=job_id or name,
            name=name,
        )

    def add_one_off_job(
        self,
        *,
        func: Callable,
        job_id: str,
        name: str,
        run_at: datetime,
        args: Optional[list] = None,
    ):
        """Schedule a one-off callable for immediate or future execution."""
        self.scheduler.add_job(
            func=func,
            trigger="date",
            run_date=run_at,
            args=args or [],
            id=job_id,
            name=name,
            replace_existing=False,
        )
        logger.info("Scheduled one-off job %s (%s) for %s", name, job_id, run_at.isoformat())

    def start(self):
        """Start the scheduler"""
        logger.info("Starting scheduler...")
        for job in self.scheduler.get_jobs():
            logger.info(f"  - {job.name}: {job.trigger}")

        try:
            self.scheduler.start()
        except (KeyboardInterrupt, SystemExit):
            logger.info("Scheduler stopped")

    def shutdown(self):
        """Shutdown the scheduler"""
        self.scheduler.shutdown()
        logger.info("Scheduler shut down")
