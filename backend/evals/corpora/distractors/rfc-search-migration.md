# RFC-112: Migrating Search to a Dedicated Cluster

Status: Accepted. Authors: Platform team.

## Background

Search currently runs on the same database cluster as the transactional workload. During month-end closing, customers run many reports and search latency rises sharply. This RFC proposes moving search to a dedicated cluster so that reporting traffic cannot degrade transactions.

## Goals

- Keep search latency under a few hundred milliseconds during month-end.
- Allow independent scaling of search and the main database.
- Avoid any customer-visible downtime during the migration.

## Non-goals

This RFC does not change the API, rate limits, plans or pricing. It does not change how backups or retention work, and it does not touch authentication, passwords or SSO.

## Proposal

We will create a new cluster with three nodes in each region. Writes will be mirrored from the primary database through change data capture. Once the new cluster is caught up, traffic will be moved gradually using a feature flag, starting with internal accounts.

During the rollout, the on-call engineer will watch dashboards for errors and latency. If anything looks wrong, the feature flag is switched off to send traffic back to the old path. The team will avoid running the migration during the change freeze and will coordinate with Customer Success before each step.

## Risks

Change data capture can fall behind under heavy load. To limit the impact, the rollout will pause automatically if the delay grows, and alerts will page the platform team. Another risk is cost: the new cluster increases infrastructure spending, which Finance has approved for this fiscal year.

## Security considerations

The new cluster will sit in the same private network as the existing database. Access follows least privilege and is limited to the search service account. No customer data leaves the existing regions.

## Timeline

Preparation in June, internal rollout in July, and full rollout before the end of the quarter. A short retrospective will be written after completion.
