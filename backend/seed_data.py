"""Seed database with AI chip industry chain data."""
import random
from datetime import date, timedelta, datetime
from database import SessionLocal, engine, Base
from models import (
    Company, Product, ProductMetric, MarketData, StorageProduct,
    IndustryChainLink, CompanyChainLink, Financial, SupplyDemand,
    KeyIndicator, IndicatorObservation, Forecast, JudgmentLog,
    ScoringDimension, CompanyScore, Portfolio, PortfolioHolding,
    PortfolioPerformance, PortfolioEvaluation,
)

Base.metadata.create_all(bind=engine)

YEAR = 2026


def seed():
    db = SessionLocal()
    if db.query(Company).count() > 5:
        db.close()
        print("Already seeded, skipping.")
        return

    # ── Companies (Expanded: 50+ across entire AI industry chain) ──
    companies_data = [
        # ===== AI芯片设计 (7) =====
        ("NVIDIA", "英伟达", "NVDA", "chip_design", "GPU / AI Accelerator", "全球AI芯片领导者，GPU和AI加速器龙头", True, 1650, 36000),
        ("AMD", "超威半导体", "AMD", "chip_design", "GPU / CPU", "CPU与GPU领先企业，AI加速器市场挑战者", True, 310, 26000),
        ("Intel", "英特尔", "INTC", "chip_design", "CPU / AI Accelerator", "传统CPU巨头，加速AI芯片和代工转型", True, 560, 124000),
        ("Broadcom", "博通", "AVGO", "chip_design", "Networking / AI ASIC", "AI定制芯片(ASIC)和网络芯片领导者", True, 510, 20000),
        ("Qualcomm", "高通", "QCOM", "chip_design", "Mobile / AI", "移动SoC领导者，AI边缘计算芯片龙头", True, 470, 50000),
        ("Apple", "苹果", "AAPL", "chip_design", "消费电子 / AI", "自研M系列/A18芯片，AI端侧推理领导者", True, 3910, 164000),
        ("Google", "谷歌", "GOOGL", "chip_design", "互联网 / AI / 云", "TPU/Axion芯片自研，AI大模型领先者(Gemini)", True, 3500, 182000),

        # ===== AI芯片设计 - 未上市 / ASIC (4) =====
        ("Huawei", "华为", None, "chip_design", "通信 / 芯片 / AI", "Ascend昇腾AI芯片系列，中国AI芯片领导者", False, 1000, 207000),
        ("Cerebras", "Cerebras", None, "chip_design", "AI芯片", "晶圆级AI加速器(WSE-3)设计，专注大模型训练", False, 7, 900),
        ("Groq", "Groq", None, "chip_design", "AI芯片", "LPU推理芯片架构，AI推理速度领先", False, 3, 500),
        ("SambaNova", "SambaNova", None, "chip_design", "AI芯片", "SN40L可重构数据流架构AI芯片", False, 2, 400),

        # ===== 晶圆制造 (6) =====
        ("TSMC", "台积电", "TSM", "manufacturing", "晶圆代工", "全球晶圆代工龙头，3nm/5nm制程垄断者", True, 880, 76500),
        ("Samsung", "三星", "SMSN", "manufacturing", "存储 / 晶圆代工", "全球存储龙头+晶圆代工追赶者(GAA技术)", True, 680, 270000),
        ("Intel Foundry", "英特尔代工", "INTC", "manufacturing", "晶圆代工", "Intel代工服务，18A制程追赶台积电", True, 560, 124000),
        ("SMIC", "中芯国际", "SMI", "manufacturing", "晶圆代工", "中国最大晶圆代工厂，N+2制程量产", True, 63, 20000),
        ("UMC", "联电", "UMC", "manufacturing", "晶圆代工", "中国台湾晶圆代工大厂，成熟制程领先", True, 72, 20000),
        ("GlobalFoundries", "格芯", "GFS", "manufacturing", "晶圆代工", "美国晶圆代工厂，成熟制程FD-SOI技术", True, 74, 15000),

        # ===== HBM / 存储 (6) =====
        ("SK Hynix", "SK海力士", "000660", "memory", "HBM / DRAM / NAND", "HBM绝对领导者(HBM3E/HBM4)，AI存储核心供应商", True, 562, 35000),
        ("Samsung Memory", "三星存储", "SMSN", "memory", "DRAM / NAND / HBM", "全球存储芯片第一，HBM追赶SK海力士", True, 680, 270000),
        ("Micron", "美光", "MU", "memory", "DRAM / NAND / HBM", "美国存储芯片领先企业，HBM3E量产中", True, 280, 48000),
        ("Kioxia", "铠侠", None, "memory", "NAND Flash", "日本NAND Flash制造商，全球第三大", False, 105, 13000),
        ("Western Digital", "西部数据", "WDC", "memory", "HDD / NAND", "全球硬盘+SSD领导厂商", True, 130, 53000),
        ("YMTC", "长江存储", None, "memory", "NAND Flash", "长江存储，中国NAND Flash领军者", False, 55, 8000),

        # ===== 先进封装 (4) =====
        ("ASE", "日月光", "ASX", "packaging", "半导体封装测试", "全球最大半导体封装测试厂(日月光投控)", True, 185, 55000),
        ("Amkor", "安靠", "AMKR", "packaging", "半导体封装测试", "美国最大封装测试厂，先进封装布局", True, 65, 30000),
        ("JCET", "长电科技", None, "packaging", "半导体封装测试", "长电科技，中国最大封装测试厂", True, 40, 22000),
        ("Powertech", "力成科技", None, "packaging", "半导体封装测试", "力成科技，内存封装测试领导者", True, 22, 8000),

        # ===== 半导体设备 (8) =====
        ("ASML", "阿斯麦", "ASML", "equipment", "光刻机", "EUV光刻机全球独家供应商", True, 350, 42000),
        ("Applied Materials", "应用材料", "AMAT", "equipment", "半导体设备", "全球最大半导体设备供应商(沉积/离子注入)", True, 310, 34000),
        ("Lam Research", "泛林半导体", "LRCX", "equipment", "半导体设备", "刻蚀与薄膜沉积设备龙头", True, 200, 18000),
        ("Tokyo Electron", "东京电子", "TOELY", "equipment", "半导体设备", "日本半导体设备龙头，涂布/刻蚀设备领先", True, 200, 16000),
        ("KLA", "科磊", "KLAC", "equipment", "半导体设备", "半导体工艺控制与检测设备龙头", True, 125, 14000),
        ("ASM International", "ASM国际", "ASMIY", "equipment", "半导体设备", "ALD原子层沉积设备领导者", True, 35, 5000),
        ("Advantest", "爱德万", "ATEYY", "equipment", "半导体设备", "半导体测试设备龙头，HBM测试核心供应商", True, 55, 6000),
        ("DISCO", "DISCO", None, "equipment", "半导体设备", "日本晶圆切割/研磨设备龙头，先进封装关键设备", True, 38, 5500),

        # ===== EDA / IP (5) =====
        ("Synopsys", "新思科技", "SNPS", "eda", "EDA / IP", "全球EDA龙头，AI辅助芯片设计工具领导者", True, 82, 20000),
        ("Cadence", "铿腾电子", "CDNS", "eda", "EDA / IP", "全球EDA第二大厂，仿真/验证工具领先", True, 52, 12000),
        ("ARM", "ARM", "ARM", "eda", "CPU IP", "全球CPU IP授权龙头，AI端侧芯片核心架构", True, 42, 7000),
        ("Siemens EDA", "西门子EDA", "SIEGY", "eda", "EDA", "西门子EDA(原Mentor Graphics)全球EDA三强", True, 25, 15000),
        ("Ansys", "安西斯", "ANSS", "eda", "仿真软件", "多物理场仿真软件龙头，芯片设计仿真关键工具", True, 23, 6000),

        # ===== 大模型公司 / AI应用 (8) =====
        ("OpenAI", "OpenAI", None, "llm", "大模型 / AI", "GPT系列大模型领导者，ChatGPT/AI Agent平台", False, 120, 4000),
        ("Anthropic", "Anthropic", None, "llm", "大模型 / AI", "Claude系列大模型，AI安全研究领导者", False, 35, 1500),
        ("xAI", "xAI", None, "llm", "大模型 / AI", "Elon Musk创立，Grok大模型，Colossus超算集群", False, 10, 800),
        ("Mistral AI", "Mistral AI", None, "llm", "大模型 / AI", "法国AI大模型公司，开源模型领导者", False, 3, 300),
        ("Baidu", "百度", "BIDU", "llm", "互联网 / 大模型 / AI", "文心一言大模型，百度智能云，Apollo自动驾驶", True, 185, 39000),
        ("ByteDance", "字节跳动", None, "llm", "互联网 / 大模型 / AI", "抖音/TikTok，豆包大模型，AI应用领导者", False, 1200, 150000),
        ("Tencent", "腾讯", "TCEHY", "llm", "互联网 / 大模型 / AI", "腾讯混元大模型，社交/游戏/AI应用领导者", True, 860, 105000),
        ("Alibaba", "阿里巴巴", "BABA", "llm", "电商 / 云 / 大模型", "通义千问大模型，阿里云AI基础设施领导者", True, 1300, 218000),

        # ===== 云厂商 (6) =====
        ("Amazon", "亚马逊", "AMZN", "cloud", "电商 / 云 / AI", "AWS全球云第一，Trainium/Inferentia自研AI芯片", True, 6200, 1560000),
        ("Microsoft", "微软", "MSFT", "cloud", "软件 / 云 / AI", "Azure云+OpenAI深度合作，Maia自研AI芯片", True, 2500, 228000),
        ("Google Cloud", "谷歌云", "GOOGL", "cloud", "云 / AI", "Google Cloud TPU/Axion芯片，Gemini大模型", True, 3500, 182000),
        ("Oracle", "甲骨文", "ORCL", "cloud", "云 / 数据库", "Oracle Cloud+OCI AI集群，NVIDIA GPU大客户", True, 550, 164000),
        ("Alibaba Cloud", "阿里云", "BABA", "cloud", "云 / AI", "阿里云中国第一，AI基础设施领导者", True, 1300, 218000),
        ("Tencent Cloud", "腾讯云", "TCEHY", "cloud", "云 / AI", "腾讯云中国第二，AI+社交/游戏生态", True, 860, 105000),

        # ===== 应用厂商 / AI终端 (5) =====
        ("Meta", "Meta", "META", "application", "社交 / AI / VR", "LLaMA大模型+MTIA自研芯片+AI社交应用", True, 1600, 72000),
        ("Tesla", "特斯拉", "TSLA", "application", "电动车 / 机器人 / AI", "FSD自动驾驶+Dojo超算+Optimus机器人+AI训练", True, 980, 140000),
        ("Xiaomi", "小米", "XIACF", "application", "消费电子 / 电动车 / AI", "手机+IoT+汽车，AI端侧部署领导者", True, 400, 32000),
        ("Meituan", "美团", "MPNGY", "application", "本地生活 / AI", "美团AI在本地生活服务的大规模应用", True, 420, 100000),
        ("Pinduoduo", "拼多多", "PDD", "application", "电商 / AI", "拼多多/Temu AI推荐算法驱动增长", True, 390, 13000),

        # ===== 网络互联 (3) =====
        ("Marvell", "迈威尔科技", "MRVL", "networking", "网络 / 互联 / 存储", "AI网络互联芯片(DSP/CXL/Switch)领导者", True, 60, 8000),
        ("Arista", "Arista", "ANET", "networking", "网络交换机", "AI数据中心高速交换机领导者", True, 70, 6000),
        ("Cisco", "思科", "CSCO", "networking", "网络设备", "全球网络设备巨头，AI网络安全/交换机", True, 540, 90000),
    ]

    company_map = {}
    for name, name_cn, ticker, ctype, sector, desc, listed, rev, emp in companies_data:
        c = Company(name=name, name_cn=name_cn, ticker=ticker, company_type=ctype, sector=sector,
                    description=desc, is_listed=listed, revenue_2024=rev, employee_count=emp)
        db.add(c); db.flush()
        company_map[name] = c

    # ── Industry Chain Links ───────────────────────────────────
    chains_data = [
        ("ai_chip_design", "AI芯片设计", 1,
         "AI加速器/GPGPU架构设计，包括GPU、AI ASIC、NPU等",
         800, 1200, 1800, 50.0,
         "极高 - 需要顶尖架构设计团队、CUDA生态壁垒、数十亿美元研发投入",
         "高",
         "供不应求，H100/B200交货周期长达36周",
         "供需仍紧张，产能优先保障头部客户",
         "产能大幅扩张后有望缓解，但高端产品仍紧张",
         "大模型训练需求爆发、AI推理规模化、企业AI渗透率提升",
         "出口管制风险、地缘政治、技术迭代加速"),

        ("wafer_fab", "晶圆制造", 2,
         "先进制程晶圆代工(7nm/5nm/3nm/2nm)，AI芯片制造核心环节",
         1200, 1600, 2200, 35.0,
         "极高 - 资本开支超200亿美元/厂、5年建设周期、台积电垄断",
         "极高",
         "3nm/5nm产能满载(>100%)，2025年扩产有限",
         "产能持续满载，CoWoS封装产能为瓶颈",
         "新建工厂陆续投产，但仍供不应求",
         "AI芯片需求高速增长、先进制程节点持续下探",
         "集中度风险、地缘政治、技术物理极限"),

        ("hbm_memory", "HBM高带宽存储", 3,
         "HBM(High Bandwidth Memory)制造，AI芯片关键配套",
         250, 450, 750, 73.0,
         "高 - 需要先进封装技术、TSV工艺、与晶圆厂深度绑定",
         "极高",
         "HBM3E供应极度紧张，SK海力士领先",
         "HBM4开发周期长，供需缺口仍大",
         "扩产逐步释放，但仍供不应求",
         "HBM容量和带宽需求随AI芯片升级倍增",
         "技术路线变化、客户集中度高"),

        ("advanced_packaging", "先进封装", 4,
         "CoWoS/3D封装等先进封装技术，AI芯片集成的关键环节",
         150, 250, 400, 63.0,
         "高 - CoWoS产能稀缺、良率爬坡缓慢、认证周期长",
         "极高",
         "CoWoS产能严重不足，台积电急扩产",
         "产能扩建2倍+，仍难以满足全部需求",
         "封装产能瓶颈逐步缓解",
         "AI芯片集成度提升、Chiplet架构普及",
         "良率风险、技术竞争"),

        ("eda_ip", "EDA/IP设计工具", 5,
         "芯片设计自动化工具和IP授权",
         200, 230, 270, 16.0,
         "极高 - 三大EDA巨头垄断，生态壁垒极高",
         "低",
         "EDA供应稳定，AI设计工具需求增长",
         "AI辅助EDA工具升级，需求稳定增长",
         "市场格局稳定，供需平衡",
         "芯片复杂度提升、AI辅助设计普及",
         "技术垄断、出口管制"),

        ("semiconductor_equipment", "半导体设备", 6,
         "晶圆制造和封装测试设备，扩产的瓶颈",
         1100, 1300, 1600, 20.0,
         "极高 - EUV光刻机ASML独家、刻蚀/沉积设备集中度高",
         "高",
         "EUV光刻机交付期12-18个月",
         "设备订单持续增长，先进制程设备短缺",
         "设备产能扩张缓慢，维持紧平衡",
         "先进制程扩产、存储厂设备投资增加",
         "出口管制、设备交付周期"),

        ("ai_server_integration", "AI服务器集成", 7,
         "AI服务器集成制造与云服务部署",
         600, 900, 1400, 53.0,
         "中等 - 系统集成门槛相对较低，但GPU获取是关键瓶颈",
         "低",
         "GPU供应紧张限制服务器出货",
         "GPU产能扩建推动服务器出货增长",
         "供需趋于平衡",
         "企业AI部署加速、云厂商资本开支增长",
         "GPU供应依赖、竞争激烈"),
    ]

    chain_map = {}
    for name, name_cn, sort_order, desc, m2025, m2026, m2027, growth, barriers, exp_diff, gap25, gap26, gap27, drivers, risks in chains_data:
        cl = IndustryChainLink(
            name=name, name_cn=name_cn, sort_order=sort_order,
            description=desc,
            market_size_2025=m2025, market_size_2026=m2026, market_size_2027=m2027,
            growth_rate=growth, entry_barriers=barriers,
            expansion_difficulty=exp_diff,
            supply_gap_2025=gap25, supply_gap_2026=gap26, supply_gap_2027=gap27,
            key_drivers=drivers, risks=risks,
        )
        db.add(cl); db.flush()
        chain_map[name] = cl

    # ── Company-Chain Links (Expanded: full industry coverage) ──
    ccl_data = [
        # AI芯片设计 (10)
        ("NVIDIA", "ai_chip_design", 85, 95, True, "CUDA生态绝对壁垒、NVLink互联、每年一代架构升级"),
        ("AMD", "ai_chip_design", 10, 5, False, "ROCm生态追赶、MI300X性能竞争力、CDNA架构"),
        ("Intel", "ai_chip_design", 3, 2, False, "Gaudi 3 AI加速器、Falcon Shores架构转型"),
        ("Broadcom", "ai_chip_design", 5, 3, False, "AI定制ASIC领导者、3nm/5nm Chiplet设计能力"),
        ("Qualcomm", "ai_chip_design", 1, 1, False, "AI Edge SoC领先、Hexagon NPU、Snapdragon X Elite"),
        ("Apple", "ai_chip_design", 1, 1, False, "M系列芯片Neural Engine、端侧AI推理领导者"),
        ("Google", "ai_chip_design", 2, 2, False, "TPU v5p/Axion自研AI芯片、Gemini大模型训练主力"),
        ("Huawei", "ai_chip_design", 2, 3, False, "Ascend昇腾910B/910C系列、中国AI芯片替代首选"),
        ("Cerebras", "ai_chip_design", 0.5, 0.5, False, "晶圆级AI芯片独特路线、大模型训练专用"),
        ("Groq", "ai_chip_design", 0.3, 0.2, False, "LPU推理架构极致速度和低延迟"),

        # 晶圆制造 (6)
        ("TSMC", "wafer_fab", 90, 100, True, "3nm/5nm制程垄断、CoWoS先进封装整合、良率领先"),
        ("Samsung", "wafer_fab", 6, 5, False, "GAA 3nm技术追赶、存储+代工协同"),
        ("Intel Foundry", "wafer_fab", 3, 3, False, "Intel 18A制程、代工服务转型"),
        ("SMIC", "wafer_fab", 1, 1, False, "中国先进制程替代主力、N+2制程"),
        ("UMC", "wafer_fab", 1, 1, False, "成熟制程代工领导者"),
        ("GlobalFoundries", "wafer_fab", 1, 1, False, "美国政府支持、FD-SOI技术"),

        # HBM存储 (6)
        ("SK Hynix", "hbm_memory", 50, 60, True, "HBM3E率先量产、MR-MUF先进封装、HBM4领先"),
        ("Samsung Memory", "hbm_memory", 30, 25, False, "HBM3E追赶、大规模产能、垂直整合优势"),
        ("Micron", "hbm_memory", 15, 10, False, "HBM3E量产中、1-beta制程优势"),
        ("Kioxia", "hbm_memory", 2, 0.5, False, "NAND Flash专注、HBM研发初期"),
        ("Western Digital", "hbm_memory", 0, 0, False, "NAND Flash+HDD"),
        ("YMTC", "hbm_memory", 0, 0, False, "中国NAND Flash新势力"),

        # 先进封装 (5)
        ("TSMC", "advanced_packaging", 80, 85, True, "CoWoS/InFO/3D封装全套技术、产能领先"),
        ("ASE", "advanced_packaging", 10, 8, False, "全球封装测试老大、先进封装布局加速"),
        ("Amkor", "advanced_packaging", 5, 4, False, "美国封装大厂、CoWoS-like技术"),
        ("JCET", "advanced_packaging", 3, 2, False, "中国封装龙头、先进封装追赶"),
        ("Powertech", "advanced_packaging", 2, 1, False, "内存封装测试领先"),

        # 半导体设备 (8)
        ("ASML", "semiconductor_equipment", 100, 90, True, "EUV光刻机全球独家、High NA EUV技术领导者"),
        ("Applied Materials", "semiconductor_equipment", 25, 20, False, "沉积/离子注入/CMP设备全覆盖"),
        ("Lam Research", "semiconductor_equipment", 20, 15, False, "刻蚀设备领导者、先进存储/逻辑关键设备"),
        ("Tokyo Electron", "semiconductor_equipment", 20, 15, False, "涂布/显影/刻蚀设备领先"),
        ("KLA", "semiconductor_equipment", 15, 12, False, "晶圆检测/量测设备绝对龙头"),
        ("ASM International", "semiconductor_equipment", 5, 5, False, "ALD原子层沉积设备领导者"),
        ("Advantest", "semiconductor_equipment", 3, 3, False, "SOC/存储测试设备、HBM测试关键"),
        ("DISCO", "semiconductor_equipment", 3, 2, False, "晶圆切割/研磨/抛光设备龙头"),

        # EDA/IP (5)
        ("Synopsys", "eda_ip", 35, 40, True, "AI辅助EDA工具领导者(Synopsys.ai)、全球EDA第一"),
        ("Cadence", "eda_ip", 30, 35, False, "仿真/验证/PCB设计领先、AI+EDA融合"),
        ("ARM", "eda_ip", 25, 20, True, "CPU IP授权统治、ARM架构AI端侧全覆盖"),
        ("Siemens EDA", "eda_ip", 10, 5, False, "EDA三强、PCB/布线/热仿真"),
        ("Ansys", "eda_ip", 5, 3, False, "多物理场仿真、芯片-封装-系统协同设计"),

        # 云厂商 (6)
        ("Amazon", "ai_server_integration", 20, 25, True, "AWS全球云第一、Trainium/Inferentia自研芯片"),
        ("Microsoft", "ai_server_integration", 25, 30, True, "Azure+OpenAI最深度合作、Maia芯片"),
        ("Google Cloud", "ai_server_integration", 15, 18, True, "Google Cloud+TPU/Gemini大模型"),
        ("Oracle", "ai_server_integration", 5, 5, False, "OCI AI集群+Elon Musk Colossus合作"),
        ("Alibaba Cloud", "ai_server_integration", 5, 3, False, "阿里云中国第一+通义千问大模型"),
        ("Tencent Cloud", "ai_server_integration", 3, 2, False, "腾讯云+混元大模型+AI应用部署"),

        # AI服务器集成 - NVIDIA/Broadcom也参与
        ("NVIDIA", "ai_server_integration", 40, 50, True, "DGX/HGX系统+NVLink网络+AI Infra一体化"),
        ("Broadcom", "ai_server_integration", 10, 5, False, "AI网络交换机+定制AI加速器互联"),
        ("Marvell", "ai_server_integration", 3, 2, False, "AI数据中心互联芯片"),
        ("Arista", "ai_server_integration", 5, 3, False, "AI数据中心高速交换机"),
        ("Cisco", "ai_server_integration", 3, 2, False, "AI网络设备+Silicon One芯片"),
    ]

    for comp_name, chain_name, share, rev_share, leader, advantage in ccl_data:
        if comp_name in company_map and chain_name in chain_map:
            ccl = CompanyChainLink(
                company_id=company_map[comp_name].id,
                chain_link_id=chain_map[chain_name].id,
                market_share=share, revenue_share=rev_share,
                is_leader=leader, competitive_advantage=advantage,
            )
            db.add(ccl)

    # ── Financials (2023-2025 actual, company-specific data) ────
    # (revenue, net_income, pe_ttm, ps_ttm)
    fin_data = {
        "NVIDIA": [(2023, 609, 126, 55, 18), (2024, 1305, 530, 48, 15), (2025, 1650, 720, 55, 18)],
        "AMD": [(2023, 227, 16, 25, 8), (2024, 258, 32, 22, 7), (2025, 310, 48, 25, 8)],
        "Intel": [(2023, 542, 17, 35, 2), (2024, 531, 15, 30, 2.5), (2025, 560, 20, 35, 2)],
        "TSMC": [(2023, 695, 265, 20, 10), (2024, 760, 295, 22, 11), (2025, 880, 340, 25, 15)],
        "ASML": [(2023, 285, 80, 35, 12), (2024, 300, 82, 38, 12), (2025, 350, 95, 40, 12)],
        "SK Hynix": [(2023, 250, 18, 35, 3), (2024, 420, 95, 15, 5), (2025, 560, 150, 15, 6)],
        "Samsung": [(2023, 520, 35, 25, 2), (2024, 580, 55, 22, 2), (2025, 680, 80, 20, 2)],
        "Micron": [(2023, 155, -5, 0, 3), (2024, 215, 32, 12, 4), (2025, 280, 58, 12, 4)],
        "Broadcom": [(2023, 358, 140, 25, 8), (2024, 420, 165, 28, 9), (2025, 510, 200, 30, 10)],
        "Qualcomm": [(2023, 420, 95, 15, 5), (2024, 440, 100, 16, 5), (2025, 470, 105, 18, 5)],
        "Applied Materials": [(2023, 265, 68, 18, 5), (2024, 278, 72, 20, 5), (2025, 310, 80, 22, 6)],
        "Lam Research": [(2023, 175, 46, 18, 4), (2024, 182, 48, 20, 5), (2025, 200, 52, 20, 5)],
        "Apple": [(2023, 3830, 970, 28, 8), (2024, 3910, 937, 30, 8), (2025, 4100, 980, 30, 8)],
        "Google": [(2023, 3070, 738, 20, 6), (2024, 3500, 800, 22, 6), (2025, 3800, 870, 22, 6)],
        "Amazon": [(2023, 5740, 304, 50, 3), (2024, 6200, 485, 45, 3), (2025, 6800, 560, 40, 3)],
        "Microsoft": [(2023, 2120, 720, 28, 10), (2024, 2500, 830, 30, 10), (2025, 2700, 900, 32, 10)],
        "Meta": [(2023, 1350, 390, 20, 7), (2024, 1600, 500, 22, 8), (2025, 1800, 560, 25, 8)],
        "Tesla": [(2023, 970, 150, 60, 10), (2024, 980, 145, 65, 10), (2025, 1050, 165, 70, 10)],
        "Tencent": [(2023, 780, 215, 18, 6), (2024, 860, 240, 20, 6), (2025, 930, 265, 20, 6)],
        "Alibaba": [(2023, 1250, 115, 12, 2), (2024, 1300, 135, 14, 2), (2025, 1400, 150, 15, 2)],
        "Baidu": [(2023, 176, 35, 10, 2), (2024, 185, 38, 11, 2), (2025, 195, 42, 12, 2)],
        "Tokyo Electron": [(2023, 175, 42, 20, 5), (2024, 200, 48, 22, 5), (2025, 220, 52, 22, 5)],
        "KLA": [(2023, 105, 30, 22, 6), (2024, 125, 35, 25, 7), (2025, 140, 40, 25, 7)],
        "Synopsys": [(2023, 68, 16, 50, 14), (2024, 82, 20, 55, 15), (2025, 92, 24, 55, 15)],
        "Cadence": [(2023, 44, 12, 55, 16), (2024, 52, 15, 60, 18), (2025, 58, 17, 60, 18)],
        "ARM": [(2023, 28, 5, 70, 20), (2024, 42, 9, 80, 25), (2025, 50, 12, 80, 25)],
        "ASE": [(2023, 175, 14, 15, 2), (2024, 185, 16, 15, 2), (2025, 198, 18, 15, 2)],
        "Amkor": [(2023, 61, 5, 18, 3), (2024, 65, 5, 18, 3), (2025, 72, 6, 18, 3)],
        "SMIC": [(2023, 60, 8, 35, 7), (2024, 63, 7, 40, 8), (2025, 70, 9, 40, 8)],
        "Marvell": [(2023, 55, -1, 0, 5), (2024, 60, 4, 30, 8), (2025, 72, 8, 25, 8)],
        "Arista": [(2023, 58, 17, 35, 10), (2024, 70, 22, 38, 12), (2025, 82, 26, 40, 12)],
        "Cisco": [(2023, 530, 110, 15, 3), (2024, 540, 115, 15, 3), (2025, 550, 115, 15, 3)],
        "Oracle": [(2023, 500, 85, 22, 6), (2024, 530, 95, 25, 6), (2025, 560, 100, 25, 6)],
        "Xiaomi": [(2023, 370, 25, 22, 2), (2024, 400, 30, 25, 2), (2025, 420, 33, 25, 2)],
        "Meituan": [(2023, 380, 18, 20, 3), (2024, 420, 25, 20, 3), (2025, 450, 30, 20, 3)],
        "Pinduoduo": [(2023, 360, 25, 15, 3), (2024, 390, 32, 15, 3), (2025, 420, 35, 15, 3)],
        "JCET": [(2023, 36, 3, 20, 2), (2024, 40, 4, 20, 2), (2025, 45, 5, 20, 2)],
        "Western Digital": [(2023, 120, -8, 0, 2), (2024, 125, 5, 18, 2), (2025, 130, 8, 15, 2)],
    }

    for comp_name, years_data in fin_data.items():
        if comp_name not in company_map:
            continue
        cid = company_map[comp_name].id
        for idx, (fy, rev, ni, pe_ttm, ps_ttm) in enumerate(years_data):
            rev_growth = ((rev / years_data[idx-1][1]) - 1) * 100 if idx > 0 else 20.0
            nm = (ni / rev) * 100 if rev else 0
            pe = pe_ttm if pe_ttm > 0 else None
            ps = ps_ttm
            pb = round(ps_ttm * random.uniform(2, 5), 1)
            roe = nm * random.uniform(0.8, 1.2) if nm > 0 else 5.0
            ev_ebitda = round(pe_ttm * random.uniform(0.8, 1.2), 1) if pe_ttm > 0 else None

            f = Financial(
                company_id=cid, fiscal_year=fy,
                revenue=rev, revenue_growth=round(rev_growth, 1),
                net_income=ni, gross_margin=round(random.uniform(45, 75), 1) if comp_name in ["NVIDIA", "ASML"] else round(random.uniform(35, 60), 1),
                operating_margin=round(random.uniform(25, 55), 1) if comp_name == "NVIDIA" else round(random.uniform(10, 35), 1),
                net_margin=round(nm, 1),
                eps=round(ni / random.uniform(0.5, 2.5), 2) if ni > 0 else 0,
                pe=pe, pb=pb, ps=ps,
                pe_ttm=pe_ttm, ps_ttm=ps_ttm,
                ev_ebitda=ev_ebitda,
                roe=round(roe, 1), debt_equity=round(random.uniform(0.1, 0.8), 2),
                dividend_yield=round(random.uniform(0, 1.5), 2),
            )
            db.add(f)

    # ── Supply-Demand ──────────────────────────────────────────
    for chain_name in ["ai_chip_design", "wafer_fab", "hbm_memory", "advanced_packaging"]:
        clid = chain_map[chain_name].id
        for period, supply, demand, gap, util, lead in [
            ("2025", 80, 100, -20, 98, 36),
            ("2026E", 95, 115, -17, 95, 30),
            ("2027E", 115, 130, -12, 90, 24),
        ]:
            sd = SupplyDemand(
                chain_link_id=clid, period=period,
                supply=supply, demand=demand, unit="%",
                gap_pct=gap, gap_description=f"供需缺口{abs(gap)}%",
                capacity_utilization=util, lead_time_weeks=lead,
            )
            db.add(sd)

    # ── Key Indicators (Expanded: 24 indicators with real trackable sources) ──
    indicators_data = [
        # ===== 价格与供需 (6) =====
        ("hbm3e_price", "HBM3E价格", "美元/GB",
         "集邦咨询 TrendForce", "https://www.trendforce.com/research/dram",
         "price_supply", "HBM3E每GB合约价格变动，直接反映AI存储供需关系",
         "↑价格上涨→HBM制造商利润率提升→SK海力士/三星受益；↓价格下跌→供应缓解信号，存储厂商盈利承压",
         False, "月度",
         "访问TrendForce DRAMeXchange月度合约价报告；关注SK海力士/三星/Micron财报中HBM ASP指引"),

        ("ddr5_spot_price", "DDR5现货价格", "美元/颗粒",
         "DRAMeXchange / 集邦", "https://www.dramexchange.com",
         "price_supply", "DDR5 DRAM颗粒现货市场价格走势",
         "↑价格上涨→存储周期上行确认；↓价格下跌→需求疲软信号",
         True, "周度",
         "DRAMeXchange网站实时报价；关注集邦咨询周度内存价格报告"),

        ("nand_spot_price", "NAND Flash现货价格", "美元/颗粒",
         "集邦咨询 / DRAMeXchange", "https://www.trendforce.com/research/nand",
         "price_supply", "NAND Flash颗粒现货价格指数",
         "↑价格上涨→存储供需改善；↓价格下跌→库存调整信号",
         True, "周度",
         "TrendForce NAND Flash价格页面；关注美光/三星NAND产品线营收"),

        ("h100_lease_price", "H100云租赁价格", "美元/小时/卡",
         "Lambda Labs / Vast.ai", "https://lambdalabs.com/service/gpu-cloud",
         "price_supply", "H100云端GPU租赁市场价格趋势",
         "↑价格坚挺→GPU供应紧张持续；↓价格下降→供应改善或需求边际回落",
         True, "周度",
         "Lambda Labs官网GPU云定价页；Vast.ai公开市场价格；GPU List网站汇总"),

        ("a100_secondhand_price", "A100二手市场价格", "美元/卡",
         "eBay / 二手服务器市场", "https://www.ebay.com/sch/i.html?_nkw=nvidia+a100+80gb",
         "price_supply", "A100 GPU二手市场价格反映AI芯片供需切换趋势",
         "↑价格上涨→新旧GPU均供不应求；↓价格大幅下跌→H100/B200替代效应加速",
         True, "周度",
         "eBay搜索NVIDIA A100完成拍卖价；服务器二手商报价；关注价量变化"),

        ("coWoS_capacity", "CoWoS月产能", "千片/月",
         "台积电法说会", "https://www.tsmc.com/tsmcdotcom/EN/investor_relations/events_and_presentations",
         "price_supply", "台积电CoWoS先进封装月产能扩张进度",
         "↑产能快速扩张→AI芯片出货瓶颈缓解→利好NVIDIA/AMD；↓产能爬坡慢→封装持续瓶颈",
         False, "季度",
         "台积电每季度法说会投资者简报；集邦咨询封装产能追踪报告"),

        # ===== 行业景气度 (5) =====
        ("sox_index", "费城半导体指数(SOX)", "点数",
         "Yahoo Finance", "https://finance.yahoo.com/quote/%5ESOX/",
         "industry", "费城半导体指数，全球半导体行业景气度风向标",
         "↑指数上涨→行业整体景气向上；↓指数下跌→资金撤离半导体板块",
         True, "日度",
         "Yahoo Finance SOX指数页面；Google Finance搜索'SOX'；TradingView SOX图表"),

        ("semiconductor_sales", "全球半导体月度销售额", "亿美元",
         "SIA / WSTS", "https://www.semiconductors.org/resources/sia-market-data/",
         "industry", "全球半导体行业月度销售额(WSTS/SIA数据)",
         "↑同比增长→行业景气上行；↓同比转负→周期下行拐点",
         True, "月度",
         "SIA官网月度销售报告(WMS数据)；WSTS quarterly forecast更新"),

        ("semiconductor_book_to_bill", "半导体设备BB值", "比率",
         "SEMI", "https://www.semi.org/en/market-research",
         "industry", "北美半导体设备订单出货比(B/B Ratio)，1.0为荣枯线",
         ">1.0→设备需求扩张，fab扩产积极；<1.0→设备需求收缩，fab投资谨慎",
         True, "月度",
         "SEMI每月发布北美BB值报告；关注Applied Materials/Lam Research财报订单指引"),

        ("china_semiconductor_import", "中国半导体进口额", "亿美元",
         "中国海关总署", "http://www.customs.gov.cn/",
         "industry", "中国月度半导体/集成电路进口金额，反映中国需求",
         "↑进口增长→中国需求强劲，利好全球半导体；↓进口减少→国产替代加速或需求疲软",
         True, "月度",
         "中国海关总署月度商品进口数据；集邦咨询中国半导体进口分析"),

        ("ai_chip_shipment", "AI芯片季度出货量", "百万颗",
         "IDC / Gartner", "https://www.idc.com/promo/semiconductors",
         "industry", "全球AI加速器/GPU季度出货量(Gartner/IDC追踪)",
         "↑出货量高增长→AI需求真实强劲；↓增速放缓→库存调整或技术换代",
         False, "季度",
         "IDC Semiconductor Tracker报告；Gartner AI Semiconductor预测；Jon Peddie Research GPU报告"),

        # ===== 产业链交期 (3) =====
        ("gpu_lead_time", "AI GPU交货周期", "周",
         "供应链调研 / 电子时报", "https://www.digitimes.com/",
         "lead_time", "H100/B200等AI GPU从下单到交付的lead time趋势",
         "↓交期缩短→供应改善，AI服务器出货加速；↑交期延长→供应紧张加剧，定价权增强",
         True, "月度",
         "Digitimes供应链报道；电子时报ASIC/GPU交期追踪；Morgan Stanley供应链调研"),

        ("euv_delivery", "EUV光刻机季度交付量", "台",
         "ASML财报", "https://www.asml.com/en/investors/annual-report",
         "lead_time", "ASML每季度EUV光刻机出货量，先进制程扩产先行指标",
         "↑出货增加→晶圆厂先进制程扩产加速；↓出货不足→制程升级可能延迟",
         True, "季度",
         "ASML投资者关系季度报告(EUV/ArFi出货量)；关注ASML积压订单金额"),

        ("chip_design_startup", "芯片设计服务收入", "百万美元",
         "Cadence/Synopsys财报", "https://www.cadence.com/en_US/home/company/investor-relations.html",
         "lead_time", "EDA巨头设计服务收入趋势，反映芯片设计活动活跃度（未来12-18个月芯片需求的先行指标）",
         "↑收入增长→芯片设计项目增多→未来芯片需求增加；↓增速放缓→设计活动降温",
         True, "季度",
         "Cadence/Synopsys财报中IP授权和服务收入；ANSYS EDA业务追踪"),

        # ===== 公司财务追踪 (5) =====
        ("nvidia_dc_revenue", "NVIDIA数据中心营收", "亿美元",
         "NVIDIA Investor Relations", "https://investor.nvidia.com/financial-info/default.aspx",
         "financial", "NVIDIA数据中心业务季度营收，AI需求的直接晴雨表",
         "↑持续增长并超预期→AI需求真实强劲；↓增速放缓或miss→AI周期担忧信号",
         True, "季度",
         "NVIDIA IR季度财报；SeekingAlpha NVDA earnings transcript；关注营收增速变化"),

        ("tsmc_monthly_revenue", "台积电月度营收", "亿新台币",
         "TSMC 月营收报告", "https://www.tsmc.com/tsmcdotcom/EN/investor_relations/monthly_revenue",
         "financial", "台积电月度营收数据，AI芯片需求的高频验证指标",
         "↑月营收同比增长超预期→AI/HPC需求强劲；↓低于季节性→需求走弱风险",
         True, "月度",
         "TSMC官网每月10日发布前月营收；关注3nm/5nm制程营收占比变化"),

        ("sk_hynix_hbm_ratio", "SK海力士HBM营收占比", "%",
         "SK Hynix财报", "https://www.skhynix.com/ir/financial-info",
         "financial", "SK海力士HBM占DRAM营收比例，体现HBM对存储厂商盈利贡献",
         "↑占比快速提升→HBM成为存储核心增长引擎；↓占比下降→HBM竞争加剧或需求切换",
         True, "季度",
         "SK Hynix IR季度财报中HBM营收披露；关注HBM3E vs HBM4产品结构"),

        ("datacenter_capex", "四大云厂商合计资本开支", "亿美元",
         "MSFT/AMZN/GOOG/META财报", "https://www.microsoft.com/en-us/investor",
         "financial", "微软、亚马逊、谷歌、Meta四家公司季度资本开支总和",
         "↑持续超预期→AI军备竞赛加速→算力需求持续强劲；↓下调指引→AI投资回报担忧→需求放缓",
         True, "季度",
         "各公司IR季度财报/Capex指引；汇总四家Capex趋势；关注AI占Capex比重"),

        ("amd_dc_revenue", "AMD数据中心营收", "亿美元",
         "AMD Investor Relations", "https://ir.amd.com/financial-information/default.aspx",
         "financial", "AMD数据中心(含MI系列AI加速器)季度营收",
         "↑持续高增长→AI加速器市场双寡头格局确立；↓增长不及预期→NVIDIA主导地位强化",
         True, "季度",
         "AMD IR季度财报数据中心分部的营收披露；对比NVIDIA DC营收趋势"),

        # ===== 技术前沿 (3) =====
        ("ai_llm_training_cost", "前沿大模型训练成本", "百万美元",
         "Epoch AI / 公开文献", "https://epochai.org/blog/trends-in-training",
         "technology", "GPT/Claude/Gemini等前沿大模型单次训练成本变化趋势",
         "↑训练成本仍在增长→算力需求未到天花板；↓训练成本大幅下降→模型效率提升可能降低算力需求增速",
         False, "年度",
         "Epoch AI公开数据库跟踪训练计算量→成本换算；各公司技术博客披露"),

        ("chip_advance_node_yeild", "先进制程良率传闻", "%",
         "行业传言/分析报告", "https://www.semiwiki.com/",
         "technology", "3nm/2nm/GAA制程良率进展(非官方)，影响扩产速度和成本",
         "↑良率爬坡超预期→扩产加速，成本下降；↓良率低于预期→产能释放延迟，客户多元化需求增加",
         True, "季度",
         "SemiWiki/AnandTech技术分析；IC Knowledge制程成本报告；分析师研报"),

        ("ai_inference_efficiency", "AI推理成本趋势", "美元/百万token",
         "Artificial Analysis", "https://artificialanalysis.ai/",
         "technology", "主流AI模型推理API价格趋势，反映AI推理效率提升速度",
         "↓推理价格快速下降→AI应用普及加速，长期算力需求增加；↓下降缓慢→推理成本仍高，普及受限",
         True, "月度",
         "Artificial Analysis价格追踪；各模型API官方定价页；Latency/Speed对比"),

        # ===== 市场情绪 (2) =====
        ("semiconductor_etf_flow", "半导体ETF资金流", "百万美元",
         "ETF.com / Morningstar", "https://www.etf.com/SMH",
         "sentiment", "SMH/SOXL等半导体ETF周度资金净流入/流出",
         "↑持续净流入→市场对半导体板块情绪高涨；↓持续净流出→板块降温，资金轮出",
         True, "周度",
         "ETF.com SMH资金流数据；Morningstar ETF资金流报告；Yahoo Finance基金页面"),

        ("ai_search_trend", "AI相关搜索热度指数", "指数",
         "Google Trends", "https://trends.google.com/trends/explore?q=AI%20chip,NVIDIA%20GPU",
         "sentiment", "Google搜索'AIGC'/'AI芯片'/'GPU'等关键词的相对搜索热度",
         "↑搜索热度↑→公众关注度提升→终端需求关注增加；↓热度下降→AI话题降温",
         True, "周度",
         "Google Trends对比关键词趋势；关注NVIDIA/AMD/AI芯片搜索热度相对变化"),
    ]

    indicator_map = {}
    for name, name_cn, unit, source, url, cat, desc, impact, auto, freq, method in indicators_data:
        ki = KeyIndicator(
            name=name, name_cn=name_cn, unit=unit, source=source,
            source_url=url, category=cat, description=desc,
            impact_analysis=impact, is_automated=auto, update_frequency=freq,
            collection_method=method,
        )
        db.add(ki); db.flush()
        indicator_map[name] = ki

    # ── Indicator Observations (expanded) ──────────────────────
    today = date(YEAR, 6, 10)
    obs_specs = [
        ("hbm3e_price", [(30, 28), (25, 26), (20, 25), (15, 24), (10, 22), (5, 21), (0, 20)]),
        ("ddr5_spot_price", [(30, 4.5), (25, 4.2), (20, 4.0), (15, 3.8), (10, 3.5), (5, 3.3), (0, 3.1)]),
        ("nand_spot_price", [(30, 2.8), (25, 2.6), (20, 2.5), (15, 2.4), (10, 2.3), (5, 2.2), (0, 2.1)]),
        ("h100_lease_price", [(30, 3.5), (20, 3.2), (10, 2.8), (0, 2.5)]),
        ("a100_secondhand_price", [(60, 18000), (45, 16500), (30, 15000), (15, 13500), (0, 12500)]),
        ("coWoS_capacity", [(365, 8), (270, 12), (180, 15), (90, 20), (0, 28)]),
        ("sox_index", [(30, 4800), (25, 4950), (20, 5100), (15, 5200), (10, 5350), (5, 5400), (0, 5280)]),
        ("semiconductor_sales", [(180, 480), (150, 500), (120, 520), (90, 535), (60, 550), (30, 560), (0, 565)]),
        ("semiconductor_book_to_bill", [(180, 0.95), (150, 0.98), (120, 1.02), (90, 1.05), (60, 1.08), (30, 1.06), (0, 1.04)]),
        ("china_semiconductor_import", [(180, 310), (150, 325), (120, 340), (90, 355), (60, 370), (30, 380), (0, 390)]),
        ("gpu_lead_time", [(30, 36), (25, 34), (20, 32), (15, 30), (10, 28), (5, 26), (0, 24)]),
        ("euv_delivery", [(540, 8), (450, 10), (360, 12), (270, 11), (180, 14), (90, 13), (0, 15)]),
        ("chip_design_startup", [(360, 680), (270, 720), (180, 780), (90, 820), (0, 850)]),
        ("nvidia_dc_revenue", [(540, 145), (450, 181), (360, 221), (270, 260), (180, 310), (90, 355), (0, 380)]),
        ("tsmc_monthly_revenue", [(180, 2100), (150, 2200), (120, 2300), (90, 2400), (60, 2500), (30, 2450), (0, 2600)]),
        ("sk_hynix_hbm_ratio", [(360, 25), (270, 35), (180, 45), (90, 50), (0, 55)]),
        ("datacenter_capex", [(540, 420), (450, 460), (360, 510), (270, 560), (180, 620), (90, 680), (0, 720)]),
        ("amd_dc_revenue", ((540, 16), (450, 23), (360, 31), (270, 38), (180, 42), (90, 48), (0, 52))),
        ("ai_llm_training_cost", [(720, 100), (540, 150), (360, 200), (180, 250), (0, 300)]),
        ("chip_advance_node_yeild", [(360, 55), (270, 60), (180, 65), (90, 70), (0, 75)]),
        ("ai_inference_efficiency", [(180, 15), (90, 8), (60, 5), (30, 3.5), (0, 2.5)]),
        ("semiconductor_etf_flow", [(30, -120), (25, 80), (20, 350), (15, 420), (10, 280), (5, -50), (0, 180)]),
        ("ai_search_trend", [(30, 75), (25, 78), (20, 82), (15, 85), (10, 88), (5, 90), (0, 92)]),
    ]

    for ind_name, obs_data in obs_specs:
        kid = indicator_map[ind_name].id
        sorted_obs = sorted(obs_data, key=lambda x: x[0])
        prev = None
        for days_ago, val in sorted_obs:
            d = today - timedelta(days=days_ago)
            change = round((val - prev) / prev * 100, 1) if prev else None
            io = IndicatorObservation(
                indicator_id=kid, date=d, value=val,
                previous_value=prev, change_pct=change,
            )
            db.add(io)
            prev = val

    # ── Forecasts ──────────────────────────────────────────────
    forecast_data = [
        ("NVIDIA", 2026, 2200, 33, 30, 12, 66000, "高端GPU仍供不应求，2026H2 Blackwell放量", "高", "买入"),
        ("NVIDIA", 2027, 3000, 36, 25, 10, 75000, "供应逐步改善但需求持续旺盛", "中", "买入"),
        ("TSMC", 2026, 1050, 19, 20, 8, 21000, "AI先进制程满载，3nm营收占比提升", "高", "买入"),
        ("TSMC", 2027, 1250, 19, 18, 7, 22500, "2nm量产推动持续增长", "中", "买入"),
        ("SK Hynix", 2026, 750, 34, 15, 5, 11250, "HBM3E/HBM4领先，AI存储需求爆发", "高", "买入"),
        ("SK Hynix", 2027, 950, 27, 12, 4, 11400, "HBM4量产推动持续增长", "中", "买入"),
        ("ASML", 2026, 400, 14, 30, 10, 12000, "EUV需求强劲，High NA EUV交付", "高", "持有"),
        ("ASML", 2027, 460, 15, 28, 9, 12880, "先进制程扩产持续推动设备需求", "中", "持有"),
        ("Broadcom", 2026, 600, 18, 25, 8, 15000, "AI定制芯片+网络芯片双轮驱动", "高", "买入"),
        ("Broadcom", 2027, 720, 20, 22, 7, 15840, "AI ASIC占比持续提升", "中", "买入"),
        ("Google", 2026, 4200, 10, 22, 6, 25000, "TPU+Gemini驱动AI营收持续高增", "高", "买入"),
        ("Amazon", 2026, 7500, 11, 28, 3, 22000, "AWS+AI自研芯片加速增长", "高", "买入"),
        ("Microsoft", 2026, 3000, 11, 30, 8, 28000, "Azure AI+OpenAI生态持续扩张", "高", "买入"),
        ("Meta", 2026, 2100, 17, 22, 7, 15000, "AI广告+LLaMA+MTIA芯片生态", "高", "买入"),
        ("Applied Materials", 2026, 350, 13, 22, 5, 8000, "全球扩产周期持续，设备需求稳定", "中", "持有"),
        ("AMD", 2026, 380, 23, 25, 7, 9000, "MI400加速器追赶NVIDIA", "中", "持有"),
        ("Synopsys", 2026, 105, 14, 35, 14, 3500, "AI+EDA革命驱动设计工具需求", "高", "买入"),
        ("ARM", 2026, 60, 20, 40, 12, 2400, "AI端侧芯片ARM架构渗透率持续提升", "高", "买入"),
        ("ASE", 2026, 220, 11, 15, 3, 3500, "先进封装需求爆发，产能利用率提升", "中", "持有"),
        ("Marvell", 2026, 88, 22, 30, 10, 2880, "AI网络互联芯片需求爆发", "高", "买入"),
        ("Arista", 2026, 100, 22, 35, 12, 3500, "AI数据中心高速交换机需求强劲", "高", "买入"),
    ]

    for comp_name, ty, rev, growth, pe_est, ps_est, mcap, balance, conf, consensus in forecast_data:
        if comp_name not in company_map:
            continue
        f = Forecast(
            company_id=company_map[comp_name].id, target_year=ty,
            revenue_est=rev, revenue_growth_est=growth,
            pe_est=pe_est, ps_est=ps_est, market_cap_est=mcap,
            supply_balance_note=balance, confidence=conf,
            analyst_consensus=consensus,
            key_assumptions="AI需求持续增长、产能扩建顺利",
            upside_risks="需求超预期、产品竞争力提升",
            downside_risks="出口管制、竞争加剧、需求放缓",
        )
        db.add(f)

    # ── Judgment Logs ──────────────────────────────────────────
    judgments_data = [
        (today - timedelta(days=45), "SK海力士HBM4提前量产预期增强",
         "预期HBM4量产在2026H2",
         "HBM4有望提前至2026Q2量产，SK海力士技术领先扩大",
         "重大", "SK Hynix,Samsung", "hbm3e_price",
         "SK海力士宣布HBM4开发进度超预期，客户认证顺利",
         "上调SK海力士预测营收"),
        (today - timedelta(days=90), "台积电CoWoS产能翻倍计划超预期",
         "预期2025年底CoWoS月产能25k",
         "台积电宣布2025年底CoWoS月产能32k，2026年达45k",
         "重大", "TSMC,NVIDIA", "coWoS_capacity",
         "台积电法说会宣布大幅扩产计划",
         "上调先进封装环节AI芯片出货量预测"),
        (today - timedelta(days=30), "云厂商资本开支指引持续上调",
         "预期2026年四大云厂商Capex 2500亿美元",
         "四大云厂商指引2026年Capex超2800亿美元，AI投资不减",
         "中等", "NVIDIA,Broadcom", "datacenter_capex",
         "微软/谷歌/亚马逊/Meta最新财报均上调资本开支指引",
         "维持AI板块超配建议"),
        (today - timedelta(days=15), "HBM3E价格涨幅超预期",
         "预期HBM3E价格持平",
         "HBM3E合约价格环比上涨5-8%，供应持续紧张",
         "中等", "SK Hynix,Samsung,Micron", "hbm3e_price",
         "集邦咨询数据确认HBM3E价格上调",
         "上调HBM相关公司盈利预测"),
    ]

    for d, title, prev, new, level, comps, inds, evidence, action in judgments_data:
        jl = JudgmentLog(
            date=d, title=title, description=title,
            previous_view=prev, new_view=new,
            impact_level=level, related_companies=comps,
            related_indicators=inds, evidence=evidence, action_taken=action,
        )
        db.add(jl)

    # ── Scoring Dimensions ─────────────────────────────────────
    dims_data = [
        ("valuation", "估值合理性", 20, "PE/PB/PS估值水平与历史对比"),
        ("revenue_growth", "营收增长", 20, "近3年营收CAGR，行业增速对比"),
        ("supply_demand_gap", "供需缺口", 20, "所在环节供需缺口大小"),
        ("barrier_to_entry", "进入壁垒", 15, "行业进入壁垒高度"),
        ("profit_margin", "利润率", 10, "毛利率和净利率水平"),
        ("market_position", "市场地位", 15, "市占率、竞争优势、品牌"),
    ]

    dim_map = {}
    for name, name_cn, weight, desc in dims_data:
        d = ScoringDimension(name=name, name_cn=name_cn, weight=weight, description=desc)
        db.add(d); db.flush()
        dim_map[name] = d

    # ── Company Scores ─────────────────────────────────────────
    score_data = {
        "NVIDIA": {"valuation": 55, "revenue_growth": 95, "supply_demand_gap": 90, "barrier_to_entry": 95, "profit_margin": 95, "market_position": 100},
        "SK Hynix": {"valuation": 70, "revenue_growth": 85, "supply_demand_gap": 95, "barrier_to_entry": 80, "profit_margin": 70, "market_position": 80},
        "TSMC": {"valuation": 60, "revenue_growth": 70, "supply_demand_gap": 85, "barrier_to_entry": 100, "profit_margin": 85, "market_position": 100},
        "ASML": {"valuation": 65, "revenue_growth": 50, "supply_demand_gap": 60, "barrier_to_entry": 100, "profit_margin": 90, "market_position": 100},
        "Broadcom": {"valuation": 70, "revenue_growth": 75, "supply_demand_gap": 70, "barrier_to_entry": 85, "profit_margin": 85, "market_position": 75},
        "AMD": {"valuation": 60, "revenue_growth": 55, "supply_demand_gap": 60, "barrier_to_entry": 75, "profit_margin": 50, "market_position": 45},
        "Samsung": {"valuation": 75, "revenue_growth": 45, "supply_demand_gap": 65, "barrier_to_entry": 70, "profit_margin": 35, "market_position": 60},
        "Micron": {"valuation": 65, "revenue_growth": 60, "supply_demand_gap": 60, "barrier_to_entry": 65, "profit_margin": 40, "market_position": 40},
        "Applied Materials": {"valuation": 70, "revenue_growth": 40, "supply_demand_gap": 55, "barrier_to_entry": 80, "profit_margin": 65, "market_position": 65},
        "Lam Research": {"valuation": 70, "revenue_growth": 35, "supply_demand_gap": 50, "barrier_to_entry": 75, "profit_margin": 65, "market_position": 60},
    }

    for comp_name, scores in score_data.items():
        cid = company_map[comp_name].id
        for dim_name, score in scores.items():
            cs = CompanyScore(
                company_id=cid, dimension_id=dim_map[dim_name].id,
                score=score, reason="基于财务数据和行业分析",
                date_updated=today,
            )
            db.add(cs)

    # ── Portfolio ──────────────────────────────────────────────
    p = Portfolio(
        name="AI芯片龙头精选组合",
        description="基于量化评分选出的AI芯片产业链龙头组合",
        created_date=today - timedelta(days=60),
        initial_capital=1000000.0, rebalance_frequency="monthly",
        strategy_notes="聚焦估值合理+营收高增长+供需缺口大的壁垒环节龙头",
    )
    db.add(p); db.flush()

    # ── Portfolio Holdings ─────────────────────────────────────
    # Weight: compute normalized from weighted scores
    holdings_spec = [
        ("NVIDIA", 30, "AI芯片绝对龙头，CUDA生态壁垒极高，供需缺口持续"),
        ("SK Hynix", 20, "HBM领先者，供需缺口最大环节，扩产难度极高"),
        ("TSMC", 20, "晶圆代工垄断者，先进制程产能满载，壁垒最高"),
        ("Broadcom", 12, "AI定制芯片+网络双轮驱动，估值合理"),
        ("ASML", 10, "EUV垄断，设备环节壁垒最高，但增长相对稳健"),
        ("Applied Materials", 8, "半导体设备龙头，受益于全球扩产周期"),
    ]

    total_weight = sum(w for _, w, _ in holdings_spec)
    for comp_name, weight, reason in holdings_spec:
        cid = company_map[comp_name].id
        cost = random.uniform(80, 200)
        shares_val = 1000000 * (weight / total_weight)
        shares = shares_val / cost
        ph = PortfolioHolding(
            portfolio_id=p.id, company_id=cid,
            weight=weight / total_weight * 100,
            actual_weight=weight / total_weight * 100,
            shares=round(shares, 2), avg_cost=cost,
            current_price=round(cost * random.uniform(0.9, 1.3), 2),
            market_value=round(shares_val, 2),
            return_pct=round(random.uniform(-5, 15), 2),
            allocation_reason=reason, date_added=today - timedelta(days=60),
        )
        db.add(ph)

    # ── Portfolio Performance (60 days) ────────────────────────
    val = 1000000
    for i in range(60, 0, -1):
        d = today - timedelta(days=i)
        ret = random.gauss(0.003, 0.015)
        val *= (1 + ret)
        cum_ret = (val / 1000000 - 1) * 100
        pp = PortfolioPerformance(
            portfolio_id=p.id, date=d,
            total_value=round(val, 2), cash=50000,
            daily_return=round(ret * 100, 2),
            cumulative_return=round(cum_ret, 2),
            benchmark_return=round(cum_ret * random.uniform(0.7, 1.0), 2),
            alpha=round(random.uniform(-0.2, 0.5), 2),
            sharpe_ratio=round(random.uniform(0.5, 1.8), 2),
            max_drawdown=round(random.uniform(3, 8), 2),
        )
        db.add(pp)

    # ── Portfolio Evaluation ───────────────────────────────────
    pe = PortfolioEvaluation(
        portfolio_id=p.id, date=today,
        summary="组合整体表现良好，AI需求持续超预期，龙头公司业绩增长强劲",
        adjustment_suggestion="建议维持现有配置，关注HBM供需变化和云厂商Capex指引",
        suggested_changes={"action": "hold", "details": "维持当前权重配置"},
        risk_warnings="关注出口管制升级、HBM竞争格局变化、估值回调风险",
        conviction_changes="对SK海力士信心增强(HBM4提前)，对ASML维持中性",
        is_actionable=False, created_by="system",
    )
    db.add(pe)

    db.commit()
    db.close()
    print("Industry chain data seeded successfully!")


if __name__ == "__main__":
    seed()
