# -*- coding: utf-8 -*-
"""
Atualização automática do ranking Itaberabão.

Baseado na lógica do Torneio_Diario_Itaberabao_v11.py.
A versão para GitHub não usa Google OAuth nem um loop infinito:
o GitHub Actions agenda a execução.
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
START_TIMESTAMP_MS = int(datetime(2025, 9, 7, 0, 0, tzinfo=timezone.utc).timestamp() * 1000)
END_TIMESTAMP_MS   = int(datetime(2026, 9, 9, 0, 0, tzinfo=timezone.utc).timestamp() * 1000)
EXCLUDED_TOURNAMENTS = {"WOE0IJur"}
NAME_PATTERN = re.compile(r"ITABERAB|Embaixador", re.IGNORECASE)

# Mantém a mesma regra do programa original.
NICK_REPLACEMENTS = {
    "Grillote": "Grillito",
    "Grillito": "Grillito",
}

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

OUTPUT = Path(__file__).resolve().parents[1] / "site" #a priori os dados estavam sendo salvos em /data
OUTPUT.mkdir(parents=True, exist_ok=True)

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "Itaberabao-Ranking/1.0",
    "Accept": "application/x-ndjson",
})


# ============================================================
# UTILIDADES
# ============================================================

def save_json(filename: str, obj) -> None:
    path = OUTPUT / filename
    with path.open("w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def safe_float(value):
    try:
        if value is None or value == "":
            return float("nan")
        return float(value)
    except (ValueError, TypeError):
        return float("nan")


def json_number(value):
    """Converte NaN/inf para None para produzir JSON válido."""
    if value is None:
        return None
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None
        return round(value, 2)
    return value


def records(df: pd.DataFrame):
    result = []
    for rec in df.to_dict(orient="records"):
        result.append({
            str(k): json_number(v.item() if hasattr(v, "item") else v)
            for k, v in rec.items()
        })
    return result


# ============================================================
# LICHESS
# ============================================================

def get_team_tournaments(start_ms=None, end_ms=None):
    url = f"https://lichess.org/api/team/{TEAM_ID}/arena?max=2000"
    response = SESSION.get(url, timeout=60)
    response.raise_for_status()

    items = [json.loads(line) for line in response.text.splitlines() if line.strip()]
    if not items:
        return pd.DataFrame()

    df = pd.DataFrame(items)

    if "startsAt" not in df.columns:
        raise RuntimeError("A resposta do Lichess não contém 'startsAt'.")

    # 🔹 Filtro por intervalo de datas
    if start_ms is not None:
        df = df[df["startsAt"].fillna(0) >= start_ms].copy()
    if end_ms is not None:
        df = df[df["startsAt"].fillna(0) <= end_ms].copy()

    df["startsAt_dt"] = pd.to_datetime(df["startsAt"], unit="ms", utc=True)
    df = df[~df["startsAt_dt"].dt.dayofweek.isin([5, 6])].copy()

    if "id" in df.columns:
        df = df[~df["id"].isin(EXCLUDED_TOURNAMENTS)].copy()
    if "fullName" in df.columns:
        df = df[df["fullName"].fillna("").str.contains(NAME_PATTERN)].copy()
    if "winner" in df.columns:
        df = df[df["winner"].fillna(False).astype(bool)].copy()

    return df.sort_values("startsAt").reset_index(drop=True)


def fetch_tournament_results(tournament_id: str):
    url = f"https://lichess.org/api/tournament/{tournament_id}/results"
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
        headers={"Accept": "application/x-ndjson"},
        params=params,
        timeout=60,
    )
    response.raise_for_status()

    rows = []
    for line in response.text.splitlines():
        if line.strip():
            rows.append(json.loads(line))

    wanted = ["username", "rating", "score", "performance", "rank"]
    data = []

    for row in rows:
        data.append({
            "username": row.get("username"),
            "rating": row.get("rating"),
            "score": row.get("score"),
            "performance": row.get("performance"),
            "rank": row.get("rank"),
        })

    return pd.DataFrame(data, columns=wanted)


def download_all_results(tournaments: pd.DataFrame):
    results = {}

    if tournaments.empty:
        return results

    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {
            executor.submit(fetch_tournament_results, tid): tid
            for tid in tournaments["id"].tolist()
        }

        for future in as_completed(futures):
            tid = futures[future]
            try:
                results[tid] = future.result()
                print(f"OK: resultados {tid}")
            except Exception as exc:
                print(f"ERRO no torneio {tid}: {exc}")
                results[tid] = pd.DataFrame(
                    columns=["username", "rating", "score", "performance", "rank"]
                )

    return results


# ============================================================
# PROCESSAMENTO
# ============================================================

def build_participation_table(tournaments, results):
    frames = []

    for _, tournament in tournaments.iterrows():
        tid = tournament["id"]
        df = results.get(tid)

        if df is None or df.empty:
            continue

        temp = df.copy()
        temp["tournament_id"] = tid
        temp["tournament_name"] = tournament.get("fullName", tid)
        temp["startsAt"] = tournament.get("startsAt")
        frames.append(temp)

    if not frames:
        return pd.DataFrame(
            columns=[
                "username", "rating", "score", "performance", "rank",
                "tournament_id", "tournament_name", "startsAt"
            ]
        )

    all_results = pd.concat(frames, ignore_index=True)

    all_results["username"] = all_results["username"].fillna("").astype(str)
    all_results["rating"] = pd.to_numeric(all_results["rating"], errors="coerce")
    all_results["score"] = pd.to_numeric(all_results["score"], errors="coerce")
    all_results["performance"] = pd.to_numeric(
        all_results["performance"], errors="coerce"
    )
    all_results["rank"] = pd.to_numeric(all_results["rank"], errors="coerce")

    # Participações sem username não entram no ranking.
    all_results = all_results[all_results["username"].str.strip() != ""].copy()

    return all_results


def build_ranking(participations):
    if participations.empty:
        return pd.DataFrame(columns=[
            "Nick", "Pontos", "Desempenho_Medio",
            "podio_primeiro", "podio_segundo", "podio_terceiro",
            "Rating_Medio", "Pontos_por_Torneio", "Maior_Pontuacao",
            "Menor_Ranking", "Participacoes"
        ])

    df = participations.copy()
    df["Nick"] = df["username"].replace(NICK_REPLACEMENTS)

    grouped = df.groupby("Nick", as_index=False).agg(
        Rating_Medio=("rating", "mean"),
        Pontos=("score", "sum"),
        Desempenho_Medio=("performance", "mean"),
        podio_primeiro=("rank", lambda s: (s == 1).sum()),
        podio_segundo=("rank", lambda s: (s == 2).sum()),
        podio_terceiro=("rank", lambda s: (s == 3).sum()),
        Maior_Pontuacao=("score", "max"),
        Menor_Ranking=("rank", "min"),
        Participacoes=("score", "count"),
    )

    # A versão original usa soma de pontos / número de ratings válidos.
    rating_counts = df.groupby("Nick")["rating"].count()
    grouped["Pontos_por_Torneio"] = (
        grouped["Pontos"] /
        grouped["Nick"].map(rating_counts).replace(0, pd.NA)
    )

    # Correções manuais do programa original.
    for nick, correction in POINT_CORRECTIONS.items():
        mask = grouped["Nick"].eq(nick)
        grouped.loc[mask, "Pontos"] = grouped.loc[mask, "Pontos"] + correction

    grouped = grouped.sort_values(
        [
            "Pontos",
            "Desempenho_Medio",
            "podio_primeiro",
            "podio_segundo",
            "podio_terceiro",
            "Rating_Medio",
        ],
        ascending=[False, False, False, False, False, False],
    ).reset_index(drop=True)

    numeric_cols = [
        "Pontos", "Desempenho_Medio", "podio_primeiro",
        "podio_segundo", "podio_terceiro", "Rating_Medio",
        "Pontos_por_Torneio", "Maior_Pontuacao",
        "Menor_Ranking", "Participacoes",
    ]

    grouped[numeric_cols] = grouped[numeric_cols].round()

    return grouped[
        [
            "Nick", "Pontos", "Desempenho_Medio",
            "podio_primeiro", "podio_segundo", "podio_terceiro",
            "Rating_Medio", "Pontos_por_Torneio", "Maior_Pontuacao",
            "Menor_Ranking", "Participacoes"
        ]
    ]


def get_winner_name(row):
    winner = row.get("winner")
    if isinstance(winner, dict):
        return winner.get("name") or winner.get("username")
    if isinstance(winner, str):
        return winner
    return None


def build_winners(tournaments, ranking):
    if tournaments.empty:
        return pd.DataFrame()

    rows = []
    for _, row in tournaments.iterrows():
        winner = get_winner_name(row)
        if winner:
            rows.append({
                "Torneio": row.get("fullName", row.get("id")),
                "vencedores": NICK_REPLACEMENTS.get(winner, winner),
                "id": row.get("id"),
                "startsAt": row.get("startsAt"),
            })

    wins = pd.DataFrame(rows)

    if wins.empty:
        return wins

    frequency = (
        wins.groupby("vencedores")
        .size()
        .reset_index(name="vitorias")
    )

    result = frequency.merge(
        ranking,
        left_on="vencedores",
        right_on="Nick",
        how="left",
    ).drop(columns=["Nick"], errors="ignore")

    result = result.sort_values(
        ["vitorias", "Pontos", "Desempenho_Medio"],
        ascending=[False, False, False],
    ).reset_index(drop=True)

    return result


def build_categories(ranking):
    if ranking.empty:
        return pd.DataFrame()

    pieces = []

    for low, high, label in RATING_LIMITS:
        if math.isinf(high):
            subset = ranking[ranking["Rating_Medio"] >= low].head(5).copy()
        else:
            subset = ranking[
                (ranking["Rating_Medio"] >= low)
                & (ranking["Rating_Medio"] < high)
            ].head(5).copy()

        if subset.empty:
            continue

        subset.insert(0, "Categoria", label)
        pieces.append(subset)

    if not pieces:
        return pd.DataFrame()

    return pd.concat(pieces, ignore_index=True)


# ============================================================
# PUBLICAÇÃO DOS JSON
# ============================================================

def main():
    started = datetime.now(timezone.utc)

    print("Consultando torneios do Itaberabão...")
    tournaments = get_team_tournaments(
        start_ms=START_TIMESTAMP_MS,
        end_ms=END_TIMESTAMP_MS
    )
    print(f"Torneios selecionados: {len(tournaments)}")

    results = download_all_results(tournaments)
    participations = build_participation_table(tournaments, results)
    ranking = build_ranking(participations)
    winners = build_winners(tournaments, ranking)
    categories = build_categories(ranking)

    # Dados de torneios para o site.
    tournament_records = []
    for _, row in tournaments.iterrows():
        winner = get_winner_name(row)
        start = row.get("startsAt_dt")
        tournament_records.append({
            "id": row.get("id"),
            "name": row.get("fullName"),
            "winner": NICK_REPLACEMENTS.get(winner, winner),
            "startsAt": start.isoformat() if pd.notna(start) else None,
            "url": f"https://lichess.org/tournament/{row.get('id')}",
        })

    save_json("jogadores.json", records(ranking))
    save_json("vencedores.json", records(winners))
    save_json("categorias.json", records(categories))
    save_json("torneios.json", tournament_records)

    # Histórico de participações, útil para páginas futuras de jogador.
    save_json("participacoes.json", records(participations))

    finished = datetime.now(timezone.utc)

    status = {
        "updated_at": finished.isoformat(),
        "duration_seconds": round((finished - started).total_seconds(), 2),
        "team": TEAM_ID,
        "tournaments": int(len(tournaments)),
        "players": int(len(ranking)),
        "participations": int(len(participations)),
        "success": True,
    }
    save_json("status.json", status)

    print(json.dumps(status, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
