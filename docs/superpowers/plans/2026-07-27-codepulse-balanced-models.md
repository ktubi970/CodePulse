# CodePulse Balanced Models Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Télécharger dans Ollama les dix tags de modèles équilibrés approuvés, sans doublon, substitution ou lancement de benchmark.

**Architecture:** Un serveur Ollama direct écoute uniquement sur loopback. Un inventaire préalable sépare les tags présents des tags manquants, puis les pulls manquants sont exécutés séquentiellement et s’arrêtent au premier échec. Un inventaire final et l’arrêt du serveur fournissent les preuves de réussite et de confinement.

**Tech Stack:** Ollama 0.30.6, PowerShell, API HTTP loopback de CodePulse Local.

## Global Constraints

- Candidats exacts : `qwen2.5-coder:0.5b`, `qwen2.5-coder:1.5b`, `qwen2.5-coder:3b`, `qwen2.5-coder:7b`, `deepseek-coder:1.3b`, `deepseek-coder:6.7b`, `starcoder2:3b`, `codegemma:2b`, `granite-code:3b`, `codellama:7b`.
- Exécuter uniquement les pulls des tags absents de l’inventaire préalable.
- Exécuter les pulls séquentiellement et arrêter au premier échec non transitoire.
- Ne substituer aucun tag, modèle ou format.
- Ne modifier ni `codepulse.toml`, ni le corpus, ni les résultats.
- Ne lancer aucune inférence ou campagne de benchmark.
- Le seul service externe autorisé est le registre nécessaire à `ollama pull`.
- Aucun code, prompt, corpus ou résultat CodePulse ne doit être envoyé.

---

### Task 1: Préflight local et inventaire

**Files:**
- Read: `D:\projet\fin\codepulse-local\codepulse.toml`
- Modify: aucun

**Interfaces:**
- Consumes: exécutable `C:\Users\ktubi\AppData\Local\Programs\Ollama\ollama.exe`, port local 11434, volume D:.
- Produces: serveur local prêt, version Ollama, inventaire exact des tags présents et liste des candidats manquants.

- [ ] **Step 1: Vérifier la capacité et l’absence de serveur résiduel**

Run:

```powershell
Get-PSDrive -Name D | Select-Object Name,Used,Free
Get-NetTCPConnection -LocalPort 11434 -State Listen -ErrorAction SilentlyContinue
Get-Process -Name "ollama*","llama-server" -ErrorAction SilentlyContinue
```

Expected: au moins 30 Go libres ; aucune écoute résiduelle sur 11434. Si un
serveur appartenant à l’utilisateur existe, ne pas l’arrêter et demander une
décision.

- [ ] **Step 2: Démarrer Ollama directement en mode local**

Run in a long-lived terminal:

```powershell
$env:OLLAMA_NO_CLOUD = "true"
$env:OLLAMA_NOHISTORY = "true"
$env:OLLAMA_HOST = "http://127.0.0.1:11434"
& "C:\Users\ktubi\AppData\Local\Programs\Ollama\ollama.exe" serve
```

Expected:

```text
Ollama cloud disabled: true
Listening on 127.0.0.1:11434
```

- [ ] **Step 3: Réinventorier les modèles via CodePulse**

Run:

```powershell
Set-Location D:\projet\fin\codepulse-local
python -m runner.cli list-models
```

Expected: sortie locale de `/api/tags` et aucun téléchargement. Comparer les
tags exacts, sans considérer un alias ou une autre taille comme équivalent.

### Task 2: Pulls séquentiels des seuls tags manquants

**Files:**
- Modify: magasin de modèles Ollama configuré sur `D:\model_ia`
- Modify: aucun fichier CodePulse

**Interfaces:**
- Consumes: liste des tags manquants produite par Task 1.
- Produces: pour chaque candidat, statut `déjà présent`, `téléchargé` ou `échec`.

- [ ] **Step 1: Puller les quatre Qwen Coder manquants, un par un**

Run each command only if its exact tag is absent:

```powershell
ollama pull qwen2.5-coder:0.5b
ollama pull qwen2.5-coder:1.5b
ollama pull qwen2.5-coder:3b
ollama pull qwen2.5-coder:7b
```

Expected after each command: exit code 0 and a completed manifest. On the first
failure, stop and preserve the output verbatim.

- [ ] **Step 2: Puller les deux DeepSeek Coder manquants, un par un**

Run each command only if execution has not stopped:

```powershell
ollama pull deepseek-coder:1.3b
ollama pull deepseek-coder:6.7b
```

Expected after each command: exit code 0. Stop on first failure.

- [ ] **Step 3: Puller les quatre familles complémentaires, une par une**

Run each command only if execution has not stopped:

```powershell
ollama pull starcoder2:3b
ollama pull codegemma:2b
ollama pull granite-code:3b
ollama pull codellama:7b
```

Expected after each command: exit code 0. Stop on first failure. Ne jamais
essayer une autre taille ou un autre namespace sans nouvelle approbation.

### Task 3: Inventaire final, confinement et rapport

**Files:**
- Read: inventaire Ollama local
- Modify: aucun fichier CodePulse

**Interfaces:**
- Consumes: statuts de Task 2 et serveur Ollama actif.
- Produces: preuve finale des tags présents, capacité disque restante et arrêt du serveur.

- [ ] **Step 1: Vérifier les tags exacts et l’espace restant**

Run:

```powershell
Set-Location D:\projet\fin\codepulse-local
python -m runner.cli list-models
Get-PSDrive -Name D | Select-Object Name,Used,Free
```

Expected: les dix tags approuvés apparaissent exactement si tous les pulls ont
réussi. Sinon, l’inventaire s’arrête au dernier tag réussi et correspond au
journal de pulls.

- [ ] **Step 2: Arrêter le serveur démarré pour l’opération**

Send `Ctrl+C` to the long-lived `ollama serve` terminal, then run:

```powershell
Get-NetTCPConnection -LocalPort 11434 -State Listen -ErrorAction SilentlyContinue
Get-Process -Name "ollama*","llama-server" -ErrorAction SilentlyContinue
```

Expected: aucune écoute et aucun processus démarré pour cette opération.

- [ ] **Step 3: Rapporter les preuves**

Report:

```text
- inventaire préalable et candidats manquants ;
- statut individuel des dix tags ;
- octets libres avant et après ;
- premier échec exact, le cas échéant ;
- confirmation qu’aucune inférence et aucune modification CodePulse n’ont eu lieu ;
- confirmation de l’arrêt du serveur.
```
