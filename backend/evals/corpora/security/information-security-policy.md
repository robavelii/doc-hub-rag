# Information Security Policy

Document ID: SEC-POL-001. Owner: Security Engineering. Last reviewed: January 2026.

## Scope

This policy applies to every employee, contractor and vendor with access to Northwind systems or customer data. Violations may lead to disciplinary action up to and including termination.

## Data Classification

Northwind data is classified into four levels:

- Public: approved for anyone, such as the marketing website and published documentation.
- Internal: default for company information, such as the handbook, roadmaps and meeting notes.
- Confidential: customer data, financial results before publication, contracts and employee records.
- Restricted: encryption keys, production database credentials, payment card data and health information.

Confidential data may only be shared externally under a signed NDA. Restricted data must never be stored on laptops, in chat messages or in email, and may only be accessed through the production bastion host with a ticket reference.

## Passwords and Authentication

All accounts must use the company SSO (Okta) wherever the application supports it. Passwords for systems outside SSO must be at least 16 characters long and stored in 1Password; reusing passwords across systems is prohibited.

Multi-factor authentication is mandatory for every account. Hardware security keys (YubiKey 5 series) are required for administrators, engineers with production access and the finance team. SMS codes are not an accepted second factor.

Okta sessions expire after 12 hours. Production access sessions through the bastion expire after 1 hour of inactivity.

## Devices

Company laptops must have full-disk encryption (FileVault) enabled, automatic screen lock after 5 minutes of inactivity, and the Kandji agent installed. Operating system security updates must be installed within 14 days of release; devices more than 30 days behind are automatically blocked from SSO.

Personal devices may be used for email and chat only through the Okta Verify mobile app with a device passcode. Personal computers may not be used to access source code or customer data.

Lost or stolen devices must be reported to security@northwindlabs.example within 1 hour of discovery so they can be remotely wiped.

## Access Management

Access is granted according to least privilege and requested through the IT portal with manager approval. Production access additionally requires approval from the Security on-call engineer.

Access reviews are performed every quarter. Accounts of departing employees are disabled within 4 hours of their last working day; contractor accounts expire automatically after 90 days unless renewed.

Shared accounts are prohibited, except for break-glass accounts whose credentials are sealed in the Restricted vault and rotated after every use.

## Network and Remote Access

Access to internal tools does not require VPN; it is protected by Cloudflare Access with device posture checks. The legacy OpenVPN service was decommissioned in September 2025.

Public Wi-Fi may be used, but employees must not disable the Cloudflare WARP client on company devices.

## Vendors and AI Tools

New vendors that will process Confidential or Restricted data need a security review before the contract is signed. The review takes about 10 working days and requires the vendor's SOC 2 Type II report or ISO 27001 certificate.

Customer data must not be pasted into external AI chatbots. Approved AI tools are listed on the Security wiki; at the time of writing, only the enterprise workspace of Claude and the internal Doc-Hub assistant are approved for Confidential data.

## Incident Reporting

Anyone who suspects a security incident must report it immediately in the #security-incidents Slack channel or by calling the security hotline at +1-555-0100. Do not try to investigate on your own and do not delete evidence.

Phishing emails should be reported with the "Report Phish" button in Gmail. Clicking a phishing link is not a disciplinary matter if it is reported promptly.

The Security team classifies incidents within 30 minutes of the report. If personal data is affected, Legal is informed so that regulators can be notified within 72 hours as required by GDPR.

## Logging and Retention

Security logs are retained for 13 months in the SIEM. Application logs must not contain passwords, API keys, full payment card numbers or health information.

## Exceptions

Exceptions to this policy must be requested in writing from the CISO, are valid for at most 6 months, and must include a compensating control.
