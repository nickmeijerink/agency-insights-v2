# Agency Insights v2

Automatische wekelijkse marketingrapportage per klant, via Google Analytics 4, Search Console en (optioneel) Google Ads. De data wordt samengevat door Claude en verstuurd naar Slack.

---

## Vereisten

- Python 3.11+
- Google-serviceaccount met toegang tot GA4 en Search Console
- Anthropic API-sleutel
- Slack Incoming Webhook URL

---

## Installatie

```bash
pip install -r requirements.txt
```

---

## Configuratie

### 1. Klanten instellen

Pas [`clients.yaml`](clients.yaml) aan. Voeg per klant een blok toe:

```yaml
clients:
  - name: "Naam Klant BV"
    ga4_property_id: "123456789"          # Alleen het getal, geen 'properties/' prefix
    gsc_site_url: "https://www.klant.nl/" # Exacte URL zoals in Search Console
    google_ads_customer_id: ""            # Optioneel, laat leeg als niet van toepassing
    slack_webhook: ""                     # Optioneel, valt terug op SLACK_WEBHOOK_URL
```

### 2. Omgevingsvariabelen

Maak lokaal een `.env`-bestand (nooit committen!) of stel GitHub Secrets in:

| Variabele | Beschrijving |
|---|---|
| `GOOGLE_SERVICE_ACCOUNT_JSON` | De volledige inhoud van je service-account JSON-bestand |
| `ANTHROPIC_API_KEY` | Je Anthropic API-sleutel |
| `SLACK_WEBHOOK_URL` | Slack Incoming Webhook URL (fallback voor alle klanten) |

### 3. Google-serviceaccount instellen

1. Maak een serviceaccount aan in Google Cloud Console.
2. Ken de volgende rollen toe:
   - **Google Analytics**: voeg het serviceaccount-e-mailadres toe als *Viewer* in GA4 Property-instellingen → Toegangsbeheer.
   - **Search Console**: voeg het e-mailadres toe als *Eigenaar* of *Volledig* in GSC → Instellingen → Gebruikers en machtigingen.
3. Maak een JSON-sleutel aan en kopieer de **volledige inhoud** als waarde voor `GOOGLE_SERVICE_ACCOUNT_JSON`.

---

## Lokaal draaien

```bash
export GOOGLE_SERVICE_ACCOUNT_JSON='{ ... }'
export ANTHROPIC_API_KEY='sk-ant-...'
export SLACK_WEBHOOK_URL='https://hooks.slack.com/...'

python main.py
```

---

## GitHub Actions

De workflow in [`.github/workflows/weekly-report.yml`](.github/workflows/weekly-report.yml) draait elke maandag om 06:00 UTC.

**Secrets instellen in GitHub:**
1. Ga naar je repository → *Settings* → *Secrets and variables* → *Actions*.
2. Voeg toe: `GOOGLE_SERVICE_ACCOUNT_JSON`, `ANTHROPIC_API_KEY`, `SLACK_WEBHOOK_URL`.

**Handmatig triggeren:**
Ga naar *Actions* → *Weekly Marketing Report* → *Run workflow*.

---

## Projectstructuur

```
├── clients.yaml          # Klantconfiguratie
├── main.py               # Hoofdscript - loopt over alle klanten
├── ga4.py                # Google Analytics 4 dataverzameling
├── gsc.py                # Google Search Console dataverzameling
├── ads.py                # Google Ads (stub, nog te implementeren)
├── summarize.py          # Samenvatting via Claude (claude-sonnet-4-6)
├── slack.py              # Slack Block Kit bericht sturen
├── requirements.txt      # Python-afhankelijkheden
└── .github/
    └── workflows/
        └── weekly-report.yml
```

---

## Google Ads uitbreiden

`ads.py` bevat momenteel een stub. Om Google Ads te activeren:
1. Installeer `google-ads` via pip en voeg toe aan `requirements.txt`.
2. Maak een Google Ads developer token aan en configureer OAuth.
3. Implementeer de `fetch()`-functie in `ads.py`.
