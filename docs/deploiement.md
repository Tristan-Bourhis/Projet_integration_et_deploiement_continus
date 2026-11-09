# Déploiement continu et infrastructure AWS

Les fichiers sont prêts pour les options 1 et 4 du niveau 3. La création de ressources AWS et le déploiement distant nécessitent ton compte, ta clé publique SSH et tes secrets GitHub. Ils ne sont pas exécutés lors de la préparation locale du projet.

## 1. Provisionner la VM avec Terraform

Prérequis : Terraform >= 1.6 et < 2, un compte AWS configuré via le profil ou les variables AWS habituelles, une paire de clés SSH. Ne pas placer la clé privée dans le dépôt.

```bash
cp infra/terraform.tfvars.example infra/terraform.tfvars
# Renseigner la clé PUBLIQUE et les CIDR d'accès SSH.
terraform -chdir=infra init
terraform -chdir=infra fmt -check
terraform -chdir=infra validate
terraform -chdir=infra plan -out=production.tfplan
terraform -chdir=infra apply production.tfplan
terraform -chdir=infra output
```

Ressources créées : VPC, sous-réseau public, route et passerelle Internet, groupe de sécurité SSH restreint, clé publique, VM Ubuntu 24.04 `t3.small`, disque racine chiffré de 30 Go et adresse IPv4 fixe. Cela engendre des frais AWS tant que les ressources existent. `terraform destroy` les supprime, données locales de la VM comprises.

Le bootstrap installe Docker/Compose, prépare `/opt/transaction-pipeline` et génère `.env` avec des secrets aléatoires. Les secrets sont créés sur la VM, pas injectés dans le state Terraform. Attendre la fin du bootstrap :

```bash
ssh ubuntu@<IP_VM> 'sudo cloud-init status --wait'
```

L'état Terraform local est ignoré par Git. Le conserver dans un emplacement sûr ; pour un travail en équipe, configurer un backend distant avec verrouillage avant de partager les opérations d'infrastructure.

## 2. Préparer le runner CD et SSH

Le groupe de sécurité n'ouvre pas SSH au monde entier. `ssh_allowed_cidrs` doit inclure l'IP de sortie du runner de déploiement ainsi que ton IP d'administration.

Pour une configuration stable, utiliser un runner GitHub avec IP de sortie fixe : runner hébergé adapté ou runner dédié dont le label est renseigné dans la variable GitHub `DEPLOY_RUNNER`. Les runners GitHub `ubuntu-latest` standard ont des IP variables ; la valeur par défaut ne suffit donc pas à joindre une VM restreinte sans configuration réseau supplémentaire. Les jobs de test restent sur les runners GitHub standards. Ne pas exécuter les pull requests sur le runner dédié de production.

Depuis un canal de confiance (console AWS ou connexion administrateur déjà vérifiée), relever la clé d'hôte SSH de la VM. Le secret `DEPLOY_KNOWN_HOSTS` doit contenir la ligne OpenSSH correspondante avec l'adresse de `DEPLOY_HOST`. La vérification de clé d'hôte reste activée pendant le déploiement.

Créer l'environnement GitHub **production**, puis ces secrets :

| Secret | Valeur |
|---|---|
| `DEPLOY_HOST` | IP fixe produite par Terraform |
| `DEPLOY_USER` | `ubuntu` |
| `DEPLOY_SSH_KEY` | Clé privée correspondant à la clé publique Terraform |
| `DEPLOY_KNOWN_HOSTS` | Clé d'hôte SSH vérifiée de la VM |

Créer les variables du dépôt :

- `DEPLOY_ENABLED` = `true` pour activer le déploiement automatique.
- `DEPLOY_RUNNER` = label du runner disposant de l'accès réseau autorisé (par défaut `ubuntu-latest`).

L'utilisateur Ubuntu peut utiliser Docker et sudo grâce au bootstrap/à l'image Ubuntu. Sa clé de déploiement donne donc un accès d'administration à cette VM pédagogique.

## 3. Déploiement après CI verte

À chaque push sur **main**, les trois jobs qualité, intégration et Terraform doivent réussir avant le CD. Celui-ci :

1. archive exactement le commit testé ;
2. transfère les sources via SSH avec vérification de l'hôte ;
3. construit le conteneur et démarre les services persistants ;
4. initialise le bucket et le schéma puis vérifie la base ;
5. installe et active le timer systemd.

Le job est sérialisé par GitHub Actions. Le script de déploiement utilise aussi `flock`, partagé avec le traitement périodique. Les volumes sont conservés lors du déploiement. Ce projet reconstruit l'image sur la VM à partir du commit validé ; il n'utilise pas de registre d'images privé.

Commandes de contrôle sur la VM :

```bash
cd /opt/transaction-pipeline
docker compose ps
sudo systemctl list-timers transaction-pipeline.timer
sudo journalctl -u transaction-pipeline.service -n 100 --no-pager
docker compose run --rm pipeline report
```

Le timer exécute `process --source s3` toutes les minutes après la fin du traitement précédent. Il ne réinsère pas les fichiers connus. En cas d'erreur, systemd conserve le statut et les logs ; le prochain déclenchement retente le traitement.

## 4. Alimenter le bucket

Pour initialiser les données de démonstration sur la VM :

```bash
cd /opt/transaction-pipeline
docker compose run --rm pipeline run --source s3
```

Pour de nouveaux CSV, utiliser un client compatible S3 avec les identifiants du `.env` de la VM et le bucket `transactions`. Le service S3 étant lié à l'interface locale, utiliser un tunnel SSH depuis le poste administrateur :

```bash
ssh -L 8333:127.0.0.1:8333 ubuntu@<IP_VM>
```

Le client S3 utilise alors `http://127.0.0.1:8333`, la région `us-east-1` et l'adressage path-style. Les fichiers doivent finir par `.csv` et respecter les colonnes du sujet. Le timer récupère automatiquement les nouveaux objets.

## 5. Exploitation et limites

Il s'agit d'un environnement de démonstration sur une seule VM. Prévoir une stratégie de sauvegarde PostgreSQL et S3 pour une utilisation durable. Les ressources AWS ne sont pas déployées automatiquement par la CI : l'infrastructure se crée via Terraform, puis le CD met à jour les conteneurs.

Pour revenir à une version précédente, pousser un revert sur `main` ; la CI reconstruit et redéploie cette version. Les modifications de schéma doivent être accompagnées de migrations avant une utilisation en production.
