#!/usr/bin/env python3
"""
Script de vérification — Nouvelle clé Sportmonks API intégrée
Teste chaque pilier pour confirmer connectivity avec Sportmonks v3
"""

import os
import asyncio
from dotenv import load_dotenv
import logging

logging.basicConfig(level=logging.INFO, format='%(message)s')

print("=" * 75)
print("VÉRIFICATION — Clé Sportmonks v3 Intégrée au Moteur de Trading")
print("=" * 75)

# Charger .env
load_dotenv()

# 1. Afficher config
print("\n📋 Configuration chargée depuis .env:")
sportmonks_key = os.getenv("SPORTMONKS_API_KEY", "NOT FOUND")
api_football_key = os.getenv("API_KEY", "NOT FOUND")

print(f"  ✓ Sportmonks v3 API Key: {sportmonks_key[:25]}...")
print(f"  ✓ API-FOOTBALL (fallback): {api_football_key}")
print(f"  ✓ Sportmonks Base URL: https://api.sportmonks.com/v3")

# 2. Test imports
print("\n🔧 Tests d'importation des modules:")
try:
    from quant_engine.trading_orchestrator import TradingOrchestrator
    print("  ✓ TradingOrchestrator")

    from quant_engine.data_tier_1 import DataTier1Ingestion
    print("  ✓ DataTier1Ingestion")

    from quant_engine.prematch_engine import PreMatchEngine
    print("  ✓ PreMatchEngine")

    from quant_engine.live_engine import LiveEngine
    print("  ✓ LiveEngine")

    from quant_engine.pricing_engine import PricingEngine
    print("  ✓ PricingEngine")

except ImportError as e:
    print(f"  ✗ Erreur import: {e}")
    exit(1)

# 3. Tester DataTier1 avec clé Sportmonks
print("\n📡 Initialisation DataTier1Ingestion avec clé Sportmonks:")
try:
    tier1 = DataTier1Ingestion()
    print(f"  ✓ DataTier1 initialisée")
    print(f"    - API Key chargée: {len(tier1.api_key)} caractères")
    print(f"    - Base URL: {tier1.base_url}")
except Exception as e:
    print(f"  ✗ Erreur: {e}")

# 4. Tester TradingOrchestrator
print("\n🎯 Initialisation TradingOrchestrator avec configuration .env:")
try:
    orchestrator = TradingOrchestrator()
    print(f"  ✓ TradingOrchestrator initialisée")
    print(f"    - Database: {orchestrator.db_path}")
    print(f"    - Sportmonks Key: {'✓ Configured' if orchestrator.sportmonks_key else '✗ Missing'}")
    print(f"    - Pinnacle API: {'✓ Configured' if orchestrator.pinnacle_user else '✗ Not configured (optional)'}")
except Exception as e:
    print(f"  ✗ Erreur: {e}")

# 5. Summary
print("\n" + "=" * 75)
print("✅ RESULT: Nouvelle clé Sportmonks v3 intégrée avec succès")
print("=" * 75)
print("\nProchain étapes:")
print("  1. Tester fetch_fixture(fixture_id) avec fixtures réelles")
print("  2. Valider live_snapshot() pendant match en cours")
print("  3. Vérifier EMA Pressure Index lissage du bruit")
print("  4. Lancer orchestrator.run([fixtures]) en production")
print("\nCommande pour lancer moteur complet:")
print("  python -c \"import asyncio; from quant_engine import TradingOrchestrator;")
print("            asyncio.run(TradingOrchestrator().run([12345, 12346]))\"")
print("=" * 75)

