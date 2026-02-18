#!/bin/bash
# build_templates.sh — Sync source files from the main codebase into templates/
# Run from the create-ontology-app directory:
#   cd tools/create-ontology-app && bash build_templates.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
TPL="$SCRIPT_DIR/templates"

echo "Repo root: $REPO_ROOT"
echo "Templates: $TPL"

# Clean existing templates
rm -rf "$TPL"
mkdir -p "$TPL"

# ===== SPEC-2: Static copies (core/, system/, domain_plugin.py) =====

echo "Copying core/ ..."
mkdir -p "$TPL/backend"
rsync -a --exclude='__pycache__' "$REPO_ROOT/backend/core/" "$TPL/backend/core/"

echo "Copying app/system/ ..."
mkdir -p "$TPL/backend/app/system"
rsync -a --exclude='__pycache__' "$REPO_ROOT/backend/app/system/" "$TPL/backend/app/system/"

echo "Copying app/domain_plugin.py ..."
cp "$REPO_ROOT/backend/app/domain_plugin.py" "$TPL/backend/app/domain_plugin.py"

# ===== Generic app files (static copies) =====

echo "Copying generic app/models/ ..."
mkdir -p "$TPL/backend/app/models"
cp "$REPO_ROOT/backend/app/models/ontology.py" "$TPL/backend/app/models/ontology.py"
cp "$REPO_ROOT/backend/app/models/events.py" "$TPL/backend/app/models/events.py"
cp "$REPO_ROOT/backend/app/models/security_events.py" "$TPL/backend/app/models/security_events.py"
cp "$REPO_ROOT/backend/app/models/snapshots.py" "$TPL/backend/app/models/snapshots.py"
cp "$REPO_ROOT/backend/app/models/benchmark.py" "$TPL/backend/app/models/benchmark.py"

echo "Copying generic app/routers/ ..."
mkdir -p "$TPL/backend/app/routers"
for f in ai.py auth.py audit_logs.py conversations.py debug.py ontology.py security.py settings.py undo.py benchmark.py; do
    cp "$REPO_ROOT/backend/app/routers/$f" "$TPL/backend/app/routers/$f"
done

echo "Copying generic app/services/ ..."
mkdir -p "$TPL/backend/app/services"
for f in llm_service.py conversation_service.py event_bus.py config_history_service.py schema_index_service.py security_event_service.py alert_service.py metadata.py benchmark_assertions.py benchmark_service.py; do
    if [ -f "$REPO_ROOT/backend/app/services/$f" ]; then
        cp "$REPO_ROOT/backend/app/services/$f" "$TPL/backend/app/services/$f"
    fi
done

echo "Copying generic app/services/actions/ ..."
mkdir -p "$TPL/backend/app/services/actions"
for f in base.py query_actions.py smart_update_actions.py interface_actions.py notification_actions.py webhook_actions.py; do
    cp "$REPO_ROOT/backend/app/services/actions/$f" "$TPL/backend/app/services/actions/$f"
done

echo "Copying app/security/ ..."
mkdir -p "$TPL/backend/app/security"
cp "$REPO_ROOT/backend/app/security/__init__.py" "$TPL/backend/app/security/__init__.py" 2>/dev/null || touch "$TPL/backend/app/security/__init__.py"

# ===== Frontend static copies =====

echo "Copying frontend static files ..."
mkdir -p "$TPL/frontend/src"

# Components (exclude hotel/)
rsync -a --exclude='__pycache__' --exclude='hotel/' "$REPO_ROOT/frontend/src/components/" "$TPL/frontend/src/components/"

# Pages (exclude hotel/, only generic + system/)
mkdir -p "$TPL/frontend/src/pages"
for f in "$REPO_ROOT/frontend/src/pages/"*.tsx; do
    [ -f "$f" ] && cp "$f" "$TPL/frontend/src/pages/"
done
if [ -d "$REPO_ROOT/frontend/src/pages/system" ]; then
    rsync -a "$REPO_ROOT/frontend/src/pages/system/" "$TPL/frontend/src/pages/system/"
fi

# Services - apiClient.ts (static)
mkdir -p "$TPL/frontend/src/services"
cp "$REPO_ROOT/frontend/src/services/apiClient.ts" "$TPL/frontend/src/services/apiClient.ts"

# Store - ontologyStore.ts (static)
mkdir -p "$TPL/frontend/src/store"
cp "$REPO_ROOT/frontend/src/store/ontologyStore.ts" "$TPL/frontend/src/store/ontologyStore.ts"

# Types - debug.ts (static)
mkdir -p "$TPL/frontend/src/types"
cp "$REPO_ROOT/frontend/src/types/debug.ts" "$TPL/frontend/src/types/debug.ts"

# Other frontend dirs
for d in i18n lib; do
    if [ -d "$REPO_ROOT/frontend/src/$d" ]; then
        rsync -a "$REPO_ROOT/frontend/src/$d/" "$TPL/frontend/src/$d/"
    fi
done

# main.tsx, index.css
for f in main.tsx index.css; do
    [ -f "$REPO_ROOT/frontend/src/$f" ] && cp "$REPO_ROOT/frontend/src/$f" "$TPL/frontend/src/$f"
done

# Frontend config files
for f in postcss.config.js tailwind.config.js tsconfig.json tsconfig.node.json eslint.config.js vite-env.d.ts; do
    [ -f "$REPO_ROOT/frontend/$f" ] && cp "$REPO_ROOT/frontend/$f" "$TPL/frontend/$f"
done
[ -f "$REPO_ROOT/frontend/src/vite-env.d.ts" ] && cp "$REPO_ROOT/frontend/src/vite-env.d.ts" "$TPL/frontend/src/vite-env.d.ts"

echo ""
echo "Static template sync complete."
echo "Next: create .j2 templates for coupling points and domain stubs."
