const DATA = "./";

let ranking = [];
let winners = [];
let categories = [];
let tournaments = [];
let status = {};

async function loadJSON(file) {
  const response = await fetch(DATA + file);
  if (!response.ok) throw new Error(`Falha ao carregar ${file}`);
  return response.json();
}

function fmt(value, digits = 0) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "—";
  }
  return Number(value).toLocaleString("pt-BR", {
    maximumFractionDigits: digits,
    minimumFractionDigits: digits
  });
}

function dateFmt(value) {
  if (!value) return "—";
  return new Intl.DateTimeFormat("pt-BR", {
    dateStyle: "short",
    timeStyle: "short"
  }).format(new Date(value));
}

function renderCards() {
  const cards = [
    ["Jogadores", status.players ?? ranking.length],
    ["Torneios", status.tournaments ?? tournaments.length],
    ["Participações", status.participations ?? "—"],
    ["Atualizado", status.updated_at ? dateFmt(status.updated_at) : "—"]
  ];

  document.querySelector("#cards").innerHTML = cards.map(([label, value]) => `
    <div class="card">
      <span class="card-label">${label}</span>
      <strong class="card-value">${value}</strong>
    </div>
  `).join("");
}

function renderRanking(filter = "") {
  const query = filter.trim().toLowerCase();
  const rows = ranking.filter(p => (p.Nick || "").toLowerCase().includes(query));

  const tbody = document.querySelector("#ranking tbody");
  tbody.innerHTML = rows.map((p, i) => `
    <tr data-index="${i}">
      <td class="rank">${i + 1}</td>
      <td class="player">${p.Nick ?? "—"}</td>
      <td><strong>${fmt(p.Pontos)}</strong></td>
      <td>${fmt(p.Desempenho_Medio)}</td>
      <td>${fmt(p.podio_primeiro)}</td>
      <td>${fmt(p.podio_segundo)}</td>
      <td>${fmt(p.podio_terceiro)}</td>
      <td>${fmt(p.Rating_Medio)}</td>
      <td>${fmt(p.Participacoes)}</td>
    </tr>
  `).join("");

  // 🔹 Agora usa rows[i] para abrir o jogador correto
  tbody.querySelectorAll("tr").forEach((tr, i) => {
    tr.addEventListener("click", () => {
      showPlayerDetails(rows[i]);
    });
  });
}

function renderWinners() {
  document.querySelector("#winners tbody").innerHTML = winners.slice(0, 20).map((p, i) => `
    <tr>
      <td class="rank">${i + 1}</td>
      <td class="player">${p.vencedores ?? "—"}</td>
      <td>${fmt(p.vitorias)}</td>
      <td>${fmt(p.Pontos)}</td>
    </tr>
  `).join("");
}

function renderCategories() {
  document.querySelector("#categories tbody").innerHTML = categories.map(p => `
    <tr>
      <td>${p.Categoria ?? "—"}</td>
      <td class="player">${p.Nick ?? "—"}</td>
      <td>${fmt(p.Rating_Medio)}</td>
      <td>${fmt(p.Pontos)}</td>
    </tr>
  `).join("");
}

function renderTournaments() {
  const recent = [...tournaments].reverse().slice(0, 30);

  document.querySelector("#tournaments tbody").innerHTML = recent.map(t => `
    <tr>
      <td>${dateFmt(t.startsAt)}</td>
      <td>${t.name ?? "—"}</td>
      <td class="player">${t.winner ?? "—"}</td>
      <td><a href="${t.url}" target="_blank" rel="noopener">Lichess ↗</a></td>
    </tr>
  `).join("");
}

// 🔹 Função para abrir o modal com detalhes do jogador + gráfico
function showPlayerDetails(player) {
  const modal = document.getElementById("player-modal");
  const details = document.getElementById("player-details");

  details.innerHTML = `
    <h2 style="color: var(--accent)">#${ranking.indexOf(player) + 1} ${player.Nick}</h2>
    <p><strong>${fmt(player.Pontos)}</strong> pontos</p>
    <hr>
    <p><strong>Torneios:</strong> ${fmt(player.Participacoes)}</p>
    <p><strong>Desempenho médio:</strong> ${fmt(player.Desempenho_Medio)}</p>
    <p><strong>Rating médio:</strong> ${fmt(player.Rating_Medio)}</p>
    <p><strong>1º lugares:</strong> ${fmt(player.podio_primeiro)}</p>
    <p><strong>2º lugares:</strong> ${fmt(player.podio_segundo)}</p>
    <p><strong>3º lugares:</strong> ${fmt(player.podio_terceiro)}</p>
    <p><strong>Pontos por torneio:</strong> ${fmt(player.Pontos_por_Torneio)}</p>
  `.replace(/—/g, '<span class="muted">—</span>');

  // 🔹 Renderizar gráfico Chart.js
  const ctx = document.getElementById("performance-chart").getContext("2d");
  if (window.performanceChart) {
    window.performanceChart.destroy(); // destruir gráfico anterior
  }
  window.performanceChart = new Chart(ctx, {
    type: "bar",
    data: {
      labels: ["Pontos", "Desempenho", "Rating", "Pontos/Torneio"],
      datasets: [{
        label: "Desempenho",
        data: [
          player.Pontos,
          player.Desempenho_Medio,
          player.Rating_Medio,
          player.Pontos_por_Torneio
        ],
        backgroundColor: ["#d4af37", "#9a9a9a", "#e0e0e0", "#444"]
      }]
    },
    options: {
      responsive: true,
      plugins: { legend: { display: false } }
    }
  });

  modal.classList.remove("hidden");
  modal.setAttribute("aria-hidden", "false");
}

// 🔹 Botão para fechar o modal
document.getElementById("close-modal").addEventListener("click", () => {
  const modal = document.getElementById("player-modal");
  modal.classList.add("hidden");
  modal.setAttribute("aria-hidden", "true");
});

// 🔹 Fechar modal com tecla Esc
document.addEventListener("keydown", e => {
  if (e.key === "Escape") {
    const modal = document.getElementById("player-modal");
    modal.classList.add("hidden");
    modal.setAttribute("aria-hidden", "true");
  }
});

async function init() {
  try {
    [ranking, winners, categories, tournaments, status] = await Promise.all([
      loadJSON("jogadores.json"),
      loadJSON("vencedores.json"),
      loadJSON("categorias.json"),
      loadJSON("torneios.json"),
      loadJSON("status.json")
    ]);

    renderCards();
    renderRanking();
    renderWinners();
    renderCategories();
    renderTournaments();

    document.querySelector("#status").textContent =
      status.updated_at
        ? `Última atualização: ${dateFmt(status.updated_at)}`
        : "Aguardando a primeira atualização automática.";
  } catch (error) {
    document.querySelector("#status").textContent =
      "Não foi possível carregar os dados. Execute o workflow de atualização.";
    console.error(error);
  }
}

document.querySelector("#search").addEventListener("input", e => {
  renderRanking(e.target.value);
});

init();

// 🔹 Atualização automática às 19h
function scheduleUpdate(hour, minute) {
  const now = new Date();
  const next = new Date();

  next.setHours(hour, minute, 0, 0);

  if (next <= now) {
    next.setDate(next.getDate() + 1);
  }

  const delay = next.getTime() - now.getTime();

  setTimeout(() => {
    init(); // atualiza os dados
    scheduleUpdate(hour, minute); // agenda novamente para o próximo dia
  }, delay);
}

scheduleUpdate(19, 0);
