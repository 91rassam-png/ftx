// ============================================================
// THE DESK — 프론트엔드 로직
// ============================================================

const ANALYSTS = [
  { key: "Taro",  role: "TECHNICAL · 기술적 분석" },
  { key: "Smith", role: "FUNDAMENTAL · 기본적 분석" },
  { key: "Nova",  role: "NEWS · 뉴스 분석" },
  { key: "Kirk",  role: "COMMUNITY · 커뮤니티 분석" },
];

const VIEW_LABEL = { bullish: "BULL", bearish: "BEAR", neutral: "NEUTRAL" };
const VIEW_LED_CLASS = { bullish: "done-bull", bearish: "done-bear", neutral: "done-neutral" };

let tvWidget = null;
let ticketTapeInjected = false;
let currentEventSource = null;

// ---------- 데스크 카드 초기화 ----------
function renderDesks() {
  const desks = document.getElementById("desks");
  desks.innerHTML = ANALYSTS.map(a => `
    <div class="desk-card" data-analyst="${a.key}" id="desk-${a.key}">
      <div class="desk-top">
        <div class="desk-name">${a.key}</div>
        <div class="led" id="led-${a.key}"></div>
      </div>
      <div class="desk-role">${a.role}</div>
      <div class="desk-status" id="status-${a.key}">대기 중</div>
      <div id="result-${a.key}"></div>
    </div>
  `).join("");
}

function setDeskAnalyzing(key) {
  document.getElementById(`led-${key}`).className = "led analyzing";
  document.getElementById(`status-${key}`).textContent = "분석 중 ...";
}

function setDeskResult(result) {
  const key = result.analyst;
  const led = document.getElementById(`led-${key}`);
  const status = document.getElementById(`status-${key}`);
  const resultBox = document.getElementById(`result-${key}`);
  if (!led || !resultBox) return;

  const view = result.view || "neutral";
  led.className = `led ${VIEW_LED_CLASS[view] || "done-neutral"}`;
  status.textContent = "분석 완료";

  const confidence = Number.isFinite(result.confidence) ? result.confidence : 0;
  const points = Array.isArray(result.key_points) ? result.key_points : [];

  resultBox.innerHTML = `
    <span class="view-badge ${view}">${VIEW_LABEL[view] || "NEUTRAL"}</span>
    <div class="confidence-row" style="margin-top:8px;">
      <span>확신도</span>
      <div class="confidence-bar"><div class="confidence-fill" style="width:${confidence}%; background:var(--${view === 'bullish' ? 'bull' : view === 'bearish' ? 'bear' : 'neutral'});"></div></div>
      <span>${confidence}</span>
    </div>
    <div class="desk-summary" style="margin-top:10px;">${escapeHtml(result.summary || "")}</div>
    ${points.length ? `<ul class="desk-points" style="margin-top:8px;">${points.map(p => `<li>${escapeHtml(p)}</li>`).join("")}</ul>` : ""}
  `;
}

// ---------- 리서치팀 패널 ----------
function setResearch(note) {
  const box = document.getElementById("research-body");
  const stance = note.overall_stance || "mixed";
  const stanceClass = stance === "bull" ? "bull" : stance === "bear" ? "bear" : "mixed";
  const stanceLabel = stance === "bull" ? "BULL CASE 우세" : stance === "bear" ? "BEAR CASE 우세" : "의견 혼재";
  const conviction = Number.isFinite(note.conviction) ? note.conviction : 0;
  const bull = Array.isArray(note.bull_case) ? note.bull_case : [];
  const bear = Array.isArray(note.bear_case) ? note.bear_case : [];

  box.innerHTML = `
    <div class="stance-row">
      <div class="stance-badge ${stanceClass}">${stanceLabel}</div>
      <div class="confidence-row" style="flex:1;">
        <span>종합 확신도</span>
        <div class="confidence-bar"><div class="confidence-fill" style="width:${conviction}%; background:var(--amber);"></div></div>
        <span>${conviction}</span>
      </div>
    </div>
    <div class="case-grid">
      <div class="case-col bull-col">
        <div class="case-col-title">Bull Case</div>
        <ul>${bull.map(p => `<li>${escapeHtml(p)}</li>`).join("") || "<li>—</li>"}</ul>
      </div>
      <div class="case-col bear-col">
        <div class="case-col-title">Bear Case</div>
        <ul>${bear.map(p => `<li>${escapeHtml(p)}</li>`).join("") || "<li>—</li>"}</ul>
      </div>
    </div>
    ${note.key_disagreements ? `<div class="disagreement">⚡ 의견 불일치: ${escapeHtml(note.key_disagreements)}</div>` : ""}
    <div class="research-summary">${escapeHtml(note.summary || "")}</div>
  `;
}

// ---------- Ace 최종 판단 패널 ----------
function setVerdict(decision) {
  const box = document.getElementById("verdict-body");
  const d = (decision.decision || "hold").toLowerCase();
  const dClass = d === "buy" ? "buy" : d === "sell" ? "sell" : "hold";
  const dLabel = d === "buy" ? "BUY" : d === "sell" ? "SELL" : "HOLD";
  const conviction = Number.isFinite(decision.conviction) ? decision.conviction : 0;
  const posSize = Number.isFinite(decision.suggested_position_size_pct) ? decision.suggested_position_size_pct : 0;
  const risks = Array.isArray(decision.key_risks) ? decision.key_risks : [];

  box.innerHTML = `
    <div class="decision-word ${dClass}">${dLabel}</div>
    <div class="decision-sub">ACE'S CALL</div>

    <div class="gauge-row">
      <div class="gauge-label"><span>확신도</span><span>${conviction}/100</span></div>
      <div class="gauge-track"><div class="gauge-fill" style="width:${conviction}%;"></div></div>
    </div>
    <div class="gauge-row">
      <div class="gauge-label"><span>제안 비중</span><span>${posSize}%</span></div>
      <div class="gauge-track"><div class="gauge-fill" style="width:${posSize}%; background:var(--taro);"></div></div>
    </div>

    <div class="verdict-reasoning">${escapeHtml(decision.reasoning || "")}</div>

    ${risks.length ? `<div class="verdict-section-title">주요 리스크</div><ul>${risks.map(r => `<li>${escapeHtml(r)}</li>`).join("")}</ul>` : ""}
    ${decision.invalidation_condition ? `<div class="verdict-section-title">판단 무효 조건</div><div class="invalidation">${escapeHtml(decision.invalidation_condition)}</div>` : ""}
    <div class="disclaimer-line">${escapeHtml(decision.disclaimer || "이 결과는 AI 기반 참고용 리서치이며 투자 자문이 아닙니다.")}</div>
  `;
}

function resetPanels() {
  document.getElementById("research-body").innerHTML = `<div class="empty-state">애널리스트 4인의 분석이 끝나면<br>리서치팀이 bull/bear 케이스를 종합합니다</div>`;
  document.getElementById("verdict-body").innerHTML = `<div class="empty-state">리서치팀의 종합 노트를 바탕으로<br>Ace가 최종 결정을 내립니다</div>`;
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = String(str);
  return div.innerHTML;
}

// ---------- TradingView 차트 ----------
function toTradingViewSymbol(ticker) {
  const t = ticker.trim().toUpperCase();
  if (t.endsWith(".KS") || t.endsWith(".KQ")) return `KRX:${t.replace(".KS", "").replace(".KQ", "")}`;
  if (/^\d{6}$/.test(t)) return `KRX:${t}`;
  return t; // 미국 등: TradingView가 자동으로 주요 거래소 심볼을 해석
}

function updateChart(ticker) {
  const symbol = toTradingViewSymbol(ticker);
  document.getElementById("chart-symbol-label").textContent = symbol;
  const container = document.getElementById("tv-chart-container");
  container.innerHTML = "";

  if (typeof TradingView === "undefined") {
    container.innerHTML = `<div class="chart-placeholder">TradingView 위젯 로딩 실패<br>네트워크 연결을 확인하세요</div>`;
    return;
  }

  tvWidget = new TradingView.widget({
    autosize: true,
    symbol: symbol,
    interval: "D",
    timezone: "Etc/UTC",
    theme: "dark",
    style: "1",
    locale: "kr",
    toolbar_bg: "#171B22",
    enable_publishing: false,
    hide_top_toolbar: false,
    hide_legend: false,
    save_image: false,
    container_id: "tv-chart-container",
  });
}

function injectTickerTape() {
  if (ticketTapeInjected) return;
  ticketTapeInjected = true;
  const container = document.querySelector(".tv-ticker-tape");
  const script = document.createElement("script");
  script.src = "https://s3.tradingview.com/external-embedding/embed-widget-ticker-tape.js";
  script.async = true;
  script.innerHTML = JSON.stringify({
    symbols: [
      { proName: "FOREXCOM:SPXUSD", title: "S&P 500" },
      { proName: "NASDAQ:AAPL", title: "AAPL" },
      { proName: "NASDAQ:TSLA", title: "TSLA" },
      { proName: "KRX:005930", title: "삼성전자" },
      { proName: "BITSTAMP:BTCUSD", title: "BTC" },
    ],
    showSymbolLogo: true,
    colorTheme: "dark",
    isTransparent: true,
    displayMode: "compact",
    locale: "kr",
  });
  container.appendChild(script);
}

// ---------- 분석 실행 (SSE) ----------
function runAnalysis(ticker) {
  if (currentEventSource) currentEventSource.close();

  renderDesks();
  resetPanels();
  ANALYSTS.forEach(a => setDeskAnalyzing(a.key));
  updateChart(ticker);

  const btn = document.getElementById("analyze-btn");
  btn.disabled = true;
  btn.textContent = "분석 중 ...";

  const es = new EventSource(`/api/analyze?ticker=${encodeURIComponent(ticker)}`);
  currentEventSource = es;

  es.addEventListener("analyst", (e) => setDeskResult(JSON.parse(e.data)));
  es.addEventListener("research", (e) => setResearch(JSON.parse(e.data)));
  es.addEventListener("decision", (e) => setVerdict(JSON.parse(e.data)));
  es.addEventListener("done", () => {
    es.close();
    btn.disabled = false;
    btn.textContent = "분석 개시";
  });
  es.onerror = () => {
    es.close();
    btn.disabled = false;
    btn.textContent = "분석 개시";
  };
}

// ---------- 초기화 ----------
document.addEventListener("DOMContentLoaded", () => {
  renderDesks();
  injectTickerTape();

  document.getElementById("ticker-form").addEventListener("submit", (e) => {
    e.preventDefault();
    const ticker = document.getElementById("ticker-input").value.trim();
    if (ticker) runAnalysis(ticker);
  });
});
