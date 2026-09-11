/* ============================================================
   RANKING ITABERABÃO
   ============================================================ */

const DATA = "";

let ranking = [];
let winners = [];
let categories = [];
let tournaments = [];
let participations = [];
let status = {};

let pointsChart = null;
let positionChart = null;


/* ============================================================
   CARREGAMENTO DOS JSONs
   ============================================================ */

async function loadJSON(file) {

  const response = await fetch(DATA + file);

  if (!response.ok) {

    throw new Error(`Falha ao carregar ${file}`);

  }

  return response.json();
}


/* ============================================================
   FORMATAÇÃO
   ============================================================ */

function fmt(value, digits = 0) {

  if (
    value === null ||
    value === undefined ||
    Number.isNaN(Number(value))
  ) {

    return "—";

  }

  return Number(value).toLocaleString("pt-BR", {

    maximumFractionDigits: digits,

    minimumFractionDigits: digits

  });
}


function dateFmt(value) {

  if (!value) {

    return "—";

  }

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {

    return "—";

  }

  return new Intl.DateTimeFormat("pt-BR", {

    dateStyle: "short",

    timeStyle: "short"

  }).format(date);

}


function dateOnly(value) {

  if (!value) {

    return "—";

  }

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {

    return "—";

  }

  return new Intl.DateTimeFormat("pt-BR", {

    dateStyle: "short"

  }).format(date);

}


/* ============================================================
   SEGURANÇA
   ============================================================ */

function escapeHTML(value) {

  if (value === null || value === undefined) {

    return "";

  }

  return String(value)

    .replaceAll("&", "&amp;")

    .replaceAll("<", "&lt;")

    .replaceAll(">", "&gt;")

    .replaceAll('"', "&quot;")

    .replaceAll("'", "&#039;");
}


/* ============================================================
   MOVIMENTO
   ============================================================ */

function movementHTML(player) {

  const text = player.Movimento_Texto;

  if (!text || text === "NOVO") {

    return `
      <span class="movement new">
        NOVO
      </span>
    `;

  }

  if (text === "—") {

    return `
      <span class="movement same">
        —
      </span>
    `;

  }

  if (text.startsWith("↑")) {

    return `
      <span class="movement up">
        ${escapeHTML(text)}
      </span>
    `;

  }

  if (text.startsWith("↓")) {

    return `
      <span class="movement down">
        ${escapeHTML(text)}
      </span>
    `;

  }

  return `
    <span class="movement same">
      ${escapeHTML(text)}
    </span>
  `;
}


/* ============================================================
   CARDS PRINCIPAIS
   ============================================================ */

function renderCards() {

  const updated = status.updated_at
    ? dateFmt(status.updated_at)
    : "—";


  const cards = [

    [
      "Jogadores",
      status.players ?? ranking.length
    ],

    [
      "Torneios",
      status.tournaments ?? tournaments.length
    ],

    [
      "Participações",
      status.participations ?? participations.length
    ],

    [
      "Atualizado",
      updated
    ]

  ];


  document.querySelector("#cards").innerHTML =

    cards.map(([label, value]) => `

      <div class="card">

        <span class="card-label">
          ${escapeHTML(label)}
        </span>

        <strong class="card-value">
          ${escapeHTML(value)}
        </strong>

      </div>

    `).join("");
}


/* ============================================================
   INTERVALO DOS DADOS
   ============================================================ */

function renderInterval() {

  const element =
    document.querySelector("#interval");


  if (
    !status.interval_start ||
    !status.interval_end
  ) {

    element.textContent =
      "Período dos dados: —";

    return;

  }


  const start =
    dateOnly(status.interval_start);

  const end =
    dateOnly(status.interval_end);


  element.textContent =
    `Período dos dados: ${start} a ${end}`;
}


/* ============================================================
   RANKING GERAL
   ============================================================ */

function renderRanking(filter = "") {

  const query =
    filter.trim().toLowerCase();


  const rows =
    ranking.filter(player =>

      (player.Nick || "")
        .toLowerCase()
        .includes(query)

    );


  const tbody =
    document.querySelector("#ranking tbody");


  tbody.innerHTML = rows.map(player => `

    <tr
      data-player="${escapeHTML(player.Nick)}"
      title="Clique para visualizar o desempenho"
    >

      <td class="rank">
        ${fmt(player.Posicao)}
      </td>

      <td class="movement">
        ${movementHTML(player)}
      </td>

      <td class="player">
        ${escapeHTML(player.Nick ?? "—")}
      </td>

      <td>
        <strong>
          ${fmt(player.Pontos)}
        </strong>
      </td>

      <td>
        ${fmt(player.Desempenho_Medio)}
      </td>

      <td>
        ${fmt(player.podio_primeiro)}
      </td>

      <td>
        ${fmt(player.podio_segundo)}
      </td>

      <td>
        ${fmt(player.podio_terceiro)}
      </td>

      <td>
        ${fmt(player.Rating_Medio)}
      </td>

      <td>
        ${fmt(player.Participacoes)}
      </td>

    </tr>

  `).join("");


  tbody
    .querySelectorAll("tr")
    .forEach(row => {

      row.addEventListener("click", () => {

        const nick =
          row.dataset.player;

        selectPlayer(nick);

        document
          .getElementById("player-performance")
          .scrollIntoView({
            behavior: "smooth",
            block: "start"
          });

      });

    });

}


/* ============================================================
   VENCEDORES
   ============================================================ */

function renderWinners() {

  document.querySelector("#winners tbody").innerHTML =

    winners
      .slice(0, 20)
      .map((player, index) => `

        <tr>

          <td class="rank">
            ${index + 1}
          </td>

          <td class="player">
            ${escapeHTML(player.vencedores ?? "—")}
          </td>

          <td>
            ${fmt(player.vitorias)}
          </td>

          <td>
            ${fmt(player.Pontos)}
          </td>

        </tr>

      `)
      .join("");
}


/* ============================================================
   CATEGORIAS
   ============================================================ */

function renderCategories() {

  document.querySelector("#categories tbody").innerHTML =

    categories
      .map(player => `

        <tr>

          <td>
            ${escapeHTML(player.Categoria ?? "—")}
          </td>

          <td class="player">
            ${escapeHTML(player.Nick ?? "—")}
          </td>

          <td>
            ${fmt(player.Rating_Medio)}
          </td>

          <td>
            ${fmt(player.Pontos)}
          </td>

        </tr>

      `)
      .join("");
}


/* ============================================================
   TORNEIOS
   ============================================================ */

function renderTournaments() {

  const recent = [...tournaments]

    .sort(
      (a, b) =>
        new Date(b.startsAt) -
        new Date(a.startsAt)
    )

    .slice(0, 30);


  document.querySelector("#tournaments tbody").innerHTML =

    recent
      .map(tournament => `

        <tr>

          <td>
            ${dateFmt(tournament.startsAt)}
          </td>

          <td class="player">
            ${escapeHTML(tournament.name ?? "—")}
          </td>

          <td>
            ${escapeHTML(tournament.winner ?? "—")}
          </td>

          <td>

            ${
              tournament.url

                ? `
                  <a
                    href="${escapeHTML(tournament.url)}"
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    Lichess ↗
                  </a>
                `

                : "—"
            }

          </td>

        </tr>

      `)
      .join("");
}


/* ============================================================
   SELECTOR DE JOGADORES
   ============================================================ */

function renderPlayerSelector() {

  const select =
    document.querySelector("#player-select");


  const current =
    select.value;


  select.innerHTML = `

    <option value="">
      Selecione um jogador...
    </option>

    ${
      ranking.map(player => `

        <option value="${escapeHTML(player.Nick)}">

          #${fmt(player.Posicao)}
          — ${escapeHTML(player.Nick)}

        </option>

      `).join("")
    }

  `;


  if (current) {

    select.value = current;

  }
}


/* ============================================================
   LOCALIZAR PARTICIPAÇÕES
   ============================================================ */

function getPlayerParticipations(nick) {

  if (!nick) {

    return [];

  }


  const normalized =
    nick.trim().toLowerCase();


  return participations

    .filter(item => {

      const username =
        (
          item.username ??
          item.Nick ??
          item.nick ??
          ""
        )
        .trim()
        .toLowerCase();

      return username === normalized;

    })

    .sort(
      (a, b) =>
        new Date(a.startsAt) -
        new Date(b.startsAt)
    );
}


/* ============================================================
   SELECIONAR JOGADOR
   ============================================================ */

function selectPlayer(nick) {

  const select =
    document.querySelector("#player-select");


  select.value = nick;


  if (!nick) {

    showEmptyPlayer();

    return;

  }


  const player =
    ranking.find(
      p => p.Nick === nick
    );


  if (!player) {

    showEmptyPlayer();

    return;

  }


  const history =
    getPlayerParticipations(nick);


  renderPlayerSummary(
    player,
    history
  );


  renderPointsChart(
    player,
    history
  );


  renderPositionChart(
    history
  );


  renderParticipationsTable(
    history
  );


  document
    .querySelector("#player-empty")
    .classList.add("hidden");


  document
    .querySelector("#player-performance")
    .classList.remove("hidden");

}


/* ============================================================
   RESUMO DO JOGADOR
   ============================================================ */

function renderPlayerSummary(
  player,
  history
) {

  document
    .querySelector("#selected-player-name")
    .textContent =
      player.Nick ?? "—";


  document
    .querySelector("#selected-player-position")
    .textContent =
      `#${fmt(player.Posicao)}`;


  document
    .querySelector("#player-participations")
    .textContent =
      fmt(player.Participacoes);


  document
    .querySelector("#player-points")
    .textContent =
      fmt(player.Pontos);


  document
    .querySelector("#player-ranking-position")
    .textContent =
      `#${fmt(player.Posicao)}`;


  document
    .querySelector("#player-points-average")
    .textContent =
      fmt(player.Pontos_por_Torneio, 1);
}


/* ============================================================
   GRÁFICO DE PONTOS
   ============================================================ */

function renderPointsChart(
  player,
  history
) {

  const canvas =
    document.querySelector("#points-chart");


  if (pointsChart) {

    pointsChart.destroy();

    pointsChart = null;

  }


  if (!history.length) {

    return;

  }


  const labels =
    history.map(item => {

      const date =
        new Date(item.startsAt);

      return new Intl.DateTimeFormat(
        "pt-BR",
        {
          day: "2-digit",
          month: "2-digit"
        }
      ).format(date);

    });


  const data =
    history.map(item =>
      Number(item.score ?? 0)
    );


  const names =
    history.map(item =>
      item.tournament_name ?? "Torneio"
    );


  pointsChart = new Chart(canvas, {

    type: "line",

    data: {

      labels,

      datasets: [

        {

          label: "Pontos",

          data,

          borderWidth: 2,

          pointRadius: 4,

          pointHoverRadius: 6,

          tension: 0.25,

          fill: false

        }

      ]

    },


    options: {

      responsive: true,

      maintainAspectRatio: false,


      interaction: {

        mode: "index",

        intersect: false

      },


      plugins: {

        legend: {

          display: false

        },


        tooltip: {

          callbacks: {

            title: items => {

              const index =
                items[0].dataIndex;

              return names[index];

            },


            label: context =>

              ` Pontos: ${fmt(context.raw)}`

          }

        }

      },


      scales: {

        x: {

          ticks: {

            color: "#9a9a9a"

          },

          grid: {

            color: "#3b3b3b"

          }

        },


        y: {

          beginAtZero: true,

          ticks: {

            color: "#9a9a9a"

          },

          grid: {

            color: "#3b3b3b"

          }

        }

      }

    }

  });

}


/* ============================================================
   GRÁFICO DE POSIÇÃO
   ============================================================ */

function renderPositionChart(history) {

  const canvas =
    document.querySelector("#position-chart");


  if (positionChart) {

    positionChart.destroy();

    positionChart = null;

  }


  if (!history.length) {

    return;

  }


  const labels =
    history.map(item => {

      const date =
        new Date(item.startsAt);

      return new Intl.DateTimeFormat(
        "pt-BR",
        {
          day: "2-digit",
          month: "2-digit"
        }
      ).format(date);

    });


  const positions =
    history.map(item =>
      Number(item.rank ?? 0)
    );


  const names =
    history.map(item =>
      item.tournament_name ?? "Torneio"
    );


  const maxPosition =
    Math.max(
      ...positions,
      1
    );


  positionChart = new Chart(canvas, {

    type: "line",

    data: {

      labels,

      datasets: [

        {

          label: "Posição",

          data: positions,

          borderWidth: 2,

          pointRadius: 4,

          pointHoverRadius: 6,

          tension: 0.25,

          fill: false

        }

      ]

    },


    options: {

      responsive: true,

      maintainAspectRatio: false,


      interaction: {

        mode: "index",

        intersect: false

      },


      plugins: {

        legend: {

          display: false

        },


        tooltip: {

          callbacks: {

            title: items => {

              const index =
                items[0].dataIndex;

              return names[index];

            },


            label: context =>

              ` Colocação: ${fmt(context.raw)}º`

          }

        }

      },


      scales: {

        x: {

          ticks: {

            color: "#9a9a9a"

          },

          grid: {

            color: "#3b3b3b"

          }

        },


        y: {

          reverse: true,

          min: 1,

          max: Math.max(
            maxPosition,
            5
          ),

          ticks: {

            color: "#9a9a9a",

            precision: 0,

            callback: value =>
              `${value}º`

          },

          grid: {

            color: "#3b3b3b"

          }

        }

      }

    }

  });

}


/* ============================================================
   TABELA DE PARTICIPAÇÕES
   ============================================================ */

function renderParticipationsTable(history) {

  const tbody =
    document.querySelector(
      "#participations-table tbody"
    );


  tbody.innerHTML = "";


  if (!history.length) {

    tbody.innerHTML = `

      <tr>

        <td colspan="7" class="muted">

          Nenhuma participação encontrada.

        </td>

      </tr>

    `;

    return;

  }


  tbody.innerHTML = history

    .slice()

    .reverse()

    .map(item => {

      const tournamentName =
        item.tournament_name ??
        "Torneio";


      const url =
        item.tournament_url ??
        item.url ??
        "";


      return `

        <tr>

          <td>
            ${dateOnly(item.startsAt)}
          </td>

          <td class="player">

            ${
              url

                ? `
                  <a
                    href="${escapeHTML(url)}"
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    ${escapeHTML(tournamentName)}
                  </a>
                `

                : escapeHTML(tournamentName)
            }

          </td>

          <td>
            <strong>
              ${fmt(item.score)}
            </strong>
          </td>

          <td>
            ${fmt(item.rank)}º
          </td>

          <td>
            ${fmt(item.rating)}
          </td>

          <td>
            ${fmt(item.performance)}
          </td>

          <td>

            ${
              url

                ? `
                  <a
                    href="${escapeHTML(url)}"
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    ↗
                  </a>
                `

                : ""
            }

          </td>

        </tr>

      `;

    })

    .join("");
}


/* ============================================================
   ESTADO VAZIO
   ============================================================ */

function showEmptyPlayer() {

  document
    .querySelector("#player-performance")
    .classList.add("hidden");


  document
    .querySelector("#player-empty")
    .classList.remove("hidden");


  if (pointsChart) {

    pointsChart.destroy();

    pointsChart = null;

  }


  if (positionChart) {

    positionChart.destroy();

    positionChart = null;

  }

}


/* ============================================================
   EVENTOS
   ============================================================ */

document
  .querySelector("#search")
  .addEventListener(
    "input",
    event => {

      renderRanking(
        event.target.value
      );

    }
  );


document
  .querySelector("#player-select")
  .addEventListener(
    "change",
    event => {

      selectPlayer(
        event.target.value
      );

    }
  );


/* ============================================================
   INICIALIZAÇÃO
   ============================================================ */

async function init() {

  try {

    [

      ranking,

      winners,

      categories,

      tournaments,

      participations,

      status

    ] = await Promise.all([

      loadJSON("jogadores.json"),

      loadJSON("vencedores.json"),

      loadJSON("categorias.json"),

      loadJSON("torneios.json"),

      loadJSON("participacoes.json"),

      loadJSON("status.json")

    ]);


    /* -----------------------------------------
       Renderização
       ----------------------------------------- */

    renderCards();

    renderInterval();

    renderRanking();

    renderPlayerSelector();

    renderWinners();

    renderCategories();

    renderTournaments();


    /* -----------------------------------------
       Status
       ----------------------------------------- */

    document
      .querySelector("#status")
      .textContent =

      status.updated_at

        ? `Última atualização: ${dateFmt(status.updated_at)}`

        : "Aguardando a primeira atualização automática.";


  } catch (error) {

    console.error(error);


    document
      .querySelector("#status")
      .textContent =
        "Não foi possível carregar os dados.";


    document
      .querySelector("#interval")
      .textContent =
        "Verifique os arquivos JSON e execute o workflow de atualização.";

  }

}


init();
