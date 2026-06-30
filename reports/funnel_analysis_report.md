# Marketing Funnel Analysis Report

Data source: Offline sample generated because Kaggle competition data was not available locally

## Executive Summary

- Visitors analyzed: 2,500
- Leads identified: 1,685 (67.4% traffic-to-lead conversion)
- Customers identified: 55 (3.3% lead-to-customer conversion)
- Total revenue: $586
- Largest drop-off: Leads to customers

## Funnel Definition

The Kaggle Google Analytics data does not contain a CRM lead-status field, so this project uses a behavioral lead proxy: a session becomes a lead when it reaches at least 3 pageviews, 60 seconds on site, or 5 hits. A customer is a session with a transaction or transaction revenue.

## Conversion Rates

| stage     | count | stage_conversion | dropoff_from_prior |
| --------- | ----- | ---------------- | ------------------ |
| Visitors  | 2500  | 100.0%           | 0.0%               |
| Leads     | 1685  | 67.4%            | 32.6%              |
| Customers | 55    | 3.3%             | 96.7%              |

## Best Channels

| channel        | visitors | leads | customers | traffic_to_lead_rate | lead_to_customer_rate | visitor_to_customer_rate | revenue_usd |
| -------------- | -------- | ----- | --------- | -------------------- | --------------------- | ------------------------ | ----------- |
| Organic Search | 1045     | 699   | 17        | 66.9%                | 2.4%                  | 1.6%                     | 187.83      |
| Paid Search    | 533      | 366   | 16        | 68.7%                | 4.4%                  | 3.0%                     | 168.84      |
| Referral       | 272      | 186   | 13        | 68.4%                | 7.0%                  | 4.8%                     | 125.87      |
| Direct         | 359      | 242   | 7         | 67.4%                | 2.9%                  | 1.9%                     | 82.93       |
| Social         | 199      | 135   | 2         | 67.8%                | 1.5%                  | 1.0%                     | 20.98       |

## Recommendations

1. Prioritize Referral for qualified acquisition; it has the strongest visitor-to-customer conversion at 4.8%.
2. Use Paid Search landing-page and messaging patterns as a lead-capture benchmark because it converts traffic to leads at 68.7%.
3. Audit Organic Search spend and landing pages; its conversion quality trails the portfolio at 1.6%.
4. The biggest bottleneck is sales qualification; add remarketing, cart recovery, and high-intent follow-up for engaged non-buyers.
5. Track the funnel weekly by channel, campaign, device, and country so budget shifts are based on lead quality rather than traffic volume alone.
