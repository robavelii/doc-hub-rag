# Platform On-Call Runbook

Owner: Site Reliability Engineering. Applies to the Ledgerline production environment.

## Rotation

The primary on-call rotation is one week long and hands over every Tuesday at 11:00 UTC. Each rotation has a primary and a secondary engineer. If the primary does not acknowledge a page within 5 minutes, PagerDuty escalates to the secondary; after another 10 minutes it escalates to the Engineering Manager on duty.

On-call engineers receive a flat stipend of 500 USD per week plus 50 USD for every page received between 22:00 and 07:00 local time.

## Severity Levels

- SEV1: the product is down or customer data is at risk for all or most customers. Response within 15 minutes, status page update within 30 minutes, incident commander required.
- SEV2: a major feature is unavailable or severely degraded for many customers, for example bank feeds failing for a whole region. Response within 30 minutes.
- SEV3: a minor feature is broken or a single customer is affected. Handled during business hours.
- SEV4: cosmetic issues and internal tooling problems. Tracked as a normal ticket.

Every SEV1 and SEV2 requires a written postmortem within 5 business days, reviewed in the Thursday reliability meeting.

## Incident Process

1. Acknowledge the page in PagerDuty.
2. Open an incident channel with the Slack command `/incident new`, which creates a channel named `#inc-<date>-<slug>`.
3. For SEV1 and SEV2, assign an incident commander. The commander coordinates and does not debug.
4. Post status updates in the channel every 30 minutes until resolved.
5. Update status.ledgerline.example for anything customer-visible.

## Deployments

Production deploys run through the `ship` pipeline in GitHub Actions. Deploys are allowed Monday through Thursday between 09:00 and 16:00 UTC. Deploying on Fridays, weekends or during the December change freeze (December 15 to January 5) requires approval from the VP of Engineering.

Every deploy goes to a 5% canary for 20 minutes. The pipeline automatically promotes the release if the error rate stays below 1% and p95 latency stays below 800 ms; otherwise it rolls back automatically.

## Rollback

To roll back manually, run `ship rollback --env production --to <release-id>` from the ops toolbox. Rollbacks typically complete in about 4 minutes. Database migrations are not rolled back automatically: every migration must be backward compatible with the previous release so that application rollback is always safe.

## Database

The primary database is PostgreSQL 16 on Amazon RDS with one synchronous standby in a second availability zone and two read replicas. Automatic failover to the standby takes 60 to 120 seconds; the application reconnects on its own.

If replication lag on a read replica exceeds 30 seconds, remove it from the reader pool with `ops db replica drain <name>`. Never run manual writes against production without a second engineer reviewing the SQL in the incident channel.

Point-in-time recovery is available for the last 14 days.

## Queues and Background Jobs

Background jobs run on Celery with Redis as the broker. If the bank-feed queue backlog exceeds 50,000 jobs, scale the `feeds-worker` deployment to 40 replicas with `ops scale feeds-worker 40`. Do not flush the Redis broker; that loses customer sync jobs.

## Third-Party Outages

If Plaid is degraded, enable the feature flag `bankfeeds.plaid.pause` to stop retries and avoid hitting Plaid's rate limits. Post in #customer-success so support can answer tickets. If Stripe webhooks are delayed, no action is needed; Stripe retries for up to 3 days.

## Access During Incidents

Production shell access is granted through Teleport with the `prod-incident` role, which requires approval from a second on-call engineer and expires after 4 hours.
