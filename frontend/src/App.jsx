import { lazy, Suspense } from "react";
import { BrowserRouter, Routes, Route, NavLink, Navigate } from "react-router-dom";
import Dashboard from "./pages/Dashboard";
import Companies from "./pages/Companies";
import IndustryChain from "./pages/IndustryChain";
import InvestmentPlan from "./pages/InvestmentPlan";
import PortfolioPage from "./pages/PortfolioPage";
import IndustryIntelligence from "./pages/IndustryIntelligence";
import JudgmentLog from "./pages/JudgmentLog";
import IndustryData from "./pages/IndustryData";
import CompanyData from "./pages/CompanyData";

const TechGlossary = lazy(() => import("./pages/TechGlossary"));

function App() {
  // Vite uses VITE_BASE at build time; dev defaults to "/" so local "npm run dev"
  // works at http://localhost:5180/, and the Docker build sets it to "/teck_dashboard/"
  // for the cloud deploy.
  const basename = import.meta.env.VITE_BASE === "/teck_dashboard/" ? "/teck_dashboard" : "/";
  return (
    <BrowserRouter basename={basename}>
      <div className="app-layout">
        <nav className="sidebar">
          <h1>Teck Dashboard</h1>
          <p className="subtitle">AI 芯片产业链分析平台</p>
          <ul className="nav-list">
            <li><NavLink to="/overview" end>📊 市场概览</NavLink></li>
            <li><NavLink to="/portfolio">📁 跟踪组合</NavLink></li>
            <li style={{ marginTop: 8, borderTop: "1px solid var(--border)", paddingTop: 8 }}>
              <span style={{ fontSize: 11, color: "var(--text-secondary)", textTransform: "uppercase", letterSpacing: 1 }}>全景</span>
            </li>
            <li><NavLink to="/industry-chain">🔗 产业链</NavLink></li>
            <li><NavLink to="/tech-glossary">📖 技术栈</NavLink></li>
            <li><NavLink to="/companies">🏢 龙头公司</NavLink></li>
            <li><NavLink to="/investment-plan">📋 台积电与海力士</NavLink></li>
            <li style={{ marginTop: 8, borderTop: "1px solid var(--border)", paddingTop: 8 }}>
              <span style={{ fontSize: 11, color: "var(--text-secondary)", textTransform: "uppercase", letterSpacing: 1 }}>情报</span>
            </li>
            <li><NavLink to="/industry-intelligence" end>⚡ 产业情报-截面</NavLink></li>
            <li><NavLink to="/industry-intelligence/sequence">📅 产业情报-序时</NavLink></li>
            <li style={{ marginTop: 8, borderTop: "1px solid var(--border)", paddingTop: 8 }}>
              <span style={{ fontSize: 11, color: "var(--text-secondary)", textTransform: "uppercase", letterSpacing: 1 }}>数据</span>
            </li>
            <li><NavLink to="/company-data">📊 数据浏览-公司</NavLink></li>
            <li><NavLink to="/industry-data">📈 数据浏览-产业</NavLink></li>
          </ul>
        </nav>
        <main className="main-content">
          <Routes>
            <Route path="/" element={<Navigate to="/overview" replace />} />
            <Route path="/overview" element={<Dashboard />} />
            <Route path="/industry-chain" element={<IndustryChain />} />
            <Route path="/industry-intelligence" element={<IndustryIntelligence />} />
            <Route path="/industry-intelligence/sequence" element={<JudgmentLog />} />
            <Route path="/industry-data" element={<IndustryData />} />
            <Route path="/company-data" element={<CompanyData />} />
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
            <Route path="*" element={<Navigate to="/overview" replace />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}

export default App;
