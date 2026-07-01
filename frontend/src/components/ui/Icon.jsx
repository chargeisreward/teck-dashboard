import {
  ChartLineUp,
  ChartPieSlice,
  Factory,
  HardDrives,
  Lightning,
  Link,
  Memory,
  Minus,
  Monitor,
  Plus,
  SquaresFour,
  TrendUp,
  Wrench,
  CaretDown,
  CaretUp,
  ArrowUpRight,
  ArrowDownRight,
  ArrowsHorizontal,
  Warning,
  Info,
  CheckCircle,
  XCircle,
} from "@phosphor-icons/react";

/**
 * Icon — 统一图标映射
 *
 * 避免在代码中直接使用 emoji。所有图标通过 name 映射到 Phosphor Icons。
 */
const ICONS = {
  overview: ChartPieSlice,
  portfolio: SquaresFour,
  industryChain: Link,
  techGlossary: HardDrives,
  companies: Factory,
  investmentPlan: TrendUp,
  industryIntelligence: Lightning,
  sequence: ChartLineUp,
  companyData: Monitor,
  industryData: ChartLineUp,

  rawMaterials: Wrench,
  equipment: Wrench,
  eda: Memory,
  chipDesign: Memory,
  foundry: Factory,
  memory: HardDrives,
  packaging: SquaresFour,
  distribution: Link,
  endMarket: ChartPieSlice,
  gpuCloud: Lightning,

  up: CaretUp,
  down: CaretDown,
  change: ArrowsHorizontal,
  expand: CaretDown,
  collapse: CaretUp,
  external: ArrowUpRight,
  trendUp: ArrowUpRight,
  trendDown: ArrowDownRight,

  info: Info,
  warning: Warning,
  success: CheckCircle,
  error: XCircle,

  plus: Plus,
  minus: Minus,
};

export const ICON_NAMES = Object.keys(ICONS);

export default function Icon({ name, size = 18, weight = "regular", className = "", ...props }) {
  const Component = ICONS[name];
  if (!Component) {
    console.warn(`Icon "${name}" not found`);
    return null;
  }
  return <Component size={size} weight={weight} className={`ui-icon${className ? " " + className : ""}`} {...props} />;
}
