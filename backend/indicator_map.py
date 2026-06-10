"""
指标 → 相关 ticker 映射
被 main.py 和 scheduler.py 共享，避免重复定义
"""

INDICATOR_TICKER_MAP = {
    # Phase 1-2 indicators
    "tsmc_monthly_revenue": ["TSM"],
    "tsmc_cowos_capacity": ["TSM"],
    "dram_contract_price": ["MU"],
    "nand_contract_price": ["MU"],
    "server_dram_price": ["MU"],
    "enterprise_ssd_price": ["MU"],
    "dram_industry_revenue": ["MU", "SK Hynix"],
    "hbm_trend": ["MU"],
    "memory_vs_foundry": ["TSM"],
    "global_semiconductor_sales": ["TSM", "NVDA"],
    "semi_equipment_billings": ["ASML", "AMAT"],
    "silicon_wafer_shipments": ["TSM"],
    "asml_backlog": ["ASML"],
    "nvidia_dc_revenue": ["NVDA"],
    # Phase 3 indicators
    "china_ic_import": ["TSM"],
    "china_ic_export": ["TSM"],
    "amazon_capex": ["AMZN"],
    "microsoft_capex": ["MSFT"],
    "google_capex": ["GOOGL"],
    "meta_capex": ["META"],
    "gpu_cloud_price_index": ["NVDA"],
    "synopsys_backlog": ["SNPS"],
    "cadence_backlog": ["CDNS"],
    "arrow_revenue": ["ON", "TXN"],
    "avnet_revenue": ["ON", "TXN"],
    "wpg_revenue": ["TSM"],
    "osat_cowos_capacity": ["TSM"],
    "osat_capex": ["TSM"],
    "ase_revenue": ["TSM"],
    # Phase 4: Taiwan ODM server monthly revenue (new)
    "quanta_monthly_revenue": ["NVDA", "SMCI"],
    "wistron_monthly_revenue": ["NVDA", "SMCI"],
    "inventec_monthly_revenue": ["NVDA"],
    "pegasron_monthly_revenue": ["NVDA"],
    "wiwynn_monthly_revenue": ["NVDA", "SMCI"],
    # Phase 4: ARM IP royalty (new)
    "arm_royalty_revenue": ["ARM"],
    "arm_chip_shipments": ["ARM"],
}
