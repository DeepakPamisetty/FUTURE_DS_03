# FUTURE_DS_03: Google Analytics Marketing Funnel Analysis

Business presentation dashboard for the Kaggle **Google Analytics Customer Revenue Prediction** competition data.

Competition: <https://www.kaggle.com/competitions/ga-customer-revenue-prediction>

## Project Goal

Analyze how users move from:

**Visitors -> Leads -> Customers**

and identify:

- Funnel drop-off points
- Traffic-to-lead conversion
- Lead-to-customer conversion
- Channel and campaign quality
- Recommendations to improve conversions

## Deliverables

- [Business funnel dashboard](dashboards/funnel_dashboard.html) - presentation-ready HTML dashboard
- [Funnel analysis report](reports/funnel_analysis_report.md) - written funnel analysis report
- [Executive presentation deck](slides/ga_funnel_business_presentation.pptx) - PowerPoint business presentation
- `data/processed/*.csv` - generated funnel, channel, campaign, and monthly metrics
- `src/funnel_analysis.py` - reproducible analysis pipeline
- `slides/build_presentation.mjs` - reproducible deck generation script

## Dashboard Links

- **Dashboard webpage:** <https://deepakpamisetty.github.io/FUTURE_DS_03/dashboards/funnel_dashboard.html>
- **Dashboard preview fallback:** <https://htmlpreview.github.io/?https://github.com/DeepakPamisetty/FUTURE_DS_03/blob/master/dashboards/funnel_dashboard.html>
- [Open the HTML dashboard](dashboards/funnel_dashboard.html)
- [View the dashboard CSS](assets/dashboard.css)
- [Read the funnel report](reports/funnel_analysis_report.md)
- [Download the PowerPoint deck](slides/ga_funnel_business_presentation.pptx)
- [Review channel metrics](data/processed/channel_metrics.csv)
- [Review campaign metrics](data/processed/campaign_metrics.csv)

## Dataset Setup

Kaggle competition downloads require Kaggle login, API credentials, and competition rules acceptance.

1. Accept the competition rules on Kaggle.
2. Download the data from the competition page.
3. Place either `train_v2.csv` or `train.csv` in:

```text
data/raw/
```

Expected paths:

```text
data/raw/train_v2.csv
data/raw/train.csv
```

If no Kaggle file is present, the pipeline generates a small deterministic offline sample so the dashboard and deck can still be reviewed end to end.

## Funnel Definition

The Kaggle Google Analytics data is web analytics data, not CRM lead-status data. This project defines funnel stages as:

- **Visitor:** one session/row in the GA export
- **Lead:** an engaged session with at least 3 pageviews, 60 seconds on site, or 5 hits
- **Customer:** a session with transactions or transaction revenue

This behavioral lead proxy is documented because the original dataset does not include form submissions, MQL, SQL, or opportunity-stage fields.

## Run the Analysis

Use the bundled or local Python environment with pandas installed:

```bash
python3 src/funnel_analysis.py
```

Generated files:

```text
data/processed/funnel_metrics.csv
data/processed/channel_metrics.csv
data/processed/monthly_metrics.csv
data/processed/campaign_metrics.csv
data/processed/summary.json
data/processed/recommendations.json
dashboards/funnel_dashboard.html
reports/funnel_analysis_report.md
```

## View the Dashboard

Open:

```text
dashboards/funnel_dashboard.html
```

The dashboard is standalone HTML/CSS and can be hosted with GitHub Pages. If GitHub Pages is enabled for this repository, use the Pages URL for `dashboards/funnel_dashboard.html`.

## Key Business Questions Answered

- Where do users drop off in the funnel?
- Which channels produce high-quality leads?
- Which campaigns generate customers?
- How do conversion rates change over time?
- Which funnel stage should be optimized first?

## Recommended Improvements

The pipeline writes recommendations dynamically based on the channel and funnel metrics. Typical actions include:

- Shift budget toward channels with high visitor-to-customer conversion
- Improve landing pages for high-traffic but low-conversion channels
- Build remarketing for engaged leads who do not purchase
- Track funnel quality weekly by channel, campaign, device, and geography
