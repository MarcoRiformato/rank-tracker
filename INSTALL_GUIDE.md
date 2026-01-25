# Guida Installazione Python - Rank Tracker

## ✅ Versione Python Richiesta

- **Minimo**: Python 3.9
- **Consigliato**: **Python 3.11** o **Python 3.12** (versione più stabile e veloce)

---

## 📥 Passo 1: Download Python

### Opzione A: Download Diretto
1. Vai su: **https://www.python.org/downloads/**
2. Clicca su "Download Python 3.11.x" (o la versione più recente)
3. Il file `.exe` verrà scaricato nella cartella Downloads

### Opzione B: Download da Microsoft Store (Alternativa)
- Apri Microsoft Store
- Cerca "Python 3.11"
- Installa (tende ad aggiungere automaticamente al PATH)

---

## 🔧 Passo 2: Installazione

1. **Esegui l'installer** scaricato (`python-3.11.x-amd64.exe`)

2. **IMPORTANTE** - Nella prima schermata:
   - ✅ **SELEZIONA la casella "Add Python to PATH"** (in basso)
   - Questa è la cosa più importante!

3. Scegli una delle opzioni:
   - **"Install Now"** (installazione standard, consigliato)
   - Oppure **"Customize installation"** se vuoi personalizzare

4. Attendi il completamento dell'installazione

5. **Riavvia il terminale/PowerShell** dopo l'installazione

---

## ✅ Passo 3: Verifica

Apri un nuovo terminale/PowerShell e verifica:

```bash
python --version
```

Dovresti vedere qualcosa tipo:
```
Python 3.11.5
```

Se vedi un errore "python non è riconosciuto", prova:

```bash
python3 --version
```

o

```bash
py --version
```

---

## 📦 Passo 4: Installa Dipendenze

Una volta che Python funziona, installa le dipendenze del progetto:

```bash
cd C:\zap\rank-tracker
python -m pip install -r requirements.txt
```

Se funziona, vedrai:
```
Successfully installed Flask-3.0.0 requests-2.31.0 python-dotenv-1.0.0 ...
```

---

## 🚀 Passo 5: Esegui l'Applicazione

1. **Crea file `.env`** (opzionale - per test senza API):
   ```
   USE_DUMMY_MODE=true
   ```

2. **Avvia il server**:
   ```bash
   python app.py
   ```

3. **Apri il browser**: `http://localhost:5000`

---

## ❌ Risoluzione Problemi

### "python non è riconosciuto" anche dopo installazione

**Soluzione 1**: Riavvia completamente il terminale/PowerShell

**Soluzione 2**: Verifica manualmente il PATH:
1. Cerca "Variabili d'ambiente" nel menu Start
2. In "Variabili di sistema", trova "Path"
3. Verifica che ci sia `C:\Users\<Tuonome>\AppData\Local\Programs\Python\Python311` (o simile)
4. Se manca, aggiungilo manualmente

**Soluzione 3**: Usa il Python Launcher:
```bash
py -m pip install -r requirements.txt
py app.py
```

### Errore durante installazione dipendenze

Prova a aggiornare pip:
```bash
python -m pip install --upgrade pip
```

Poi riprova:
```bash
python -m pip install -r requirements.txt
```

---

## 📝 Note

- **Python 3.11** è la versione consigliata per questo progetto (Flask 3.0.0 richiede Python 3.9+)
- L'app funziona anche con Python 3.12 o 3.10
- Python 3.8 o inferiore **NON funzionerà** con Flask 3.0.0
