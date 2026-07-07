# EMS VOC Radar

Multi-channel voice-of-customer monitoring for the **ASSA ABLOY
Electromechanical Solutions Group** (HES · Securitron · Alarm Controls ·
Adams Rite).

The tool regularly collects publicly available information about commercial
access control and door hardware — trade press, installer/integrator
discussion on Reddit, and competitor news pages — tags it against a
product/brand/theme taxonomy, and publishes:

- **`reports/dashboard.html`** — a visual dashboard (open in any browser;
  light/dark aware) with period stats, category/theme/brand share-of-voice
  charts, a 12-week volume trend, and the period's notable items.
- **`reports/digest-latest.md`** (plus dated copies) — a Markdown digest of
  the same data for reading directly on GitHub.
- An optional **Claude-generated insight brief** (key takeaways, competitor
  activity, voice of the field, suggested follow-ups) embedded in both.

**Primary users:** product managers (roadmap signal). **Secondary:** tech
support (recurring installation/troubleshooting pain points surface in the
*Themes* chart and Reddit items).

## How it works

```
config/sources.yaml ──▶ collectors (RSS · Reddit JSON · web pages)
                              │
                              ▼
                        data/voc.db  (SQLite, deduped by URL, history accumulates)
                              │
config/taxonomy.yaml ──▶ keyword tagger (categories · brands · themes)
                              │
                              ▼
                   analysis (period counts, deltas, weekly trend)
                              │            │
                              ▼            ▼
                  reports/digest-*.md   reports/dashboard.html
                              ▲
              optional: Claude insight brief (ANTHROPIC_API_KEY)
```

- **RSS** — Locksmith Ledger, SDM Magazine, Security Info Watch, SSI,
  Campus Safety, DHI (stdlib XML parsing; no fragile dependencies).
- **Reddit** — r/accesscontrol, r/Locksmith and friends via the public JSON
  listings (no API key needed; polite UA + rate limiting).
- **Web** — competitor news pages (Allegion, dormakaba, SDC, Camden, Detex,
  Command Access) scraped with per-source CSS selectors.

Every source is fetched independently — one broken feed never aborts a run.

## Running it

```bash
pip install -r requirements.txt

python -m voc run              # collect + tag + report (last 7 days)
python -m voc run --days 30    # wider window
python -m voc collect          # just fetch into data/voc.db
python -m voc analyze          # re-tag everything (after taxonomy edits)
python -m voc report --no-llm  # regenerate reports without the Claude brief
```

Outputs land in `reports/`; the database lives at `data/voc.db`.

### Claude insight brief (optional)

If `ANTHROPIC_API_KEY` is set (or an `ant auth login` profile exists), the
report step sends the period's top ~50 items to Claude (`claude-opus-4-8`)
and embeds a structured insight brief. Without credentials the pipeline
simply skips it.

## Scheduled runs

`.github/workflows/voc.yml` runs the whole pipeline **every Monday at 11:00
UTC** (and on demand via *Run workflow*), then commits the updated database
and reports back to the repo — so trend history accumulates and the latest
dashboard/digest are always one click away in `reports/`.

To enable the insight brief in CI, add an `ANTHROPIC_API_KEY` repository
secret. Everything else works with no configuration.

### Live dashboard (GitHub Pages)

Each run also publishes the dashboard to GitHub Pages, so the latest version
is always at:

```
https://<owner>.github.io/<repo>/            (dashboard)
https://<owner>.github.io/<repo>/digest-latest.md
```

The workflow attempts to enable Pages automatically on its first run. If
that step is skipped due to permissions, enable it once manually:
**Settings → Pages → Source: GitHub Actions**, then re-run the workflow.

> **First-run note:** RSS feed URLs for trade publications occasionally move.
> Check the first Actions run log — any source that fails is logged as a
> warning with its URL. Fix the URL in `config/sources.yaml` and re-run.

## Tuning the sources and taxonomy

- **Add/remove sources** in `config/sources.yaml`. Web sources take an
  `item_selector` (CSS selector matching headline links).
- **Tune tagging** in `config/taxonomy.yaml` — product categories, own
  brands, sibling ASSA ABLOY brands, competitors, and discussion themes are
  all plain keyword lists (case-insensitive, word-boundary matched, phrases
  allowed). After editing, run `python -m voc analyze` to re-tag the whole
  database, then `python -m voc report`.

## Development

```bash
python tests/test_pipeline.py   # fixture-based end-to-end test, no network
```

Project layout:

```
voc/
  collectors/   rss.py · reddit.py · web.py · http.py
  tagging.py    keyword tagger
  analysis.py   period stats, deltas, weekly volume, notable items
  llm.py        optional Claude insight brief
  report/       digest.py (Markdown) · dashboard.py (HTML)
  db.py         SQLite storage
  cli.py        collect / analyze / report / run
config/         sources.yaml · taxonomy.yaml
data/           voc.db (committed so history accumulates)
reports/        dashboard.html · digest-*.md
```

## Notes & limitations

- Public sources only; Reddit is fetched through the public JSON listings
  within their unauthenticated usage allowance.
- Competitor pages rarely expose machine-readable dates, so those items are
  windowed by collection date — they appear in the period they were first
  seen.
- Keyword tagging is intentionally transparent and editable; the optional
  Claude brief adds interpretation on top, and is labeled as
  machine-generated in the reports.
