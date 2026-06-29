"""一次性跑完所有 pending 的 overseas 任务。"""
import logging
import time
from database import SessionLocal
from overseas_financial_collector import ensure_tasks, run_next_batch

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def main():
    db = SessionLocal()
    try:
        ensure_tasks(db)
        total = {"processed": 0, "success": 0, "failed": 0}
        while True:
            result = run_next_batch(db, tickers_per_run=3)
            if result["processed"] == 0:
                break
            for k in total:
                total[k] += result.get(k, 0)
            logger.info(f"Running total: {total}")
            time.sleep(1)
        logger.info(f"Backfill finished: {total}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
