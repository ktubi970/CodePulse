# CodePulse Local — sélection équilibrée de modèles

Date : 2026-07-27  
Statut : sélection approuvée

## Objectif

Ajouter localement dix modèles Ollama adaptés au benchmark CodePulse Local,
avec un compromis entre vitesse, diversité d’architecture et qualité sur une
RTX 2070 8 Gio. Aucun code, prompt, corpus ou résultat CodePulse ne doit être
envoyé pendant cette opération.

## Sélection approuvée

1. `qwen2.5-coder:0.5b`
2. `qwen2.5-coder:1.5b`
3. `qwen2.5-coder:3b`
4. `qwen2.5-coder:7b`
5. `deepseek-coder:1.3b`
6. `deepseek-coder:6.7b`
7. `starcoder2:3b`
8. `codegemma:2b`
9. `granite-code:3b`
10. `codellama:7b`

La sélection forme deux échelles de taille comparables, Qwen et DeepSeek, et
quatre références d’autres familles. Le volume estimé est de 22 à 26 Go,
compatible avec les quelque 188 Go libres observés sur le volume D:.

## Procédure

1. Démarrer directement `ollama serve` sur `127.0.0.1:11434`, avec historique
   et fonctions cloud désactivés.
2. Interroger l’inventaire local avant toute mutation.
3. Marquer comme déjà présents les tags exacts trouvés dans l’inventaire.
4. Exécuter séquentiellement `ollama pull <tag>` pour chaque tag manquant.
5. Arrêter au premier tag inexistant ou au premier échec non transitoire.
6. Ne jamais substituer silencieusement un autre tag ou une autre taille.
7. Réinventorier les modèles et rapporter, pour chaque candidat, le statut
   présent, téléchargé ou échoué.
8. Arrêter le serveur Ollama démarré pour l’opération.

Les pulls contactent nécessairement le registre de modèles configuré par
Ollama et téléchargent uniquement des manifests et des poids. Ils n’envoient
aucun fichier du projet CodePulse. Aucun modèle ne sera lancé en inférence
pendant cette opération.

## Hors périmètre

- modification de `codepulse.toml` ;
- lancement d’un benchmark ;
- suppression ou remplacement de modèles existants ;
- publication Git ou service externe autre que le registre requis par
  `ollama pull`.

## Critères de réussite

- les dix tags exacts sont présents après l’opération, ou l’échec du premier
  tag bloquant est rapporté sans substitution ;
- aucun pull n’est exécuté pour un tag déjà présent ;
- aucun processus Ollama démarré pour l’opération ne subsiste à la fin ;
- le détail des téléchargements et l’inventaire final sont fournis à
  l’utilisateur.
