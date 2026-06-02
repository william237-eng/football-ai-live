"""
Orchestrator
Coordonne la récupération des données, la validation, le calcul des probabilités
et la production d'un rapport conforme à la règle : 100% données réelles,
aucune fabrication.
"""
from typing import Dict, Any, Optional
import time

from .api_layer import FootballAPI
from .data_pipeline import DataPipeline
from .data_validator import DataValidator, DataQuality
from .features import FeatureEngineer
from .modeling import ModelingEngine
from .prediction import PredictionEngine
from .confidence import ConfidenceEngine


class Orchestrator:
    def __init__(self, api: Optional[FootballAPI] = None):
        self.api = api or FootballAPI(providers=[])
        self.dp = DataPipeline(api=self.api)
        self.validator = DataValidator()
        self.fe = FeatureEngineer()
        self.me = ModelingEngine()
        self.ce = ConfidenceEngine()
        self.pe = PredictionEngine(self.me)

    def run_match_analysis(self, match_id: int, market_odds: Optional[Dict[str, float]] = None) -> Dict[str, Any]:
        """Main flow:
        - récupère fixtures / live / historical
        - valide qualité
        - si insuffisant -> renvoie rapport d'erreur
        - sinon calcule probabilités (en utilisant le meilleur niveau disponible)
        Retourne un dict contenant: source utilisée, qualité, last_update, données utilisées,
        probabilités (si calculées), confidence multiplier, message.
        """
        report = {"match_id": match_id, "timestamp": time.time()}

        # 1) fetch live stats
        live_res = self.dp.fetch_live_stats(match_id, minute=0)
        self.validator.record_retrieval("live_stats", time.time())

        # 2) fetch historical (teams unknown here; attempt to read fixtures first)
        fixtures_res = self.dp.fetch_fixtures()
        self.validator.record_retrieval("fixtures", time.time())

        home = None
        away = None
        if isinstance(fixtures_res, dict) and fixtures_res.get("data"):
            for f in fixtures_res.get("data", []):
                if f.get("match_id") == match_id:
                    home = f.get("home")
                    away = f.get("away")
                    break

        hist_home = None
        hist_away = None
        if home:
            hist_home = self.dp.fetch_historical(home)
            self.validator.record_retrieval("historical", time.time())
        if away:
            hist_away = self.dp.fetch_historical(away)
            self.validator.record_retrieval("historical", time.time())

        # 3) assess data quality
        assessment = self.validator.assess_data_quality(
            live_stats=(live_res.get("data") if isinstance(live_res, dict) and live_res.get("data") else None),
            form_data=(hist_home.get("data") if isinstance(hist_home, dict) and hist_home.get("data") else None),
            prematch_data=(fixtures_res.get("data")[0] if isinstance(fixtures_res, dict) and fixtures_res.get("data") else None)
        )

        report["assessment"] = {
            "quality": assessment["quality_str"],
            "sources": assessment["sources"],
            "missing_fields": assessment["missing_fields"],
            "confidence_multiplier": assessment["confidence_multiplier"],
            "report": assessment["report"]
        }

        # 4) Determine if we can compute
        can_compute, reason = self.validator.can_compute_model(assessment)
        if not can_compute:
            return {"error": "Analyse impossible", "reason": reason, "report": report}

        # 5) Compute probabilities using best available data
        probabilities = None
        used_sources = assessment["sources"]
        last_update_info = {
            "live_stats": self.validator.get_freshness_info("live_stats"),
            "fixtures": self.validator.get_freshness_info("fixtures"),
            "historical": self.validator.get_freshness_info("historical")
        }

        try:
            if assessment["level"] and assessment["level"].value == 1:
                # Level 1: use live xG to compute lambdas for remaining time
                live_stats_data = live_res.get("data")
                minute = live_stats_data.get("minute")
                # require minute > 0 to project; otherwise fall back to historical strengths
                if minute and minute > 0:
                    lam_h, lam_a = self.me.lambdas_from_live_xg(live_stats_data)
                    # Compute 1X2 from lambdas (these are expected goals for remaining game)
                    probs = self.me.compute_1x2(lam_h, lam_a)
                    probabilities = probs
                else:
                    # minute==0 — use pre-match strengths derived from historical
                    if hist_home and hist_away and isinstance(hist_home, dict) and isinstance(hist_away, dict) and hist_home.get("data") and hist_away.get("data"):
                        sh = self.fe.compute_team_strengths(hist_home.get("data"))
                        sa = self.fe.compute_team_strengths(hist_away.get("data"))
                        if "error" in sh or "error" in sa:
                            return {"error": "Données insuffisantes pour estimer forces d'équipe"}
                        home_adv = self.fe.home_advantage()
                        base_lh = self.fe.poisson_rate(sh["attack"], sa["defense"], home_adv)
                        base_la = self.fe.poisson_rate(sa["attack"], sh["defense"], 1.0)
                        probabilities = self.me.compute_1x2(base_lh, base_la)
                    else:
                        return {"error": "Données insuffisantes pour pré-match"}

            elif assessment["level"] and assessment["level"].value == 2:
                # Level 2: use historical/form metrics to estimate lambdas conservatively
                # Use average goals scored/conceded from historical matches (real data)
                if hist_home and hist_away and isinstance(hist_home, dict) and isinstance(hist_away, dict) and hist_home.get("data") and hist_away.get("data"):
                    # compute crude rates
                    matches_h = hist_home.get("data").get("matches", [])
                    matches_a = hist_away.get("data").get("matches", [])
                    gh = sum(m.get("goals_for", 0) for m in matches_h) / max(len(matches_h), 1)
                    ga = sum(m.get("goals_for", 0) for m in matches_a) / max(len(matches_a), 1)
                    # use as lambdas per match and scale to per-match Poisson
                    probabilities = self.me.compute_1x2(gh, ga)
                else:
                    return {"error": "Données insuffisantes niveau 2"}

            elif assessment["level"] and assessment["level"].value == 3:
                # Level 3: prematch only — compute probabilities with low confidence
                # Require prematch fixture data
                if fixtures_res and isinstance(fixtures_res, dict) and fixtures_res.get("data"):
                    # naive neutral model — but avoid fabricating strengths: block if no historical
                    return {"error": "Analyse impossible: Niveau 3 nécessite au moins historique"}
                else:
                    return {"error": "Données insuffisantes niveau 3"}

        except Exception as e:
            return {"error": "Erreur lors du calcul", "details": str(e), "report": report}

        # 6) Prepare final output
        out = {
            "match_id": match_id,
            "used_sources": used_sources,
            "last_update": last_update_info,
            "quality": assessment["quality_str"],
            "confidence_multiplier": assessment["confidence_multiplier"],
            "probabilities": probabilities,
            "market_odds": market_odds,
            "recommendations": None,
            "note": "Toutes les données utilisées proviennent exclusivement des providers configurés."
        }

        # recommendations only if market odds provided and probabilities available
        if probabilities and market_odds:
            rec = self.pe.recommend(probabilities, market_odds, min_edge=0.02)
            out["recommendations"] = rec

        # attach a human-readable confidence level from ConfidenceEngine using quality & variance placeholder
        # variance unknown here; use 1 - confidence_multiplier as proxy for variance
        variance_est = 1.0 - assessment["confidence_multiplier"]
        conf_label = self.ce.score(data_quality=assessment["confidence_multiplier"], model_stability=0.8, variance=variance_est, liquidity=0.5)
        out["confidence_label"] = conf_label

        return out


if __name__ == "__main__":
    # run a simple local test (without provider configured) to show behavior
    orch = Orchestrator(api=FootballAPI(providers=[]))
    res = orch.run_match_analysis(match_id=1)
    import pprint

    pprint.pprint(res)

