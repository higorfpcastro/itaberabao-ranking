# -*- coding: utf-8 -*-
"""
Atualização automática do ranking Itaberabão.

Fluxo:
Lichess API
    ↓
Coleta dos torneios
    ↓
Coleta das participações
    ↓
Cálculo do ranking
    ↓
Comparação com ranking anterior
    ↓
Geração dos JSON utilizados pelo site

O GitHub Actions é responsável pelo agendamento da execução.
"""

from __future__ import annotations

import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
import requests


# ============================================================
# CONFIGURAÇÃO
# ============================================================

TEAM_ID = "itaberabao"

# Primeiro torneio considerado.
START_TIMESTAMP_MS = int(
    datetime(2025, 9, 7, 0, 0, tzinfo=timezone.utc).timestamp() * 1000
)

# None = considerar até o momento da execução.
# Isso permite que o ranking continue sendo atualizado diariamente.
END_TIMESTAMP_MS = None

EXCLUDED_TOURNAMENTS = {"WOE0IJur"}

NAME_PATTERN = re.compile(
    r"ITABERAB|Embaixador",
    re.IGNORECASE
)


# ============================================================
# SUBSTITUIÇÃO DE NOMES
# ============================================================

NICK_REPLACEMENTS = {
    "Grillote": "Grillito",
    "Grillito": "Grillito",
}


# ============================================================
# CORREÇÕES MANUAIS DE PONTUAÇÃO
# ============================================================

POINT_CORRECTIONS = {
    "batolsai": 2,
    "Hunter04": 2,
    "Herzog_Treinamentos": 2,
    "princeofchess": 3,
    "motacta30": 4,
    "CCapivara": 4,
    "Jesus33": 4,
    "macgyversp": 4,
    "lafitt": 4,
    "danger-perigo": 4,
    "j_erry": 6,
    "AnyPeople": 8,
    "XADREZCSC": -153,
}


# ============================================================
# CATEGORIAS POR RATING
# ============================================================

RATING_LIMITS = [
    (0, 800, "Abaixo de 800"),
    (800, 900, "800–899"),
    (900, 1000, "900–999"),
    (1000, 1100, "1000–1099"),
    (1100, 1200, "1100–1199"),
    (1200, 1300, "1200–1299"),
    (1300, 1400, "1300–1399"),
    (1400, 1500, "1400–1499"),
    (1500, 1600, "1500–1599"),
    (1600, 1700, "1600–1699"),
    (1700, 1800, "1700–1799"),
    (1800, 1900, "1800–1899"),
    (1900, 2000, "1900–1999"),
    (2000, 2100, "2000–2099"),
    (2100, 2200, "2100–2199"),
    (2200, 2300, "2200–2299"),
    (2300, 2400, "2300–2399"),
    (2400, 2500, "2400–2499"),
    (2500, 2600, "2500–2599"),
    (2600, math.inf, "2600+"),
]


# ============================================================
# DIRETÓRIOS
# ============================================================

OUTPUT = Path(__file__).resolve().parents[1] / "site"
OUTPUT.mkdir(parents=True, exist_ok=True)


# ============================================================
# SESSÃO HTTP
# ============================================================

SESSION = requests.Session()

SESSION.headers.update({
    "User-Agent": "Itaberabao-Ranking/1.0",
    "Accept": "application/x-ndjson",
})


# ============================================================
# UTILIDADES
# ============================================================

def save_json(filename: str, obj) -> None:
    """
    Salva um objeto Python como JSON UTF-8.
    """
    path = OUTPUT / filename

    with path.open("w", encoding="utf-8") as f:
        json.dump(
            obj,
            f,
            ensure_ascii=False,
            indent=2
        )


def json_number(value):
    """
    Converte NaN/inf para None e arredonda números.
    """
    if value is None:
        return None

    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None

        return round(value, 2)

    return value


def records(df: pd.DataFrame):
    """
    Converte DataFrame em lista de dicionários compatível com JSON.
    """
    result = []

    for rec in df.to_dict(orient="records"):
        result.append({
            str(k): json_number(
                v.item() if hasattr(v, "item") else v
            )
            for k, v in rec.items()
        })

    return result


# ============================================================
# RANKING ANTERIOR
# ============================================================

def load_previous_ranking():
    """
    Carrega o ranking publicado na execução anterior.

    O arquivo jogadores.json é lido antes de ser substituído.
    """

    path = OUTPUT / "jogadores.json"

    if not path.exists():
        return {}

    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as exc:
        print(f"AVISO: não foi possível ler ranking anterior: {exc}")
        return {}

    previous = {}

    for item in data:
        nick = item.get("Nick")
        position = item.get("Posicao")

        if nick and position is not None:
            try:
                previous[nick] = int(position)
            except (ValueError, TypeError):
                pass

    return previous


def add_ranking_movement(ranking, previous_positions):
    """
    Acrescenta posição atual e movimentação em relação à execução anterior.

    movimento:
        positivo = subiu
        negativo = caiu
        zero      = permaneceu
        None      = jogador novo
    """

    ranking = ranking.copy()

    ranking["Posicao"] = range(1, len(ranking) + 1)

    movimentos = []
    textos = []

    for _, row in ranking.iterrows():

        nick = row["Nick"]
        atual = int(row["Posicao"])

        anterior = previous_positions.get(nick)

        if anterior is None:
            movimentos.append(None)
            textos.append("NOVO")

        else:
            movimento = anterior - atual

            movimentos.append(movimento)

            if movimento > 0:
                textos.append(f"↑ {movimento}")

            elif movimento < 0:
                textos.append(f"↓ {abs(movimento)}")

            else:
                textos.append("—")

    ranking["Movimento"] = movimentos
    ranking["Movimento_Texto"] = textos

    return ranking


# ============================================================
# LICHESS — TORNEIOS
# ============================================================

def get_team_tournaments(start_ms=None, end_ms=None):

    url = (
        f"https://lichess.org/api/team/"
        f"{TEAM_ID}/arena?max=2000"
    )

    response = SESSION.get(
        url,
        timeout=60
    )

    response.raise_for_status()

    items = [
        json.loads(line)
        for line in response.text.splitlines()
        if line.strip()
    ]

    if not items:
        return pd.DataFrame()

    df = pd.DataFrame(items)

    if "startsAt" not in df.columns:
        raise RuntimeError(
            "A resposta do Lichess não contém 'startsAt'."
        )

    # --------------------------------------------------------
    # Intervalo
    # --------------------------------------------------------

    if start_ms is not None:
        df = df[
            df["startsAt"].fillna(0) >= start_ms
        ].copy()

    if end_ms is not None:
        df = df[
            df["startsAt"].fillna(0) <= end_ms
        ].copy()

    # --------------------------------------------------------
    # Data/hora
    # --------------------------------------------------------

    df["startsAt_dt"] = pd.to_datetime(
        df["startsAt"],
        unit="ms",
        utc=True
    )

    # Apenas segunda a sexta.
    df = df[
        ~df["startsAt_dt"].dt.dayofweek.isin([5, 6])
    ].copy()

    # --------------------------------------------------------
    # Exclusões
    # --------------------------------------------------------

    if "id" in df.columns:
        df = df[
            ~df["id"].isin(EXCLUDED_TOURNAMENTS)
        ].copy()

    if "fullName" in df.columns:
        df = df[
            df["fullName"]
            .fillna("")
            .str.contains(NAME_PATTERN)
        ].copy()

    if "winner" in df.columns:
        df = df[
            df["winner"]
            .fillna(False)
            .astype(bool)
        ].copy()

    return (
        df
        .sort_values("startsAt")
        .reset_index(drop=True)
    )


# ============================================================
# LICHESS — RESULTADOS
# ============================================================

def fetch_tournament_results(tournament_id: str):

    url = (
        f"https://lichess.org/api/tournament/"
        f"{tournament_id}/results"
    )

    params = {
        "rank": "true",
        "score": "true",
        "rating": "true",
        "username": "true",
        "title": "true",
        "performance": "true",
        "team": "true",
    }

    response = SESSION.get(
        url,
        headers={
            "Accept": "application/x-ndjson"
        },
        params=params,
        timeout=60,
    )

    response.raise_for_status()

    rows = []

    for line in response.text.splitlines():
        if line.strip():
            rows.append(json.loads(line))

    wanted = [
        "username",
        "rating",
        "score",
        "performance",
        "rank"
    ]

    data = []

    for row in rows:

        data.append({
            "username": row.get("username"),
            "rating": row.get("rating"),
            "score": row.get("score"),
            "performance": row.get("performance"),
            "rank": row.get("rank"),
        })

    return pd.DataFrame(
        data,
        columns=wanted
    )


def download_all_results(tournaments):

    results = {}

    if tournaments.empty:
        return results

    with ThreadPoolExecutor(
        max_workers=4
    ) as executor:

        futures = {
            executor.submit(
                fetch_tournament_results,
                tid
            ): tid
            for tid in tournaments["id"].tolist()
        }

        for future in as_completed(futures):

            tid = futures[future]

            try:

                results[tid] = future.result()

                print(
                    f"OK: resultados {tid}"
                )

            except Exception as exc:

                print(
                    f"ERRO no torneio {tid}: {exc}"
                )

                results[tid] = pd.DataFrame(
                    columns=[
                        "username",
                        "rating",
                        "score",
                        "performance",
                        "rank"
                    ]
                )

    return results


# ============================================================
# PARTICIPAÇÕES
# ============================================================

def build_participation_table(
    tournaments,
    results
):

    frames = []

    for _, tournament in tournaments.iterrows():

        tid = tournament["id"]

        df = results.get(tid)

        if df is None or df.empty:
            continue

        temp = df.copy()

        temp["tournament_id"] = tid

        temp["tournament_name"] = (
            tournament.get(
                "fullName",
                tid
            )
        )

        temp["startsAt"] = (
            tournament.get("startsAt")
        )

        frames.append(temp)

    if not frames:

        return pd.DataFrame(
            columns=[
                "username",
                "rating",
                "score",
                "performance",
                "rank",
                "tournament_id",
                "tournament_name",
                "startsAt"
            ]
        )

    all_results = pd.concat(
        frames,
        ignore_index=True
    )

    # --------------------------------------------------------
    # Conversões
    # --------------------------------------------------------

    all_results["username"] = (
        all_results["username"]
        .fillna("")
        .astype(str)
    )

    all_results["rating"] = pd.to_numeric(
        all_results["rating"],
        errors="coerce"
    )

    all_results["score"] = pd.to_numeric(
        all_results["score"],
        errors="coerce"
    )

    all_results["performance"] = pd.to_numeric(
        all_results["performance"],
        errors="coerce"
    )

    all_results["rank"] = pd.to_numeric(
        all_results["rank"],
        errors="coerce"
    )

    # --------------------------------------------------------
    # Participações sem usuário
    # --------------------------------------------------------

    all_results = all_results[
        all_results["username"].str.strip() != ""
    ].copy()

    # --------------------------------------------------------
    # URL do torneio
    # --------------------------------------------------------

    all_results["tournament_url"] = (
        "https://lichess.org/tournament/"
        + all_results["tournament_id"].astype(str)
    )

    return all_results


# ============================================================
# RANKING
# ============================================================

def build_ranking(participations):

    columns = [
        "Nick",
        "Pontos",
        "Desempenho_Medio",
        "podio_primeiro",
        "podio_segundo",
        "podio_terceiro",
        "Rating_Medio",
        "Pontos_por_Torneio",
        "Maior_Pontuacao",
        "Menor_Ranking",
        "Participacoes",
    ]

    if participations.empty:
        return pd.DataFrame(columns=columns)

    df = participations.copy()

    # --------------------------------------------------------
    # Substituição de nick
    # --------------------------------------------------------

    df["Nick"] = (
        df["username"]
        .replace(NICK_REPLACEMENTS)
    )

    # --------------------------------------------------------
    # Agrupamento
    # --------------------------------------------------------

    grouped = df.groupby(
        "Nick",
        as_index=False
    ).agg(

        Rating_Medio=("rating", "mean"),

        Pontos=("score", "sum"),

        Desempenho_Medio=(
            "performance",
            "mean"
        ),

        podio_primeiro=(
            "rank",
            lambda s: (s == 1).sum()
        ),

        podio_segundo=(
            "rank",
            lambda s: (s == 2).sum()
        ),

        podio_terceiro=(
            "rank",
            lambda s: (s == 3).sum()
        ),

        Maior_Pontuacao=(
            "score",
            "max"
        ),

        Menor_Ranking=(
            "rank",
            "min"
        ),

        Participacoes=(
            "score",
            "count"
        ),
    )

    # --------------------------------------------------------
    # Média de pontos por torneio
    # --------------------------------------------------------

    rating_counts = (
        df.groupby("Nick")["rating"]
        .count()
    )

    grouped["Pontos_por_Torneio"] = (
        grouped["Pontos"]
        /
        grouped["Nick"]
        .map(rating_counts)
        .replace(0, pd.NA)
    )

    # --------------------------------------------------------
    # Correções manuais
    # --------------------------------------------------------

    for nick, correction in POINT_CORRECTIONS.items():

        mask = grouped["Nick"].eq(nick)

        grouped.loc[
            mask,
            "Pontos"
        ] = (
            grouped.loc[mask, "Pontos"]
            + correction
        )

    # --------------------------------------------------------
    # Ordenação
    # --------------------------------------------------------

    grouped = grouped.sort_values(
        [
            "Pontos",
            "Desempenho_Medio",
            "podio_primeiro",
            "podio_segundo",
            "podio_terceiro",
            "Rating_Medio",
        ],
        ascending=[
            False,
            False,
            False,
            False,
            False,
            False,
        ],
    ).reset_index(drop=True)

    # --------------------------------------------------------
    # Arredondamento
    # --------------------------------------------------------

    numeric_cols = [
        "Pontos",
        "Desempenho_Medio",
        "podio_primeiro",
        "podio_segundo",
        "podio_terceiro",
        "Rating_Medio",
        "Pontos_por_Torneio",
        "Maior_Pontuacao",
        "Menor_Ranking",
        "Participacoes",
    ]

    grouped[numeric_cols] = (
        grouped[numeric_cols].round()
    )

    return grouped[columns]


# ============================================================
# VENCEDORES
# ============================================================

def get_winner_name(row):

    winner = row.get("winner")

    if isinstance(winner, dict):

        return (
            winner.get("name")
            or winner.get("username")
        )

    if isinstance(winner, str):
        return winner

    return None


def build_winners(
    tournaments,
    ranking
):

    if tournaments.empty:
        return pd.DataFrame()

    rows = []

    for _, row in tournaments.iterrows():

        winner = get_winner_name(row)

        if winner:

            rows.append({

                "Torneio": row.get(
                    "fullName",
                    row.get("id")
                ),

                "vencedores": (
                    NICK_REPLACEMENTS
                    .get(winner, winner)
                ),

                "id": row.get("id"),

                "startsAt": row.get(
                    "startsAt"
                ),

            })

    wins = pd.DataFrame(rows)

    if wins.empty:
        return wins

    frequency = (
        wins
        .groupby("vencedores")
        .size()
        .reset_index(
            name="vitorias"
        )
    )

    result = frequency.merge(
        ranking,
        left_on="vencedores",
        right_on="Nick",
        how="left",
    )

    result = result.drop(
        columns=["Nick"],
        errors="ignore"
    )

    result = result.sort_values(
        [
            "vitorias",
            "Pontos",
            "Desempenho_Medio"
        ],
        ascending=[
            False,
            False,
            False
        ],
    ).reset_index(drop=True)

    return result


# ============================================================
# CATEGORIAS
# ============================================================

def build_categories(ranking):

    if ranking.empty:
        return pd.DataFrame()

    pieces = []

    for low, high, label in RATING_LIMITS:

        if math.isinf(high):

            subset = ranking[
                ranking["Rating_Medio"] >= low
            ].head(5).copy()

        else:

            subset = ranking[
                (ranking["Rating_Medio"] >= low)
                &
                (ranking["Rating_Medio"] < high)
            ].head(5).copy()

        if subset.empty:
            continue

        subset.insert(
            0,
            "Categoria",
            label
        )

        pieces.append(subset)

    if not pieces:
        return pd.DataFrame()

    return pd.concat(
        pieces,
        ignore_index=True
    )


# ============================================================
# DADOS DOS TORNEIOS
# ============================================================

def build_tournament_records(tournaments):

    records_list = []

    for _, row in tournaments.iterrows():

        winner = get_winner_name(row)

        start = row.get(
            "startsAt_dt"
        )

        records_list.append({

            "id": row.get("id"),

            "name": row.get(
                "fullName"
            ),

            "winner": (
                NICK_REPLACEMENTS
                .get(winner, winner)
            ),

            "startsAt": (
                start.isoformat()
                if pd.notna(start)
                else None
            ),

            "url": (
                "https://lichess.org/tournament/"
                f"{row.get('id')}"
            ),

        })

    return records_list


# ============================================================
# STATUS
# ============================================================

def build_status(
    started,
    finished,
    tournaments,
    ranking,
    participations
):

    if tournaments.empty:

        interval_start = None
        interval_end = None

    else:

        interval_start = (
            tournaments["startsAt_dt"]
            .min()
            .isoformat()
        )

        interval_end = (
            tournaments["startsAt_dt"]
            .max()
            .isoformat()
        )

    return {

        "updated_at":
            finished.isoformat(),

        "duration_seconds":
            round(
                (
                    finished - started
                ).total_seconds(),
                2
            ),

        "team":
            TEAM_ID,

        "tournaments":
            int(len(tournaments)),

        "players":
            int(len(ranking)),

        "participations":
            int(len(participations)),

        "interval_start":
            interval_start,

        "interval_end":
            interval_end,

        "success":
            True,
    }


# ============================================================
# MAIN
# ============================================================

def main():

    started = datetime.now(
        timezone.utc
    )

    # --------------------------------------------------------
    # Ranking anterior
    # --------------------------------------------------------

    previous_positions = (
        load_previous_ranking()
    )

    print(
        "Jogadores no ranking anterior:",
        len(previous_positions)
    )

    # --------------------------------------------------------
    # Torneios
    # --------------------------------------------------------

    print(
        "Consultando torneios do Itaberabão..."
    )

    tournaments = get_team_tournaments(
        start_ms=START_TIMESTAMP_MS,
        end_ms=END_TIMESTAMP_MS
    )

    print(
        f"Torneios selecionados: "
        f"{len(tournaments)}"
    )

    if not tournaments.empty:

        print(
            "Primeiro torneio:",
            tournaments.iloc[0]["fullName"]
        )

        print(
            "Último torneio:",
            tournaments.iloc[-1]["fullName"]
        )

    # --------------------------------------------------------
    # Resultados
    # --------------------------------------------------------

    results = download_all_results(
        tournaments
    )

    # --------------------------------------------------------
    # Participações
    # --------------------------------------------------------

    participations = (
        build_participation_table(
            tournaments,
            results
        )
    )

    # --------------------------------------------------------
    # Ranking
    # --------------------------------------------------------

    ranking = build_ranking(
        participations
    )

    # --------------------------------------------------------
    # Movimento
    # --------------------------------------------------------

    ranking = add_ranking_movement(
        ranking,
        previous_positions
    )

    # --------------------------------------------------------
    # Vencedores
    # --------------------------------------------------------

    winners = build_winners(
        tournaments,
        ranking
    )

    # --------------------------------------------------------
    # Categorias
    # --------------------------------------------------------

    categories = build_categories(
        ranking
    )

    # --------------------------------------------------------
    # Torneios
    # --------------------------------------------------------

    tournament_records = (
        build_tournament_records(
            tournaments
        )
    )

    # --------------------------------------------------------
    # Salvar JSON
    # --------------------------------------------------------

    save_json(
        "jogadores.json",
        records(ranking)
    )

    save_json(
        "vencedores.json",
        records(winners)
    )

    save_json(
        "categorias.json",
        records(categories)
    )

    save_json(
        "torneios.json",
        tournament_records
    )

    # --------------------------------------------------------
    # Participações
    # --------------------------------------------------------

    save_json(
        "participacoes.json",
        records(participations)
    )

    # --------------------------------------------------------
    # Ranking anterior
    #
    # Mantém uma cópia para inspeção futura.
    # --------------------------------------------------------

    if previous_positions:

        previous_records = [
            {
                "Nick": nick,
                "Posicao": position
            }
            for nick, position
            in sorted(
                previous_positions.items(),
                key=lambda x: x[1]
            )
        ]

        save_json(
            "jogadores_anterior.json",
            previous_records
        )

    # --------------------------------------------------------
    # Status
    # --------------------------------------------------------

    finished = datetime.now(
        timezone.utc
    )

    status = build_status(
        started,
        finished,
        tournaments,
        ranking,
        participations
    )

    save_json(
        "status.json",
        status
    )

    print(
        json.dumps(
            status,
            ensure_ascii=False,
            indent=2
        )
    )


if __name__ == "__main__":
    main()
