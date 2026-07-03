# Tradebot Dividend Bot

This is the structured master project for the paper-only Dividend Bot.

## Safety

- Paper-only
- Reporting only
- No Robinhood execution
- No brokerage execution
- No live trading
- No order placement

## Layout

```text
src/dividend_bot/     Production modules
tests/                Pytest files
docs/                 Freeze docs and architecture docs
reports/              Generated CSV/JSON/Markdown outputs
configs/              Configuration files
scripts/              Shell or launcher scripts
```

Root-level compatibility copies are preserved so existing commands such as:

```text
python -m py_compile opportunity_pairing_engine.py
pytest test_opportunity_pairing_engine.py -v
```

continue to work.
