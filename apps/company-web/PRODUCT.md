# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users
- Drug-safety lead (`company_safety`): watches side-effect signals per drug version and cohort; exports pseudonymized records.
- Medical affairs (`company_reader`): compares cohorts and drug versions.
- Survey admin (`company_admin`): edits questions and check-in cadence per cohort.
- Hackathon judges: see the portal on a projector during the demo and must understand within a minute that only coded, aggregated data reaches the company.

## Product Purpose
The company portal of SafeSignal. Patients check in by voice at home, and their device codes what they say into label terms. The company sees side-effect counts by cohort and drug version, week over week, but never names, words or audio.

## Positioning
The company is the trusted party in the system. Its value is cohort signals grounded in real trials (FLAURA, MARIPOSA, MELODY), and the evidence of that is what it cannot see.

## Capabilities and Constraints
- Routes: `#/signals`, `#/completion`, `#/survey`, `#/program`. Data comes only from the service's company endpoints (`schema/`).
- Weekly groups under 5 patients are dropped; severe counts of 1–4 show as "<5".
- Roles gate actions: export needs `company_safety`, survey publish needs `company_admin`.
- Appearance: light, dark and system.
- Fonts are bundled; no third-party requests, analytics or tracking (Scoping Doc 26.12).

## Brand Commitments
- Name: SafeSignal. Halvaren Therapeutics is a fictional company; rates and documents come from public sources.
- The product owner's binding reference for the company portal is the feel of Apple and Samsung product pages: centered, calm, premium (D-092).

## Evidence on Hand
Seeded synthetic data from the local service, public trial rates and FDA labels. No customer logos, testimonials, pricing or user counts exist; never invent them.

## Product Principles
1. Show what the company can see, and say plainly what it cannot.
2. One idea per section; readable from the back of a room.
3. The tool disappears into the task; numbers lead.
