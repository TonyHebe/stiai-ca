# Știai Că? — Facebook Auto-Poster

Publică automat curiozități despre natură în română pe o pagină de Facebook.  
Fiecare postare conține o imagine generată (fotografie + text suprapus) și un text complet în descriere.

---

## Structura proiectului

```
stiai-ca/
├── content/
│   └── curiosities.json        # Baza de date cu curiozități
├── assets/
│   ├── fonts/                  # Montserrat (descărcat de setup_project.py)
│   └── images/                 # Poze de fundal (locale sau descărcate din Unsplash)
├── output/                     # Imagini generate (temporar)
├── posted/
│   └── posted_log.json         # Jurnal cu tot ce s-a postat
├── image_generator.py          # Generare imagine cu Pillow
├── facebook_poster.py          # Postare via Graph API
├── main.py                     # Orchestrator principal
├── setup_project.py            # Setup inițial (fonturi, directoare)
├── requirements.txt
├── .env                        # Credențiale (NU se commitează în git!)
└── .env.example
```

---

## Cum funcționează generarea automată de conținut

Sistemul folosește **OpenAI GPT-4o-mini** pentru a scrie automat curiozități noi în română.

```
topics.json (130+ subiecte)
        │
        ▼
  content_generator.py  ──► OpenAI API  ──► curiosities.json
                                              │
                                              ▼
                                          main.py (postare automată)
```

- Când mai sunt **mai puțin de 3 curiozități nepostate**, `main.py` generează automat **5 noi** înainte să posteze.
- Poți genera manual oricând: `python content_generator.py --count 10`
- Ai **130+ subiecte pre-definite** în `content/topics.json` (plante, animale, fenomene, Delta Dunării etc.)

---

## Instalare rapidă

### 1. Clonează / copiază proiectul pe server (Linux recomandat)

```bash
git clone <repo-url> stiai-ca
cd stiai-ca
```

### 2. Instalează dependențele Python

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Rulează setup

```bash
python setup_project.py
```

Aceasta va:
- crea toate directoarele necesare
- descărca fonturile Montserrat
- crea fișierul `.env` din `.env.example`

### 4. Completează `.env`

```env
FACEBOOK_PAGE_ID=123456789012345
FACEBOOK_PAGE_ACCESS_TOKEN=EAABs...
UNSPLASH_ACCESS_KEY=abc123...      # opțional
MAX_RANDOM_DELAY_SECONDS=3600
```

---

## Cum obții un Page Access Token

1. Mergi la [Meta for Developers](https://developers.facebook.com/) → creează o aplicație.
2. Adaugă produsul **Facebook Login** și **Pages API**.
3. În **Graph API Explorer**, selectează pagina ta și solicită permisiunile:
   - `pages_manage_posts`
   - `pages_read_engagement`
4. Generează un **User Token** și convertește-l în **Long-Lived Page Access Token** (durată ~60 zile sau permanent cu extensie).
5. Copiază tokenul în `.env`.

---

## Fundal imagini

### Varianta A — Unsplash (automat)
Setează `UNSPLASH_ACCESS_KEY` în `.env`. Imaginile se descarcă automat pe baza cuvintelor cheie din `curiosities.json` și se salvează în `assets/images/` pentru refolosire.

### Varianta B — locale
Pune pozele (JPEG/PNG) în `assets/images/` și setează `"image_file": "poza-mea.jpg"` în `curiosities.json`.

---

## Testare

```bash
# Verifică tokenul Facebook
python main.py --verify

# Generează imaginea fără a posta
python main.py --dry-run

# Postează imediat (fără delay aleatoriu)
python main.py --no-delay

# Postare normală (cu delay aleatoriu)
python main.py
```

---

## Cron Job (Linux / VPS)

Deschide crontab-ul:

```bash
crontab -e
```

Adaugă liniile de mai jos pentru **3 postări pe zi** la ore variabile:
- ora 9 dimineața (va posta aleatoriu între 9:00–10:00)
- ora 13 (va posta aleatoriu între 13:00–14:00)
- ora 19 (va posta aleatoriu între 19:00–20:00)

```cron
# Știai Că? — Facebook auto-poster
0 9  * * * /home/user/stiai-ca/venv/bin/python /home/user/stiai-ca/main.py >> /home/user/stiai-ca/posted/cron.log 2>&1
0 13 * * * /home/user/stiai-ca/venv/bin/python /home/user/stiai-ca/main.py >> /home/user/stiai-ca/posted/cron.log 2>&1
0 19 * * * /home/user/stiai-ca/venv/bin/python /home/user/stiai-ca/main.py >> /home/user/stiai-ca/posted/cron.log 2>&1
```

> **Notă:** `MAX_RANDOM_DELAY_SECONDS=3600` adaugă un delay aleatoriu de 0–60 min,
> deci postările vor apărea la ore imprevizibile (ex: 9:17, 13:43, 19:08).

### Ajustarea frecvenței

| Dorești | Cron |
|---|---|
| 1 postare/zi | `0 10 * * *` |
| 2 postări/zi | `0 9,18 * * *` |
| 3 postări/zi | `0 9,13,19 * * *` |
| 1 postare la 2 zile | `0 10 */2 * *` |

---

## Generarea de curiozități cu AI

```bash
# Generează 1 curiozitate (subiect ales automat)
python content_generator.py

# Generează 10 curiozități deodată
python content_generator.py --count 10

# Generează despre un subiect specific
python content_generator.py --topic "Vulturul Pleșuv"

# Afișează lista de subiecte disponibile
python content_generator.py --list-topics
```

Curiozitățile generate sunt adăugate automat în `curiosities.json` cu `"posted": false`.

---

## Adăugarea manuală de curiozități

Editează `content/curiosities.json` și adaugă un obiect nou:

```json
{
  "id": "trandafir-001",
  "title": "Trandafirul",
  "image_text": "Trandafirul are un număr de petale întotdeauna un număr Fibonacci — 5, 8, 13 sau 21 — o adaptare matematică perfectă pentru maximizarea atracției polenizatorilor.",
  "caption": "Textul complet care apare în descrierea postării Facebook...\n\n#StiaiCa #Botanica #NaturaRomaniei",
  "image_keywords": "rose flower garden macro",
  "image_file": null,
  "posted": false
}
```

Când toate curiozitățile au fost postate, scriptul resetează automat ciclul și reîncepe de la început.

---

## Structura imaginii generate

```
┌─────────────────────────────────────┐  1080 px
│                                     │
│        [ Fotografie natură ]        │
│                                     │
│                                     │
├─────────────────────────────────────┤  ~45% de sus
│░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░│  gradient întunecat
│                                     │
│           Titlu (galben)            │  font 88px, bold
│                                     │
│   Text curiozitate (alb, centrat)   │  font 36px, max 6 rânduri
│                                     │
└─────────────────────────────────────┘  1350 px
```

Output: JPEG 1080×1350 px (format 4:5, optim pentru feed-ul Facebook mobil)

---

## Variabile `.env` disponibile

| Variabilă | Obligatorie | Descriere |
|---|---|---|
| `FACEBOOK_PAGE_ID` | ✅ | ID-ul numeric al paginii |
| `FACEBOOK_PAGE_ACCESS_TOKEN` | ✅ | Token de acces la pagină |
| `OPENAI_API_KEY` | ✅* | Cheie API OpenAI pentru generare AI |
| `OPENAI_MODEL` | ❌ | Model GPT (implicit: `gpt-4o-mini`) |
| `LOW_CONTENT_THRESHOLD` | ❌ | Generează când mai sunt N curiozități (implicit: 3) |
| `GENERATE_BATCH_SIZE` | ❌ | Câte curiozități să genereze per batch (implicit: 5) |
| `UNSPLASH_ACCESS_KEY` | ❌ | Cheie API Unsplash pentru fundal automat |
| `MAX_RANDOM_DELAY_SECONDS` | ❌ | Delay maxim aleatoriu (implicit: 3600) |

*Obligatorie pentru generarea automată de conținut. Fără ea, curiozitățile trebuie adăugate manual.

---

## Jurnal postări

Fiecare postare reușită este înregistrată în `posted/posted_log.json`:

```json
[
  {
    "id": "margareta-001",
    "title": "Margareta",
    "posted_at": "2026-07-07T09:17:34",
    "fb_post_id": "123456789_987654321",
    "image_file": "margareta-001_20260707_091734.jpg"
  }
]
```
