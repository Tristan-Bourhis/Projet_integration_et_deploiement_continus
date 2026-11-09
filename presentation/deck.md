---
marp: true
theme: integration
paginate: true
size: 16:9
title: "Transaction Pipeline — intégration et déploiement continus"
description: "Présentation du projet Transaction Pipeline"
author: "Projet CI/CD"
footer: "Transaction Pipeline · Projet CI/CD"
---

<!-- _class: title -->
<!-- _paginate: false -->
<!-- _footer: "" -->

# Transaction Pipeline

## Intégration et déploiement continus d'une pipeline de transactions

<div class="title-meta">Projet CI/CD · Novembre 2026</div>

---

# Objectif et architecture

<div class="pipeline">
  <div><b>CSV</b><span>Transactions synthétiques</span></div>
  <i>→</i>
  <div><b>Stockage S3</b><span>SeaweedFS</span></div>
  <i>→</i>
  <div class="engine"><b>Pipeline Python</b><span>Validation et calculs</span></div>
  <i>→</i>
  <div><b>PostgreSQL</b><span>Transactions et agrégats</span></div>
</div>

<div class="plain-explanation good">Le traitement lit les fichiers depuis S3 et enregistre les résultats en base.</div>

---

# Traitement des données

<div class="why-grid">
  <div><b>Validation</b><span>Colonnes, dates, montants et IBAN.</span></div>
  <div><b>Calculs</b><span>Totaux par compte et par banque ; signalement des montants supérieurs à 5 000 €.</span></div>
</div>

<div class="metric-row three">
  <div class="metric"><strong>2</strong><span>fichiers CSV</span></div>
  <div class="metric"><strong>12</strong><span>transactions</span></div>
  <div class="metric accent"><strong>4</strong><span>transactions signalées</span></div>
</div>

<!-- Données déterministes : montant total attendu 33 000,64 €. -->

---

# Fiabilité du traitement

<div class="three-columns">
  <div><b>Sans doublon</b><span>Une empreinte SHA-256 identifie chaque fichier déjà traité.</span></div>
  <div><b>Écriture atomique</b><span>En cas d'échec, les écritures du fichier sont annulées.</span></div>
  <div><b>Retries limités</b><span>Les erreurs temporaires de stockage ou de base sont réessayées.</span></div>
</div>

<div class="plain-explanation good">Au second passage : 0 insertion et 2 fichiers ignorés.</div>

---

# Intégration continue

<div class="three-columns">
  <div><b>Qualité</b><span>Formatage et tests Python 3.12 / 3.14.</span></div>
  <div><b>Intégration</b><span>Tests avec PostgreSQL et S3, y compris les pannes simulées.</span></div>
  <div><b>Infrastructure</b><span>Validation du code Terraform.</span></div>
</div>

<div class="plain-explanation">Une modification volontaire du seuil de 5 000 € a fait échouer la CI. Après correction, les contrôles sont repassés au vert.</div>

<!-- Preuves : docs/demonstration.md et docs/captures/ci-echec.png, ci-correction.png. -->

---

# Déploiement : état actuel

<div class="choice-list taken">
  <div><b>✓</b><strong>Préparé</strong><span>Conteneurs Docker, script de déploiement et traitement planifié sur VM.</span></div>
  <div><b>✓</b><strong>Validé</strong><span>Configuration Terraform vérifiée par la CI.</span></div>
</div>

<div class="choice-list open">
  <div><b>→</b><strong>À configurer</strong><span>Ressources AWS, accès à la VM et secrets GitHub pour activer le déploiement automatique.</span></div>
</div>

<!-- Le job deploy est ignoré tant que DEPLOY_ENABLED n'est pas activé. Voir docs/deploiement.md et docs/verification.md. -->

---

<!-- _class: closing -->
<!-- _paginate: false -->
<!-- _footer: "" -->

# Merci pour votre attention.
