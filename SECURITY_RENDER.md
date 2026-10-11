# Déploiement sécurisé FB PACK sur Render

## 1. Variables obligatoires

Dans **Render > Web Service > Environment**, configurez :

- `SECRET_KEY` : clé aléatoire longue, différente de toute ancienne clé exposée.
- `DJANGO_DEBUG=False`
- `ALLOWED_HOSTS=votre-service.onrender.com,votre-domaine.com`
- `CSRF_TRUSTED_ORIGINS=https://votre-service.onrender.com,https://votre-domaine.com`
- `ADMIN_URL=gestion-securisee-fbpack/` (choisissez une valeur difficile à deviner)
- `TIME_ZONE=Africa/Algiers`

Render fournit normalement `RENDER`, `RENDER_EXTERNAL_HOSTNAME` et `DATABASE_URL`.

Pour générer une clé sur votre ordinateur :

```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

Ne publiez jamais cette valeur.

## 2. Vérification avant déploiement

```bash
python manage.py check
python manage.py check --deploy
python manage.py migrate
python manage.py collectstatic --noinput
```

Lisez chaque avertissement de `check --deploy` avant la mise en production.

## 3. Changements importants

- Après cinq échecs pour un couple IP/identifiant, connexion bloquée 15 minutes.
- Après vingt échecs depuis une IP, cette IP est bloquée 15 minutes.
- Une seule instance Gunicorn est utilisée avec quatre threads afin que le limiteur léger reste cohérent. En cas d'autoscaling, utilisez Redis comme cache partagé avant d'ajouter des instances.
- Les sessions expirent à la fermeture du navigateur ou après huit heures.
- HTTPS, cookies sécurisés et HSTS sont activés sur Render.
- Les requêtes supérieures à 25 Mo sont refusées.
- L'export total de la base n'accepte plus `SECRET_KEY` dans l'URL. Il exige un superutilisateur connecté.
- Les opérations administratives de modification exigent POST et CSRF.

## 4. Sauvegardes

- Activez les sauvegardes PostgreSQL Render.
- Téléchargez périodiquement une sauvegarde chiffrée.
- Testez la restauration dans un environnement isolé.
- Ne laissez jamais les sauvegardes JSON dans Git ou dans un répertoire public.

## 5. Après installation

1. Changez les mots de passe faibles.
2. Désactivez les comptes inutilisés.
3. Réservez `is_staff` et `is_superuser` à très peu de personnes.
4. Examinez régulièrement les logs `login_failed`, `login_locked` et `login_success` dans Render.
5. N'envoyez jamais `SECRET_KEY`, `DATABASE_URL` ou un cookie dans une conversation ou une capture d'écran.

## 6. Limite connue

Le projet charge actuellement Tailwind et Chart.js depuis des CDN et contient plusieurs scripts intégrés aux templates. Une politique CSP extrêmement stricte casserait l'interface actuelle. La prochaine étape recommandée consiste à compiler Tailwind localement, héberger Chart.js dans `static/`, déplacer les scripts dans des fichiers statiques, puis activer une CSP avec nonce sans `unsafe-inline`.
