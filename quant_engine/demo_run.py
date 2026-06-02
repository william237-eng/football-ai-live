"""
Demo runner for quant_engine. Shows flow: fetch data, compute features, model probabilities, run live sim, detect EV and stake sizing.
"""
from .api_layer import FootballAPI
from .data_pipeline import DataPipeline
from .features import FeatureEngineer
from .modeling import ModelingEngine
from .simulation import SimulationEngine
from .risk import RiskEngine
from .prediction import PredictionEngine
from .validation import ValidationEngine
from .confidence import ConfidenceEngine

import pprint


def run_demo():
    # This runner strictly refuses to fabricate data. Configure real providers
    # in application code and pass them to FootballAPI. If no providers are
    # configured the pipeline will return clear French error messages.
    api = FootballAPI(providers=[])
    dp = DataPipeline(api=api)
    fe = FeatureEngineer()
    me = ModelingEngine()
    se = SimulationEngine(me)
    re = RiskEngine(bankroll=1000.0)
    pe = PredictionEngine(me, risk_engine=re)
    ve = ValidationEngine()
    ce = ConfidenceEngine()

    fixtures_res = dp.fetch_fixtures()
    pprint.pprint({"fixtures_result": fixtures_res})

    if isinstance(fixtures_res, dict) and fixtures_res.get("error"):
        print(fixtures_res.get("error"))
        return

    # normalised fixtures are available under fixtures_res['data']
    fixtures = fixtures_res.get("data", [])
    if not fixtures:
        print("Données insuffisantes")
        return

    # Proceed only with real historical and live data provided by the API
    match = fixtures[0]
    match_id = match.get("match_id")
    home = match.get("home")
    away = match.get("away")

    # fetch historical data for each team
    hist_home = dp.fetch_historical(home)
    hist_away = dp.fetch_historical(away)
    if (isinstance(hist_home, dict) and hist_home.get("error")) or (isinstance(hist_away, dict) and hist_away.get("error")):
        print("Données insuffisantes")
        return

    sh = fe.compute_team_strengths(hist_home)
    sa = fe.compute_team_strengths(hist_away)
    if (isinstance(sh, dict) and sh.get("error")) or (isinstance(sa, dict) and sa.get("error")):
        print("Données insuffisantes")
        return

    # derive base lambdas using strengths and home adv (must be based on real stats)
    home_adv = fe.home_advantage()
    base_lh = fe.poisson_rate(sh["attack"], sa["defense"], home_adv)
    base_la = fe.poisson_rate(sa["attack"], sh["defense"], 1.0)

    # compute pre-match probabilities using validated lambdas
    probs = me.compute_1x2(base_lh, base_la)
    if isinstance(probs, dict) and probs.get("error"):
        print("Analyse impossible")
        return

    market_odds = {"home": 2.2, "draw": 3.4, "away": 3.0}  # Integrator should supply real market odds
    print("Pre-match model probabilities:")
    pprint.pprint(probs)

    signals = pe.recommend(probs, market_odds, min_edge=0.02)
    pprint.pprint(signals)

    # Example live fetch: will abort if live stats missing or insufficient
    live_res = dp.fetch_live_stats(match_id, minute=55)
    pprint.pprint({"live_result": live_res})
    if isinstance(live_res, dict) and live_res.get("error"):
        print(live_res.get("error"))
        return

    # Integrator must compute base_lam_home/la from real live xG or expected goals
    # Here we refuse to fabricate such values; we expect an upstream step to provide them.
    print("Analyse prête: toutes les données doivent provenir d'API réelles. Configurez un provider.")


if __name__ == '__main__':
    run_demo()

