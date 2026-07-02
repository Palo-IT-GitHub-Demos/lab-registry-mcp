# TODO — Lab Registry Server

> Plan jours 2-4 + idées stretch.
> Critère de succès obligatoire : test croisé Claude Code + Copilot agent mode sur le même serveur (Jour 3).

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
