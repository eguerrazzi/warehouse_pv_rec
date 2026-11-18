# Working rules for this repository

The approved brief is [docs/spec/specification_v1.md](docs/spec/specification_v1.md); read it first.
Decisions taken later are in [docs/decisions.md](docs/decisions.md) and override the brief where they differ.

- Work in phases (spec Section 11). At the end of each phase: run `uv run ruff check . && uv run pytest`,
  then give Ema a short summary **in Italian** (built, passed, open, questions, open paper requests from
  `docs/papers/REQUESTS.md`). Do not start the next phase without Ema's ok.
- Never invent data: every number comes from `config/params/` with source and source type; missing →
  `null` + `to_be_provided`/`to_be_derived`, and ask.
- Do not change the model of spec Section 5 on your own; propose fixes and wait.
- Code, comments, docs in English; messages to Ema in Italian.
- Commit often; do not push.
- Environment: Ema works in the conda env `wpvrec` (`environment.yml`, pip-installs the exact versions of
  `requirements.lock.txt`). `uv.lock` is the reference lock (CI); after changing dependencies run `make lock`.
  `uv` is at `~/.local/bin/uv` (not on PATH by default).
- Keep [docs/guida.md](docs/guida.md) (plain-language guide for Ema, in Italian) up to date at the end of every
  phase; figures in docs/figures are regenerated with `wpvrec figures`.
