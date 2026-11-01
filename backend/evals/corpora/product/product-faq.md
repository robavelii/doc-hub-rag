# Ledgerline Product FAQ

Ledgerline is Northwind's accounting automation product for small and mid-size businesses. This FAQ is maintained by the Customer Success team.

## Plans and Pricing

Ledgerline has three plans:

- Starter: 49 USD per month, up to 3 users and 500 transactions per month.
- Growth: 149 USD per month, up to 15 users and 5,000 transactions per month, plus multi-currency support.
- Enterprise: custom pricing, unlimited users, SAML single sign-on, a dedicated customer success manager and a 99.95% uptime SLA.

Annual billing gives a 20% discount on Starter and Growth. Nonprofits registered as charities receive an additional 30% discount on any plan after verification.

Additional transactions beyond the plan limit are billed at 2 cents each. Customers are notified by email when they reach 80% of their monthly transaction limit.

## Free Trial

New accounts get a 21-day free trial of the Growth plan. No credit card is required to start the trial. When the trial ends without a payment method, the account becomes read-only for 30 days and is then deleted.

## Billing

Invoices are issued on the first day of each billing period and are payable by card or, for annual Enterprise contracts, by bank transfer within 30 days. Ledgerline accepts Visa, Mastercard and American Express; PayPal is not supported.

If a card payment fails, Ledgerline retries the charge after 3, 5 and 7 days. After the final retry fails, the account is downgraded to read-only until the balance is paid.

Customers can cancel at any time from Settings > Billing. Monthly plans are not refunded for the remaining period. Annual plans can be refunded on a prorated basis within the first 60 days.

## Integrations

Ledgerline integrates with Stripe, Shopify, QuickBooks Online, Xero and Gusto. Bank feeds are available for more than 9,000 banks in North America and Europe through Plaid and GoCardless.

The Shopify integration syncs orders every 15 minutes. The Stripe integration uses webhooks and syncs payouts in near real time. QuickBooks and Xero exports run nightly at 02:00 UTC.

## API

The REST API is available on Growth and Enterprise plans. Requests are authenticated with an API token created under Settings > Developers. The rate limit is 120 requests per minute on Growth and 600 requests per minute on Enterprise; exceeding it returns HTTP 429 with a Retry-After header.

Webhooks are signed with HMAC-SHA256 using the endpoint's signing secret. Failed webhook deliveries are retried with exponential backoff for up to 72 hours.

## Security and Compliance

Ledgerline is SOC 2 Type II certified and the report is available under NDA. Data is encrypted at rest with AES-256 and in transit with TLS 1.2 or higher. Customer data is hosted in AWS us-east-1 for North American customers and eu-central-1 (Frankfurt) for European customers; the region is chosen at sign-up and cannot be changed later.

Daily backups are kept for 35 days. Deleted accounts are permanently erased from backups after 35 days.

## Users and Permissions

There are four roles: Owner, Admin, Accountant and Viewer. Only the Owner can change the plan or close the account. Accountants can reconcile transactions and run reports but cannot invite users. Viewers have read-only access.

External accountants can be invited at no extra charge and do not count toward the user limit, up to a maximum of 2 external accountants per account.

## Support

Starter customers get email support with a response time of one business day. Growth customers get chat and email support with a 4-hour response time during business hours. Enterprise customers get 24/7 phone support with a 1-hour response time for critical issues.

The status page is available at status.ledgerline.example.
