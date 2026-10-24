# Billing cap: warn at $3, switch billing off at $5

Marisol approved Google Cloud billing with a **$5 a month maximum** (docs/decisions.md,
decision 9). A Google budget on its own only sends warnings; it never stops spending. This
folder is the missing piece: a small function that switches billing off when the month's
cost reaches $5.

**Status: built, not set up.** Nothing here has been deployed, and billing is not on.
Every step below needs the user's OK first (CLAUDE.md, "How work moves").

## How it works

1. A **budget** of $5/month on the project emails the billing account's people at **$3**
   (60%) and **$5** (100%).
2. The budget also sends a message to a Pub/Sub topic, `billing-cap`, several times a day,
   with the month's cost so far.
3. The **`billing-cap` function** (`main.py` → `cap.py`) reads each message. When the cost
   has reached the budget and billing is still on, it unlinks the project from its billing
   account, which switches billing off.

It starts in **dry run** (`CAP_DRY_RUN=true`): it only logs what it would do. It's armed
(`CAP_DRY_RUN=false`) only after a test shows it works.

## If the cap triggers

- **Stops:** the 6 AM daily run, and with it new data and Slack alerts. The control panel
  loads, but says the pipeline server isn't responding; Run now and Settings don't work.
- **Keeps working:** the master sheet and everything already in it, Looker Studio, and
  Google Analytics / Search Console themselves.
- **Billing does not come back on by itself, not even next month.** To restart: Cloud Console →
  Billing → link the project to the billing account again.
- Google reports costs with a delay of a few hours, sometimes up to a day, so spending can
  go slightly over $5 before the switch fires.
- Google may eventually delete resources in a project left without billing for a long
  time, so switch it back on promptly.

## Before setting it up

- Marisol has created a billing account with a payment method, and given the user
  **Billing Account User** (to link the project) and **Billing Account Costs Manager**
  (to create the budget). Neither role can see or change payment details.
- The user is an Owner of the project `ga4-search-console-pipeline`.
- `gcloud` is installed and signed in as the user.

In the commands, replace `BILLING_ACCOUNT_ID` with the account's ID (Cloud Console →
Billing → Account management, shaped like `0X0X0X-0X0X0X-0X0X0X`).

## Setup steps (each one needs the user's OK)

```powershell
$PROJECT = "ga4-search-console-pipeline"
$REGION  = "us-east1"

# 1. Link the billing account (this switches billing ON).
gcloud billing projects link $PROJECT --billing-account=BILLING_ACCOUNT_ID

# 2. Turn on what the cap needs.
gcloud services enable cloudbilling.googleapis.com billingbudgets.googleapis.com pubsub.googleapis.com `
  run.googleapis.com cloudfunctions.googleapis.com cloudbuild.googleapis.com eventarc.googleapis.com `
  artifactregistry.googleapis.com --project=$PROJECT

# 3. The topic the budget talks to.
gcloud pubsub topics create billing-cap --project=$PROJECT

# 4. The function's own identity, allowed to change this project's billing and nothing else.
gcloud iam service-accounts create billing-cap --display-name="Billing cap" --project=$PROJECT
gcloud projects add-iam-policy-binding $PROJECT `
  --member="serviceAccount:billing-cap@$PROJECT.iam.gserviceaccount.com" --role="roles/billing.projectManager"

# 5. The $5 budget: emails at $3 and $5, and messages the topic.
gcloud billing budgets create --billing-account=BILLING_ACCOUNT_ID `
  --display-name="SWC pipeline: 5 USD cap" --budget-amount=5USD `
  --threshold-rule=percent=0.6 --threshold-rule=percent=1.0 `
  --filter-projects="projects/$PROJECT" `
  --notifications-rule-pubsub-topic="projects/$PROJECT/topics/billing-cap"

# 6. Deploy the function in DRY RUN.
gcloud functions deploy billing-cap --gen2 --runtime=python313 --region=$REGION `
  --source=infra/billing_cap --entry-point=on_budget_message --trigger-topic=billing-cap `
  --service-account="billing-cap@$PROJECT.iam.gserviceaccount.com" --max-instances=1 `
  --set-env-vars="CAP_PROJECT_ID=$PROJECT,CAP_DRY_RUN=true" --project=$PROJECT

# 7. Test: pretend $6 was spent, then check the log says "DRY RUN: would switch billing off".
gcloud pubsub topics publish billing-cap --project=$PROJECT `
  --message='{"costAmount": 6.0, "budgetAmount": 5.0, "currencyCode": "USD"}'
gcloud functions logs read billing-cap --gen2 --region=$REGION --project=$PROJECT --limit=10

# 8. Arm it.
gcloud functions deploy billing-cap --gen2 --region=$REGION --source=infra/billing_cap `
  --update-env-vars="CAP_DRY_RUN=false" --project=$PROJECT
```

**Notes:**
- **Runtime:** `python313` because Google's functions may not offer Python 3.14 yet. The
  code doesn't depend on 3.14.
- **Permission:** switching billing off needs only *Project Billing Manager* on this
  project (step 4). If Google refuses, the log says so. The fallback is to grant that service
  account *Billing Account Administrator* on the billing account, which is broader. Ask
  before doing that.
- **Cost:** the topic and the function run within Google's free tier. Expected cost: $0.
