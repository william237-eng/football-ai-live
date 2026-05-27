"""
Health Check Component
Vérifie l'état de l'application et de l'API
"""
import time
from datetime import datetime
from typing import Dict, Any, Optional

import streamlit as st
import requests

from services.football_api import FootballAPI, ConfigError, APIError, NetworkError


def check_api_status() -> Dict[str, Any]:
    """
    Vérifie le statut de l'API Football
    """
    result = {
        "status": "unknown",
        "message": "",
        "latency_ms": None,
        "timestamp": datetime.now().isoformat(),
    }
    
    try:
        api = FootballAPI()
        
        if not api.is_configured():
            result["status"] = "not_configured"
            result["message"] = "API_KEY ou API_URL non configurés"
            return result
        
        # Test simple: récupérer les timezones (endpoint léger)
        start_time = time.time()
        response = api.session.get(
            f"{api.api_url}/timezone",
            timeout=5
        )
        latency = (time.time() - start_time) * 1000
        
        result["latency_ms"] = round(latency, 2)
        
        if response.status_code == 200:
            result["status"] = "healthy"
            result["message"] = f"API opérationnelle ({latency:.0f}ms)"
        elif response.status_code == 429:
            result["status"] = "rate_limited"
            result["message"] = "Limite de requêtes atteinte"
        else:
            result["status"] = "error"
            result["message"] = f"Erreur HTTP {response.status_code}"
            
    except ConfigError as e:
        result["status"] = "not_configured"
        result["message"] = str(e)
    except NetworkError:
        result["status"] = "network_error"
        result["message"] = "Erreur réseau"
    except requests.exceptions.Timeout:
        result["status"] = "timeout"
        result["message"] = "Délai d'attente dépassé"
    except Exception as e:
        result["status"] = "error"
        result["message"] = f"Erreur: {str(e)}"
    
    return result


def check_app_health() -> Dict[str, Any]:
    """
    Vérifie l'état général de l'application
    """
    checks = {
        "api": check_api_status(),
        "app": {
            "status": "healthy",
            "message": "Application opérationnelle",
            "timestamp": datetime.now().isoformat(),
        }
    }
    
    # Déterminer le statut global
    api_status = checks["api"]["status"]
    if api_status == "healthy":
        checks["overall"] = "healthy"
    elif api_status in ["not_configured", "rate_limited"]:
        checks["overall"] = "degraded"
    else:
        checks["overall"] = "unhealthy"
    
    return checks


def render_health_check():
    """
    Affiche le health check dans Streamlit
    """
    st.markdown("### 🏥 État du système")
    
    with st.spinner("Vérification en cours..."):
        health = check_app_health()
    
    # Affichage du statut global
    overall = health.get("overall", "unknown")
    if overall == "healthy":
        st.success("✅ Système opérationnel")
    elif overall == "degraded":
        st.warning("⚠️ Système partiellement dégradé")
    else:
        st.error("❌ Problème système détecté")
    
    # Détails API
    api = health.get("api", {})
    col1, col2 = st.columns(2)
    
    with col1:
        status = api.get("status", "unknown")
        if status == "healthy":
            st.metric("Statut API", "🟢 OK")
        elif status == "rate_limited":
            st.metric("Statut API", "🟡 Limité")
        elif status == "not_configured":
            st.metric("Statut API", "⚪ Non config")
        else:
            st.metric("Statut API", "🔴 Erreur")
    
    with col2:
        latency = api.get("latency_ms")
        if latency:
            st.metric("Latence API", f"{latency:.0f} ms")
        else:
            st.metric("Latence API", "N/A")
    
    # Message détaillé
    message = api.get("message", "")
    if message:
        st.caption(message)
    
    # Timestamp
    st.caption(f"Dernière vérification: {health.get('app', {}).get('timestamp', 'N/A')}")


def render_api_config_guide():
    """
    Affiche un guide de configuration de l'API
    """
    st.markdown("### 🔧 Configuration API")
    
    st.info("""
    **Configuration requise pour l'API-Football:**
    
    **Option 1 - Local (.env):**
    ```
    API_KEY=votre_cle_api
    API_URL=https://v3.football.api-sports.io
    ```
    
    **Option 2 - Streamlit Cloud (secrets):**
    Dans `.streamlit/secrets.toml`:
    ```toml
    API_KEY = "votre_cle_api"
    API_URL = "https://v3.football.api-sports.io"
    ```
    
    Obtenez une clé API gratuite sur: https://www.api-football.com/
    """)
