# Fake News Detection & News Verification API

API FastAPI conçue pour le Hackathon Ambassade de France, dédiée à la détection de fausses informations, la collecte de nouvelles sur le web et les réseaux sociaux (Facebook), et la vérification automatisée de faits.

---

## 🚀 Fonctionnalités principales

1. **Authentification JWT complète**
   - Inscription (`/api/v1/auth/register`)
   - Connexion (`/api/v1/auth/login` et `/api/v1/auth/token` OAuth2 compatible Swagger UI)
   - Profil utilisateur connecté (`/api/v1/auth/me`)
   - Rôles : `admin`, `journalist`, `user`

2. **Module News (Collecte Web & Facebook)**
   - Collecte automatique de publications d'actualité depuis **Google (Web)** et **Facebook** via scraping (`/api/v1/news/collect`)
   - Ajout manuel d'articles par les journalistes (`POST /api/v1/news/`)
   - Liste paginée avec filtre par statut (`pending`, `verified`, `fake`, `unverified`)
   - Recherche plein texte dans les actualités stockées (`/api/v1/news/search?q=...`)
   - Gestion des statuts et suppression d'articles

3. **Module Verification (Fact-checking automatisé)**
   - Soumission d'une affirmation ou rumeur (`POST /api/v1/verification/verify`)
   - Scraping multi-sources en temps réel (Google Search + Facebook public)
   - Analyse de pertinence textuelle et détection de posture (confirmation vs démenti/fake news)
   - Attribution d'un **verdict** :
     - `likely_true` : Affirmation probablement vraie
     - `likely_false` : Affirmation probablement fausse / infox
     - `mixed` : Sources contradictoires / avis partagés
     - `insufficient_data` : Données insuffisantes pour trancher
   - Calcul d'un score de confiance (0.0 à 1.0) et résumé d'analyse en français
   - Historique individuel (`GET /api/v1/verification/`) et public (`GET /api/v1/verification/all`)
   - Détail d'une vérification avec toutes ses sources analysées (`GET /api/v1/verification/{id}`)

---

## 🛠️ Stack Technique

- **Framework** : FastAPI (Python 3.10+)
- **Base de données** : PostgreSQL avec SQLAlchemy (AsyncIO)
- **Migrations** : Alembic
- **Scraping** : httpx + BeautifulSoup4
- **Sécurité** : Passlib (bcrypt), PyJWT (HS256)
- **Serveur ASGI** : Uvicorn

---

## ⚙️ Installation & Démarrage

### 1. Prérequis
- Docker et Docker Compose (pour PostgreSQL)
- Python 3.10+

### 2. Démarrer les services
```bash
# Démarrer le conteneur PostgreSQL
make up-docker

# Créer le venv et installer les dépendances
make install

# Appliquer les migrations de base de données
make migrate

# Lancer le serveur avec rechargement automatique
make reload
```

L'API est accessible sur `http://localhost:8000`.  
La documentation interactive Swagger est disponible sur `http://localhost:8000/docs`.

---

## 📋 Endpoints de l'API

### 🔐 Authentification (`/api/v1/auth`)
| Méthode | Route | Description |
|---|---|---|
| `POST` | `/api/v1/auth/register` | Inscription d'un nouvel utilisateur |
| `POST` | `/api/v1/auth/login` | Connexion JSON (retourne le token JWT) |
| `POST` | `/api/v1/auth/token` | Connexion OAuth2 form (compatible Swagger) |
| `GET` | `/api/v1/auth/me` | Informations de l'utilisateur connecté |

### 📰 News (`/api/v1/news`)
| Méthode | Route | Description |
|---|---|---|
| `POST` | `/api/v1/news/collect` | Collecte des news depuis Google et Facebook |
| `POST` | `/api/v1/news/` | Création manuelle d'un article |
| `GET` | `/api/v1/news/` | Liste paginée des actualités collectées |
| `GET` | `/api/v1/news/search` | Recherche par mot-clé dans les news |
| `GET` | `/api/v1/news/{id}` | Détail d'une actualité |
| `PATCH` | `/api/v1/news/{id}/status` | Mise à jour du statut (`verified`, `fake`, etc.) |
| `DELETE` | `/api/v1/news/{id}` | Suppression d'un article |

### 🔍 Vérification (`/api/v1/verification`)
| Méthode | Route | Description |
|---|---|---|
| `POST` | `/api/v1/verification/verify` | Vérifier une affirmation (scrape Google + Facebook) |
| `GET` | `/api/v1/verification/` | Historique de mes vérifications |
| `GET` | `/api/v1/verification/all` | Historique public des vérifications |
| `GET` | `/api/v1/verification/{id}` | Détail d'une vérification avec sources |
| `DELETE` | `/api/v1/verification/{id}` | Supprimer une vérification |

---

## 🧪 Exemples d'utilisation (cURL)

### 1. Se connecter
```bash
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "journalist@example.com", "password": "Password123!"}' | jq -r .access_token)
```

### 2. Collecter des news sur Facebook & Google
```bash
curl -X POST http://localhost:8000/api/v1/news/collect \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Madagascar",
    "num_results": 5,
    "source": "all"
  }'
```

### 3. Vérifier une information
```bash
curl -X POST http://localhost:8000/api/v1/verification/verify \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "claim": "Madagascar est une île située dans l océan Indien"
  }'
```