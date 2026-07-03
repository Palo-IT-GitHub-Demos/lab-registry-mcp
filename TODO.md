# TODO — Lab Registry Server

> Critère de succès obligatoire : test croisé Claude Code + Copilot agent mode sur le même serveur.
> Légende : ✅ fait · ⚠️ partiel · [ ] à faire · 🔴 bloquant · 🟡 moyen · 🟢 faible

---

## Jour 2 — Connexion Claude Code + test en conditions réelles ✅

### Setup
- ✅ Initialiser le repo git (`git init`, premier commit)
- ✅ Config Claude Code dans `~/.claude/settings.json` (user-level, non commité)
- ✅ Config Copilot dans `gen-e2-marketplace/.vscode/mcp.json` (gitignored)
- ✅ Serveur démarre avec le vrai registry — 60 artefacts chargés

### Tests — couverts par test_e2e.py (10 tests, 50/50 au total)
- ✅ `list_entries` → 60 entrées
- ✅ `list_entries type=skill` → 40 skills
- ✅ `list_entries plugin=android` → 14+ artefacts android
- ✅ `search_entries query=architecture` → résultats cohérents
- ✅ `get_entry` → `content_raw` non vide + metadata parsé
- ✅ `get_plugin plugin=research-suite` → version 1.0.1 + 2 skills
- ✅ `check_compliance` → distingue à jour / obsolète
- ✅ `list_entries tags=inexistant` → `[]` sans crash (cas liste vide)
- ✅ `REGISTRY_PATH` vide → RuntimeError propagée correctement

### Corrections appliquées en cours de route
- ✅ `FastMCP(description=)` → `instructions=` (API 1.28, aurait crashé le serveur)
- ✅ FastMCP 1.28 sérialise `list[dict]` en N items séparés — `_call_server` corrigé
- ✅ `content:[]` (liste vide) → retourne `[]` sans IndexError
- ✅ `isError:true` → RuntimeError avec message lisible
- ✅ `structuredContent` utilisé en priorité (format plus fiable)

### Livrable vérifiable manquant
- ⚠️ `get_entry` sur `android/skill/compose-ui` depuis **Claude Code IDE** non vérifié manuellement
  → configs en place, test E2E passe, mais l'IDE n'a pas été ouvert

---

## Jour 3 — Tests + GitHub source mode ✅

### Tests (121 → 137 tests, tous verts)
- ✅ `tests/test_contract.py` (38 tests) — contrats de forme pour les 5 outils
- ✅ `tests/test_registry.py` +17 — `_parse_frontmatter`, `_extract_updated_at`, cache lru
- ✅ `tests/test_integration.py` +8 — 4 types d'artefacts, format ID, search ranking
- ✅ `tests/test_e2e.py` +9 — get_entry agent/command/hook, filtres combinés, count math

### GitHub source mode (plus de clone local nécessaire)
- ✅ `registry_github.py` — fetche le tree GitHub (1 appel API) + fichiers via CDN
- ✅ `registry.py` — dispatcher `load_registry()` et `get_entry_content()` selon env
- ✅ `tests/test_registry_github.py` (16 tests) — HTTP entièrement mocké
- ✅ `REGISTRY_GITHUB_REPO=owner/repo` active le mode GitHub
- ✅ `REGISTRY_GITHUB_BRANCH` et `REGISTRY_GITHUB_TOKEN` supportés
- ✅ `REGISTRY_PATH` reste disponible pour dev local et tests

### Configs mises à jour
- ✅ `~/.claude/settings.json` → `REGISTRY_GITHUB_REPO` (plus de chemin local)
- ✅ `~/Library/.../Code/User/mcp.json` → config user-level VS Code (tous les projets)
- ✅ `REGISTRY_GITHUB_TOKEN` ajouté dans `mcp.json` pour l'accès au repo privé
- ✅ `.env.example` documenté avec les 3 variables GitHub

---

## Jour 3 — Interopérabilité Copilot agent mode ⚠️ PARTIEL

### Ce qui a été validé
- ✅ Serveur démarre et tourne (`MCP: List Servers` → status: running)
- ✅ Copilot agent mode appelle `list_entries` correctement (outil découvert et invoqué)
- ✅ Le protocole JSON-RPC stdio fonctionne entre VS Code et le serveur

### Bloqué — token GitHub en attente d'approbation
- ⚠️ Fine-grained PAT créé mais **pending** (approbation org GLOBAL-PALO-IT requise)
- ⚠️ Classic PAT à créer pour test immédiat (pas d'approbation org requise)
- [ ] Une fois le token actif : retester `list_entries type=skill` → attendre ~39 résultats
- [ ] Valider `get_entry`, `search_entries`, `check_compliance` via Copilot
- [ ] Tester depuis Claude Code IDE (config en place, jamais validée depuis l'IDE)

### Documentation
- [ ] Créer `TESTING.md` : protocole, clients, versions, résultats

---

## Jour 4 — Polish + publication (lundi)

### Interopérabilité (priorité 1)
- [ ] Obtenir un classic PAT GitHub (repo scope) → tester Copilot end-to-end
- [ ] Tester depuis Claude Code IDE → confirmer `~/.claude/settings.json` fonctionnel
- [ ] Capturer un screenshot ou log des deux clients appelant le même outil

### Robustesse
- [ ] Tester `reload_registry` stretch goal (vide le lru_cache → force re-fetch GitHub)
- [ ] Vérifier comportement si repo GitHub inaccessible au démarrage (message d'erreur clair)

### Documentation finale
- [ ] `TESTING.md` avec protocole reproductible
- [ ] README mis à jour avec la nouvelle config GitHub source

### Stretch : publication
- [ ] Publier sur PyPI → permettre `uvx lab-registry-server` sans clone local
- [ ] Config collègue universelle : `uvx lab-registry-server` + `REGISTRY_GITHUB_REPO`

---

## ⚠️ Points de vigilance (mise à jour vendredi 4 juillet)

### 🔴 Bloquant

**1. Token GitHub en attente d'approbation org**
- Fine-grained PAT créé, status "pending" sur GLOBAL-PALO-IT
- Action requise lundi : créer un **classic PAT** (scope `repo`) ou demander l'approbation à un admin org
- Le serveur fonctionne, le protocole fonctionne — seul l'accès au repo privé bloque

**2. Claude Code IDE jamais testé manuellement**
- Config `~/.claude/settings.json` avec `REGISTRY_GITHUB_REPO` en place
- Jamais ouvert Claude Code pour confirmer que le serveur apparaît dans `/mcp`
- À tester lundi en priorité

### 🟡 Moyen

**3. Token GitHub en clair dans `mcp.json`**
- Fichier `~/Library/.../Code/User/mcp.json` contient le token en clair
- Token pending donc pas encore actif, mais à remplacer par un secret manager à terme
- Solution court terme : utiliser `inputs` de VS Code MCP pour lire depuis le keychain

**4. `updated_at: null` pour 4 plugins**
- `html-presentation`, `migration-implementation-plan`, `go-tdd-orchestrator`, `figma-design-to-code` sans CHANGELOG.md
- `check_compliance` fonctionne (version présente), mais `updated_at` est `null`

**5. Cache GitHub non invalidé automatiquement**
- Si `gen-e2-marketplace` reçoit un commit pendant que le serveur tourne → données périmées
- Mitigation : redémarrer le serveur MCP ou implémenter `reload_registry`

### 🟢 Faible

**6. `search_entries` sans scoring de pertinence réel**
- Ranking actuel : name match > description match. Acceptable pour 65 entrées.

**7. Publication PyPI non faite**
- Collègues ne peuvent pas utiliser le serveur sans cloner le repo localement
- Bloqué intentionnellement — à faire après validation interopérabilité

### `get_entry_batch` — récupération groupée
`get_entry_batch(entries: [{plugin, type, name}])` → liste complète en un seul appel.

### Recherche par `context: fork`
`list_entries type=skill context=fork` → uniquement les skills subagents.

### `diff_plugin` — changelog structuré
`diff_plugin(plugin, from_version, to_version)` → sections CHANGELOG.md correspondantes.


---

## Jour 2 — Connexion Claude Code + test en conditions réelles

**Objectif** : le serveur tourne face à un vrai client MCP avec les 60 artefacts réels.

### Setup

- [ ] Initialiser le repo git (`git init`, premier commit)
- [ ] Ajouter `.claude/settings.json` au repo avec la config MCP (chemin absolu)
- [ ] Vérifier que `mcp run src/lab_registry/server.py` démarre sans erreur avec `REGISTRY_PATH` réel

### Tests manuels depuis Claude Code

- [ ] `list_entries` → doit retourner 60 entrées
- [ ] `list_entries type=skill` → doit retourner 40 skills
- [ ] `list_entries plugin=android` → doit retourner les 14 skills + 9 agents + 9 commands + 1 hook android
- [ ] `search_entries query=architecture` → doit trouver android-architecture + architecture-reviewer
- [ ] `get_entry plugin=android type=skill name=android-architecture` → doit retourner `content_raw` non vide
- [ ] `get_plugin plugin=research-suite` → doit retourner version 1.0.1 + 2 skills
- [ ] `check_compliance` avec une entrée à jour + une obsolète → doit distinguer les deux

### Corrections attendues

- [ ] Identifier les artefacts mal parsés (frontmatter atypique, encodage, fichier vide)
- [ ] Vérifier que `updated_at` est bien extrait pour tous les plugins avec CHANGELOG

### Livrable vérifiable

`get_entry` sur `android/skill/compose-ui` retourne un `content_raw` > 100 lignes depuis Claude Code.

---

## Jour 3 — Interopérabilité Copilot agent mode (NON-NÉGOCIABLE)

**Objectif** : les deux clients appellent les mêmes 5 outils sur le même serveur stdio, sans différence de comportement.

### Setup Copilot

- [ ] Créer `.vscode/mcp.json` dans le workspace gen-e2-marketplace avec la config lab-registry
- [ ] Vérifier que le serveur apparaît dans la liste des outils MCP dans Copilot agent mode
- [ ] Confirmer que le nom `lab-registry` et les 5 tools sont visibles côté Copilot

### Tests croisés (même requête, deux clients)

- [ ] `list_entries type=skill` → même nombre de résultats depuis Claude Code et Copilot
- [ ] `get_entry plugin=delivery type=skill name=execute-plan` → même `content_raw` dans les deux
- [ ] `check_compliance` avec payload mixte → même réponse `outdated`/`unknown` dans les deux

### Documentation interop

- [ ] Créer `TESTING.md` avec : protocole de test, clients testés, versions, résultats des 3 cas ci-dessus
- [ ] Documenter les différences de comportement observées (timeout, encoding, schéma JSON…)

### Livrable vérifiable

Screenshot ou log des deux clients retournant le même résultat sur `get_entry` pour le même artefact.

---

## Jour 4 — Polish + validation E2E

**Objectif** : le projet est livrable et maintenable.

### Robustesse
- [ ] Gérer les plugins dont `source` pointe vers un dossier absent (log warning, ne pas crasher)
- [ ] Gérer les SKILL.md sans frontmatter valide (retourner l'entrée avec `description: ""`)
- [ ] Tester avec un `REGISTRY_PATH` inexistant → message d'erreur clair

### Tests
- [ ] Ajouter 1 test d'intégration qui charge le vrai marketplace (`REGISTRY_PATH` réel, marqué `@pytest.mark.integration`)
- [ ] Vérifier que tous les 60 artefacts ont un `name` non vide et un `id` unique

### Config client finale
- [ ] Valider la config Claude Code avec chemin absolu + venv Python
- [ ] Valider la config Copilot avec `${workspaceFolder}` variable
- [ ] Tester un redémarrage du serveur (le cache se vide, les données sont rechargées)

### Livrable vérifiable
`pytest tests/ -v` vert + test d'intégration marqué + `TESTING.md` complété.

---

## Idées stretch (si le temps le permet)

### `reload_registry` — rechargement forcé du cache
**Priorité : haute** — utile dès qu'on modifie un SKILL.md sans redémarrer le serveur.

```python
@mcp.tool()
def reload_registry() -> dict:
    """Force reload the registry from REGISTRY_PATH.
    Use after adding, modifying, or removing entries in the source repo.
    Returns a summary: plugins loaded, entries added/modified/removed vs previous state."""
    from lab_registry.registry import load_registry
    
    old_entries = {e.id: e.plugin_version for e in load_registry()[0]}
    load_registry.cache_clear()
    new_entries = {e.id: e.plugin_version for e in load_registry()[0]}
    
    added   = [id for id in new_entries if id not in old_entries]
    removed = [id for id in old_entries if id not in new_entries]
    modified = [id for id in new_entries if id in old_entries and new_entries[id] != old_entries[id]]
    
    return {"added": added, "removed": removed, "modified": modified,
            "total": len(new_entries)}
```

### `list_plugins` — inventaire rapide des plugins
Retourne la liste des plugins avec version + nombre d'artefacts par type — plus léger que `get_plugin` × 13.

### `get_entry_batch` — récupération groupée
`get_entry_batch(entries: [{plugin, type, name}])` → liste de résultats en un seul appel.
Utile pour un client qui veut récupérer un plugin entier avec contenu.

### Recherche par `context: fork`
`list_entries type=skill context=fork` → liste uniquement les skills subagents.
Nécessite d'ajouter `context` comme paramètre de filtre dans `list_entries_handler`.

### `diff_plugin` — changelog structuré entre deux versions
`diff_plugin(plugin, from_version, to_version)` → parse le CHANGELOG.md et retourne les sections correspondantes. Utile pour qu'un client comprenne ce qui a changé avant de mettre à jour.

### Export snapshot
`export_snapshot()` → retourne tout le registre sérialisé en JSON (sans `content_raw`).
Permet au client de cacher localement le registre et de ne faire `check_compliance` qu'au démarrage.
