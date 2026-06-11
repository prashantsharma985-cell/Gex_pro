#!/bin/bash
# =============================================
# GEX PRO - Android Auto Setup & Run Script
# Pydroid 3 Terminal mein ek baar chalao
# Uske baad sirf: bash /sdcard/GEX/run.sh
# =============================================

APP_DIR="/sdcard/GEX"
APP_FILE="$APP_DIR/app.py"
REQ_FILE="$APP_DIR/requirements.txt"
FLAG_FILE="$APP_DIR/.setup_done"

echo ""
echo "======================================"
echo "  ⚡ GEX PRO v7.0 - Starting..."
echo "======================================"
echo ""

# ── STEP 1: Pehli baar setup (sirf ek baar hoga) ──
if [ ! -f "$FLAG_FILE" ]; then
  echo "🔧 Pehli baar setup ho raha hai..."
  echo "   (Internet chahiye — WiFi pe raho)"
  echo ""

  pip install -r "$REQ_FILE" --quiet

  if [ $? -eq 0 ]; then
    touch "$FLAG_FILE"
    echo ""
    echo "✅ Setup complete! Ab se seedha start hoga."
  else
    echo ""
    echo "❌ Install fail hua. WiFi check karo aur dobara try karo."
    exit 1
  fi
else
  echo "✅ Setup already done — seedha start ho raha hai!"
fi

echo ""
echo "🌐 Browser mein kholo: localhost:8501"
echo "🛑 Band karna ho toh: Ctrl+C dabaao"
echo ""

# ── STEP 2: App start karo ──
streamlit run "$APP_FILE" \
  --server.port 8501 \
  --server.headless true \
  --server.enableCORS false \
  --server.enableXsrfProtection false \
  --browser.gatherUsageStats false
