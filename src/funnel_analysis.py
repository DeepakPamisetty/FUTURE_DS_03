from __future__ import annotations

import json
import math
import random
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
PROCESSED_DIR = ROOT / "data" / "processed"
DASHBOARD_DIR = ROOT / "dashboards"
REPORTS_DIR = ROOT / "reports"


def _parse_json_cell(value: object) -> dict:
    if isinstance(value, dict):
        return value
    if pd.isna(value):
        return {}
    if not isinstance(value, str):
        return {}
    try:
        return json.loads(value.replace("'", '"'))
    except json.JSONDecodeError:
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return {}


def _to_number(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").fillna(0)


def _find_source_file() -> Path | None:
    candidates = [
        RAW_DIR / "train_v2.csv",
        RAW_DIR / "train.csv",
        RAW_DIR / "ga-customer-revenue-prediction" / "train_v2.csv",
        RAW_DIR / "ga-customer-revenue-prediction" / "train.csv",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def _make_sample_data(rows: int = 2500) -> pd.DataFrame:
    random.seed(42)
    channels = {
        "Organic Search": (0.42, 0.18, 0.018),
        "Paid Search": (0.22, 0.23, 0.023),
        "Direct": (0.14, 0.16, 0.017),
        "Referral": (0.10, 0.24, 0.031),
        "Social": (0.08, 0.11, 0.006),
        "Display": (0.04, 0.09, 0.004),
    }
    channel_names = list(channels.keys())
    weights = [channels[c][0] for c in channel_names]
    campaigns = ["(not set)", "brand", "summer remarketing", "content syndication", "partner launch"]
    devices = ["desktop", "mobile", "tablet"]
    countries = ["United States", "India", "United Kingdom", "Canada", "Germany", "Australia"]
    start = pd.Timestamp("2017-08-01")

    records: list[dict] = []
    for i in range(rows):
        channel = random.choices(channel_names, weights=weights, k=1)[0]
        lead_rate = channels[channel][1]
        customer_rate = channels[channel][2]
        date = start + pd.Timedelta(days=random.randrange(365))
        device = random.choices(devices, weights=[0.56, 0.36, 0.08], k=1)[0]
        is_lead = random.random() < lead_rate
        is_customer = is_lead and random.random() < min(customer_rate / max(lead_rate, 0.01), 0.35)
        pageviews = random.randint(1, 2) if not is_lead else random.randint(3, 12)
        hits = pageviews + random.randint(0, 8)
        time_on_site = random.randint(5, 55) if not is_lead else random.randint(70, 900)
        revenue = 0
        if is_customer:
            revenue = random.choice([1990000, 4990000, 7990000, 12990000, 24990000])
        records.append(
            {
                "fullVisitorId": f"sample_{i:06d}",
                "visitId": i,
                "date": date.strftime("%Y%m%d"),
                "channelGrouping": channel,
                "device": json.dumps({"deviceCategory": device}),
                "geoNetwork": json.dumps({"country": random.choice(countries)}),
                "trafficSource": json.dumps(
                    {
                        "campaign": random.choice(campaigns),
                        "source": channel.lower().replace(" ", "_"),
                        "medium": "organic" if channel == "Organic Search" else "paid" if "Paid" in channel else "referral",
                    }
                ),
                "totals": json.dumps(
                    {
                        "hits": hits,
                        "pageviews": pageviews,
                        "timeOnSite": time_on_site,
                        "transactions": 1 if is_customer else 0,
                        "transactionRevenue": revenue,
                    }
                ),
            }
        )
    return pd.DataFrame(records)


def load_data() -> tuple[pd.DataFrame, str]:
    source = _find_source_file()
    if source:
        usecols = None
        df = pd.read_csv(source, dtype={"fullVisitorId": "str"}, low_memory=False, usecols=usecols)
        return df, f"Real Kaggle file: {source.relative_to(ROOT)}"
    return _make_sample_data(), "Offline sample generated because Kaggle competition data was not available locally"


def flatten_ga_data(df: pd.DataFrame) -> pd.DataFrame:
    result = df.copy()
    for column in ["totals", "trafficSource", "device", "geoNetwork"]:
        if column in result.columns:
            parsed = result[column].map(_parse_json_cell)
            expanded = pd.json_normalize(parsed)
            expanded.columns = [f"{column}_{name}" for name in expanded.columns]
            result = pd.concat([result.drop(columns=[column]), expanded], axis=1)

    if "date" in result.columns:
        result["date"] = pd.to_datetime(result["date"].astype(str), format="%Y%m%d", errors="coerce")
    else:
        result["date"] = pd.NaT

    result["channel"] = result.get("channelGrouping", "Unknown").fillna("Unknown")
    result["campaign"] = result.get("trafficSource_campaign", "(not set)").fillna("(not set)")
    result["source"] = result.get("trafficSource_source", "unknown").fillna("unknown")
    result["medium"] = result.get("trafficSource_medium", "unknown").fillna("unknown")
    result["device_category"] = result.get("device_deviceCategory", "unknown").fillna("unknown")
    result["country"] = result.get("geoNetwork_country", "unknown").fillna("unknown")

    for column in [
        "totals_hits",
        "totals_pageviews",
        "totals_timeOnSite",
        "totals_transactions",
        "totals_transactionRevenue",
        "totals_totalTransactionRevenue",
    ]:
        if column not in result.columns:
            result[column] = 0
        result[column] = _to_number(result[column])

    revenue = result["totals_transactionRevenue"]
    if revenue.eq(0).all() and "totals_totalTransactionRevenue" in result:
        revenue = result["totals_totalTransactionRevenue"]
    result["revenue_usd"] = revenue / 1_000_000

    result["visitor"] = 1
    result["lead"] = (
        (result["totals_pageviews"] >= 3)
        | (result["totals_timeOnSite"] >= 60)
        | (result["totals_hits"] >= 5)
    ).astype(int)
    result["customer"] = ((result["totals_transactions"] > 0) | (result["revenue_usd"] > 0)).astype(int)
    result.loc[result["customer"].eq(1), "lead"] = 1
    return result


def _rate(numerator: float, denominator: float) -> float:
    return 0.0 if denominator == 0 else numerator / denominator


def build_metrics(df: pd.DataFrame) -> dict[str, pd.DataFrame | dict]:
    visitors = int(df["visitor"].sum())
    leads = int(df["lead"].sum())
    customers = int(df["customer"].sum())
    revenue = float(df["revenue_usd"].sum())

    funnel = pd.DataFrame(
        [
            {"stage": "Visitors", "count": visitors, "stage_conversion": 1.0, "dropoff_from_prior": 0.0},
            {
                "stage": "Leads",
                "count": leads,
                "stage_conversion": _rate(leads, visitors),
                "dropoff_from_prior": 1 - _rate(leads, visitors),
            },
            {
                "stage": "Customers",
                "count": customers,
                "stage_conversion": _rate(customers, leads),
                "dropoff_from_prior": 1 - _rate(customers, leads),
            },
        ]
    )

    channel = (
        df.groupby("channel", dropna=False)
        .agg(
            visitors=("visitor", "sum"),
            leads=("lead", "sum"),
            customers=("customer", "sum"),
            revenue_usd=("revenue_usd", "sum"),
            avg_pageviews=("totals_pageviews", "mean"),
            avg_time_on_site=("totals_timeOnSite", "mean"),
        )
        .reset_index()
    )
    channel["traffic_to_lead_rate"] = channel["leads"] / channel["visitors"]
    channel["lead_to_customer_rate"] = channel["customers"] / channel["leads"].replace(0, pd.NA)
    channel["visitor_to_customer_rate"] = channel["customers"] / channel["visitors"]
    channel["revenue_per_visitor"] = channel["revenue_usd"] / channel["visitors"]
    channel = channel.fillna(0).sort_values(["customers", "visitor_to_customer_rate"], ascending=False)

    monthly = (
        df.dropna(subset=["date"])
        .assign(month=lambda x: x["date"].dt.to_period("M").astype(str))
        .groupby("month")
        .agg(visitors=("visitor", "sum"), leads=("lead", "sum"), customers=("customer", "sum"), revenue_usd=("revenue_usd", "sum"))
        .reset_index()
    )
    monthly["traffic_to_lead_rate"] = monthly["leads"] / monthly["visitors"]
    monthly["lead_to_customer_rate"] = monthly["customers"] / monthly["leads"].replace(0, pd.NA)
    monthly = monthly.fillna(0)

    campaign = (
        df.groupby(["channel", "campaign"], dropna=False)
        .agg(visitors=("visitor", "sum"), leads=("lead", "sum"), customers=("customer", "sum"), revenue_usd=("revenue_usd", "sum"))
        .reset_index()
    )
    campaign["visitor_to_customer_rate"] = campaign["customers"] / campaign["visitors"]
    campaign = campaign.sort_values(["customers", "visitor_to_customer_rate"], ascending=False).head(15)

    summary = {
        "visitors": visitors,
        "leads": leads,
        "customers": customers,
        "revenue_usd": revenue,
        "traffic_to_lead_rate": _rate(leads, visitors),
        "lead_to_customer_rate": _rate(customers, leads),
        "visitor_to_customer_rate": _rate(customers, visitors),
        "largest_dropoff_stage": "Visitors to leads" if (1 - _rate(leads, visitors)) >= (1 - _rate(customers, leads)) else "Leads to customers",
        "data_source_note": "",
    }
    return {"funnel": funnel, "channel": channel, "monthly": monthly, "campaign": campaign, "summary": summary}


def make_recommendations(metrics: dict[str, pd.DataFrame | dict]) -> list[str]:
    channel = metrics["channel"]
    summary = metrics["summary"]
    assert isinstance(channel, pd.DataFrame)
    assert isinstance(summary, dict)

    best_quality = channel.sort_values("visitor_to_customer_rate", ascending=False).iloc[0]
    best_lead = channel.sort_values("traffic_to_lead_rate", ascending=False).iloc[0]
    weak = channel[channel["visitors"] >= max(20, channel["visitors"].median())].sort_values("visitor_to_customer_rate").iloc[0]

    recs = [
        f"Prioritize {best_quality['channel']} for qualified acquisition; it has the strongest visitor-to-customer conversion at {best_quality['visitor_to_customer_rate']:.1%}.",
        f"Use {best_lead['channel']} landing-page and messaging patterns as a lead-capture benchmark because it converts traffic to leads at {best_lead['traffic_to_lead_rate']:.1%}.",
        f"Audit {weak['channel']} spend and landing pages; its conversion quality trails the portfolio at {weak['visitor_to_customer_rate']:.1%}.",
    ]
    if summary["largest_dropoff_stage"] == "Visitors to leads":
        recs.append("The biggest bottleneck is top-of-funnel engagement; test clearer offers, faster landing pages, and stronger form/CTA placement.")
    else:
        recs.append("The biggest bottleneck is sales qualification; add remarketing, cart recovery, and high-intent follow-up for engaged non-buyers.")
    recs.append("Track the funnel weekly by channel, campaign, device, and country so budget shifts are based on lead quality rather than traffic volume alone.")
    return recs


def _fmt_int(value: float) -> str:
    return f"{int(round(value)):,}"


def _fmt_pct(value: float) -> str:
    return f"{value:.1%}"


def _markdown_table(df: pd.DataFrame) -> str:
    printable = df.copy()
    for column in printable.columns:
        if "rate" in column or "conversion" in column or "dropoff" in column:
            printable[column] = printable[column].map(lambda value: f"{float(value):.1%}")
        elif pd.api.types.is_float_dtype(printable[column]):
            printable[column] = printable[column].map(lambda value: f"{float(value):,.2f}")
    headers = [str(column) for column in printable.columns]
    rows = printable.astype(str).values.tolist()
    widths = [len(header) for header in headers]
    for row in rows:
        widths = [max(width, len(cell)) for width, cell in zip(widths, row)]
    header_line = "| " + " | ".join(header.ljust(width) for header, width in zip(headers, widths)) + " |"
    separator = "| " + " | ".join("-" * width for width in widths) + " |"
    body = ["| " + " | ".join(cell.ljust(width) for cell, width in zip(row, widths)) + " |" for row in rows]
    return "\n".join([header_line, separator, *body])


def _bar_rows(df: pd.DataFrame, metric: str, label: str, formatter) -> str:
    max_value = max(float(df[metric].max()), 1e-9)
    rows = []
    for _, row in df.iterrows():
        width = max(4, min(100, float(row[metric]) / max_value * 100))
        rows.append(
            f"""
            <div class="bar-row">
              <div class="bar-label">{row[label]}</div>
              <div class="bar-track"><span style="width:{width:.1f}%"></span></div>
              <div class="bar-value">{formatter(row[metric])}</div>
            </div>
            """
        )
    return "\n".join(rows)


def _table_rows(df: pd.DataFrame, columns: list[tuple[str, str, callable | None]]) -> str:
    rows = []
    for _, row in df.iterrows():
        cells = []
        for key, _, formatter in columns:
            value = row[key]
            cells.append(f"<td>{formatter(value) if formatter else value}</td>")
        rows.append(f"<tr>{''.join(cells)}</tr>")
    return "\n".join(rows)


def _table_header(columns: list[tuple[str, str, callable | None]]) -> str:
    return "".join(f"<th>{label}</th>" for _, label, _ in columns)


def write_dashboard(metrics: dict[str, pd.DataFrame | dict], recommendations: list[str]) -> None:
    funnel = metrics["funnel"]
    channel = metrics["channel"]
    monthly = metrics["monthly"]
    campaign = metrics["campaign"]
    summary = metrics["summary"]
    assert isinstance(funnel, pd.DataFrame)
    assert isinstance(channel, pd.DataFrame)
    assert isinstance(monthly, pd.DataFrame)
    assert isinstance(campaign, pd.DataFrame)
    assert isinstance(summary, dict)

    top_channels = channel.head(8)
    quality_channels = channel.sort_values("visitor_to_customer_rate", ascending=False).head(8)
    lead_channels = channel.sort_values("traffic_to_lead_rate", ascending=False).head(8)
    months = monthly.tail(12)
    max_month_customers = max(float(months["customers"].max()), 1)
    points = []
    for i, row in months.reset_index(drop=True).iterrows():
        x = 40 + i * (520 / max(len(months) - 1, 1))
        y = 220 - (float(row["customers"]) / max_month_customers * 160)
        points.append(f"{x:.1f},{y:.1f}")

    max_month_leads = max(float(months["leads"].max()), 1)
    lead_points = []
    for i, row in months.reset_index(drop=True).iterrows():
        x = 40 + i * (520 / max(len(months) - 1, 1))
        y = 220 - (float(row["leads"]) / max_month_leads * 160)
        lead_points.append(f"{x:.1f},{y:.1f}")

    funnel_blocks = []
    max_stage = float(funnel["count"].max())
    for _, row in funnel.iterrows():
        width = 300 + (float(row["count"]) / max_stage * 520)
        left = (900 - width) / 2
        funnel_blocks.append(
            f"""
            <div class="funnel-stage" style="width:{width:.0f}px;margin-left:{left:.0f}px">
              <span>{row['stage']}</span><strong>{_fmt_int(row['count'])}</strong>
              <em>{_fmt_pct(row['stage_conversion'])} stage conversion</em>
            </div>
            """
        )

    channel_columns = [
        ("channel", "Channel", None),
        ("visitors", "Visitors", _fmt_int),
        ("leads", "Leads", _fmt_int),
        ("customers", "Customers", _fmt_int),
        ("visitor_to_customer_rate", "V->C", _fmt_pct),
    ]
    campaign_columns = [
        ("campaign", "Campaign", None),
        ("channel", "Channel", None),
        ("customers", "Customers", _fmt_int),
        ("revenue_usd", "Revenue", lambda value: f"${value:,.0f}"),
    ]
    best_quality = quality_channels.iloc[0]
    best_lead = lead_channels.iloc[0]
    top_campaign = campaign.iloc[0] if not campaign.empty else {"campaign": "n/a", "customers": 0}

    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>GA Customer Revenue Funnel Dashboard</title>
  <link rel="stylesheet" href="../assets/dashboard.css">
</head>
<body>
  <main class="dashboard-shell">
    <header class="dashboard-title">
      <div>
        <p class="eyebrow">Marketing & lead funnel dashboard</p>
        <h1>Google Analytics Customer Revenue Prediction</h1>
      </div>
      <div class="source-note">{summary['data_source_note']}</div>
    </header>

    <section class="kpi-grid">
      <article><span>Total Visitors</span><strong>{_fmt_int(summary['visitors'])}</strong><em>sessions analyzed</em></article>
      <article><span>Qualified Leads</span><strong>{_fmt_int(summary['leads'])}</strong><em>{_fmt_pct(summary['traffic_to_lead_rate'])} traffic-to-lead</em></article>
      <article><span>Customers</span><strong>{_fmt_int(summary['customers'])}</strong><em>{_fmt_pct(summary['lead_to_customer_rate'])} lead-to-customer</em></article>
      <article><span>Revenue</span><strong>${summary['revenue_usd']:,.0f}</strong><em>{_fmt_pct(summary['visitor_to_customer_rate'])} visitor conversion</em></article>
    </section>

    <div class="dashboard-grid">
      <section class="left-board">
        <section class="panel panel-wide">
          <div class="section-title">
            <h2>Funnel Conversion</h2>
            <p>Largest drop-off: {summary['largest_dropoff_stage']}</p>
          </div>
          <div class="funnel">{''.join(funnel_blocks)}</div>
        </section>

        <section class="panel">
          <div class="section-title"><h2>Lead Quality by Channel</h2><p>Visitor-to-customer rate</p></div>
          {_bar_rows(quality_channels, 'visitor_to_customer_rate', 'channel', _fmt_pct)}
        </section>

        <section class="panel">
          <div class="section-title"><h2>Lead Capture by Channel</h2><p>Traffic-to-lead rate</p></div>
          {_bar_rows(lead_channels, 'traffic_to_lead_rate', 'channel', _fmt_pct)}
        </section>

        <section class="panel">
          <div class="section-title"><h2>Leads and Customers by Month</h2><p>Recent 12-month trend</p></div>
          <svg viewBox="0 0 600 260" class="line-chart" role="img" aria-label="Leads and customers by month">
            <polyline class="lead-line" points="{' '.join(lead_points)}"></polyline>
            <polyline class="customer-line" points="{' '.join(points)}"></polyline>
            {''.join(f'<circle class="lead-dot" cx="{p.split(",")[0]}" cy="{p.split(",")[1]}" r="3"></circle>' for p in lead_points)}
            {''.join(f'<circle class="customer-dot" cx="{p.split(",")[0]}" cy="{p.split(",")[1]}" r="4"></circle>' for p in points)}
          </svg>
          <div class="legend"><span class="lead-key"></span> Leads <span class="customer-key"></span> Customers</div>
        </section>

        <section class="panel">
          <div class="section-title"><h2>Top Campaigns Table</h2><p>Customer generation</p></div>
          <div class="table-wrap">
            <table>
              <thead><tr>{_table_header(campaign_columns)}</tr></thead>
              <tbody>{_table_rows(campaign.head(8), campaign_columns)}</tbody>
            </table>
          </div>
        </section>

        <section class="panel">
          <div class="section-title"><h2>Channel Detail</h2><p>Funnel metrics</p></div>
          <div class="table-wrap">
            <table>
              <thead><tr>{_table_header(channel_columns)}</tr></thead>
              <tbody>{_table_rows(top_channels, channel_columns)}</tbody>
            </table>
          </div>
        </section>

        <section class="panel insight-panel">
          <div class="section-title"><h2>Business Insights</h2><p>What the funnel says</p></div>
          <ul>
            <li>The biggest conversion loss is <strong>{summary['largest_dropoff_stage']}</strong>, so the next improvement cycle should focus there first.</li>
            <li><strong>{best_quality['channel']}</strong> brings the highest-quality traffic at {_fmt_pct(best_quality['visitor_to_customer_rate'])} visitor-to-customer conversion.</li>
            <li><strong>{best_lead['channel']}</strong> is the strongest lead-capture benchmark at {_fmt_pct(best_lead['traffic_to_lead_rate'])} traffic-to-lead conversion.</li>
          </ul>
        </section>

        <section class="panel insight-panel">
          <div class="section-title"><h2>Recommendations</h2><p>Actionable next steps</p></div>
          <ul>
            {''.join(f'<li>{rec}</li>' for rec in recommendations[:4])}
          </ul>
        </section>
      </section>

      <aside class="right-rail">
        <section class="rail-panel">
          <h3>Channel Focus</h3>
          {''.join(f'<div class="filter-pill">{row["channel"]}</div>' for _, row in channel.head(6).iterrows())}
        </section>
        <section class="rail-panel highlight">
          <h3>Best Quality Channel</h3>
          <strong>{best_quality['channel']}</strong>
          <span>{_fmt_pct(best_quality['visitor_to_customer_rate'])}</span>
        </section>
        <section class="rail-panel highlight">
          <h3>Top Campaign</h3>
          <strong>{top_campaign['campaign']}</strong>
          <span>{_fmt_int(top_campaign['customers'])} customers</span>
        </section>
      </aside>
    </div>
  </main>
</body>
</html>"""
    DASHBOARD_DIR.mkdir(parents=True, exist_ok=True)
    (DASHBOARD_DIR / "funnel_dashboard.html").write_text(html, encoding="utf-8")


def write_css() -> None:
    css = """
:root {
  --ink: #13202c;
  --muted: #5a6775;
  --page: #e7f3f1;
  --panel: #fbfdfc;
  --panel-soft: #eef7f5;
  --line: #2f4f5f;
  --grid: #d4e4e1;
  --accent: #6157c9;
  --accent-2: #008f86;
  --accent-3: #d78c28;
  --danger: #b64f6f;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  color: var(--ink);
  background: var(--page);
  font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}
.dashboard-shell { width: min(1240px, calc(100vw - 28px)); margin: 0 auto; padding: 18px 0 36px; }
.dashboard-title {
  display: grid;
  grid-template-columns: 1fr 360px;
  gap: 18px;
  align-items: center;
  padding: 18px 20px;
  background: linear-gradient(90deg, #253858, #315d65);
  border: 2px solid var(--line);
  border-radius: 6px;
  color: #fff;
}
.eyebrow { margin: 0 0 6px; color: #c9e8e3; font-weight: 800; text-transform: uppercase; letter-spacing: .08em; font-size: 13px; }
h1 { margin: 0; font-size: clamp(28px, 3.6vw, 46px); line-height: 1.02; letter-spacing: 0; }
.source-note { color: #e9f6f3; font-size: 13px; line-height: 1.4; text-align: right; }
.kpi-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; margin: 12px 0; }
.kpi-grid article, .panel, .rail-panel { background: var(--panel); border: 2px solid var(--line); border-radius: 6px; box-shadow: 0 1px 0 rgba(19, 32, 44, .08); }
.kpi-grid article { padding: 14px 16px; min-height: 98px; }
.kpi-grid span, .kpi-grid em { display: block; color: var(--muted); font-style: normal; font-size: 14px; }
.kpi-grid strong { display: block; margin: 10px 0 4px; font-size: 31px; line-height: 1; color: var(--accent); }
.dashboard-grid { display: grid; grid-template-columns: 1fr 132px; gap: 8px; align-items: start; }
.left-board { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; }
.panel { padding: 12px; min-height: 250px; }
.panel-wide { grid-column: 1 / -1; min-height: 230px; }
.section-title { display: flex; justify-content: space-between; gap: 12px; align-items: baseline; border-bottom: 1px solid var(--grid); padding-bottom: 8px; margin-bottom: 12px; }
h2 { margin: 0; font-size: 20px; text-align: center; flex: 1; }
.section-title p { margin: 0; color: var(--muted); font-size: 12px; white-space: nowrap; }
.funnel { overflow-x: auto; padding: 6px 0 0; }
.funnel-stage {
  display: grid;
  grid-template-columns: minmax(96px, 1fr) minmax(150px, auto) minmax(62px, auto);
  gap: 14px;
  align-items: center;
  background: var(--accent);
  color: #fff;
  margin: 0 auto 8px;
  padding: 12px 18px;
  min-width: 360px;
  border-radius: 4px;
}
.funnel-stage:nth-child(2) { background: var(--accent-2); }
.funnel-stage:nth-child(3) { background: var(--accent-3); }
.funnel-stage span { font-weight: 800; }
.funnel-stage strong { font-size: 25px; order: 3; text-align: right; }
.funnel-stage em { font-style: normal; opacity: .86; order: 2; text-align: right; }
.bar-row { display: grid; grid-template-columns: 134px 1fr 58px; gap: 10px; align-items: center; margin: 10px 0; }
.bar-label { font-weight: 700; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.bar-track { height: 13px; background: var(--panel-soft); border: 1px solid var(--grid); }
.bar-track span { display: block; height: 100%; background: var(--accent-2); }
.bar-value { text-align: right; color: var(--muted); font-weight: 700; }
.line-chart { width: 100%; height: 220px; background: #fff; border: 1px solid var(--grid); }
.line-chart polyline { fill: none; stroke-width: 4; }
.lead-line { stroke: var(--accent); }
.customer-line { stroke: var(--accent-3); }
.lead-dot { fill: var(--accent); }
.customer-dot { fill: var(--accent-3); }
.legend { display: flex; justify-content: center; gap: 14px; align-items: center; color: var(--muted); font-weight: 700; font-size: 13px; }
.legend span { width: 18px; height: 5px; display: inline-block; border-radius: 4px; }
.lead-key { background: var(--accent); }
.customer-key { background: var(--accent-3); }
.table-wrap { overflow-x: auto; }
table { width: 100%; border-collapse: collapse; font-size: 13px; }
th { background: #dcefeb; color: var(--ink); text-align: left; padding: 9px 8px; }
td { padding: 8px; border-bottom: 1px solid var(--grid); }
td:not(:first-child), th:not(:first-child) { text-align: right; }
.insight-panel { min-height: 250px; }
.insight-panel ul { margin: 0; padding-left: 18px; font-size: 15px; line-height: 1.45; }
.insight-panel li { margin: 9px 0; }
.right-rail { display: grid; gap: 8px; position: sticky; top: 10px; }
.rail-panel { padding: 8px; text-align: center; }
.rail-panel h3 { margin: 0 0 8px; font-size: 16px; }
.filter-pill {
  display: flex;
  min-height: 48px;
  align-items: center;
  justify-content: center;
  padding: 8px;
  margin: 7px 0;
  background: #f5fbff;
  border: 1px solid #aac5d5;
  border-radius: 8px;
  color: var(--ink);
  font-weight: 800;
}
.rail-panel.highlight strong { display: block; font-size: 16px; line-height: 1.2; }
.rail-panel.highlight span { display: block; margin-top: 10px; padding: 10px 6px; background: #fff5df; border: 1px solid #dfbd75; border-radius: 8px; font-weight: 800; }
@media (max-width: 980px) {
  .dashboard-title, .dashboard-grid, .left-board, .kpi-grid { grid-template-columns: 1fr; }
  .source-note { text-align: left; }
  .bar-row { grid-template-columns: 110px 1fr 58px; }
  .right-rail { position: static; }
}
"""
    (ROOT / "assets").mkdir(exist_ok=True)
    (ROOT / "assets" / "dashboard.css").write_text(css.strip() + "\n", encoding="utf-8")


def write_report(metrics: dict[str, pd.DataFrame | dict], recommendations: list[str]) -> None:
    summary = metrics["summary"]
    funnel = metrics["funnel"]
    channel = metrics["channel"]
    assert isinstance(summary, dict)
    assert isinstance(funnel, pd.DataFrame)
    assert isinstance(channel, pd.DataFrame)

    top = channel.head(5)
    report = [
        "# Marketing Funnel Analysis Report",
        "",
        f"Data source: {summary['data_source_note']}",
        "",
        "## Executive Summary",
        "",
        f"- Visitors analyzed: {_fmt_int(summary['visitors'])}",
        f"- Leads identified: {_fmt_int(summary['leads'])} ({_fmt_pct(summary['traffic_to_lead_rate'])} traffic-to-lead conversion)",
        f"- Customers identified: {_fmt_int(summary['customers'])} ({_fmt_pct(summary['lead_to_customer_rate'])} lead-to-customer conversion)",
        f"- Total revenue: ${summary['revenue_usd']:,.0f}",
        f"- Largest drop-off: {summary['largest_dropoff_stage']}",
        "",
        "## Funnel Definition",
        "",
        "The Kaggle Google Analytics data does not contain a CRM lead-status field, so this project uses a behavioral lead proxy: a session becomes a lead when it reaches at least 3 pageviews, 60 seconds on site, or 5 hits. A customer is a session with a transaction or transaction revenue.",
        "",
        "## Conversion Rates",
        "",
        _markdown_table(funnel),
        "",
        "## Best Channels",
        "",
        _markdown_table(top[["channel", "visitors", "leads", "customers", "traffic_to_lead_rate", "lead_to_customer_rate", "visitor_to_customer_rate", "revenue_usd"]]),
        "",
        "## Recommendations",
        "",
    ]
    report.extend([f"{i}. {rec}" for i, rec in enumerate(recommendations, start=1)])
    REPORTS_DIR.mkdir(exist_ok=True)
    (REPORTS_DIR / "funnel_analysis_report.md").write_text("\n".join(report) + "\n", encoding="utf-8")


def main() -> None:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    df, source_note = load_data()
    clean = flatten_ga_data(df)
    metrics = build_metrics(clean)
    summary = metrics["summary"]
    assert isinstance(summary, dict)
    summary["data_source_note"] = source_note
    recommendations = make_recommendations(metrics)

    clean_sample_cols = [
        "date",
        "fullVisitorId",
        "channel",
        "campaign",
        "source",
        "medium",
        "device_category",
        "country",
        "totals_hits",
        "totals_pageviews",
        "totals_timeOnSite",
        "revenue_usd",
        "lead",
        "customer",
    ]
    clean[[c for c in clean_sample_cols if c in clean.columns]].to_csv(PROCESSED_DIR / "clean_sessions_sample.csv", index=False)
    for name in ["funnel", "channel", "monthly", "campaign"]:
        value = metrics[name]
        assert isinstance(value, pd.DataFrame)
        value.to_csv(PROCESSED_DIR / f"{name}_metrics.csv", index=False)

    (PROCESSED_DIR / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (PROCESSED_DIR / "recommendations.json").write_text(json.dumps(recommendations, indent=2), encoding="utf-8")
    write_css()
    write_dashboard(metrics, recommendations)
    write_report(metrics, recommendations)
    print(f"Analysis complete. {source_note}")


if __name__ == "__main__":
    main()
