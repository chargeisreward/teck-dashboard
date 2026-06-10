import { lazy, Suspense } from "react";
import { BrowserRouter, Routes, Route, NavLink, Navigate } from "react-router-dom";
import Dashboard from "./pages/Dashboard";
import Companies from "./pages/Companies";
import IndustryChain from "./pages/IndustryChain";
import InvestmentPlan from "./pages/InvestmentPlan";
import PortfolioPage from "./pages/PortfolioPage";
import IndustryIntelligence from "./pages/IndustryIntelligence";

const TechGlossary = lazy(() => import("./pages/TechGlossary"));

function App() {
  return (
    <BrowserRouter>
      <div className="app-layout">
        <nav className="sidebar">
          <h1>Teck Dashboard</h1>
          <p className="subtitle">AI 芯片产业链分析平台</p>
          <ul className="nav-list">
            <li><NavLink to="/" end>市场概览</NavLink></li>
            <li><NavLink to="/industry-chain">产业链全景</NavLink></li>
            <li><NavLink to="/industry-intelligence" style={{ fontWeight: 600, color: "var(--accent, #3b82f6)" }}>⚡ 产业情报</NavLink></li>
            <li><NavLink to="/investment-plan">TSM+EWY配置方案</NavLink></li>
            <li><NavLink to="/portfolio">模拟组合</NavLink></li>
            <li style={{ marginTop: 16, borderTop: "1px solid var(--border)", paddingTop: 12 }}>
              <span style={{ fontSize: 11, color: "var(--text-secondary)", textTransform: "uppercase", letterSpacing: 1 }}>数据</span>
            </li>
            <li><NavLink to="/industry-intelligence?tab=timeline">判断日志</NavLink></li>
            <li><NavLink to="/companies">公司列表</NavLink></li>
            <li><NavLink to="/tech-glossary">技术释义全景</NavLink></li>
          </ul>
        </nav>
        <main className="main-content">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/industry-chain" element={<IndustryChain />} />
            <Route path="/industry-intelligence" element={<IndustryIntelligence />} />
            <Route path="/industry-data" element={<IndustryIntelligence />} />
            <Route path="/indicators" element={<IndustryIntelligence />} />
            <Route path="/judgment-log" element={<IndustryIntelligence />} />
            <Route path="/investment-plan" element={<InvestmentPlan />} />
            <Route path="/portfolio" element={<PortfolioPage />} />
            <Route path="/companies" element={<Companies />} />
            <Route path="/tech-glossary" element={
              <Suspense fallback={<div className="loading">加载技术释义...</div>}>
                <TechGlossary />
              </Suspense>
            } />
            <Route path="/storage" element={
              <Suspense fallback={<div className="loading">加载技术释义...</div>}>
                <TechGlossary />
              </Suspense>
            } />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}

export default App;
