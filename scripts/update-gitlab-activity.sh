#!/usr/bin/env bash
# Atualiza o heatmap de atividade do GitLab e publica no GitHub, se algo mudou.
# Feito pra rodar via cron na maquina do usuario (a instancia do GitLab exige VPN,
# por isso nao roda em GitHub Actions).
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$REPO_DIR/.env"

cd "$REPO_DIR"

if [ -f "$ENV_FILE" ]; then
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
fi

python3 scripts/gitlab_activity_heatmap.py

if ! git diff --quiet -- assets/gitlab-activity.svg; then
  git add assets/gitlab-activity.svg
  git commit -m "chore: atualiza heatmap de atividade do GitLab"
  git push origin main
else
  echo "Sem mudancas na atividade de hoje."
fi
