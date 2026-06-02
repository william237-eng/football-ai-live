"""
Risk Engine
Fractional Kelly staking, exposure limits, risk scores.
"""
import math

class RiskEngine:
    def __init__(self, bankroll: float = 1000.0, max_exposure: float = 0.1, max_drawdown: float = 0.3, kelly_fraction: float = 0.2):
        self.bankroll = bankroll
        self.max_exposure = max_exposure
        self.max_drawdown = max_drawdown
        self.kelly_fraction = kelly_fraction
        self.peak = bankroll

    def fractional_kelly(self, p: float, b: float):
        # p: model prob, b: odds - 1 (decimal odds - 1)
        if p <= 0 or b <= 0:
            return 0.0
        q = 1 - p
        kelly = (p * (b + 1) - 1) / b
        frac = max(0.0, kelly * self.kelly_fraction)
        return frac

    def stake(self, p: float, odds: float):
        b = odds - 1.0
        fraction = self.fractional_kelly(p, b)
        stake = fraction * self.bankroll
        # apply exposure limit
        stake = min(stake, self.max_exposure * self.bankroll)
        # apply floor
        stake = max(0.0, stake)
        return stake

    def update_bankroll(self, profit: float):
        self.bankroll += profit
        self.peak = max(self.peak, self.bankroll)

    def current_drawdown(self):
        if self.peak <= 0:
            return 0.0
        return (self.peak - self.bankroll) / self.peak

    def assess_risk(self):
        dd = self.current_drawdown()
        if dd > self.max_drawdown:
            return "exceeded"
        return "ok"

