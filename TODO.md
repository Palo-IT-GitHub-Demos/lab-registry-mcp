# TODO — Lab Registry Server

> Critère de succès obligatoire : test croisé Claude Code + Copilot agent mode sur le même serveur (Jour 3).
> Légende : ✅ fait · ⚠️ partiel · [ ] à faire

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

## Jour 3 — Interopérabilité Copilot agent mode (NON-NÉGOCIABLE)

**Objectif** : les deux clients appellent les mêmes 5 outils sur le même serveur stdio.

### Setup Copilot
- ✅ `.vscode/mcp.json` créé dans gen-e2-marketplace
- [ ] Vérifier que le serveur apparaît dans Copilot agent mode (nécessite VS Code ouvert)
- [ ] Confirmer que les 5 tools sont visibles côté Copilot

### Tests croisés (même requête, deux clients)
- [ ] `list_entries type=skill` → même nombre de résultats Claude Code et Copilot
- [ ] `get_entry plugin=delivery type=skill name=execute-plan` → même `content_raw`
- [ ] `check_compliance` payload mixte → même réponse `outdated`/`unknown`

### Documentation
- [ ] Créer `TESTING.md` : protocole, clients, versions, résultats des 3 cas

### Livrable vérifiable
Log ou screenshot des deux clients retournant le même résultat sur `get_entry`.

---

## Jour 4 — Polish + validation E2E

**Objectif** : le projet est livrable et maintenable.

### Robustesse
- [ ] Gérer les plugins dont `source` pointe vers un dossier absent (log warning, ne pas crasher)
- [ ] Gérer les SKILL.md sans frontmatter valide (retourner l'entrée avec `description: ""`)

### Config client finale
- [ ] Valider la config Claude Code avec chemin absolu + venv Python depuis l'IDE
- [ ] Tester un redémarrage du serveur (cache vidé, données rechargées)

### Livrable vérifiable
`pytest tests/ -v` vert + `TESTING.md` complété.

---

## ⚠️ Inquiétudes et zones non vérifiées

> Problèmes potentiels connus, non testés ou non confirmés. À surveiller activement.

### 🔴 Critique — bloquant si ça échoue

**1. Claude Code IDE ne voit pas le serveur MCP**
- Config dans `~/.claude/settings.json`, mais jamais ouvert Claude Code pour confirmer
- Risque : chemin absolu du venv incorrect, ou Claude Code ne charge pas les mcpServers user-level
- Vérification : ouvrir Claude Code, taper `/mcp` ou vérifier le panneau MCP

**2. Copilot agent mode ne voit pas le serveur**
- `.vscode/mcp.json` créé dans gen-e2-marketplace, jamais testé dans VS Code
- Risque : format `mcp.json` a changé dans une version récente de Copilot, ou le serveur stdio n'est pas supporté dans cette config
- Vérification : ouvrir VS Code dans gen-e2-marketplace, chercher "lab-registry" dans Copilot agent tools

### 🟡 Moyen — dégradation silencieuse

**3. `updated_at: null` pour 4 plugins**
- `html-presentation`, `migration-implementation-plan`, `go-tdd-orchestrator`, `figma-design-to-code` n'ont pas de CHANGELOG.md → `updated_at` est `null`
- Impact : `check_compliance` fonctionne (version toujours présente), mais les clients qui affichent `updated_at` voient `null`
- Non corrigé intentionnellement — gap documenté dans `.github/copilot-instructions.md`

**4. `argument-hint` liste dans certains fichiers commands**
- Trouvé et corrigé sur android, mais d'autres plugins pourraient avoir d'autres anomalies de frontmatter non vues
- Test d'intégration `test_real_no_empty_descriptions` couvre les descriptions vides, mais pas tous les types de frontmatter malformé

**5. Comportement de `lru_cache` après un `git pull` sur le marketplace**
- Le cache n'est jamais invalidé automatiquement — si `gen-e2-marketplace` reçoit un commit pendant que le serveur tourne, les clients voient des données périmées
- Mitigation prévue : outil `reload_registry` (stretch goal), mais non implémenté

**6. Taille des réponses `list_entries` sans filtre**
- 60 entrées × ~500 chars chacune ≈ 30 KB JSON. Testé avec buffer 8MB, pas de problème actuellement.
- Si le marketplace grossit (200+ entrées), risque de timeout côté client MCP (Claude Code a des timeouts configurables)

### 🟢 Faible — non critique

**7. `search_entries` sans scoring de pertinence réel**
- Ranking actuel : name match > description match. Pas de TF-IDF, pas de fuzzy search.
- Acceptable pour 60 entrées. Devient problématique à 500+.

**8. Standalone `test_e2e.py __main__` sans assertions**
- Le runner standalone imprime les résultats mais ne valide pas les formes
- Masquait les bugs de format FastMCP 1.28 lors de la première exécution
- Pas corrigé (non prioritaire — pytest couvre tout)

---

## Idées stretch (si le temps le permet)

### `reload_registry` — rechargement forcé du cache
**Priorité : haute** — résout l'inquiétude n°5 ci-dessus.

```python
@mcp.tool()
def reload_registry() -> dict:
    """Force reload the registry from REGISTRY_PATH.
    Returns: added/removed/modified entry IDs vs previous state."""
    old = {e.id: e.plugin_version for e in load_registry()[0]}
    load_registry.cache_clear()
    new = {e.id: e.plugin_version for e in load_registry()[0]}
    return {
        "added":    [id for id in new if id not in old],
        "removed":  [id for id in old if id not in new],
        "modified": [id for id in new if id in old and new[id] != old[id]],
        "total":    len(new),
    }
```

### `list_plugins` — inventaire rapide
Retourne les 13 plugins avec version + nombre d'artefacts par type.

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
