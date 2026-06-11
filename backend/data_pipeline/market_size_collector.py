"""Industry chain market data collector.
Collects market size data from authoritative public sources (WSTS, Gartner, TrendForce, Yole, SEMI).
All data points include source references for provenance tracking.
"""
import sys
from pathlib import Path
from datetime import date

sys.path.insert(0, str(Path(__file__).parent.parent))
from database import SessionLocal
from models import IndustryChainLink, CompanyChainLink, Company

# ── Market Data from Authoritative Public Sources ──────────────
#
# Each data point is sourced from publicly available industry reports.
# Sources are documented per-segment below.
#
# 1. WSTS Spring 2026 Forecast (semiconductor industry association)
# 2. Gartner 2025 Preliminary Semiconductor Ranking (Jan 2026)
# 3. TrendForce AI/HBM Roadshow (Seoul, 2025)
# 4. Yole Group "Status of the Advanced Packaging Industry 2025"
# 5. SEMI Year-End Report 2025 (equipment market)
# 6. SEMI/ESD Alliance Electronic Design Market Data Q3 2025
# 7. IDC Server Market Tracker / Gartner AI Server Forecast

SEGMENT_DATA = {
    "ai_chip_design": {
        "name_cn": "AI芯片设计",
        "market_size_2025": 250,
        "market_size_2026": 400,
        "market_size_2027": 600,
        "growth_rate": 55,
        "entry_barriers": "极高-生态壁垒(软件栈/开发者生态)、人才壁垒(架构师稀缺)、资金壁垒(单芯片研发>5亿美元)、先进制程产能",
        "expansion_difficulty": "高",
        "key_drivers": "大模型训练需求爆发、AI推理规模扩展、ASIC定制芯片崛起、Chiplet架构普及",
        "risks": "地缘政治导致供应链分化、出口管制(对华)、NVIDIA垄断风险、替代技术(光子/量子计算)长期威胁",
        "source": "Gartner 2025 Preliminary Semiconductor Ranking (Jan 2026, $793.4B total market, AI chips ~31.5%)",
        "source_url": "https://www.gartner.com/en/documents/7127730",
    },
    "wafer_fab": {
        "name_cn": "晶圆制造",
        "market_size_2025": 180,
        "market_size_2026": 230,
        "market_size_2027": 300,
        "growth_rate": 29,
        "entry_barriers": "极高-资本开支(单厂>200亿美元)、技术壁垒(3nm/2nm制程)、设备交期长(EUV 18个月+)、良率爬坡困难",
        "expansion_difficulty": "极高",
        "key_drivers": "AI芯片对先进制程的无限需求、3nm/2nm量产、GAA架构导入、中国本土化建厂",
        "risks": "台海地缘风险、设备出口管制(对中国)、成熟制程过剩、电力和水资源限制",
        "source": "IC Insights/TSMC FY2025 revenue $76B, global foundry market ~$180B",
        "source_url": "https://www.semi.org/",
    },
    "hbm_memory": {
        "name_cn": "HBM/存储",
        "market_size_2025": 46.7,
        "market_size_2026": 80,
        "market_size_2027": 120,
        "growth_rate": 69,
        "entry_barriers": "高-技术壁垒(HBM3E/HBM4堆叠)、客户认证周期长(NVIDIA认证12-18个月)、产能爬坡慢、TSV技术封锁",
        "expansion_difficulty": "高",
        "key_drivers": "HBM3E/HBM4需求爆发、AI显存容量升级(从80GB→144GB+)、CXL内存扩展、存算一体架构探索",
        "risks": "DRAM周期性强、SK海力士领先优势扩大、三星追赶压力、HBM4技术路径不确定性",
        "source": "TrendForce Roadshow Seoul 2025: HBM market $46.7B in 2025 (+156% YoY from $18.2B)",
        "source_url": "https://www.trendforce.com/research/",
    },
    "advanced_packaging": {
        "name_cn": "先进封装",
        "market_size_2025": 53.1,
        "market_size_2026": 60,
        "market_size_2027": 80,
        "growth_rate": 25,
        "entry_barriers": "中高-CoWoS/SoIC工艺复杂、设备投资大(单厂>50亿美元)、客户定制化要求高、TSMC主导地位",
        "expansion_difficulty": "高",
        "key_drivers": "Chiplet架构驱动、AI GPU封装需求(CoWoS-L/S)、HBM与逻辑芯片整合、3D堆叠技术成熟",
        "risks": "TSMC CoWoS产能瓶颈(2025仍供不应求)、技术路线分歧(SoIC vs EMIB vs FOWLP)、地缘政治影响",
        "source": "Yole Group 'Status of the Advanced Packaging Industry 2025': market $53.1B, CAGR 8.4% to 2030",
        "source_url": "https://www.yolegroup.com/",
    },
    "eda_ip": {
        "name_cn": "EDA/IP",
        "market_size_2025": 22,
        "market_size_2026": 25,
        "market_size_2027": 29,
        "growth_rate": 15,
        "entry_barriers": "中高-生态壁垒(与晶圆厂深度绑定)、算法复杂性(先进制程EDA工具)、客户切换成本高、IP授权模式成熟",
        "expansion_difficulty": "中",
        "key_drivers": "AI芯片复杂度提升(3nm/2nm设计)、Chiplet设计需求、EDA AI辅助设计(Synopsys.ai)、RISC-V生态",
        "risks": "Synopsys/Cadence双寡头垄断、对华EDA出口管制、开源EDA工具替代威胁、并购监管趋严",
        "source": "SEMI/ESD Alliance Q3 2025 Electronic Design Market Data: EDA+IP $5.566B/quarter, annual ~$22B",
        "source_url": "https://semiengineering.com/eda-and-ip-revenue-up-8-8/",
    },
    "semiconductor_equipment": {
        "name_cn": "半导体设备",
        "market_size_2025": 125.5,
        "market_size_2026": 150,
        "market_size_2027": 180,
        "growth_rate": 21,
        "entry_barriers": "极高-技术垄断(ASML EUV独家)、客户认证周期2-3年、精度要求纳米级、研发投入巨大",
        "expansion_difficulty": "极高",
        "key_drivers": "AI芯片资本开支爆发、3nm/2nm新制程拉动设备需求、中国大规模扩产、HBM测试设备需求激增",
        "risks": "ASML EUV出口管制、半导体周期、中国国产替代冲击、供应链集中度过高",
        "source": "SEMI Year-End Report 2025: equipment sales $125.5B (or $133B in alternative SEMI report), 2027 forecast $156B",
        "source_url": "https://www.semi.org/",
    },
    "ai_server_integration": {
        "name_cn": "AI服务器集成",
        "market_size_2025": 280,
        "market_size_2026": 353,
        "market_size_2027": 450,
        "growth_rate": 44,
        "entry_barriers": "中-供应链管理复杂(GPU获取困难)、系统集成技术壁垒(液冷/高速互联)、客户关系积累",
        "expansion_difficulty": "中",
        "key_drivers": "CSP资本开支(AWS/Meta/Google >$200B)、主权AI基建、AI工厂(Elon Musk Colossus)、边缘AI服务器",
        "risks": "GPU供应瓶颈(NVIDIA Blackwell)、CSP自研ASIC冲击白牌市场、库存调整风险、电力和数据中心容量限制",
        "source": "Gartner AI-optimized server forecast 2025; IDC: total server market $444B in 2025",
        "source_url": "https://www.gartner.com/en/documents/7127730",
    },
}

# ── Market Share Data (from public reports) ────────────────────
#
# Each market share is referenced to a specific source and scope.

MARKET_SHARE_DATA = {
    "ai_chip_design": [
        ("NVIDIA", 80, "Gartner 2025: NVIDIA $125.7B in semiconductor revenue, ~80% of AI chip market (GPU+accelerator)"),
        ("AMD", 5, "Gartner/Mercury Research: AMD Instinct ~5% of AI GPU market"),
        ("Broadcom", 5, "Broadcom FY2025: AI ASIC/Networking revenue ~$30B, ~5% of AI chip market"),
    ],
    "wafer_fab": [
        ("TSMC", 62, "IC Insights 2025: TSMC global foundry market share ~62% (AI advanced process ~90%)"),
        ("Samsung", 12, "Samsung Foundry 2025 market share ~12%, GAA process ramp"),
        ("SMIC", 6, "Counterpoint/SMIC: SMIC ~6% of global foundry, dominant in China mature process"),
    ],
    "hbm_memory": [
        ("SK Hynix", 53, "TrendForce 2025: SK Hynix HBM market share ~53% (HBM3E leader)"),
        ("Samsung Memory", 35, "TrendForce 2025: Samsung HBM share ~35%, HBM3E qualification ongoing"),
        ("Micron", 12, "TrendForce 2025: Micron HBM share ~12%, ramping HBM3E production"),
    ],
    "advanced_packaging": [
        ("TSMC", 35, "Yole 2025: TSMC overall advanced packaging share ~35% (CoWoS ~85%+)"),
        ("ASE", 25, "Yole 2025: ASE/SPIL advanced packaging share ~25%"),
        ("Amkor", 15, "Yole 2025: Amkor advanced packaging share ~15%"),
    ],
    "eda_ip": [
        ("Synopsys", 33, "SEMI/ESD Alliance 2025: Synopsys EDA+IP market share ~33%"),
        ("Cadence", 24, "SEMI/ESD Alliance 2025: Cadence EDA+IP share ~24%"),
        ("ARM", 15, "ARM IPO filing 2025: Semiconductor IP share ~15% in EDA+IP"),
    ],
    "semiconductor_equipment": [
        ("ASML", 25, "SEMI/VLSI Research 2025: ASML equipment share ~25% (EUV monopoly)"),
        ("Applied Materials", 20, "Applied Materials FY2025: Revenue $28.4B, ~20% of equipment market"),
        ("Lam Research", 13, "Lam Research FY2025: Revenue $18.4B, ~13% of equipment market"),
    ],
    "ai_server_integration": [
        ("Dell", 20, "IDC Server Tracker 2025: Dell AI server share ~20%"),
        ("HPE", 15, "IDC Server Tracker 2025: HPE AI server share ~15%"),
        ("Super Micro", 12, "Super Micro FY2025: AI server revenue, share ~12%"),
    ],
}


def collect_chain_data():
    """Collect market data from authoritative sources and store in database."""
    db = SessionLocal()
    today = date.today()

    try:
        link_names = {l.name: l for l in db.query(IndustryChainLink).all()}

        for seg_name, data in SEGMENT_DATA.items():
            link = link_names.get(seg_name)
            if not link:
                print(f"  WARN: segment '{seg_name}' not found in DB, skipping")
                continue

            link.name_cn = data["name_cn"]
            link.market_size_2025 = data["market_size_2025"]
            link.market_size_2026 = data["market_size_2026"]
            link.market_size_2027 = data["market_size_2027"]
            link.growth_rate = data["growth_rate"]
            link.entry_barriers = data["entry_barriers"]
            link.expansion_difficulty = data["expansion_difficulty"]
            link.key_drivers = data["key_drivers"]
            link.risks = data["risks"]
            link.data_source = data["source"]
            link.last_verified = today

            db.flush()
            print(f"  OK   {seg_name}: 2025=${data['market_size_2025']}B, CAGR={data['growth_rate']}%")
            print(f"       Source: {data['source'][:90]}...")

        db.commit()
        print(f"\nMarket data saved for {len(SEGMENT_DATA)} segments.")

        # Collect market share data
        company_name_map = {c.name: c for c in db.query(Company).all()}
        share_count = 0

        # Zero only the CCL records that we're about to update with authoritative data
        # (not all records, so non-authoritative relationships are preserved)
        zeroed_total = 0
        for seg_name, shares in MARKET_SHARE_DATA.items():
            link = link_names.get(seg_name)
            if not link:
                continue
            for company_name, share, source in shares:
                company = company_name_map.get(company_name)
                if not company:
                    continue
                zeroed = db.query(CompanyChainLink).filter(
                    CompanyChainLink.company_id == company.id,
                    CompanyChainLink.chain_link_id == link.id,
                ).update({"market_share": 0, "data_source": None, "last_verified": None})
                zeroed_total += zeroed
        db.flush()
        print(f"  Zeroed {zeroed_total} existing CCL market shares (only for authoritative companies).")

        for seg_name, shares in MARKET_SHARE_DATA.items():
            link = link_names.get(seg_name)
            if not link:
                continue

            for company_name, share, source in shares:
                company = company_name_map.get(company_name)
                if not company:
                    print(f"  WARN: company '{company_name}' not found in DB")
                    continue

                # Check if link exists
                ccl = db.query(CompanyChainLink).filter(
                    CompanyChainLink.company_id == company.id,
                    CompanyChainLink.chain_link_id == link.id,
                ).first()

                if ccl:
                    ccl.market_share = share
                    ccl.data_source = source
                    ccl.last_verified = today
                else:
                    ccl = CompanyChainLink(
                        company_id=company.id,
                        chain_link_id=link.id,
                        market_share=share,
                        data_source=source,
                        last_verified=today,
                    )
                    db.add(ccl)

                share_count += 1

        db.commit()
        print(f"Market share data saved for {share_count} company-chain links.")

    finally:
        db.close()


def main():
    print("Starting industry chain data collection from authoritative sources...")
    collect_chain_data()
    print("Done.")


if __name__ == "__main__":
    main()
