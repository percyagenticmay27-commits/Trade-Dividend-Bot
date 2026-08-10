# Swing Legacy Unassigned Exit Compatibility Addendum

## Purpose

This addendum records the Dividend-side policy for open paper positions that were created before persistent Strategy A / Strategy B ownership existed. It is also a handoff to the Swing Bot development chat. The Dividend repository does not modify the Swing repository.

## Dividend legacy management state

An existing open pre-ownership Dividend position may be explicitly marked:

- `strategy_owner = LEGACY_UNASSIGNED`
- `strategy_ownership_source = LEGACY_PRE_OWNERSHIP_POSITION`

This marker does **not** claim that Strategy A or Strategy B owned the historical entry. It is a lifecycle-management status only.

The migration is explicit and paper-only. It does not create a trade, move capital, or retroactively reconstruct a methodology. A backup of `paper_state.json` is written before the explicit migration changes state.

## Legacy technical exit policy

A `LEGACY_UNASSIGNED` open position uses a conservative consensus bridge until that old lifecycle closes:

- Strategy A SELL alone -> `WARNING_BUFFERED`, no sale.
- Strategy B SELL alone -> `WARNING_BUFFERED`, no sale.
- Strategy A fast Stoch RSI warning alone -> `WARNING_BUFFERED`, no sale.
- Strategy A confirmed SELL **and** Strategy B confirmed SELL -> `SELL_CONFIRMED`.
- Neither strategy SELL -> `HOLD`.

The permanent policy code is:

`REQUIRE_STRATEGY_A_AND_B_SELL_CONSENSUS`

This rule exists only for pre-ownership open positions. New entries must still resolve to one real owner through the qualified entry gate.

## Why consensus is required

The system must not solve missing historical ownership by arbitrarily choosing whichever current strategy happens to issue a SELL first. Requiring both independent current exit methodologies to agree provides a conservative bridge without falsifying the original entry methodology.

Scheduled earnings/risk-governance exits remain independent overrides and are not blocked by the legacy consensus policy.

## Lifecycle after exit

Once a legacy position is actually closed to SGOV, the old lifecycle is complete. Any later re-entry must go through the normal qualified entry gate and persist a real `STRATEGY_A` or `STRATEGY_B` owner. `LEGACY_UNASSIGNED` is never a valid new-entry methodology.

## Swing compatibility requirement

If Swing has open paper positions that predate a future method-ownership architecture, Swing should not silently assign those positions to a current method. Swing may use its own explicit legacy-management status and conservative exit policy, but it must document the policy, preserve provenance, keep risk overrides separate, and require all later re-entries to receive a real current method owner.

Swing does not need to copy Dividend's A+B consensus formula unless that is appropriate for Swing's own methods. The interoperability requirement is semantic: legacy status must remain distinct from a genuine strategy/method owner, and Enterprise AI CIO should display the supplied status rather than invent ownership.
