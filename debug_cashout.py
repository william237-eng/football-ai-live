#!/usr/bin/env python3
"""
debug_cashout.py
==============
Script de test pour analyser pourquoi le Smart Cashout propose un bénéfice faible.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import logging
from modules.betting.smart_cashout import SmartCashoutEngine

# Configuration des logs
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class MockAPI:
    """API mock pour tester."""
    def get_fixture_detail(self, fixture_id):
        return None  # Simule API indisponible
    
    def get_fixture_events(self, fixture_id):
        return None
    
    def get_fixture_statistics(self, fixture_id):
        return None

def test_cashout_calculation():
    """Test le calcul du cashout pour comprendre le problème."""
    print("🔍 TEST SMART CASHOUT - ANALYSE DU PROBLÈME")
    print("=" * 50)
    
    # Créer le moteur avec API mock
    api = MockAPI()
    engine = SmartCashoutEngine(api)
    
    # Simuler les données du ticket #7
    ticket_data = {
        "ticket_id": 7,
        "stake": 8,  # Mise de 8⭐
        "potential_gain": 45,  # Gain potentiel de 45⭐
        "status": "ACTIVE",
        "total_events": 3,
        "validated_events": 0,  # 0/3 validés
        "won_events": 0,
        "lost_events": 0,
        "pending_events": 3,  # 3 matchs en attente
        "total_odds": 5.625
    }
    
    print(f"Données du ticket :")
    print(f"  - Mise : {ticket_data['stake']} ⭐")
    print(f"  - Gain potentiel : {ticket_data['potential_gain']} ⭐")
    print(f"  - Progression : {ticket_data['validated_events']}/{ticket_data['total_events']} ({ticket_data['validated_events']/ticket_data['total_events']*100:.0f}%)")
    print(f"  - Matchs restants : {ticket_data['pending_events']}")
    print()
    
    # Test 1 : Calcul du fallback cashout directement
    print("📊 TEST 1 - CALCUL FALLBACK DIRECT")
    print("-" * 30)
    
    try:
        fallback_result = engine._get_fallback_cashout(ticket_data)
        print(f"Résultat fallback : {fallback_result['amount']} ⭐ ({fallback_result['percentage']}%)")
        print(f"Bénéfice : +{fallback_result['amount'] - ticket_data['stake']} ⭐ ({((fallback_result['amount'] - ticket_data['stake'])/ticket_data['stake']*100):+.0f}%)")
        print()
    except Exception as e:
        print(f"Erreur fallback : {e}")
        print()
    
    # Test 2 : Calcul du principal cashout avec facteurs par défaut
    print("📊 TEST 2 - CALCUL PRINCIPAL AVEC FACTEURS")
    print("-" * 30)
    
    try:
        # Facteurs typiques quand pas de données live
        factors = {
            "progress_factor": 0.0,  # 0/3 validés
            "time_factor": 0.8,
            "live_probability": 0.5,
            "risk_score": 0.5,
            "confidence": 50
        }
        
        principal_result = engine._calculate_cashout_offer(ticket_data, factors)
        print(f"Facteurs utilisés :")
        print(f"  - Progression : {factors['progress_factor']}")
        print(f"  - Temps : {factors['time_factor']}")
        print(f"  - Probabilité : {factors['live_probability']}")
        print(f"  - Risque : {factors['risk_score']}")
        print()
        print(f"Résultat principal : {principal_result['amount']} ⭐ ({principal_result['percentage']}%)")
        print(f"Bénéfice : +{principal_result['amount'] - ticket_data['stake']} ⭐ ({((principal_result['amount'] - ticket_data['stake'])/ticket_data['stake']*100):+.0f}%)")
        print()
    except Exception as e:
        print(f"Erreur principal : {e}")
        print()
    
    # Test 3 : Simulation du calcul complet
    print("📊 TEST 3 - SIMULATION CALCUL COMPLET")
    print("-" * 30)
    
    try:
        # Simuler le calcul manuellement
        stake = ticket_data["stake"]
        potential = ticket_data["potential_gain"]
        
        # Calcul du bonus de progression
        progress_bonus = (potential - stake) * 0.0 * 0.5 * 0.8 * (1 - 0.5)
        print(f"Progress bonus : (45-8) × 0.0 × 0.5 × 0.8 × 0.5 = {progress_bonus}")
        
        cashout = stake + progress_bonus
        print(f"Cashout brut : {stake} + {progress_bonus} = {cashout}")
        
        # Application des limites
        min_cashout = stake * 1.3
        max_cashout = potential * 0.8
        print(f"Limites : min={min_cashout}, max={max_cashout}")
        
        final_cashout = max(min_cashout, min(max_cashout, cashout))
        print(f"Cashout final : max({min_cashout}, min({max_cashout}, {cashout})) = {final_cashout}")
        
        print(f"Bénéfice final : +{final_cashout - stake} ⭐ ({((final_cashout - stake)/stake*100):+.0f}%)")
        print()
    except Exception as e:
        print(f"Erreur simulation : {e}")
        print()
    
    print("🎯 CONCLUSION")
    print("=" * 50)
    print("Le problème vient du fait que la progression est de 0% (0/3 validés)")
    print("Donc le bonus de progression est nul, et le cashout utilise seulement le minimum.")
    print("Solution : utiliser un calcul plus généreux même avec progression faible.")

if __name__ == "__main__":
    test_cashout_calculation()
