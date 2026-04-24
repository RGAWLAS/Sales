# Tender Aggregator

Aplikacja webowa w Pythonie, która cyklicznie agreguje ogłoszenia o przetargach
i zapytaniach ofertowych z wielu źródeł (API + scraping), filtruje je pod
kątem marketingu/reklamy, prezentuje na dashboardzie i wysyła codzienny
digest mailowy.

Architektura jest otwarta na rozbudowę: **dodanie nowego źródła sprowadza się
do napisania jednej klasy adaptera i zarejestrowania jej** w
`app/adapters/registry.py`.

## Wymagania

- Python 3.11+
- Node.js (wymagany przez Playwright, gdy dołożysz adaptery korzystające z JS)
- Konto SMTP (Gmail z hasłem aplikacji / dowolny zewnętrzny SMTP)

## Instalacja

```bash
git clone <repo>
cd tender-aggregator
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# Dla adapterów korzystających z Playwright (w tej iteracji jeszcze niepotrzebne):
# playwright install chromium
cp .env.example .env
# wypełnij .env (przede wszystkim sekcję SMTP_*)
```

## Pierwsze uruchomienie

```bash
python run.py
```

Serwer wystartuje pod adresem podanym w `.env` (domyślnie
http://127.0.0.1:8000) i w tym samym procesie uruchomi APScheduler z dwoma
jobami:

- `daily_scrape` — codziennie o `SCRAPE_HOUR:SCRAPE_MINUTE`
- `daily_digest` — codziennie o `DIGEST_HOUR:DIGEST_MINUTE`

## Ręczne odpalenia

```bash
# jednorazowy scrape wszystkich adapterów:
python -m app.scheduler run-once

# jeden konkretny adapter:
python -m app.scheduler run-adapter ezamowienia
python -m app.scheduler run-adapter eb2b_nask

# ręczne wysłanie digestu (np. po pierwszym scrape):
python -m app.scheduler digest
```

Można też odpalić pojedynczy adapter z poziomu dashboardu — `Źródła` →
`Run now`.

## Konfiguracja (`.env`)

Wszystkie klucze wypisane w `.env.example`. Kluczowe:

| Klucz | Opis |
|---|---|
| `DATABASE_URL` | domyślnie SQLite w `./data/tenders.db` |
| `SMTP_*`, `NOTIFICATION_EMAIL` | poczta wychodząca i adres adresata |
| `TIMEZONE` | domyślnie `Europe/Warsaw` |
| `SCRAPE_HOUR/MINUTE` | godzina scrape |
| `DIGEST_HOUR/MINUTE` | godzina digestu |
| `SEND_EMPTY_DIGEST` | czy wysyłać e-mail "brak nowości" |

## Filtry

Reguły filtrowania są w `config/filters.yml`. Ogłoszenie przechodzi, jeśli:
- którykolwiek z jego CPV zaczyna się od wpisanego prefiksu, **lub**
- w tytule/opisie (case-insensitive, ignorując polskie znaki diakrytyczne)
  wystąpi któreś słowo kluczowe,

i jednocześnie nie trafi żadne `exclude_keywords`. Dopasowane słowa
kluczowe są zapisywane w bazie w polu `keywords_matched`.

## Jak dodać nowy adapter

1. Utwórz nowy plik w `app/adapters/`, np. `moje_zrodlo.py`:

   ```python
   from typing import List
   from app.adapters.base import BaseAdapter, RawTender

   class MojeZrodloAdapter(BaseAdapter):
       source_id = "moje_zrodlo"
       source_name = "Moje Źródło"

       def fetch(self) -> List[RawTender]:
           session = self.build_session()
           resp = self.http_get(session, "https://example.com/api/tenders")
           return [
               RawTender(
                   external_id=str(item["id"]),
                   title=item["title"],
                   description=item.get("description", ""),
                   organization=item.get("buyer", ""),
                   url=item["link"],
                   cpv_codes=item.get("cpv", []),
               )
               for item in resp.json()["items"]
           ]
   ```

2. Zarejestruj go w `app/adapters/registry.py`:

   ```python
   from app.adapters.moje_zrodlo import MojeZrodloAdapter
   ADAPTERS: List[BaseAdapter] = [
       ...
       MojeZrodloAdapter(),
   ]
   ```

3. To wszystko — kolejne uruchomienie `python -m app.scheduler run-once`
   zacznie korzystać z nowego źródła. Nie ma konieczności zmian w
   schedulerze, bazie, filtrach ani UI.

### Adaptery parametryzowane (wiele podobnych stron pod jednym silnikiem)

Klasa eB2B jest parametryzowana subdomeną — dla każdej dodatkowej instancji
wystarczy dopisać obiekt w `registry.py`:

```python
Eb2bAdapter(subdomain="nowaagencja", display_name="eB2B Nowa Agencja"),
```

### Wybór strategii scrapingu

Kolejność sprawdzania przy pisaniu nowego adaptera:

1. **API pod spodem** — otwórz DevTools → Network → Fetch/XHR i sprawdź,
   czy listing ładuje JSON. Jeśli tak — używaj `requests` na tym endpoincie.
2. **Statyczny HTML** — `requests` + `BeautifulSoup`.
3. **JS-rendered** — `Playwright`. W kodzie adaptera dodaj komentarz,
   dlaczego sięgnięto po Playwright.

## Testy

```bash
pytest
```

Pokrywają logikę filtrowania, deduplikacji, zmianę statusu oraz parsowanie
odpowiedzi ezamowienia (mock HTTP).

## Troubleshooting

- **SMTP: `AUTH failed` na Gmailu** — musisz utworzyć *hasło aplikacji*
  w ustawieniach konta Google (2FA → Hasła aplikacji). Zwykłe hasło konta
  nie zadziała.
- **Playwright: `Executable doesn't exist`** — uruchom
  `playwright install chromium` po `pip install`.
- **Żaden CPV nie trafia** — upewnij się, że prefiksy w `filters.yml`
  są bez myślnika (ezamowienia zwraca czasem `79340000-1`; filtr używa
  `startswith`, więc `79340000` wystarczy).
- **Pusty digest mimo nowych danych** — `daily_digest_job` pokazuje
  tylko status `NEW` i tylko z ostatnich 24h; oznaczenie tendera jako
  `INTERESTED`/`NOT_INTERESTED` usuwa go z digestu.

## Struktura

```
tender-aggregator/
├── app/
│   ├── main.py            # FastAPI + routes
│   ├── config.py          # pydantic-settings + logging
│   ├── database.py        # engine + session
│   ├── models.py          # SQLAlchemy
│   ├── schemas.py         # pydantic I/O
│   ├── filters.py         # CPV + keyword
│   ├── services.py        # dedup, persist, status
│   ├── notifier.py        # mail digest
│   ├── scheduler.py       # APScheduler + CLI
│   ├── adapters/
│   │   ├── base.py        # BaseAdapter + RawTender
│   │   ├── registry.py    # lista instancji adapterów
│   │   ├── ezamowienia.py
│   │   ├── ted.py
│   │   ├── baza_konkurencyjnosci.py
│   │   ├── platformazakupowa.py
│   │   └── eb2b.py        # parametryzowany subdomeną
│   ├── templates/
│   └── static/
├── config/
│   └── filters.yml
├── tests/
├── run.py                 # uvicorn + scheduler w 1 procesie
└── requirements.txt
```
