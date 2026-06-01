#!/usr/bin/env python3
"""
credit_user_points.py
====================
Script pour créditer 10 points à l'utilisateur pour le ticket vendu par erreur.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from modules.betting.points_manager import credit_points, get_points_info

def credit_user():
    """Crédite 10 points à l'utilisateur par défaut."""
    try:
        # Obtenir le solde actuel
        current_balance = get_points_info(1)["points"]
        
        # Ajouter 10 points à l'utilisateur par défaut (ID: 1)
        new_balance = credit_points(1, 10)
        
        print(f"✅ 10 points crédités avec succès !")
        print(f"   Ancien solde : {current_balance} ⭐")
        print(f"   Nouveau solde : {new_balance} ⭐")
        print(f"   Raison : Remboursement ticket vendu par erreur")
        return True
            
    except Exception as e:
        print(f"❌ Erreur système lors du crédit des points : {e}")
        return False

if __name__ == "__main__":
    print("💰 CRÉDIT DE POINTS UTILISATEUR")
    print("=" * 40)
    success = credit_user()
    
    if success:
        print("\n🎉 Opération réussie ! L'utilisateur a été crédité de 10 points.")
    else:
        print("\n❌ Opération échouée. Vérifiez les logs.")
