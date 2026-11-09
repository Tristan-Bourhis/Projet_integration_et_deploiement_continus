# Vérifications réalisées

Vérification locale du 2 octobre 2026, avant liaison à un dépôt distant.

| Contrôle | Résultat |
|---|---|
| Ruff : règles et formatage | Réussi |
| Tests Python 3.14.4, sans services | 30 réussis ; couverture du package : 87 % |
| Tests Python 3.12.15 dans le conteneur | 30 réussis |
| Tests réels PostgreSQL 17.5 + SeaweedFS 3.85 | 3 réussis |
| Image Docker Python et dépendances verrouillées | Construction réussie |
| Exécution S3 → PostgreSQL avec deux pannes de lecture et deux pannes d'insertion | Réussie ; 12 transactions et 4 flags |
| Second passage Docker | 0 insertion, 2 fichiers ignorés ; toujours 12 transactions |
| Démonstration CSV invalide, correction, retry et rollback | Codes de sortie attendus vérifiés ; six captures PNG |
| GitHub Actions : actionlint 1.7.7 | Réussi |
| Terraform 1.11.4 : init sans backend, fmt, validate | Réussi ; provider AWS 5.100.0 verrouillé |
| Scripts Bash : contrôle syntaxique | Réussi |

Les tests PostgreSQL couvrent l'insertion, les trois regroupements exacts, les flags, le renommage de fichiers, la concurrence, le rollback et les retries. Les tests de services utilisent des buckets et des schémas temporaires pour ne pas supprimer les données applicatives.

Le correctif de concurrence a été vérifié sur PostgreSQL réel : `RETURNING` remplace une détection basée sur `rowcount`, qui n'est pas fiable avec tous les pilotes. SeaweedFS dispose de 100 emplacements de volumes et écoute explicitement sur toutes les interfaces internes au conteneur ; ses ports publics restent liés à 127.0.0.1 sur l'hôte.

**Non exécutés ici :** création de ressources AWS (`terraform apply`), accès à une VM distante, job CD et exécution GitHub Actions sur un dépôt distant. Ces étapes nécessitent la configuration personnelle décrite dans [le guide de déploiement](deploiement.md).
