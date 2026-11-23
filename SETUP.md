# Setup Guide - Rank Tracker

## Installing Python Dependencies on Windows

If `pip` is not recognized, try these methods:

### Method 1: Use `python -m pip` (Recommended)

```bash
python -m pip install -r requirements.txt
```

or

```bash
python3 -m pip install -r requirements.txt
```

### Method 2: Install Python if not installed

**Versione richiesta: Python 3.9 o superiore**
**Versione consigliata: Python 3.11** (per migliori prestazioni e stabilità)

1. **Scarica Python**:
   - Vai su https://www.python.org/downloads/
   - Scarica **Python 3.11.x** (o 3.12.x se disponibile) per Windows
   - Oppure usa direttamente: https://www.python.org/downloads/windows/

2. **Installa Python**:
   - Esegui l'installer scaricato
   - ✅ **IMPORTANTE**: Durante l'installazione, SELEZIONA "Add Python to PATH" (in basso nella finestra di installazione)
   - Scegli "Install Now" o "Customize installation"
   - Completa l'installazione

3. **Verifica installazione**:
   - Riavvia il terminale/PowerShell (IMPORTANTE!)
   - Verifica: `python --version` (dovrebbe mostrare Python 3.11.x o simile)

4. **Installa dipendenze**:
   ```bash
   python -m pip install -r requirements.txt
   ```

### Method 3: Use Python Launcher for Windows

If Python is installed but not in PATH:

```bash
py -m pip install -r requirements.txt
```

### Method 4: Find Python Installation

Check if Python is installed in common locations:

- `C:\Python39\python.exe`
- `C:\Python310\python.exe`
- `C:\Python311\python.exe`
- `C:\Users\<YourUsername>\AppData\Local\Programs\Python\`

Then use the full path:

```bash
C:\Python311\python.exe -m pip install -r requirements.txt
```

## After Installing Dependencies

1. **Create `.env` file** (optional - for real API):

   Create a file named `.env` in the project root:
   ```
   DATAFORSEO_LOGIN=your_login
   DATAFORSEO_PASSWORD=your_password
   ```

   Or set `USE_DUMMY_MODE=true` to test without API credentials.

2. **Run the application**:

   ```bash
   python app.py
   ```

   or

   ```bash
   python -m flask run
   ```

3. **Open in browser**: `http://localhost:5000`

## Testing Without API (Dummy Mode)

You can test the application immediately without an API key by creating a `.env` file with:

```
USE_DUMMY_MODE=true
```

This will use fake random data instead of real API calls.
