const homeView = document.getElementById("homeView");
const resultView = document.getElementById("resultView");
const pageTitle = document.getElementById("pageTitle");
const backBtn = document.getElementById("backBtn");
const latestDate = document.getElementById("latestDate");
const latestPeriod = document.getElementById("latestPeriod");
const latestNumbers = document.getElementById("latestNumbers");
const weekRange = document.getElementById("weekRange");
const weekList = document.getElementById("weekList");
const updateInfo = document.getElementById("updateInfo");

let currentGame = null;
let weekOffset = 0;
let visibleWeekRows = [];

async function loadLotteryData() {
  const files = {
    "539": "539.json",
    "lotto649": "lotto649.json",
    "fantasy5": "fantasy5.json"
  };

  for (const [id, filename] of Object.entries(files)) {
    try {
      const response = await fetch(`data/${filename}?v=${Date.now()}`, { cache: "no-store" });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const payload = await response.json();

      // 支援目前 Python 輸出的 { updatedAt, records } 格式，
      // 也相容舊版直接存陣列的 JSON。
      const game = window.LOTTERY_GAMES[id];
      game.records = Array.isArray(payload) ? payload : (payload.records || []);
      game.updatedAt = Array.isArray(payload) ? "資料已載入" : (payload.updatedAt || "未知");

      game.records.sort((a, b) =>
        (b.date || "").localeCompare(a.date || "") ||
        (b.period || "").localeCompare(a.period || "")
      );
      console.log(`${game.name}：載入 ${game.records.length} 筆`);
    } catch (error) {
      window.LOTTERY_GAMES[id].updatedAt = "資料讀取失敗";
      console.error(`${filename} 讀取失敗：`, error);
    }
  }
}

document.querySelectorAll(".game-card").forEach(button => {
  button.addEventListener("click", () => openGame(button.dataset.game));
});
backBtn.addEventListener("click", showHome);
document.getElementById("prevWeek").addEventListener("click", () => {
  weekOffset--;
  renderWeek();
});
document.getElementById("nextWeek").addEventListener("click", () => {
  if (weekOffset < 0) {
    weekOffset++;
    renderWeek();
  }
});

function openGame(id) {
  currentGame = window.LOTTERY_GAMES[id];
  weekOffset = 0;
  homeView.hidden = true;
  resultView.hidden = false;
  backBtn.hidden = false;
  pageTitle.textContent = currentGame.name;
  renderLatest();
  renderWeek();
}

function showHome() {
  currentGame = null;
  resultView.hidden = true;
  homeView.hidden = false;
  backBtn.hidden = true;
  pageTitle.textContent = "開獎查詢";
}

function makeBalls(numbers, specialNumber = null) {
  const main = (numbers || []).map(n =>
    `<span class="ball">${String(n).padStart(2, "0")}</span>`
  ).join("");

  const special = specialNumber == null ? "" :
    `<span class="special-wrap"><span class="special-label">特別號</span><span class="ball special">${String(specialNumber).padStart(2, "0")}</span></span>`;

  return main + special;
}

function formatDate(date) {
  const d = new Date(date + "T12:00:00");
  return `${d.getFullYear()}年${d.getMonth() + 1}月${d.getDate()}日`;
}

function renderLatest() {
  const record = currentGame.records[0];

  if (!record) {
    latestDate.textContent = "目前沒有資料";
    latestPeriod.textContent = "";
    latestNumbers.innerHTML = '<div class="empty">目前沒有可顯示的開獎資料。</div>';
    updateInfo.textContent = `資料狀態：${currentGame.updatedAt}`;
    document.getElementById("shareLatest").disabled = true;
    return;
  }

  document.getElementById("shareLatest").disabled = false;
  latestDate.textContent = formatDate(record.date);
  latestPeriod.textContent = record.period ? `第 ${record.period} 期` : "";
  latestNumbers.innerHTML = makeBalls(record.numbers, record.specialNumber);
  updateInfo.textContent = `資料更新時間：${currentGame.updatedAt}`;

  document.getElementById("shareLatest").onclick = () =>
    shareRows(`${currentGame.name} 最新開獎`, formatDate(record.date), [record]);
}

function getWeekRange(offset) {
  // 以使用者手機/電腦的本地日期為準，週一至週日。
  const today = new Date();
  today.setHours(12, 0, 0, 0);
  const monday = new Date(today);
  monday.setDate(today.getDate() - ((today.getDay() + 6) % 7) + offset * 7);
  const sunday = new Date(monday);
  sunday.setDate(monday.getDate() + 6);
  return { monday, sunday };
}

function toISO(d) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

function renderWeek() {
  const { monday, sunday } = getWeekRange(weekOffset);
  weekRange.textContent = `${monday.getMonth() + 1}/${monday.getDate()}－${sunday.getMonth() + 1}/${sunday.getDate()}`;
  document.getElementById("nextWeek").disabled = weekOffset === 0;

  const start = toISO(monday);
  const end = toISO(sunday);
  visibleWeekRows = currentGame.records
    .filter(r => r.date >= start && r.date <= end)
    .sort((a, b) => b.date.localeCompare(a.date));

  weekList.innerHTML = visibleWeekRows.length
    ? visibleWeekRows.map(r => `
      <article class="week-item">
        <div class="week-date">${formatDate(r.date)}</div>
        <div class="number-row">${makeBalls(r.numbers, r.specialNumber)}</div>
      </article>
    `).join("")
    : '<div class="empty">這一週沒有開獎紀錄</div>';

  document.getElementById("shareWeek").disabled = visibleWeekRows.length === 0;
  document.getElementById("shareWeek").onclick = () =>
    shareRows(`${currentGame.name} 每週開獎紀錄`, weekRange.textContent, visibleWeekRows);
}

document.getElementById("shareLatest").addEventListener("click", () => {
  if (!currentGame || !currentGame.records.length) return;
});
document.getElementById("shareWeek").addEventListener("click", () => {
  if (!visibleWeekRows.length) return;
});

// 網頁載入時先讀取 JSON，再讓使用者選擇彩券。
loadLotteryData();
