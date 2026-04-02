# # NetQoE — Analyseur QoS / QoE

## Description

NetQoE est une application web moderne pour mesurer la **Qualité de Service (QoS)** réseau (latence, jitter, perte de paquets, débit) et la transformer en **Qualité d'Expérience (QoE)** pour différents usages (VoIP, vidéo, gaming). Elle combine des mesures réelles avec un simulateur interactif pour démontrer comment les métriques réseau objectives affectent la satisfaction utilisateur.

L'application utilise Flask pour le backend, SQLite pour le stockage, et une interface web responsive avec thème sombre.

## Prérequis

- Python 3.7 ou supérieur
- Connexion internet (pour les mesures réelles ; mode démo disponible pour tester sans réseau)
- Navigateur web moderne

## Installation

1. **Cloner ou télécharger le projet** dans un dossier de votre choix.

2. **Créer un environnement virtuel** (recommandé pour isoler les dépendances) :
   ```
   python -m venv venv
   ```

3. **Activer l'environnement virtuel** :
   - Sur Windows : `venv\Scripts\activate`
   - Sur Linux/macOS : `source venv/bin/activate`

4. **Installer les dépendances** :
   ```
   pip install -r requirements.txt
   ```

## Utilisation

1. **Lancer l'application** :
   ```
   python app.py
   ```

2. **Accéder à l'interface** :
   Ouvrez votre navigateur et allez à `http://localhost:5000`.



## Fonctionnalités

- **Dashboard** : Vue d'ensemble des dernières mesures avec graphiques en temps réel.
- **Simulateur** : Testez différents scénarios réseau avec des curseurs interactifs (latence, jitter, perte, débit).
- **Historique** : Consultez les 50 dernières mesures stockées.
- **QoS vs QoE** : Informations éducatives sur les différences entre QoS et QoE.

L'application mesure automatiquement la latence, le jitter, la perte de paquets et le débit, puis calcule des scores QoE sur une échelle de 1 à 5.

## Notes

- Les mesures réelles peuvent prendre 5-35 secondes selon la connexion.
- La base de données `database.db` stocke automatiquement les mesures.
- Pour arrêter l'application, utilisez Ctrl+C dans le terminal.

Si vous rencontrez des problèmes, assurez-vous que Python et pip sont correctement installés.
