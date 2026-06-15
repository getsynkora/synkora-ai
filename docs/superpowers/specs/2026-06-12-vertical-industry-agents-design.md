# Vertical Industry Agent Suites — Design Spec

**Date:** 2026-06-12
**Status:** Draft

---

## Overview

This spec defines decision-centric agent suites for 7 industries. Each suite ships first as public marketplace templates inside Synkora, then the best-performing ones get productized as branded vertical SaaS products.

The core principle: these agents do not replace departmental functions. They answer the questions executives cannot get answered today — because the data exists but nobody has time to connect it.

**Industries covered:**
1. Micromobility
2. Startup
3. SME (Small-Medium Enterprise)
4. Garments / Apparel Manufacturing
5. NGO / Non-profit
6. Photography Studios
7. Government / Public Sector
8. Law Firms / Legal

---

## Platform Architecture

### How Every Vertical Agent Plugs Into Synkora

Every agent is a standard Synkora Agent record:

```
agent_type:         "LLM" or "autonomous"
system_prompt:      vertical-specific, role-specific, decision-focused
tools_config:       curated tool list for that vertical
agent_metadata:     { vertical: "garments", role: "supplier_intelligence" }
is_public:          true (visible in marketplace)
suggestion_prompts: pre-built queries the user can one-click
```

### Two Deployment Modes

**Mode A — Marketplace Template**
Tenant browses marketplace → one-click installs the agent → connects data sources via OAuth or API key → agent is live.

**Mode B — Vertical SaaS**
Fork the template set into a white-labeled product. The tenant never sees "Synkora". Same backend, branded frontend, vertical-specific onboarding wizard.

### Agent Archetypes

| Archetype | How It Runs | Trigger |
|---|---|---|
| Monitor | Autonomous / scheduled | Celery beat task on schedule |
| Oracle | Chat | User asks a question |
| Analyst | Triggered | Event (new invoice, new order, doc upload) |
| Assistant | Chat + tool use | Conversational, takes actions |
| Detector | Autonomous | Fires on anomaly in data |

### Common Data Flow

```
External Data Source
  → OAuth credential (stored encrypted in Synkora)
  → Tool call (internal_tools layer)
  → Agent context window
  → LLM reasoning
  → Structured output: decision / alert / report / draft
  → Delivered via: Chat UI / Slack / Email / Webhook
```

### Scheduling

Monitor and Detector agents use Synkora's existing `ScheduledTask` model. Frequency is configurable per tenant. Output is delivered to the configured channel (Slack, email, in-app). The HITL approval gate is available for any action the agent wants to take.

### Data Pipeline Requirements — Summary

Most agents require no pipeline. They query live APIs at run time via OAuth-connected tools.

| Category | Agent count | What it means |
|---|---|---|
| No pipeline | 28 agents | OAuth connector + existing tools. Query live. |
| Light store | 5 agents | One small DB table storing daily/hourly snapshots |
| Full pipeline | 3 agents | Continuous ingestion via Celery task into new DB tables |

The 3 full-pipeline agents are: Predictive Maintenance (micromobility), Demand Forecasting (micromobility), Seasonal Demand Forecaster (garments). All use the same pattern:

```
External source → Celery ingestion task → Synkora DB table → Agent queries at run time
```

Synkora already has `data_pipeline_tools.py` and Celery infrastructure. These 3 need new DB tables and one ingestion task per source — no new infrastructure.

---

## Industry 1: Micromobility

**Who pays:** Fleet operators, city mobility directors, e-scooter / e-bike sharing companies

**The unfair advantage:** Real-time fleet intelligence that a 10-person ops team physically cannot compute manually

**Existing tools in Synkora:** `micromobility_tools.py`, `micromobility_intelligence_tools.py`, `micromobility_event_tools.py`, `openmeteo_tools.py`, `events_tools.py`, `mapbox_tools.py`

**New integrations needed:** GBFS feed connector, hardware vendor telemetry APIs (Segway-Ninebot, Superpedestrian), commodity/maintenance cost DB tables

---

### Agent 1 — Fleet Revenue Optimizer

**Archetype:** Monitor + Oracle
**Schedule:** Hourly
**Pipeline:** Light store (hourly utilization snapshots)

**What it does:** Every hour calculates revenue-per-vehicle-per-zone, finds zones that are undersupplied during peak demand, and computes the projected revenue gain from rebalancing.

**End-to-end flow:**
```
1. Pull live vehicle locations + ride counts via GBFS feed
2. Pull weather forecast for next 4 hours (openmeteo_tools)
3. Pull local events happening today (events_tools)
4. Compare: expected demand per zone vs. current supply
5. Load historical utilization snapshots from DB
   to validate the pattern (same hour last week, last month)
6. Output:
   "Zone 4 (downtown) is 34% undersupplied.
    Moving 12 vehicles from Zone 9 projected to generate
    $840 additional revenue today.
    Approve rebalancing task? [Yes / No]"
7. On approval via HITL gate: create rebalancing work order
```

**Tools:** `micromobility_tools`, `openmeteo_tools`, `events_tools`, `scheduler_tools`

---

### Agent 2 — Predictive Maintenance Agent

**Archetype:** Detector + Analyst
**Schedule:** Daily scan, real-time alert on threshold breach
**Pipeline:** Full pipeline (telemetry continuously ingested per vehicle)

**What it does:** Watches battery drain curves, fault code patterns, and ride duration anomalies per vehicle. Flags vehicles trending toward failure before they break in the field.

**End-to-end flow:**
```
1. Celery task ingests telemetry per vehicle every 15 minutes:
   battery %, fault codes, trip count since last service,
   motor temperature, brake response
2. Agent runs daily across all vehicles:
   - Compare each vehicle's metrics to failure baseline in KB
   - Score: Green / Amber / Red
3. Red threshold breach fires immediate alert:
   "Vehicle #FL-4821: fault code E07 triggered 3 times
    in 48 hours. Historical pattern: 89% of vehicles with
    this signature fail within 6 days.
    Maintenance ticket created in Zendesk. [View ticket]"
4. Updates fleet availability count
```

**Tools:** `micromobility_intelligence_tools`, `database_tools`, `zendesk_tools`

---

### Agent 3 — Regulatory Compliance Agent

**Archetype:** Monitor
**Schedule:** Weekly report, real-time breach alert
**Pipeline:** None (KB for permit docs, live GBFS for fleet count)

**What it does:** Each city has its own fleet cap, geofencing rules, parking zones, and monthly reporting obligations. This agent tracks all of them and fires before a breach.

**End-to-end flow:**
```
1. KB holds all permit conditions per city (uploaded as PDFs)
2. Agent monitors daily:
   - Current fleet count per city vs. permit cap (live GBFS)
   - Vehicles parked in prohibited zones (mapbox_tools geofence check)
   - Upcoming report deadlines per city
3. Weekly summary:
   "Chicago permit: 847 vehicles deployed, cap 900. OK.
    Denver permit expires in 14 days. Renewal requires
    Q2 utilization report.
    Draft report is ready for your review. [Review]"
4. Generates compliance report from ride data automatically
```

**Tools:** `micromobility_event_tools`, `mapbox_tools`, `document_tools`, `scheduler_tools`, `kb_ingest_tools`

---

### Agent 4 — Unit Economics Agent

**Archetype:** Oracle
**Schedule:** On-demand
**Pipeline:** None

**What it does:** Answers the question every fleet operator asks but cannot easily calculate — what does each vehicle actually earn after all costs?

**End-to-end flow:**
```
User: "What's our true margin per vehicle this month?"

1. Pull ride revenue per vehicle from billing system
2. Pull maintenance cost per vehicle from service records
3. Pull battery replacement and charging cost
4. Pull rebalancing labor cost (hours × ops staff rate)
5. Pull depreciation (purchase price ÷ expected lifespan in rides)
6. Output:
   Average net margin per vehicle: $4.20/day

   Top 10% of vehicles: $9.80/day
   - Pattern: newer hardware, downtown zones, morning peak

   Bottom 10%: -$1.40/day
   - Pattern: 3+ years old, outer zones, high maintenance
   - Recommendation: retire or redeploy 14 vehicles
```

**Tools:** `database_tools`, `micromobility_intelligence_tools`, `file_analysis_tools`

---

### Agent 5 — Demand Forecasting Agent

**Archetype:** Analyst
**Schedule:** Nightly at 11pm
**Pipeline:** Full pipeline (historical ride data by zone and time slot)

**What it does:** Pre-positions fleet for tomorrow's demand peaks before the day starts, so ops teams act proactively instead of reactively.

**End-to-end flow:**
```
Runs nightly at 11pm:
1. Pull tomorrow's weather forecast (openmeteo_tools)
2. Pull tomorrow's local events: concerts, games, conferences
3. Query historical ride demand for same day-type + weather
   pattern from DB (e.g., "Friday + rain + no major event")
4. Generate zone-by-zone demand forecast for
   6am / 9am / 12pm / 5pm / 8pm slots
5. Output pre-positioning plan sent to ops team via Slack:
   "Tomorrow's forecast — June 13 (Friday, clear, 24C)

    Action needed by 6am:
    - Stadium district: move 40 vehicles in.
      Forecast demand: 180 rides. Current supply: 12.
    - University zone: reduce by 20.
      Low demand expected (semester break).

    Expected revenue impact of pre-positioning: +$2,100"
```

**Tools:** `openmeteo_tools`, `events_tools`, `micromobility_tools`, `slack_tools`

---

## Industry 2: Startup

**Who pays:** Founders, CTOs, growth-stage startups ($1M–$50M ARR)

**The unfair advantage:** Surfaces the founder's own blind spots — the blockers, leaks, and risks they are too close to see

**Existing tools in Synkora:** `jira_tools`, `slack_tools`, `github_repo_tools`, `google_calendar_tools`, `zoho_crm_tools`, `email_tools`, `document_tools`, `database_tools`, `file_analysis_tools`, `web_tools`, `news_tools`, `clickup_tools`

**New integrations needed:** Stripe connector, QuickBooks/Xero connector, Brex/Ramp bank feed connector, Linear connector, product analytics connector (Mixpanel / Amplitude / PostHog)

---

### Agent 1 — Founder Bottleneck Agent

**Archetype:** Monitor
**Schedule:** Every Monday morning
**Pipeline:** None

**What it does:** Measures what percentage of company execution is blocked waiting for the founder. Makes the invisible visible.

**End-to-end flow:**
```
Runs every Monday at 8am:
1. Scan Jira/Linear for tickets assigned to founder
   or with status "Waiting for [founder]" open > 5 days
2. Scan Slack for messages mentioning founder
   that are unanswered > 24h in work channels
3. Scan GitHub for PRs awaiting founder review > 48h
4. Check Google Calendar: what % of team meetings
   require founder presence
5. Output sent to founder via Slack:
   "This week: 41% of active work is blocked on you.

    Top blockers:
    - 3 engineering decisions (avg wait: 6 days)
    - 2 contract approvals (avg wait: 9 days)
    - 5 unanswered Slack threads from sales team

    A 90-minute decision sprint this morning clears all of it."
```

**Tools:** `jira_tools`, `slack_tools`, `github_repo_tools`, `google_calendar_tools`

---

### Agent 2 — Runway Intelligence Agent

**Archetype:** Oracle
**Schedule:** On-demand + weekly automated snapshot
**Pipeline:** None

**What it does:** Answers the real runway question under different hiring and spend scenarios. Not a spreadsheet — a live calculation from connected systems.

**End-to-end flow:**
```
User: "If we hire 2 engineers next month, when do we hit zero?"

1. Pull current bank balance from bank feed
2. Pull last 3 months burn rate from accounting system
3. Pull confirmed MRR + pipeline from CRM
4. Pull upcoming committed expenses (payroll, AWS, vendors)
5. Model the scenario: +2 engineers at market rate
6. Output:
   "Current runway: 14 months.

    With 2 engineers hired August 1: 9.5 months.

    To maintain 12-month runway you need $480K ARR growth
    by October. Current trajectory: $310K.
    Gap: $170K ARR (roughly 14 new customers at your ACV)."
```

**Tools:** `database_tools`, `zoho_crm_tools`, `email_tools`
**New integrations:** Stripe, QuickBooks/Xero, bank feed

---

### Agent 3 — Churn Signal Detector

**Archetype:** Detector
**Schedule:** Daily
**Pipeline:** Light store (daily usage snapshots per account for trend comparison)

**What it does:** Finds customers who are about to churn 30–60 days before they cancel — when you can still save them.

**End-to-end flow:**
```
Runs daily:
1. Pull product usage per account from analytics platform:
   login frequency, feature depth, session count
2. Compare to each account's own baseline (stored snapshots)
   to detect degradation trends
3. Pull support ticket volume + sentiment per account
4. Pull email engagement rate for each account's main contact
5. Pull contract renewal dates from CRM
6. Score each account: Healthy / At Risk / Critical
7. Critical accounts fire immediate Slack alert:
   "Acme Corp [renews in 45 days]:
    - Logins dropped 60% over 3 weeks
    - 4 support tickets this week (baseline: 0.5/week)
    - Last email to CSM unanswered 8 days

    Recommended action: founder-level call this week."
```

**Tools:** `database_tools`, `email_tools`, `slack_tools`, `zoho_crm_tools`
**New integration:** Product analytics connector (Mixpanel/Amplitude/PostHog)

---

### Agent 4 — Board Deck Integrity Agent

**Archetype:** Analyst
**Trigger:** Document upload
**Pipeline:** None

**What it does:** Reviews board decks for unsupported claims, number inconsistencies, and optimistic assumptions without historical precedent — before the board sees them.

**End-to-end flow:**
```
Founder uploads draft board deck (PDF or PPTX):
1. Extract all numerical claims and forward-looking statements
2. Cross-check each claim against live connected data:
   - ARR figures vs. Stripe
   - Pipeline vs. CRM
   - Engineering velocity vs. GitHub
3. Flag three categories:
   a) Unsupported claims (no connected data source)
   b) Number inconsistencies across slides
   c) Optimistic assumptions without precedent
4. Return annotated findings:
   "Slide 7: Revenue forecast assumes 40% MoM growth.
    Your actual MoM growth last 6 months: avg 12%.
    Either justify the acceleration or revise the number.

    Slide 4 ARR: $2.4M
    Slide 11 ARR: $2.1M
    These do not match. Confirm which is correct."
```

**Tools:** `document_tools`, `file_analysis_tools`, `database_tools`

---

### Agent 5 — Weak Signal Detector

**Archetype:** Monitor
**Schedule:** Weekly (Friday)
**Pipeline:** None

**What it does:** Monitors support tickets, sales call notes, Slack, and public channels for patterns appearing across multiple sources simultaneously — the early signals of both problems and opportunities.

**End-to-end flow:**
```
Runs every Friday:
1. Pull all support tickets from the week, extract themes
2. Pull sales call notes from CRM, extract objections and requests
3. Monitor competitor job postings (signals strategic moves)
4. Monitor industry news for regulatory or market changes
5. Cross-reference: same theme in 3+ sources = signal
6. Weekly digest:
   "This week's weak signals:

    HIGH — 'API rate limits' in 11 support tickets
    (up from 2 last month). May be blocking expansion use cases.

    MEDIUM — 3 enterprise prospects asked about SSO.
    Competitor launched SSO last quarter.

    WATCH — Competitor posted 4 enterprise sales roles this week.
    Possible market segment move."
```

**Tools:** `email_tools`, `web_tools`, `news_tools`, `zoho_crm_tools`, `slack_tools`

---

## Industry 3: SME (Small-Medium Enterprise)

**Who pays:** Business owners and COOs of 10–500 person businesses across any sector

**The unfair advantage:** Finds money hiding in plain sight that no one has time to look for

**Existing tools in Synkora:** `email_tools`, `document_tools`, `contract_analysis_tools`, `zoho_crm_tools`, `database_tools`, `web_tools`, `news_tools`

**New integrations needed:** QuickBooks connector, Xero connector, bank feed connector

---

### Agent 1 — Revenue Leak Agent

**Archetype:** Detector
**Schedule:** Weekly (Monday)
**Pipeline:** None

**What it does:** Scans every revenue stream for money that should have come in but did not — unbilled work, expired discounts still applied, overdue invoices, abandoned quotes.

**End-to-end flow:**
```
Runs every Monday:
1. Pull all invoices from accounting system
2. Pull all contracts and billing schedules from document store
3. Pull actual payments received
4. Cross-check:
   a) Contract milestones vs. invoices raised
      (anything delivered but not billed?)
   b) Invoices past due > 30 days
   c) Customers on discounts: have any discount periods expired?
   d) Recurring services delivered but not invoiced
   e) Quotes sent > 14 days ago with no follow-up
5. Output:
   "Revenue at risk this week: $34,200

    Breakdown:
    - 3 invoices overdue > 30 days: $18,400
    - 2 expired discounts still being applied: $4,800/month
    - 1 project milestone unbilled: $11,000

    Draft follow-up emails? [Yes / No]"
```

**Tools:** `document_tools`, `contract_analysis_tools`, `email_tools`, `database_tools`
**New integrations:** QuickBooks, Xero

---

### Agent 2 — Cash Flow Oracle

**Archetype:** Oracle
**Schedule:** On-demand
**Pipeline:** None

**What it does:** Answers the question every SME owner fears: will I make payroll next month? Live calculation, not a spreadsheet.

**End-to-end flow:**
```
User: "What does cash look like in 60 days?"

1. Pull current bank balance
2. Pull confirmed receivables (invoices sent + each client's
   historical payment probability based on past behaviour)
3. Pull committed payables (payroll, rent, subscriptions,
   supplier payments scheduled)
4. Model three scenarios: best / expected / worst case
5. Output:
   "60-day cash forecast:

    Best case:  +$42K (all receivables pay on time)
    Expected:   +$8K  (67% on-time rate applied)
    Worst case: -$14K (3 large clients pay late as usual)

    Alert: Apex Corp has paid late 4 of last 4 invoices.
    Their $22K invoice is due July 15.
    Recommend contacting them now, not on July 16."
```

**Tools:** `database_tools`, `document_tools`, `email_tools`
**New integrations:** QuickBooks/Xero, bank feed

---

### Agent 3 — Vendor Risk Agent

**Archetype:** Monitor
**Schedule:** Monthly
**Pipeline:** None

**What it does:** Maps every vendor the business depends on and monitors them for signs of failure — before a delivery crisis hits.

**End-to-end flow:**
```
Runs monthly:
1. Pull all vendors paid in last 12 months from accounting
2. For each vendor above $5K/year:
   a) Search news for financial distress signals (web_tools)
   b) Check review sites for service quality changes
   c) Check: is there an identified alternative supplier?
3. Calculate concentration risk:
   what % of operations depends on this single vendor?
4. Monthly report:
   "Vendor Risk — June:

    Critical (no alternative identified):
    - Cloud hosting: 100% dependency, no disaster recovery plan
    - Payroll software: 100% dependency

    Warning signals:
    - Supplier X: 3 recent reviews mention delivery delays

    Recommended actions:
    1. Identify backup cloud provider (2 weeks)
    2. Call Supplier X to understand delay root cause"
```

**Tools:** `web_tools`, `news_tools`, `database_tools`

---

### Agent 4 — Opportunity Detector

**Archetype:** Monitor
**Schedule:** Weekly
**Pipeline:** None

**What it does:** Finds revenue opportunities the owner is too busy to notice — competitor moves, lapsed customers, unmet customer needs, market shifts.

**End-to-end flow:**
```
Runs weekly:
1. Scan industry news for market shifts (news_tools)
2. Scan competitor websites for pricing or product changes
3. Pull customer support and email themes for unmet needs
4. Check: which past customers have not bought in 6+ months
5. Weekly digest:
   "3 opportunities this week:

    1. Competitor X raised prices 20%.
       You are now $40/month cheaper. Worth promoting now.

    2. 6 customers mentioned 'mobile app' in support emails
       this month (up from 0 last quarter).

    3. 14 lapsed customers — last purchase 180+ days ago.
       Combined previous spend: $28K/year.
       Draft win-back campaign? [Yes / No]"
```

**Tools:** `web_tools`, `news_tools`, `email_tools`, `database_tools`, `zoho_crm_tools`

---

## Industry 4: Garments / Apparel Manufacturing

**Who pays:** Procurement directors, production managers, brand owners

**The unfair advantage:** Supply chain intelligence at a speed and depth no human team can match across dozens of active orders and suppliers simultaneously

**Existing tools in Synkora:** `database_tools`, `web_tools`, `document_tools`, `contract_analysis_tools`, `email_tools`, `news_tools`, `file_analysis_tools`, `kb_ingest_tools`

**New integrations needed:** ERP connector (SAP Business One, Oracle NetSuite), commodity price API (World Bank, Quandl), logistics tracking API (FedEx/DHL/freight forwarders)

---

### Agent 1 — Supplier Intelligence Agent

**Archetype:** Monitor + Oracle
**Schedule:** Weekly report, on-demand query
**Pipeline:** None (ERP queried live)

**What it does:** Tracks every supplier's delivery and quality performance in real time and identifies which suppliers are trending toward failure before a shipment is late.

**End-to-end flow:**
```
Runs weekly + available on-demand:
1. Pull order history per supplier from ERP:
   - Planned delivery date vs. actual delivery date
   - Defect rate per batch
   - Response time to queries and change requests
2. Calculate trend per supplier:
   on-time rate last 12 months vs. last 3 months
3. Search news for supplier company name:
   factory incidents, labor disputes, financial issues
4. Weekly output:
   "Supplier Watch — Week 24:

    Degrading: Supplier B
    On-time rate: 91% (12 months) → 74% (last 8 weeks)
    Last 3 orders: all 3–5 days late.
    Root cause unknown. Recommend direct call this week.

    Critical: Supplier F
    2 news articles in last 30 days re factory inspection
    failures in Vietnam. Risk to Q3 orders."
```

**Tools:** `database_tools`, `web_tools`, `news_tools`, `email_tools`
**New integration:** ERP connector

---

### Agent 2 — Material Cost Radar

**Archetype:** Monitor
**Schedule:** Daily
**Pipeline:** None (commodity APIs are live)

**What it does:** Watches commodity markets for your specific materials and tells you when locking a price today saves money versus waiting.

**End-to-end flow:**
```
Runs daily:
1. Pull current + 30-day commodity prices:
   cotton, polyester, wool, viscose, zippers, thread
   (via commodity price API)
2. Pull your upcoming purchase orders:
   materials required, quantities, planned order dates
3. Compare current price vs. your 12-month average
   purchase price per material
4. When meaningful opportunity detected:
   "Cotton (Ring-spun 30s) is 12% below your
    12-month average purchase price.

    You have 3 orders totalling 45,000kg due in Q4.
    Locking price today vs. waiting at current trajectory
    = estimated $18,600 in savings.

    Forward contract available through Supplier A until Friday.
    Proceed? [Yes / No]"
```

**New integration:** Commodity price API

---

### Agent 3 — Production Timeline Guardian

**Archetype:** Monitor
**Schedule:** Every morning
**Pipeline:** None (ERP queried live)

**What it does:** Manages the critical path across all active production orders and fires before a delay becomes a missed ship date — when there is still time to act.

**End-to-end flow:**
```
Runs every morning:
1. Pull all active orders from ERP:
   order details, customer, ship date, current stage,
   planned vs. actual completion per stage
2. For each order: calculate projected completion date
   based on remaining stages + current completion rate
3. Flag orders where projected date > ship date
4. For each flagged order, calculate options with costs:
   "Order #PO-4421 for Brand X:

    Current stage: Cutting (2 days behind schedule)
    Projected completion: July 22
    Ship date: July 19
    Gap: 3 days

    Options:
    A) Overtime in sewing stage — cost $1,200, closes gap
    B) Negotiate 3-day extension with Brand X
    C) Split shipment — ship ready units July 19,
       balance July 24 (requires Brand X approval)"
```

**Tools:** `database_tools`, `email_tools`, `scheduler_tools`
**New integration:** ERP connector

---

### Agent 4 — Quality Pattern Agent

**Archetype:** Analyst
**Trigger:** Defect rate threshold breach on an order
**Pipeline:** Light store (quality inspection records synced from ERP for cross-batch correlation)

**What it does:** When a defect spike occurs, finds the root cause by correlating supplier, material batch, factory, production line, and shift data across historical records.

**End-to-end flow:**
```
Triggered when defect rate for an order exceeds threshold:
1. Pull full details for the defective batch:
   supplier, material batch/lot number, factory,
   production line, shift, defect type and description
2. Query historical defect records in KB/DB
3. Find correlations across all dimensions
4. Output root cause hypothesis:
   "Pattern detected:

    67% of pilling defects in the last 6 months:
    Supplier C polyester blend + Factory 2 Line B

    Same material from Supplier C on Factory 1 Line A:
    3% defect rate (normal).

    Hypothesis: Line B has a tension calibration issue,
    not a material issue.

    Recommended: Inspect Line B machinery before the next
    Supplier C material run. Do not switch supplier yet."
```

**Tools:** `database_tools`, `file_analysis_tools`, `kb_ingest_tools`

---

### Agent 5 — Seasonal Demand Forecaster

**Archetype:** Analyst
**Schedule:** Quarterly (before each production planning cycle)
**Pipeline:** Full pipeline (2–3 years of sell-through data by SKU/category)

**What it does:** Combines historical sell-through data, trend signals, and external inputs to recommend production quantities per style — replacing gut-feel forecasting.

**End-to-end flow:**
```
Runs before each planning cycle:
1. Query historical sell-through data from DB:
   units sold per style/category per season
2. Pull social trend signals (search volume, runway reports,
   social mentions) via web_tools
3. Pull wholesale order book data from ERP
4. Pull weather forecasts for key selling regions
   (relevant for seasonal categories)
5. Calculate recommended production quantities per style:
   "Q4 Production Recommendations:

    Style A (wool coat): Increase 18% vs. last year.
    Basis: sell-through 94% last year, social search
    up 31%, early wholesale orders ahead of last year.

    Style B (linen shirt): Reduce 22% vs. last year.
    Basis: category trending down for 2 consecutive seasons,
    4 wholesale accounts did not reorder.

    Confidence scores attached to each recommendation."
```

**Tools:** `database_tools`, `web_tools`, `file_analysis_tools`
**New integration:** ERP connector for sell-through history

---

## Industry 5: NGO / Non-profit

**Who pays:** Executive Directors, Program Directors at organizations with $500K–$50M budgets

**The unfair advantage:** Turns scarce staff time into 10x capacity on grant writing, impact reporting, and donor retention — the three activities that determine NGO survival

**Existing tools in Synkora:** `email_tools`, `document_tools`, `google_calendar_tools`, `database_tools`, `followup_tools`, `web_tools`, `kb_ingest_tools`, `google_drive_tools`

**New integrations needed:** Salesforce NPSP connector, Bloomerang connector, Candid/GrantStation API (grant discovery), Google Sheets connector (for field data collection)

---

### Agent 1 — Grant Intelligence Agent

**Archetype:** Monitor + Assistant
**Schedule:** Weekly scan, on-demand drafting
**Pipeline:** None (KB for past grants, web search for new ones)

**What it does:** Finds grants the NGO should apply for and drafts the first version of the application using past successful grants as a template.

**End-to-end flow:**
```
Runs weekly:
1. Pull NGO mission, focus areas, past award history from KB
2. Search grant databases for new opportunities
   matching the profile (web_tools + Candid API)
3. Score each opportunity:
   - Mission fit (% alignment with stated focus areas)
   - Deadline and lead time available
   - Estimated award size
   - Past relationship with this funder (if any)
4. For top 3 matches: draft application outline
   using past successful grants from KB as templates
5. Weekly digest:
   "3 new grants match your profile:

    1. MacArthur Foundation — Community Safety ($150K)
       Deadline: Aug 30. Fit: 94%.
       Draft outline ready. [Review]

    2. City of Chicago — Youth Programs ($40K)
       Deadline: July 15. Fit: 78%.
       You won this grant in 2023.
       Use 2023 application as base? [Yes / No]"
```

**Tools:** `web_tools`, `document_tools`, `kb_ingest_tools`, `email_tools`
**New integration:** Candid/GrantStation API

---

### Agent 2 — Impact Measurement Agent

**Archetype:** Analyst + Assistant
**Schedule:** Monthly, or triggered by report deadline
**Pipeline:** None (program data queried live from connected source)

**What it does:** Collects program data from field staff and generates funder-ready impact reports automatically — turning weeks of manual work into hours.

**End-to-end flow:**
```
Monthly or on report deadline:
1. Pull program data from connected source:
   Google Sheets, database, or forms submissions
   (beneficiaries served, outcomes recorded, expenses)
2. Calculate standardized impact metrics:
   - Beneficiaries served: target vs. actual
   - Cost per beneficiary
   - Outcome rates where outcome data exists
   - Geographic distribution
3. Compare to grant targets and KPIs stored in KB
4. Detect gaps: flag missing data from field sites
   "Q2 data missing from 3 of 8 program sites.
    Sending reminder to site coordinators now."
5. Generate draft report in funder's required format
   from KB template
6. Output: publication-ready draft for staff review
   and approval before submission
```

**Tools:** `document_tools`, `database_tools`, `email_tools`, `google_drive_tools`

---

### Agent 3 — Donor Retention Agent

**Archetype:** Detector + Assistant
**Schedule:** Weekly
**Pipeline:** None (CRM queried live)

**What it does:** Identifies donors who are about to lapse and suggests the right re-engagement action before they stop giving — when a personal touch still works.

**End-to-end flow:**
```
Runs weekly:
1. Pull all donors from CRM: last gift date, gift history,
   email engagement (opens, clicks), events attended
2. Score each donor on lapse risk:
   - Days since last gift vs. their historical giving cadence
   - Email engagement trend (declining = risk signal)
   - Upcoming anniversary of first gift (high-value moment)
   - Whether they have been personally thanked recently
3. Weekly action list:
   "Donor Retention — This Week:

    High risk (act within 2 weeks):
    - Sarah M: Gave annually for 5 years.
      14 months since last gift. Last 3 emails unopened.
      Recommended: Personal call from Executive Director.

    Opportunity:
    - James K: 1-year anniversary of first gift on July 18.
      Draft personalized impact story for him? [Yes / No]"
4. Draft outreach emails or call scripts on request
```

**Tools:** `email_tools`, `database_tools`, `followup_tools`, `google_calendar_tools`
**New integration:** Salesforce NPSP or Bloomerang connector

---

### Agent 4 — Compliance Monitor Agent

**Archetype:** Monitor
**Schedule:** Weekly
**Pipeline:** None (KB for grant terms, accounting system for spend data)

**What it does:** Tracks every active grant's reporting deadlines and compliance requirements simultaneously — so no deadline is missed and no grant money is at risk.

**End-to-end flow:**
```
Runs every Monday:
1. Pull all active grants from KB:
   funder, amount, grant period, reporting schedule,
   allowable expense categories, prohibited activities
2. Check upcoming report deadlines in next 60 days
3. Check: is spend on pace with grant budget?
   (underspend risks clawback; overspend is a violation)
4. Check: are expenses being coded to correct grant lines?
5. Monday briefing:
   "Grant Compliance — Week 24:

    Deadlines:
    - Ford Foundation Q2 report: due July 1 (12 days)
      Required: beneficiary counts + expenditure report
      Status: beneficiary data ready.
      Missing: 2 May invoices from finance team.
      [Assign to: Finance / Due: June 26]

    Budget alert:
    - NEA grant: 78% spent, 47% of period remaining.
      Projected underspend: $12K. Allowable carry-over: $5K.
      Risk: $7K clawback.
      Options: [Accelerate spend] [Request budget modification]"
```

**Tools:** `database_tools`, `document_tools`, `email_tools`, `scheduler_tools`

---

## Industry 6: Photography Studios

**Who pays:** Studio owners, commercial photographers, boutique agencies ($100K–$2M revenue)

**The unfair advantage:** Turns a solo photographer into a business that runs like a 5-person agency — leads never go cold, jobs never go unbilled, licenses never expire unnoticed

**Existing tools in Synkora:** `gmail_tools`, `google_calendar_tools`, `google_drive_tools`, `email_tools`, `openmeteo_tools`, `mapbox_tools`, `document_tools`, `database_tools`, `followup_tools`

**New integrations needed:** Studio management software connector (Studio Ninja, HoneyBook), QuickBooks connector, TinEye / Google Reverse Image Search API

---

### Agent 1 — Lead Conversion Agent

**Archetype:** Monitor + Assistant
**Trigger:** New inquiry arrives (email or contact form)
**Pipeline:** None

**What it does:** Responds to every inquiry within 15 minutes, follows up automatically, and ensures no lead goes cold. Photographers lose 40–60% of inquiries to slow response.

**End-to-end flow:**
```
Triggered on new inquiry email or form submission:
1. Extract from inquiry: event type, date, location,
   budget signals, urgency
2. Check calendar availability for the requested date
3. Score lead: budget fit, lead time, event type alignment
4. Within 15 minutes, send personalized response:
   - Confirms availability (or nearest available date)
   - Links to relevant portfolio section for the event type
   - Includes starting price range
   - Proposes 2–3 discovery call time slots

Follow-up sequence:
- No response in 48h: gentle follow-up
- No response in 7 days: final follow-up + mark cold in CRM

Weekly report:
"Lead pipeline this week:
 12 inquiries received.
 Avg response time: 12 minutes (industry avg: 4 hours).
 Conversion to consultation call: 6 of 12 (50%)."
```

**Tools:** `gmail_tools`, `google_calendar_tools`, `email_tools`, `followup_tools`

---

### Agent 2 — Shoot Intelligence Agent

**Archetype:** Assistant
**Trigger:** Booking confirmed
**Pipeline:** None

**What it does:** Collects a complete creative brief from the client via a conversational flow and produces a ready-to-execute shoot plan — no back-and-forth email threads.

**End-to-end flow:**
```
Once booking is confirmed, client receives a brief
collection chat link:

Agent collects (one question at a time):
- Purpose and intended use of the photos
- Subject and target audience
- Style and mood (with visual reference examples)
- Location preference and backup option
- Must-have shots and any restrictions

Agent then produces two outputs:

1. Photographer package:
   - Prioritized shot list
   - Equipment checklist for this shoot type
   - Location notes and parking info (mapbox_tools)
   - Permit requirements for the location if public space
   - Weather forecast for shoot date + backup date
     recommendation (openmeteo_tools)

2. Client prep guide:
   - What to wear, what to bring
   - Arrival time and location pin
   - What to expect on the day

Both delivered via email to photographer and client.
```

**Tools:** `gmail_tools`, `google_calendar_tools`, `openmeteo_tools`, `mapbox_tools`, `document_tools`

---

### Agent 3 — Delivery Pipeline Agent

**Archetype:** Monitor
**Schedule:** Daily
**Pipeline:** None

**What it does:** Tracks every active shoot from delivery commitment to gallery published, fires alerts before deadlines are missed, and sends proactive client updates automatically.

**End-to-end flow:**
```
Runs daily:
1. Pull all booked shoots from calendar:
   shoot date, promised delivery date, current status
2. Flag shoots at risk:
   - Shoot completed but editing not started (3+ days after)
   - Editing in progress but pace won't meet delivery date
3. Send automatic proactive client update
   when editing begins (no photographer action required):
   "Hi Sarah — your gallery from Saturday's session
    is in editing. You will receive your preview link
    by Thursday, July 18."

4. When delivery is overdue:
   - Alert photographer with client name + days overdue
   - Draft apology + revised timeline email for review

Weekly summary to photographer:
"Delivery pipeline: 4 active jobs.
 On track: 3. At risk: 1 (Jones wedding — 2 days behind).
 Suggested action: [View]"
```

**Tools:** `gmail_tools`, `google_calendar_tools`, `google_drive_tools`, `scheduler_tools`

---

### Agent 4 — License Revenue Agent

**Archetype:** Monitor + Detector
**Schedule:** Weekly
**Pipeline:** None (KB for license records)

**What it does:** Tracks all image licenses for expiry and renewal, and finds unlicensed usage of your images online before it becomes a write-off.

**End-to-end flow:**
```
Runs weekly:
1. Pull all active licenses from KB:
   client, images covered, usage rights, expiry date, fee
2. Flag licenses expiring in 60 days:
   "Nike campaign images (15 photos):
    License expires Aug 15. Annual value: $4,200.
    Draft renewal email? [Yes / No]"

3. Run reverse image search on key portfolio images
   to detect unlicensed usage online (TinEye API)
4. If unlicensed usage found:
   "Image #Studio-0441 found used on [domain].
    No license in your records for this image + client.
    Options: [Send DMCA notice] [Send licensing offer]"

Monthly summary:
"License revenue secured this month: $8,400
 Renewals due in 60 days: $12,600
 Potential unlicensed usage detected: 2 instances"
```

**Tools:** `web_tools`, `email_tools`, `database_tools`, `document_tools`
**New integration:** TinEye API

---

### Agent 5 — Studio P&L Agent

**Archetype:** Oracle
**Schedule:** On-demand + monthly summary
**Pipeline:** None

**What it does:** Tells the photographer which type of work actually makes money after all real costs — so they can stop taking low-margin work and fill the calendar with high-margin jobs.

**End-to-end flow:**
```
User: "Which shoot types are most profitable?"

1. Pull all invoices by shoot type from QuickBooks:
   wedding, corporate, portrait, commercial, event
2. Pull time per shoot type from calendar:
   prep time + shoot hours + editing hours + delivery time
3. Pull direct costs per shoot type:
   equipment rental, travel, second shooter fees
4. Calculate effective hourly rate per shoot type
5. Output:
   "Profitability by shoot type (last 12 months):

    Commercial product:   $340/hr effective rate
    Corporate headshot:   $280/hr
    Wedding:              $110/hr (avg 14-hour days incl. editing)
    Family portrait:      $95/hr

    Key insight: Replacing 4 weddings this year with
    2 commercial clients generates the same revenue
    in 60% fewer hours."
```

**Tools:** `database_tools`, `google_calendar_tools`, `file_analysis_tools`
**New integration:** QuickBooks connector

---

## Industry 7: Government / Public Sector

**Who pays:** Department heads, agency CIOs, city governments, public sector procurement offices

**The unfair advantage:** Cross-department visibility that no individual inside government has today — service failures, budget drift, procurement anomalies, and public sentiment surfaced before they become crises

**Existing tools in Synkora:** `database_tools`, `document_tools`, `email_tools`, `web_tools`, `news_tools`, `twitter_tools`, `scheduler_tools`, `kb_ingest_tools`, `file_analysis_tools`

**New integrations needed:** SAP Public Sector connector, Tyler Technologies connector, procurement portal connectors, public records API

---

### Agent 1 — Service Delivery Monitor

**Archetype:** Monitor
**Schedule:** Daily
**Pipeline:** None (department databases queried live)

**What it does:** Tracks all public-facing service metrics in real time and surfaces failures before they become constituent complaints or news stories.

**End-to-end flow:**
```
Runs daily:
1. Pull service metrics from each department's systems:
   - Permit processing: average days to approval, backlog count
   - 311 calls: average response time, open tickets
   - Benefits processing: pending applications, avg days
   - Road repair: open requests, avg days to close
2. Compare each metric against SLA targets
   and 30-day rolling average
3. Flag services that are degrading:
   "Permit Processing — June 12:

    Average days to approval: 18 (SLA target: 10)
    Backlog: 847 applications (up 34% in 3 weeks)
    Known cause: 2 vacancies in zoning review

    Constituent complaint risk: HIGH
    Based on historical patterns, local media coverage
    typically follows 2–3 weeks after backlog reaches
    current levels.

    Recommended: Brief city manager today."
4. Daily summary emailed to department head + city manager
```

**Tools:** `database_tools`, `email_tools`, `scheduler_tools`
**New integrations:** SAP Public Sector, Tyler Technologies

---

### Agent 2 — Budget Intelligence Agent

**Archetype:** Oracle + Monitor
**Schedule:** Weekly automated report, on-demand query
**Pipeline:** None (financial system queried live)

**What it does:** Real-time spend vs. budget with early warning on both overspend trajectories and underspend risk (departments lose unspent funds at fiscal year end).

**End-to-end flow:**
```
On-demand: "Where are we on the infrastructure budget?"
1. Pull current spend by category from financial system
2. Calculate pace: spend to date ÷ fiscal days elapsed
3. Project year-end position per category

Weekly automated report:
"Budget Alert — Week 24:

 Overspend risk:
 - IT contracts: 71% spent, 42% of year remaining.
   Projected overage: $340K.
   Contracts approaching renewal: [list]

 Underspend risk (use-it-or-lose-it):
 - Parks capital: 18% spent, 58% of year remaining.
   $2.1M must be committed by Sept 30 or reverts to general fund.
   Shovel-ready projects available: [list]

 On track: 14 of 18 budget lines"
```

**Tools:** `database_tools`, `document_tools`, `email_tools`
**New integrations:** SAP Public Sector, Tyler Technologies

---

### Agent 3 — Procurement Risk Agent

**Archetype:** Analyst + Detector
**Schedule:** Monthly
**Pipeline:** None (procurement database queried live)

**What it does:** Analyzes the full procurement pipeline for concentration risk, split-purchasing patterns, sole-source anomalies, and upcoming contracts that need competitive bidding.

**End-to-end flow:**
```
Runs monthly:
1. Pull all purchase orders and contracts from
   procurement system
2. Analyze:
   a) Vendor concentration:
      % of total spend going to top 5 vendors
   b) Split purchasing detection:
      orders just below approval thresholds
      (statistically abnormal clustering = risk signal)
   c) Sole-source justification completeness:
      are required documents present and adequate?
   d) Contract expiries:
      which contracts require competitive bidding before renewal?
3. Output:
   "Procurement Risk — June:

    Pattern alert:
    Vendor XYZ received 14 purchase orders between
    $24,500–$24,900 in Q2. Approval threshold: $25K.
    Probability this clustering is random: <2%.
    Recommend: Internal procurement audit review.

    Concentration:
    68% of IT spend to 2 vendors.
    Both contracts expire Q4.
    Recommend: Begin RFP process by July 15
    to meet 90-day procurement timeline."
```

**Tools:** `database_tools`, `document_tools`, `file_analysis_tools`

---

### Agent 4 — Policy Compliance Monitor

**Archetype:** Monitor
**Schedule:** Weekly
**Pipeline:** None (KB for policies, database for activity data)

**What it does:** Watches department activities against applicable regulations and internal policies, flags deviations before they become audit findings or liabilities.

**End-to-end flow:**
```
Runs weekly:
1. KB contains: applicable regulations, department policies,
   prior audit findings, compliance checklists
2. Pull current department activity data:
   contracts signed, decisions recorded, processes documented
3. Check against policy requirements:
   - Were required approvals obtained at each threshold?
   - Were mandatory public notices published on time?
   - Are contractor insurance certificates current?
   - Are document retention requirements being followed?
4. Weekly compliance briefing:
   "Compliance Flags — Week 24:

    High: 3 contracts over $100K missing insurance certificates.
    Action required before July 15 audit.

    Medium: Public notice for zoning variance posted
    18 days before hearing. Required minimum: 20 days.
    Document corrective action.

    Low: 2 required staff certifications expire within 30 days.
    [Assign renewal reminders]"
```

**Tools:** `database_tools`, `document_tools`, `kb_ingest_tools`, `email_tools`

---

### Agent 5 — Public Sentiment Agent

**Archetype:** Monitor
**Schedule:** Daily
**Pipeline:** Light store (daily mention volume counts stored for trend comparison)

**What it does:** Monitors public channels for constituent concerns emerging before they become crises — giving government 1–3 weeks of advance warning to respond proactively instead of reactively.

**End-to-end flow:**
```
Runs daily:
1. Monitor Twitter/X for city mentions + relevant hashtags
2. Monitor local news for city-related stories (news_tools)
3. Monitor public forums and community boards via web scraping
4. Pull 311 complaint categories for theme trends
5. Detect emerging issues:
   volume spike + negative sentiment = flag for review
6. Store daily mention counts per topic in DB
   for week-over-week trend calculation
7. Daily digest to city manager:
   "Public Sentiment — June 12:

    Emerging issue (act within 7–10 days):
    'Flooding near Oak Street' — 34 social mentions this week
    (up from 3 last week). Sentiment: 91% negative.
    311 complaints filed: 8.

    Historical pattern: this issue type generates local
    news coverage when weekly mentions exceed 50.
    Current trajectory: 3 days away.

    Recommended: Proactive DPW statement + visible response
    before this reaches media."
```

**Tools:** `twitter_tools`, `news_tools`, `web_tools`, `database_tools`

---

## Industry 8: Law Firms / Legal

**Who pays:** Law firm partners, managing partners, general counsels at corporations, legal operations directors

**The unfair advantage:** Legal work is document-heavy, deadline-driven, and billing-intensive — three areas where agents provide massive leverage that no attorney has time to do manually across a full caseload

**Existing tools in Synkora:** `document_tools`, `contract_analysis_tools`, `email_tools`, `database_tools`, `web_tools`, `news_tools`, `google_calendar_tools`, `scheduler_tools`, `kb_ingest_tools`, `file_analysis_tools`

**New integrations needed:** Practice management software connector (Clio, MyCase, PracticePanther), legal research API (Westlaw, LexisNexis, or Fastcase), PACER federal court filing connector, e-billing system connector (TimeSolv, Bill4Time)

---

### Agent 1 — Billable Hours Recovery Agent

**Archetype:** Detector
**Schedule:** Weekly
**Pipeline:** None (billing system queried live)

**What it does:** Finds work that was done but never billed — the single largest revenue leak in most law firms. Industry estimates put unbilled work at 10–20% of total time recorded.

**End-to-end flow:**
```
Runs weekly:
1. Pull all time entries from billing system:
   time recorded, matter, attorney, billable/non-billable flag
2. Pull all invoices sent for the same period
3. Cross-check:
   a) Time entries marked billable but not yet invoiced
      and matter is active (not waiting on client approval)
   b) Write-offs above threshold without partner sign-off
   c) Flat-fee matters where recorded hours far exceed
      the fee (signals underpricing for future engagements)
   d) Matters with no time recorded in 30+ days
      but still marked active (forgotten open matters)
4. Output:
   "Billing Recovery — Week 24:

    Unbilled billable time: $28,400 across 6 matters
    - Smith v. Johnson: $12,200 recorded, not invoiced (34 days)
    - Acme contract review: $6,800 recorded, not invoiced

    Write-offs without approval: $4,100
    Flat-fee matters over budget: 2 matters
    (flagged for repricing on renewal)

    Draft invoices for unbilled matters? [Yes / No]"
```

**Tools:** `database_tools`, `email_tools`, `document_tools`
**New integration:** Practice management / e-billing connector

---

### Agent 2 — Contract Risk Agent

**Archetype:** Analyst
**Trigger:** Contract document uploaded or received
**Pipeline:** None

**What it does:** Reviews contracts for non-standard clauses, missing standard protections, and unusual risk allocations — giving attorneys a prioritized risk summary before they read the full document.

**End-to-end flow:**
```
Triggered when contract is uploaded to matter folder:
1. Extract all clauses from the document
2. Compare against firm's standard position stored in KB:
   - Standard limitation of liability language
   - Standard indemnification scope
   - IP ownership defaults
   - Governing law and jurisdiction preferences
   - Termination for convenience rights
3. Flag deviations by risk level:
   High — clause is materially worse than standard
   Medium — non-standard but negotiable
   Low — minor deviation, typically accepted
4. Output:
   "Contract Review Summary — Acme SaaS Agreement:

    High risk (3):
    - Clause 12.4: Unlimited liability for data breach.
      Firm standard: capped at 12 months fees.
    - Clause 8.1: IP assignment covers all work product
      including pre-existing materials.
    - Clause 19: Unilateral amendment right for vendor.

    Missing (2):
    - No limitation on consequential damages
    - No SLA or uptime commitment despite SaaS nature

    Suggested redlines ready for attorney review. [View]"
```

**Tools:** `document_tools`, `contract_analysis_tools`, `file_analysis_tools`, `kb_ingest_tools`

---

### Agent 3 — Matter Deadline Guardian

**Archetype:** Monitor
**Schedule:** Daily
**Pipeline:** None (practice management system queried live)

**What it does:** Tracks every court date, filing deadline, statute of limitations, and response deadline across all active matters — and fires alerts with enough lead time for attorneys to act.

**End-to-end flow:**
```
Runs every morning:
1. Pull all active matters and associated deadlines
   from practice management system
2. Categorize deadlines:
   - Court dates and hearings
   - Filing deadlines (motions, responses, appeals)
   - Statute of limitations (with state-specific rules from KB)
   - Contract response deadlines
   - Regulatory filing deadlines
3. Fire tiered alerts:
   - 30 days out: heads-up notification to responsible attorney
   - 14 days out: reminder + request status update
   - 7 days out: urgent alert to attorney + supervising partner
   - 48 hours out: critical alert, escalate if no response
4. Daily summary to managing partner:
   "Matter Deadlines — June 12:

    Critical (< 7 days):
    - Jones v. State: Reply brief due June 16 (4 days)
      Assigned: M. Patel. Status: in draft.
    - Riverside contract: Response deadline June 14 (2 days)
      Assigned: K. Chen. No update recorded.
      [Escalate to partner]

    Upcoming (7–30 days): 8 matters. [View all]"
```

**Tools:** `database_tools`, `google_calendar_tools`, `scheduler_tools`, `email_tools`, `kb_ingest_tools`
**New integration:** Practice management connector (Clio / MyCase)

---

### Agent 4 — Legal Research Agent

**Archetype:** Oracle
**Schedule:** On-demand
**Pipeline:** None

**What it does:** Researches case law, statutes, and regulatory positions on demand — giving attorneys a structured briefing in minutes instead of hours.

**End-to-end flow:**
```
Attorney asks: "What is the current standard for
piercing the corporate veil in Illinois?"

1. Search legal research database for:
   - Controlling case law in the specified jurisdiction
   - Relevant statutes
   - Recent decisions (last 2 years weighted higher)
2. Pull any firm memos on this topic from KB
   (prior research the firm has already done)
3. Structure output:
   "Corporate Veil Piercing — Illinois:

    Controlling standard (Illinois Supreme Court):
    [Case name, year]: Two-pronged test — (1) unity of
    interest and ownership, (2) adherence to corporate
    form would sanction fraud or injustice.

    Key factors courts apply: [list with citations]

    Recent developments:
    [Case, 2024]: Court declined to pierce where...

    Relevant firm memos: [1 found — March 2024]

    Confidence: High. 6 sources reviewed."
```

**Tools:** `web_tools`, `document_tools`, `kb_ingest_tools`, `file_analysis_tools`
**New integration:** Westlaw / LexisNexis / Fastcase API

---

### Agent 5 — Regulatory Watch Agent

**Archetype:** Monitor
**Schedule:** Weekly
**Pipeline:** None

**What it does:** Monitors regulatory changes in the firm's practice areas and alerts attorneys to developments that affect active matters or create new client opportunities.

**End-to-end flow:**
```
Runs weekly:
1. Pull the firm's active practice areas from KB:
   employment, IP, M&A, data privacy, real estate, etc.
2. Monitor:
   - Regulatory agency announcements (FTC, SEC, NLRB, etc.)
   - New legislation passed or proposed
   - Significant court decisions in covered jurisdictions
   - Industry-specific regulatory changes relevant
     to current client roster
3. Cross-reference against active matters:
   does this change affect any open file?
4. Weekly alert:
   "Regulatory Watch — Week 24:

    Affects active matters (2):
    - FTC updated guidance on non-compete enforceability.
      Affects: Hartwell employment matter (M. Patel).
      Action: Review advice letter sent March 12.

    - Illinois amended data breach notification timeline
      from 45 to 30 days effective July 1.
      Affects: 3 clients with active data processing agreements.
      Recommend: Proactive client alert this week.

    No active matter impact (4 developments):
    [View for business development opportunities]"
```

**Tools:** `web_tools`, `news_tools`, `email_tools`, `database_tools`, `kb_ingest_tools`

---

### Agent 6 — Case Intelligence Agent

**Archetype:** Oracle
**Schedule:** On-demand (persistent per matter)
**Pipeline:** None — uses Synkora Knowledge Base per matter

**What it does:** Gives attorneys a conversational interface across every document in an active case — pleadings, discovery, depositions, witness statements, expert reports, correspondence, prior rulings. Finds contradictions, surfaces supporting evidence, reconstructs timelines, and identifies what is missing.

**How the KB is structured:**

Each active matter gets its own dedicated knowledge base in Synkora. Documents are ingested as they arrive:

```
Matter KB — Smith v. Johnson (#2024-CV-441)
  ├── Pleadings (complaint, answer, counterclaim)
  ├── Discovery (interrogatory responses, RFP responses)
  ├── Depositions (all transcripts)
  ├── Witness statements
  ├── Expert reports
  ├── Correspondence (opposing counsel, client)
  ├── Prior court orders and rulings in this matter
  └── Relevant case law and statutes (attorney-added)
```

Documents can be ingested via:
- Manual upload through the KB interface
- Google Drive folder sync (auto-ingests as documents arrive)
- Email attachment capture (forwarded to matter inbox)

**End-to-end flows:**

**1. Contradiction detection**
```
Attorney: "Do any witness statements contradict each other
on where the defendant was at 9pm on March 3?"

Agent:
1. Searches all deposition transcripts and witness statements
   in the matter KB for references to that date and time
2. Extracts each account and its source document + page
3. Output:
   "3 accounts found for defendant's location on March 3 at 9pm:

    Witness A (Deposition p.34):
    'I saw him leaving the building at approximately 9pm.'

    Witness B (Statement, filed Feb 12):
    'He called me at 9:15pm from what sounded like a restaurant.'

    Defendant (Interrogatory Response #7):
    'I was at home all evening after 8pm.'

    Contradiction: Witness A and defendant's accounts
    are irreconcilable. Witness B is consistent with A
    but inconsistent with defendant.
    [View source documents]"
```

**2. Evidence gap analysis**
```
Attorney: "What evidence do we still need to prove
breach of fiduciary duty?"

Agent:
1. Pulls the elements of breach of fiduciary duty
   from KB (legal standard for the jurisdiction)
2. Maps current evidence in the matter KB
   against each required element
3. Identifies gaps:
   "Elements required vs. evidence on file:

    Duty (established): Articles of incorporation +
    board resolution confirm director relationship. COVERED.

    Breach (partial): Board meeting minutes show defendant
    voted on transaction where he had undisclosed interest.
    Missing: direct evidence defendant knew of the conflict
    at the time of the vote. Suggested: depose CFO who
    attended the pre-meeting discussion.

    Damages (weak): Only general damages claimed.
    Missing: quantified loss calculation.
    Suggested: retain financial expert."
```

**3. Timeline reconstruction**
```
Attorney: "Build me a chronological timeline of
all events in this case."

Agent:
1. Scans all documents in the matter KB for dates and events
2. Extracts each event, its date, source document, and
   which party's account it comes from
3. Flags dates where accounts conflict
4. Output: structured timeline with source citations,
   exportable as PDF for trial prep
```

**4. Deposition preparation**
```
Attorney: "I am deposing the CFO next week.
What should I ask her about?"

Agent:
1. Pulls all references to the CFO across matter documents
2. Identifies:
   - Statements she has already made (prior testimony, emails)
   - Topics where her account is incomplete or inconsistent
   - Documents she authored or received that need explanation
   - Gaps in the record that she is best positioned to fill
3. Output: prioritized deposition outline with
   suggested questions and supporting document references
```

**5. Quick document search**
```
Attorney: "Where in the discovery documents did opposing
counsel mention the February audit report?"

Agent:
Semantic search across all matter documents.
Returns: exact passages, document name, page number.
Seconds, not hours.
```

**Tools:** `kb_ingest_tools`, `document_tools`, `file_analysis_tools`, `google_drive_tools`

**Pipeline:** None. The Synkora Knowledge Base handles document ingestion, chunking, and vector search natively. The attorney uploads or syncs documents once; the agent queries the KB at every conversation turn.

**Key design point:** Each matter is a separate KB instance with access scoped to attorneys on that matter only. This enforces client confidentiality at the data layer — one client's documents cannot surface in another client's matter agent.

---

## Marketplace to Vertical SaaS Path

### Phase 1 — Marketplace Templates

All 35 agents ship as public Synkora templates with `is_public: true`. Any tenant can one-click install, connect their data sources, and go live. This validates which agents get the most usage and which verticals have the highest willingness to pay.

**Signals to watch per vertical:**
- Install count
- Active usage rate (how often the agent runs / is queried)
- Retention (are tenants still using it 30 days later?)
- Upgrade conversion (does having the agent drive tier upgrades?)

### Phase 2 — Vertical SaaS Products

The 2–3 verticals with highest engagement get forked into standalone branded products:

```
Synkora template pack
  → Branded domain (e.g. fleetos.ai, fabriciq.ai)
  → Vertical-specific onboarding wizard
     (connect your GBFS feed, ERP, etc.)
  → Custom landing page and pricing
  → Vertical-specific KB pre-loaded
     (industry benchmarks, compliance templates, etc.)
  → White-labeled — Synkora not visible to end user
```

**Technical implementation:** Each vertical SaaS is a Synkora tenant with:
- `portal_visibility` configured for public widget
- Pre-installed agent templates via seed script
- Branded via `agent_metadata.brand` config
- Vertical-specific system prompts locked (not editable by end user)
- Pricing tier tied to vertical product plan

### Recommended Build Order

Based on existing tool coverage and market opportunity:

| Priority | Vertical | Reason |
|---|---|---|
| 1 | Micromobility | 3 tool files already built, niche market, high ops budget |
| 2 | Startup | GitHub/Slack/Jira all connected, founders are early adopters |
| 3 | Garments | Large procurement budgets, no competitors in this space |
| 4 | SME | Broad market, general tools all available |
| 5 | Government | High willingness to pay, long sales cycle — build last |
| 6 | NGO | Mission-aligned, limited budget |
| 7 | Photography | Small deal size, validate as low-cost template only |
| 8 | Law | High willingness to pay, `contract_analysis_tools` already built, strong ROI story on billable recovery |

---

## New Connectors Required (Master List)

These are the integrations not yet in Synkora that are needed across all verticals:

| Connector | Used by | Priority |
|---|---|---|
| GBFS feed | Micromobility | High |
| Hardware telemetry API | Micromobility | High |
| Stripe | Startup | High |
| QuickBooks / Xero | Startup, SME, Photography | High |
| Bank feed (Brex/Ramp/Plaid) | Startup, SME | High |
| Linear | Startup | Medium |
| Product analytics (Mixpanel/Amplitude) | Startup | Medium |
| ERP (SAP B1, NetSuite) | Garments | High |
| Commodity price API | Garments | Medium |
| Salesforce NPSP / Bloomerang | NGO | Medium |
| Candid/GrantStation API | NGO | Medium |
| Studio Ninja / HoneyBook | Photography | Low |
| TinEye reverse image API | Photography | Low |
| SAP Public Sector / Tyler Technologies | Government | Medium |
| Practice management (Clio, MyCase) | Law | High |
| Legal research API (Westlaw/LexisNexis/Fastcase) | Law | High |
| PACER federal court connector | Law | Medium |
| E-billing (TimeSolv, Bill4Time) | Law | Medium |

All connectors follow the existing Synkora OAuth pattern:
`services/oauth/` + `controllers/oauth/` + tool registration in `tool_registrations/`
