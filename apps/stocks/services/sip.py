"""
Monte Carlo SIP outcome simulator. Extracted from the view; pure numpy.
"""
from __future__ import annotations

import numpy as np

# Historical Nifty: assume ~12% CAGR, ~18% annualized volatility (realistic long-term).
# Converted to monthly: mean ≈ 0.949%, std ≈ 5.2%.
ANNUAL_RETURN = 0.12
ANNUAL_VOL = 0.18
SIMULATIONS = 2000
SEED = 42


def simulate(monthly_raw: str, years_raw: str, goal_raw: str) -> tuple[dict | None, str | None]:
    """Return (result, error). Exactly one of the two is non-None."""
    try:
        monthly = float(monthly_raw)
        years = int(float(years_raw))
        goal = float(goal_raw) if goal_raw else None
        n_months = years * 12

        mu = ANNUAL_RETURN / 12
        sigma = ANNUAL_VOL / np.sqrt(12)

        sims = SIMULATIONS
        rng = np.random.default_rng(SEED)
        # monthly returns, sims × n_months
        rets = rng.normal(mu, sigma, size=(sims, n_months))

        # Apply SIP compounding
        finals = np.zeros(sims)
        for i in range(sims):
            v = 0.0
            for r in rets[i]:
                v = (v + monthly) * (1 + r)
            finals[i] = v

        p5, p50, p95 = np.percentile(finals, [5, 50, 95])
        total_invested = monthly * n_months
        prob_goal = None
        if goal:
            prob_goal = float((finals >= goal).mean() * 100)

        return {
            "monthly": monthly, "years": years, "n_months": n_months,
            "invested": round(total_invested),
            "p5": round(float(p5)), "p50": round(float(p50)), "p95": round(float(p95)),
            "p50_mult": round(float(p50) / total_invested, 2) if total_invested else 0,
            "goal": goal,
            "prob_goal": round(prob_goal, 1) if prob_goal is not None else None,
            "sims": sims,
        }, None
    except Exception as exc:
        return None, str(exc)
