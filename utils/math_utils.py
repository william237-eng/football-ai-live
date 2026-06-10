"""Utilitaires mathématiques typés pour les modèles quantitatifs.

Contient : EMA, Dixon-Coles bivarié, approximation Skellam (via convolution tronquée),
Kelly fractionné, Bayesian lambda update, pénalités de fatigue, et fonctions d'anomalies.
Tous les calculs sont explicitement commentés pour auditabilité.
"""
from __future__ import annotations

import math
from typing import Dict, Iterable, List, Tuple


def ema(prev: float, value: float, alpha: float) -> float:
    """Exponential Moving Average simple.

    ema_t = alpha * value + (1-alpha) * prev
    - prev: valeur EMA précédente (ou initialisation)
    - value: nouvelle observation
    - alpha: factor de lissage (0<alpha<=1)
    """
    return alpha * value + (1.0 - alpha) * prev


def dixon_coles_prob(h: int, a: int, lambda_h: float, lambda_a: float, rho: float) -> float:
    """Probabilité bivariée Dixon-Coles pour score (h,a).

    P(H=h, A=a) = Poisson(h; lambda_h) * Poisson(a; lambda_a) * adjustment(h,a)
    adjustment applique un facteur rho pour les faibles scores (0-1) pour capturer
    la dépendance entre petits scores.
    Référence: Dixon & Coles (1997)
    """
    # Poisson indépendantes
    def poisson(k: int, lam: float) -> float:
        return math.exp(-lam) * (lam ** k) / math.factorial(k)

    p = poisson(h, lambda_h) * poisson(a, lambda_a)

    # Adjustment term
    if h == 0 and a == 0:
        adj = 1 - (lambda_h * lambda_a * rho)
    elif h == 0 and a == 1:
        adj = 1 + (lambda_h * rho)
    elif h == 1 and a == 0:
        adj = 1 + (lambda_a * rho)
    elif h == 1 and a == 1:
        adj = 1 - rho
    else:
        adj = 1.0

    return max(0.0, p * adj)


def skellam_pmf(k: int, mu1: float, mu2: float, max_terms: int = 200) -> float:
    """Approximation PMF de la différence de deux Poissons (Skellam) par convolution.

    P(D = k) = sum_{n=max(0,k)}^{inf} Poisson(n;mu1) * Poisson(n-k;mu2)
    Nous tronquons la somme à `max_terms` autour des moyennes pour stabilité numérique.
    Cette approche évite la dépendance à scipy.special.iv.
    """
    # borne supérieure raisonnable (mu + 10*sqrt(mu) + margin)
    upper1 = int(mu1 + 10 * math.sqrt(max(1.0, mu1)) + 20)
    upper2 = int(mu2 + 10 * math.sqrt(max(1.0, mu2)) + 20)
    N = min(max_terms, max(upper1, upper2) + 50)

    def poisson_pmf(k_: int, mu: float) -> float:
        if k_ < 0:
            return 0.0
        return math.exp(-mu) * (mu ** k_) / math.factorial(k_)

    s = 0.0
    start = max(0, k)
    for n in range(start, N):
        s += poisson_pmf(n, mu1) * poisson_pmf(n - k, mu2)
    return s


def skellam_cdf_range(mu1: float, mu2: float, lo: int, hi: int) -> float:
    """Probabilité que la différence D soit entre lo et hi inclus.
    Utilisé pour estimer la probabilité de surpasser une ligne d'Asian Handicap.
    """
    s = 0.0
    for k in range(lo, hi + 1):
        s += skellam_pmf(k, mu1, mu2)
    return s


def kelly_fraction(p: float, odds: float, fraction: float = 0.25) -> float:
    """Kelly fractionné.

    - odds: cote décimale
    - p: probabilité estimée d'obtenir un gain
    - fraction: fraction de Kelly à appliquer (<=1)

    Formule de Kelly (pour cote décimale): f* = ((b * p) - q) / b where b = odds - 1, q = 1-p
    On retourne max(0, f*) * fraction
    """
    b = max(0.0, odds - 1.0)
    q = 1.0 - p
    if b <= 0:
        return 0.0
    fstar = ((b * p) - q) / b
    return max(0.0, fstar) * fraction


def bayesian_lambda_update(lambda_pre: float, xg_acc: float, t_min: float, k: float) -> float:
    """Formule Bayésienne donnée dans le cahier.

    lambda_adjusted = lambda_pre * exp(-k * t/90) + (xG_live_accumule / t * 90) * (1 - exp(-k * t/90))
    - t_min: minutes écoulées
    - k: vitesse d'oubli (plus grand = plus d'importance au live)
    """
    if t_min <= 0:
        return lambda_pre
    decay = math.exp(-k * (t_min / 90.0))
    live_rate = (xg_acc / t_min) * 90.0 if t_min > 0 else 0.0
    return (lambda_pre * decay) + (live_rate * (1.0 - decay))


def red_card_decay(lambda_before: float, t_min: float, c: float = 0.05) -> float:
    """Décroissance exponentielle après carton rouge.

    f(t) = exp(-c * (90 - t)) appliquée sur lambda de l'équipe pénalisée.
    """
    return lambda_before * math.exp(-c * (90.0 - t_min))


def fatigue_penalty(delta_t_hours: float, distance_km: float) -> float:
    """Renvoie un multiplicateur 0<mult<=1 à appliquer à lambda en fonction de la fatigue.

    - delta_t_hours: temps de repos entre derniers matches
    - distance_km: distance de voyage
    Formule heuristique (auditable) : mult = exp(-a / (delta_t+eps)) * exp(-b * distance_norm)
    où a et b sont coefficients calibrables.
    """
    a = 48.0  # sensibilité au repos (heures)
    b = 0.0005  # sensibilité à la distance
    eps = 1e-6
    mult = math.exp(-a / (max(delta_t_hours, eps) + eps)) * math.exp(-b * distance_km)
    return max(0.2, min(1.0, mult))


def pearson_correlation(x: Iterable[float], y: Iterable[float]) -> float:
    """Corrélation de Pearson simple (auditable)."""
    xs = list(x)
    ys = list(y)
    n = len(xs)
    if n == 0 or n != len(ys):
        return 0.0
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    num = sum((xi - mean_x) * (yi - mean_y) for xi, yi in zip(xs, ys))
    den = math.sqrt(sum((xi - mean_x) ** 2 for xi in xs) * sum((yi - mean_y) ** 2 for yi in ys))
    if den == 0:
        return 0.0
    return num / den

