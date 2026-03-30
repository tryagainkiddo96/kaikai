#!/bin/bash
# Kai AI Setup for Kali Linux
# Run: bash setup_kai.sh

set -e

echo ""
echo "========================================"
echo "  Kai AI - Linux Setup"
echo "========================================"
echo ""

DESKTOP="$HOME/Desktop"
KAI_DIR="$DESKTOP/Kai-AI"

# Step 1: Clone or update
echo "[1/5] Getting Kai files..."
if [ -d "$KAI_DIR" ]; then
    echo "  Updating existing Kai..."
    cd "$KAI_DIR"
    git pull origin main
else
    echo "  Cloning Kai from GitHub..."
    mkdir -p "$DESKTOP"
    cd "$DESKTOP"
    git clone https://github.com/tryagainkiddo96/kaikai.git "Kai-AI"
    cd "$KAI_DIR"
fi

# Step 2: Virtual environment
echo ""
echo "[2/5] Setting up Python environment..."
if [ ! -d "$KAI_DIR/.venv" ]; then
    python3 -m venv .venv
fi
source .venv/bin/activate

# Step 3: Install dependencies
echo ""
echo "[3/5] Installing dependencies..."
pip install --upgrade pip --quiet
pip install -r requirements.txt --quiet
pip install playwright --quiet
playwright install chromium 2>/dev/null || echo "  Playwright browsers installed or skipped"

# Step 4: Create launcher
echo ""
echo "[4/5] Creating launcher..."
cat > "$DESKTOP/start-kai.sh" << 'LAUNCHER'
#!/bin/bash
cd "$(dirname "$0")/Kai-AI"
source .venv/bin/activate
clear
echo ""
echo "  ========================================"
echo "    Kai AI is running"
echo "  ========================================"
echo ""
echo "  Type your request and press Enter."
echo "  Type /exit to quit."
echo ""
python -m kai_agent.assistant
LAUNCHER
chmod +x "$DESKTOP/start-kai.sh"

# Also create a terminal alias
cat > "$KAI_DIR/kai" << 'ALIAS'
#!/bin/bash
cd "$(dirname "$0")"
source .venv/bin/activate
python -m kai_agent.assistant "$@"
ALIAS
chmod +x "$KAI_DIR/kai"

# Step 5: Done
echo ""
echo "[5/5] Setup complete!"
echo ""
echo "========================================"
echo "  Kai AI is ready!"
echo "========================================"
echo ""
echo "  Desktop shortcut: start-kai.sh"
echo "  Project folder: $KAI_DIR"
echo "  Quick launcher: $KAI_DIR/kai"
echo ""
echo "  Try these commands in Kai:"
echo '  - "browse stfrancis.com"'
echo '  - "do task: get patient form from st francis hospital cape girardeau MO"'
echo '  - "plan: find the patient portal signup page"'
echo '  - "show documents"'
echo ""
echo "  Launch anytime with:"
echo "  bash ~/Desktop/start-kai.sh"
echo "  or: $KAI_DIR/kai"
echo "========================================"
echo ""

read -p "Press Enter to launch Kai now..."
python -m kai_agent.assistant
