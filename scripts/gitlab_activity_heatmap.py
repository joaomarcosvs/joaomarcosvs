#!/usr/bin/env python3
"""Gera um heatmap SVG anônimo de atividade do GitLab para uso no README do GitHub.

Coleta apenas a DATA de cada evento (via /api/v4/events do usuário autenticado)
e conta quantos eventos ocorreram em cada dia. Nome de projeto, branch, mensagem
de commit e qualquer outro campo do evento são descartados imediatamente e nunca
persistidos ou logados.

Variaveis de ambiente:
  GITLAB_URL             base da instancia (default: https://gitlab.services.betha.cloud)
  GITLAB_TOKEN            personal access token com escopo read_api (obrigatorio)
  GITLAB_HEATMAP_OUTPUT   caminho do heatmap SVG (default: assets/gitlab-activity.svg)
  GITLAB_STATS_OUTPUT     caminho do card de estatisticas SVG (default: assets/gitlab-stats.svg)
"""
import json
import os
import urllib.error
import urllib.request
from datetime import date, timedelta

GITLAB_URL = os.environ.get("GITLAB_URL", "https://gitlab.services.betha.cloud").rstrip("/")
GITLAB_TOKEN = os.environ.get("GITLAB_TOKEN")
OUTPUT_PATH = os.environ.get("GITLAB_HEATMAP_OUTPUT", "assets/gitlab-activity.svg")
STATS_OUTPUT_PATH = os.environ.get("GITLAB_STATS_OUTPUT", "assets/gitlab-stats.svg")
WEEKS = 53

CELL = 11
GAP = 3
LEVELS = ["#1f2335", "#2d4263", "#3a5f8a", "#4f86c6", "#7cb9ff"]


def fetch_daily_counts():
    if not GITLAB_TOKEN:
        raise SystemExit("GITLAB_TOKEN nao definido no ambiente.")

    after = (date.today() - timedelta(weeks=WEEKS)).isoformat()
    counts = {}
    page = 1
    while True:
        url = f"{GITLAB_URL}/api/v4/events?after={after}&per_page=100&page={page}"
        req = urllib.request.Request(url, headers={"PRIVATE-TOKEN": GITLAB_TOKEN})
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                batch = json.loads(resp.read())
        except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
            raise SystemExit(f"GitLab inacessivel (provavelmente sem VPN): {exc}")

        if not batch:
            break

        for event in batch:
            day = event["created_at"][:10]  # so a data; o resto do evento e descartado aqui
            counts[day] = counts.get(day, 0) + 1

        if len(batch) < 100:
            break
        page += 1

    return counts


def level_for(count, thresholds):
    for i, t in enumerate(thresholds):
        if count <= t:
            return i
    return len(thresholds)


def window_days():
    today = date.today()
    start = today - timedelta(weeks=WEEKS - 1)
    while start.weekday() != 6:  # volta até o domingo anterior (Monday=0 ... Sunday=6)
        start -= timedelta(days=1)
    return [start + timedelta(days=i) for i in range((today - start).days + 1)]


def compute_streaks(counts):
    days = window_days()
    today = date.today()

    longest = 0
    longest_range = None
    run_start = None
    run_len = 0
    for day in days:
        if counts.get(day.isoformat(), 0) > 0:
            if run_len == 0:
                run_start = day
            run_len += 1
            if run_len > longest:
                longest = run_len
                longest_range = (run_start, day)
        else:
            run_len = 0

    current = 0
    anchor = today if counts.get(today.isoformat(), 0) > 0 else today - timedelta(days=1)
    if counts.get(anchor.isoformat(), 0) > 0:
        cursor = anchor
        while counts.get(cursor.isoformat(), 0) > 0:
            current += 1
            cursor -= timedelta(days=1)

    return {
        "current": current,
        "longest": longest,
        "longest_range": longest_range,
        "window_start": days[0],
        "window_end": days[-1],
    }


def build_svg(counts):
    days = window_days()
    max_count = max(counts.values(), default=0)
    thresholds = [0, max(1, max_count // 4), max(1, max_count // 2), max(1, (max_count * 3) // 4)]

    cols = len(days) // 7 + 1
    width = cols * (CELL + GAP)
    height = 7 * (CELL + GAP)

    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" font-family="sans-serif">'
    ]

    for idx, day in enumerate(days):
        col = idx // 7
        row = (day.weekday() + 1) % 7  # domingo=0 ... sabado=6, estilo GitHub
        count = counts.get(day.isoformat(), 0)
        color = LEVELS[level_for(count, thresholds)]
        x = col * (CELL + GAP)
        y = row * (CELL + GAP)
        label = f"{day.isoformat()}: {count} atividade{'s' if count != 1 else ''}"
        svg.append(
            f'<rect x="{x}" y="{y}" width="{CELL}" height="{CELL}" rx="2" fill="{color}">'
            f"<title>{label}</title></rect>"
        )

    svg.append("</svg>")
    return "\n".join(svg)


def _fmt(day):
    return day.strftime("%d/%m/%Y")


def build_stats_svg(counts):
    streaks = compute_streaks(counts)
    total_events = sum(counts.values())
    period = f"{_fmt(streaks['window_start'])} - Hoje"

    if streaks["longest_range"]:
        longest_period = f"{_fmt(streaks['longest_range'][0])} - {_fmt(streaks['longest_range'][1])}"
    else:
        longest_period = "-"

    current_label = "Ativo hoje" if counts.get(date.today().isoformat(), 0) > 0 else "Ultimo dia ativo"

    width, height = 600, 170
    bg = "#161b22"
    border = "#30363d"
    accent = "#58a6ff"
    text = "#c9d1d9"
    muted = "#8b949e"
    col_w = width / 3

    def column(cx, value, label, sub):
        return f'''
        <text x="{cx}" y="70" text-anchor="middle" font-size="30" font-weight="700" fill="{accent}">{value}</text>
        <text x="{cx}" y="98" text-anchor="middle" font-size="13" fill="{text}">{label}</text>
        <text x="{cx}" y="118" text-anchor="middle" font-size="11" fill="{muted}">{sub}</text>
        '''

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" font-family="sans-serif">
  <rect x="0.5" y="0.5" width="{width - 1}" height="{height - 1}" rx="8" fill="{bg}" stroke="{border}"/>
  <line x1="{col_w:.1f}" y1="20" x2="{col_w:.1f}" y2="{height - 20}" stroke="{border}"/>
  <line x1="{2 * col_w:.1f}" y1="20" x2="{2 * col_w:.1f}" y2="{height - 20}" stroke="{border}"/>
  {column(col_w * 0.5, total_events, "Total de atividades", period)}
  <circle cx="{col_w * 1.5:.1f}" cy="70" r="40" fill="none" stroke="{accent}" stroke-width="4"/>
  <text x="{col_w * 1.5:.1f}" y="78" text-anchor="middle" font-size="30" font-weight="700" fill="{accent}">{streaks['current']}</text>
  <text x="{col_w * 1.5:.1f}" y="128" text-anchor="middle" font-size="13" fill="{text}">Sequencia atual</text>
  <text x="{col_w * 1.5:.1f}" y="146" text-anchor="middle" font-size="11" fill="{muted}">{current_label}</text>
  {column(col_w * 2.5, streaks['longest'], "Maior sequencia", longest_period)}
</svg>'''
    return svg


def main():
    counts = fetch_daily_counts()

    heatmap_svg = build_svg(counts)
    os.makedirs(os.path.dirname(OUTPUT_PATH) or ".", exist_ok=True)
    with open(OUTPUT_PATH, "w") as fh:
        fh.write(heatmap_svg)

    stats_svg = build_stats_svg(counts)
    os.makedirs(os.path.dirname(STATS_OUTPUT_PATH) or ".", exist_ok=True)
    with open(STATS_OUTPUT_PATH, "w") as fh:
        fh.write(stats_svg)

    active_days = len(counts)
    total_events = sum(counts.values())
    print(
        f"Heatmap gerado em {OUTPUT_PATH} e stats em {STATS_OUTPUT_PATH}: "
        f"{active_days} dias ativos, {total_events} eventos no total."
    )


if __name__ == "__main__":
    main()
