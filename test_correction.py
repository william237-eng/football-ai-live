#!/usr/bin/env python3
"""
test_correction.py
==================
Test de la correction du Smart Cashout pour progression faible.
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
        return None
    
    def get_fixture_events(self, fixture_id):
        return None
    
    def get_fixture_statistics(self, fixture_id):
        return None

def test_correction():
    """Test que la correction fonctionne correctement."""
    print("🧪 TEST DE LA CORRECTION SMART CASHOUT")
    print("=" * 50)
    
    # Créer le moteur avec API mock
    api = MockAPI()
    engine = SmartCashoutEngine(api)
    
    # Simuler les données du ticket #7
    ticket_data = {
        "ticket_id": 7,
        "stake": 8,
        "potential_gain": 45,
        "status": "ACTIVE",
        "total_events": 3,
        "validated_events": 0,
        "won_events": 0,
        "lost_events": 0,
        "pending_events": 3,
        "total_odds": 5.625
    }
    
    print(f"Test du ticket #{ticket_data['ticket_id']}:")
    print(f"  - Mise : {ticket_data['stake']} ⭐")
    print(f"  - Gain potentiel : {ticket_data['potential_gain']} ⭐")
    print(f"  - Progression : {ticket_data['validated_events']}/{ticket_data['total_events']} ({ticket_data['validated_events']/ticket_data['total_events']*100:.0f}%)")
    print()
    
    # Test du calcul complet avec la correction
    print("📊 TEST DU CALCUL COMPLET AVEC CORRECTION")
    print("-" * 40)
    
    try:
        # Simuler la fonction calculate_smart_cashout
        result = engine.calculate_smart_cashout(ticket_data['ticket_id'])
        
        if result.get("available"):
            cashout = result["cashout_offer"]
            percentage = result["cashout_percentage"]
            benefit = cashout - ticket_data["stake"]
            benefit_pct = (benefit / ticket_data["stake"]) * 100
            
            print(f"✅ Cashout proposé : {cashout} ⭐ ({percentage}%)")
            print(f"✅ Bénéfice : +{benefit} ⭐ ({benefit_pct:+.0f}%)")
            print(f"✅ Fallback utilisé : {result.get('fallback_used', False)}")
            
            if benefit >= 10:  # Au moins 10⭐ de bénéfice
                print("🎉 CORRECTION RÉUSSIE - Bénéfice généreux !")
            else:
                print("❌ CORRECTION ÉCHOUÉE - Bénéfice encore faible")
        else:
            print(f"❌ Cashout indisponible : {result.get('reason', 'Erreur')}")
            
    except Exception as e:
        print(f"❌ Erreur lors du test : {e}")
    
    print()
    print("🎯 ATTENDU :")
    print("  - Cashout : ~22 ⭐")
    print("  - Bénéfice : +14 ⭐ (+175%)")
    print("  - Fallback utilisé : True")

if __name__ == "__main__":
    test_correction()
