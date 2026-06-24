# Backlog FINARY Dashboard

---

## Pilotage budgétaire par catégorie

**Idée :** Savoir exactement combien on dépense par catégorie — ce mois-ci, les mois précédents, avec un objectif d'épargne à atteindre.

**Ce que ça couvrirait :**
- Vue mensuelle par catégorie : alimentation, transport, loisirs, shopping, etc.
- Historique mois par mois (graphe ou tableau)
- Budget cible par catégorie (ex: alimentation < 400€/mois)
- Écart entre réel et cible : vert si sous le budget, rouge si dépassé
- Objectif d'épargne global mensuel : montant visé vs montant réel
- Potentiellement : projection fin de mois basée sur le rythme actuel

**Questions à affiner :**
- Est-ce que les budgets cibles sont fixes ou glissants (moyenne des 3 derniers mois) ?
- Jérémy et Manon ont-ils des budgets séparés ou un budget commun unique ?
- Affichage dans le dashboard existant (nouvel onglet) ou page dédiée ?

---

## Robustesse envoi mail

**Idée :** L'envoi du rapport hebdo doit être fiable même en cas d'erreur réseau ou SMTP.

**Ce que ça couvrirait :**
- Retry automatique en cas d'échec SMTP (3 tentatives avec backoff)
- Notification en cas d'échec persistant (log clair + peut-être un mail de fallback)
- Test d'envoi à la demande depuis le dashboard (`/report/send`)
- Historique des envois (date, statut, destinataire) dans Google Sheets ou logs

---

## VPS + N8N

**Idée :** Déployer l'app sur un VPS et orchestrer les automatisations avec N8N au lieu d'APScheduler.

**Ce que ça couvrirait :**
- Hébergement VPS (Hetzner, OVH, DigitalOcean…) pour que l'app tourne 24/7 sans dépendre du Mac
- N8N pour remplacer ou compléter APScheduler : déclencheurs visuels, webhooks, intégrations tierces
- Possibilité de brancher d'autres sources de données dans N8N (Notion, Google Sheets, Airtable…)
- HTTPS via Caddy ou Nginx + Let's Encrypt

**Questions à affiner :**
- N8N self-hosted sur le même VPS ou N8N Cloud ?
- Garder APScheduler en fallback ou tout migrer vers N8N ?
- Docker Compose pour tout orchestrer ?
