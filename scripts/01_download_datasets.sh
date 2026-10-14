#!/usr/bin/env bash
# scripts/01_download_datasets.sh
# Download the Silesia corpus and Azure Public Dataset 2019 VM table.
# Usage: bash scripts/01_download_datasets.sh
# Safe to re-run; skips files that already exist.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
DATA_DIR="$PROJECT_ROOT/data"
mkdir -p "$DATA_DIR"

# ── Silesia corpus ────────────────────────────────────────────────────────────
SILESIA_URL="http://sun.aei.polsl.pl/~sdeor/corpus/silesia.zip"
SILESIA_ZIP="$DATA_DIR/silesia.zip"

if [ -f "$SILESIA_ZIP" ]; then
    echo "[01] Silesia already present: $SILESIA_ZIP"
else
    echo "[01] Downloading Silesia corpus …"
    curl -fL --retry 3 --progress-bar -o "$SILESIA_ZIP" "$SILESIA_URL"
    echo "[01] Silesia downloaded: $(du -sh "$SILESIA_ZIP" | cut -f1)"
fi

# ── Azure Public Dataset 2019 VM table ───────────────────────────────────────
AZURE_URL="https://azureopendatastorage.blob.core.windows.net/publicdatasets/azurepublicdataset2019/vmtable.csv.gz"
AZURE_FILE="$DATA_DIR/vmtable.csv.gz"

if [ -f "$AZURE_FILE" ]; then
    echo "[01] Azure VM table already present: $AZURE_FILE"
else
    echo "[01] Attempting to download Azure VM table …"
    set +e
    curl -fL --retry 2 --max-time 120 --progress-bar -o "$AZURE_FILE" "$AZURE_URL"
    CURL_EXIT=$?
    set -e
    if [ $CURL_EXIT -ne 0 ]; then
        echo ""
        echo "======================================================================"
        echo "  WARNING: Azure VM trace download failed (exit code $CURL_EXIT)."
        echo "  The pipeline will fall back to synthetic failure rates."
        echo ""
        echo "  To obtain the real dataset manually:"
        echo "    1. Visit https://github.com/Azure/AzurePublicDataset"
        echo "    2. Download the 2019 VM table (vmtable.csv.gz)"
        echo "    3. Place it at: $AZURE_FILE"
        echo "======================================================================"
        # Remove any partial file
        rm -f "$AZURE_FILE"
    else
        echo "[01] Azure VM table downloaded: $(du -sh "$AZURE_FILE" | cut -f1)"
    fi
fi

# ── Print sizes of what we have ───────────────────────────────────────────────
echo ""
echo "[01] Data directory contents:"
ls -lh "$DATA_DIR" 2>/dev/null || echo "  (empty)"
