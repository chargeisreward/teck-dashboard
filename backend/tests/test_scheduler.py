"""测试海外采集定时调度的频率与参数。

设计动机：生产 IP 容易被 yfinance 限流，单次跑太密集会失败 / 单次跑太少要等很久。
当前策略：每 6 小时一次（4x/天），tickers_per_run=2，每天约 8 次 yfinance 调用，
可平衡 6h 限流退避窗口与覆盖速度。
"""
import scheduler as s


def test_init_scheduler_registers_overseas_job():
    """init_scheduler 应注册 refresh_overseas_financials，且 cron 是 4x/天。"""
    # init_scheduler 会启动 scheduler；如果已有 job 则 replace_existing=True
    s.init_scheduler()
    job = next((j for j in s.scheduler.get_jobs() if j.id == "refresh_overseas_financials"), None)
    assert job is not None, "overseas refresh job 未注册"
    # cron trigger，hour 字段应为 '3,9,15,21'
    # 不同 apscheduler 版本字段可能不同；用 str() 兜底
    assert "3,9,15,21" in str(job.trigger), \
        f"overseas cron 应为 3,9,15,21，实际: {job.trigger}"


def test_refresh_overseas_financials_uses_conservative_batch_size():
    """refresh_overseas_financials_slowly 调用 run_next_batch 用 tickers_per_run=2。

    设计动机：生产 IP 限流频繁，3 个 ticker 一批太密集容易整批被 ban。
    2 个 ticker 一批 + 6h backoff 间隔，对限流 IP 更友好。
    """
    import inspect
    src = inspect.getsource(s.refresh_overseas_financials_slowly)
    assert "tickers_per_run=2" in src, \
        f"refresh_overseas_financials_slowly 应传 tickers_per_run=2，实际:\n{src}"