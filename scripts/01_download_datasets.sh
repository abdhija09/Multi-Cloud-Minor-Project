#!/usr/bin/env bash
# scripts/01_download_datasets.sh
# Download the Silesia corpus into data/ (unzipped into data/silesia/) and
# create the output directories.
#
# Usage: bash scripts/01_download_datasets.sh [--with-azure]
#   --with-azure   also download the Azure 2019 VM table (data/vmtable.csv.gz).
#                  Not needed: without it the pipeline uses synthetic failure
#                  rates (see scripts/02_fit_failure_stats.py).
#
# Safe to re-run (skips files already present). Download failures print
# instructions and the script still exits 0.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
DATA_DIR="$PROJECT_ROOT/data"

WITH_AZURE=0
for arg in "$@"; do
    case "$arg" in
        --with-azure) WITH_AZURE=1 ;;
        -h|--help) sed -n '2,13p' "$0"; exit 0 ;;
        *) echo "[01] Unknown argument: $arg (use --with-azure)"; exit 2 ;;
    esac
done

mkdir -p "$DATA_DIR" \
         "$PROJECT_ROOT/experiments/runs" \
         "$PROJECT_ROOT/results/tables" \
         "$PROJECT_ROOT/results/figures"

# ── Silesia corpus ────────────────────────────────────────────────────────────
SILESIA_URL="http://sun.aei.polsl.pl/~sdeor/corpus/silesia.zip"
SILESIA_ZIP="$DATA_DIR/silesia.zip"
SILESIA_DIR="$DATA_DIR/silesia"

if [ -f "$SILESIA_ZIP" ] && unzip -tq "$SILESIA_ZIP" >/dev/null 2>&1; then
    echo "[01] Silesia zip already present: $SILESIA_ZIP"
else
    rm -f "$SILESIA_ZIP"
    echo "[01] Downloading Silesia corpus from $SILESIA_URL ..."
    if curl -fL --retry 3 --connect-timeout 30 --progress-bar -o "$SILESIA_ZIP.part" "$SILESIA_URL" \
       && unzip -tq "$SILESIA_ZIP.part" >/dev/null 2>&1; then
        mv "$SILESIA_ZIP.part" "$SILESIA_ZIP"
        echo "[01] Silesia downloaded: $(du -sh "$SILESIA_ZIP" | cut -f1)"
    else
        rm -f "$SILESIA_ZIP.part"
        echo ""
        echo "======================================================================"
        echo "  WARNING: Silesia corpus download failed."
        echo "  To get it manually:"
        echo "    1. Download $SILESIA_URL"
        echo "    2. Save it as $SILESIA_ZIP"
        echo "    3. Re-run: bash scripts/01_download_datasets.sh"
        echo "======================================================================"
    fi
fi

if [ -f "$SILESIA_ZIP" ]; then
    if [ -d "$SILESIA_DIR" ] && [ -n "$(ls -A "$SILESIA_DIR" 2>/dev/null)" ]; then
        echo "[01] Silesia already unzipped: $SILESIA_DIR"
    else
        mkdir -p "$SILESIA_DIR"
        if unzip -oq "$SILESIA_ZIP" -d "$SILESIA_DIR"; then
            echo "[01] Silesia unzipped into $SILESIA_DIR"
        else
            echo "[01] WARNING: could not unzip $SILESIA_ZIP"
        fi
    fi
fi

# ── Azure Public Dataset 2019 VM table (optional) ────────────────────────────
AZURE_URL="https://azurepublicdatasettraces.blob.core.windows.net/azurepublicdatasetv2/trace_data/vmtable/vmtable.csv.gz"
AZURE_FILE="$DATA_DIR/vmtable.csv.gz"

if [ "$WITH_AZURE" -eq 0 ]; then
    echo "[01] Azure 2019 trace skipped (synthetic failure rates are used; pass --with-azure to download $AZURE_URL)"
elif [ -f "$AZURE_FILE" ]; then
    echo "[01] Azure VM table already present: $AZURE_FILE"
else
    echo "[01] Downloading Azure VM table from $AZURE_URL ..."
    if curl -fL --retry 2 --connect-timeout 30 --progress-bar -o "$AZURE_FILE.part" "$AZURE_URL"; then
        mv "$AZURE_FILE.part" "$AZURE_FILE"
        echo "[01] Azure VM table downloaded: $(du -sh "$AZURE_FILE" | cut -f1)"
    else
        rm -f "$AZURE_FILE.part"
        echo ""
        echo "======================================================================"
        echo "  WARNING: Azure VM trace download failed."
        echo "  The pipeline falls back to synthetic failure rates."
        echo "  To get it manually, download $AZURE_URL"
        echo "  and place it at: $AZURE_FILE"
        echo "======================================================================"
    fi
fi

# ── Sizes ─────────────────────────────────────────────────────────────────────
echo ""
echo "[01] Data directory contents:"
ls -lh "$DATA_DIR" 2>/dev/null || echo "  (empty)"
if [ -d "$SILESIA_DIR" ]; then
    echo ""
    echo "[01] Silesia files ($(du -sh "$SILESIA_DIR" | cut -f1) total):"
    ls -lh "$SILESIA_DIR"
fi
exit 0
