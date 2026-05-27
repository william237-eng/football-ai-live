# ⚽ Predict IA Football Live

Application de prédiction football en temps réel avec IA, basée sur les données de l'API-Football.

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://your-app-name.streamlit.app/)

## 🎯 Fonctionnalités

- **📊 Matchs en direct** : Suivi en temps réel des matchs avec statistiques live
- **📅 Matchs futurs** : Planning des prochains matchs avec filtres
- **🤖 Analyse IA** : Prédictions intelligentes basées sur :
  - Forme récente des équipes
  - Système de rating Elo
  - Distribution de Poisson pour les scores
  - Contexte live (momentum, pression, cartons)
- **🔥 Suggestions de paris** : Recommandations intelligentes avec niveau de confiance
- **🎨 Thèmes premium** : Dark Pro, Light Pro, Blue Sky (type Sofascore/OneFootball)
- **🔍 Recherche** : Filtrage par équipe, compétition, pays
- **📱 Responsive** : Optimisé mobile, tablette, desktop, ultra-wide

## 🚀 Installation locale

### Prérequis
- Python 3.10+
- Clé API-Football ([Inscription gratuite](https://www.api-football.com/))

### Étape 1 : Cloner le projet

```bash
git clone https://github.com/username/predict-ia-football.git
cd predict-ia-football
```

### Étape 2 : Créer l'environnement virtuel

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS/Linux
source venv/bin/activate
```

### Étape 3 : Installer les dépendances

```bash
pip install -r requirements.txt
```

### Étape 4 : Configuration API

Créer un fichier `.env` à la racine :

```env
API_KEY=votre_cle_api_football
API_URL=https://v3.football.api-sports.io
```

### Étape 5 : Lancer l'application

```bash
streamlit run app.py
```

L'application sera accessible sur http://localhost:8501

## ☁️ Déploiement Streamlit Cloud

### Étape 1 : Pousser sur GitHub

```bash
git add .
git commit -m "Initial commit"
git push origin main
```

### Étape 2 : Connecter à Streamlit Cloud

1. Rendez-vous sur [share.streamlit.io](https://share.streamlit.io/)
2. Connectez-vous avec votre compte GitHub
3. Cliquez sur "New app"
4. Sélectionnez votre dépôt GitHub
5. Main file path : `app.py`

### Étape 3 : Configurer les secrets

1. Dans l'interface Streamlit Cloud, allez dans "Settings" → "Secrets"
2. Ajoutez vos secrets :

```toml
API_KEY = "votre_cle_api_football"
API_URL = "https://v3.football.api-sports.io"
```

Ou créez un fichier `.streamlit/secrets.toml` (ne le poussez pas sur GitHub !)

### Étape 4 : Déployer

Cliquez sur "Deploy" et patientez quelques minutes.

## 🏗️ Architecture

```
predict-ia-football/
├── app.py                      # Point d'entrée Streamlit
├── components/                 # Composants UI
│   ├── analysis_dashboard.py  # Dashboard d'analyse IA
│   ├── header.py              # Header avec recherche
│   ├── sidebar.py             # Navigation latérale
│   └── health_check.py        # Vérification système
├── ai_engine/                  # Moteurs IA
│   ├── bet_suggestion_engine.py
│   ├── elo_rating.py
│   ├── form_analyzer.py
│   ├── live_context_engine.py
│   ├── poisson_engine.py
│   ├── probability_engine.py
│   └── smart_stats_fallback.py
├── services/                   # Services API
│   ├── football_api.py        # Client API-Football
│   ├── live_matches.py        # Parsing matchs live
│   └── future_matches.py      # Parsing matchs futurs
├── utils/                      # Utilitaires
│   └── theme_manager.py       # Gestion des thèmes
├── styles/                     # CSS personnalisé
│   └── style.css
├── .streamlit/                 # Configuration Streamlit
│   └── config.toml
├── .gitignore                  # Fichiers à ignorer
├── requirements.txt            # Dépendances
└── README.md                   # Documentation
```

## 🔧 Configuration avancée

### Thèmes disponibles

- **🌙 Dark Pro** : Thème sombre premium (défaut)
- **☀️ Light Pro** : Thème clair professionnel
- **🌤️ Blue Sky** : Thème bleu moderne

Les thèmes sont accessibles via le sélecteur dans l'interface.

### Cache et performance

L'application utilise le cache Streamlit pour optimiser les performances :
- Matchs live : cache 15 secondes
- Matchs futurs : cache 120 secondes
- Analyses : cache 60 secondes

### Variables d'environnement

| Variable | Description | Requis |
|----------|-------------|--------|
| `API_KEY` | Clé API-Football | ✅ |
| `API_URL` | URL de l'API | ✅ |
| `API_PROVIDER` | Fournisseur API (optionnel) | ❌ |

## 🛡️ Sécurité

- **Ne jamais** commiter le fichier `.env` ou `.streamlit/secrets.toml`
- Les clés API sont masquées dans l'interface
- Le fichier `.gitignore` est configuré pour exclure les fichiers sensibles

## 🔍 Health Check

Un health check est disponible pour vérifier :
- ✅ Connexion API
- ✅ Latence
- ✅ Configuration

Accès : intégré dans l'interface via le composant d'état.

## 🐛 Dépannage

### Erreur "API_KEY ou API_URL manquant"
- Vérifiez votre fichier `.env` en local
- Vérifiez vos secrets sur Streamlit Cloud
- Redémarrez l'application après modification

### Erreur "Limite API atteinte"
- Le plan gratuit API-Football permet 100 requêtes/jour
- Attendez le renouvellement ou passez à un plan payant

### Problèmes de cache
```bash
# Supprimer le cache Streamlit
rm -rf .streamlit/cache
```

## 📈 Limitations du plan gratuit API-Football

- 100 requêtes/jour
- Mise à jour toutes les heures pour les données live
- Pas d'accès aux données historiques complètes

## 🤝 Contribution

Les contributions sont les bienvenues !

1. Fork le projet
2. Créez une branche (`git checkout -b feature/AmazingFeature`)
3. Committez vos changements (`git commit -m 'Add some AmazingFeature'`)
4. Poussez vers la branche (`git push origin feature/AmazingFeature`)
5. Ouvrez une Pull Request

## 📝 License

Ce projet est sous licence MIT. Voir le fichier `LICENSE` pour plus de détails.

## 🙏 Remerciements

- [API-Football](https://www.api-football.com/) pour les données
- [Streamlit](https://streamlit.io/) pour le framework
- Communauté open source pour les outils Python

---

**Made ❤️by William Eng🧑‍💻

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://your-app-name.streamlit.app/)
