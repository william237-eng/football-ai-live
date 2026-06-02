quant_engine
============

This package provides a quantitative engine for football pre-match and live modelling.
IMPORTANT: this engine enforces a strict "no fabrication" policy. It will ONLY use
real data from configured providers (live API, historical results, live events, xG feeds, etc.).
If required data are missing the system will refuse to compute and will return
clear French error messages such as "Données live indisponibles" or
"Données insuffisantes".

- API Layer with retries and fallback
- Data Pipeline with simple caching and fallback
- Feature Engineering (attack/defense strengths, home advantage)
- Modeling Engine (Poisson, Dixon-Coles ideas, Elo)
- Simulation Engine (minute updates, Monte Carlo)
- Risk Engine (Fractional Kelly staking and exposure limits)
- Prediction Engine (EV calculation and recommendations)
- Validation Engine (Brier, ROI, hit rate)
- Confidence Engine (discrete confidence categories)

Usage:

1. Implement and configure one or more real provider callables that connect to
   live football APIs (they must return None when unavailable; they must not
   fabricate data).
2. Instantiate FootballAPI with the provider(s) and pass it to DataPipeline.
3. Call pipeline methods. When data are missing the pipeline returns a dict
   with an "error" key containing a French message: the engine will not
   fabricate values or produce probabilities without sufficient real data.

Example (skeleton):

```powershell
python -m quant_engine.demo_run
```

Replace the default provider list in your application with real providers.

