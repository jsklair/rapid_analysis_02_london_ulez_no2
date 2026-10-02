# Data sources and site-selection notes

**Analysis snapshot date:** 2 October 2026

## Primary monitoring data

### London Air Quality Network (LAQN)

https://www.londonair.org.uk/LondonAir/Default.aspx

API documentation:

https://api.erg.ic.ac.uk/AirQuality/help

Used for hourly nitrogen dioxide (NO₂) observations and site metadata for the treated outer-London monitors.

The API reports London air-quality measurements through Imperial College London's Environmental Research Group. LondonAir reports NO₂ concentrations in µg/m³.

Primary treated sites:

- HV1 - Havering - Rainham
- HV3 - Havering - Romford

BY7 - Bromley - Harwood Avenue is retained only as a sensitivity site because it failed the frozen operational-year-1 completeness rule.

### Defra UK-AIR / Automatic Urban and Rural Network (AURN)

https://uk-air.defra.gov.uk/

Used for hourly NO₂ observations and site metadata for the non-London comparison sites.

Primary comparison sites:

- LEIR - Leicester A594 Roadside
- DCST - Doncaster A630 Cleveland Street
- BLAR - Blackburn Accrington Road

## Study window and data-quality rule

Study window: **July 2021 to August 2025**.

A site-month is valid only when at least **75% of expected hourly NO₂ observations** are present.

Primary sites also had to pass phase-specific minimum valid-month requirements:

- at least 45 of 50 months overall;
- at least 16 of 18 baseline months;
- at least 7 of 8 anticipation months;
- at least 11 of 12 operational-year-1 months;
- at least 11 of 12 operational-year-2 months.

No missing monthly NO₂ values are imputed.

## Site-selection audit

The structured selection table is in:

`data/site_selection.csv`

The control pool was screened before the ULEZ effect was estimated. Monitoring availability alone was not enough. Sites were excluded for material data gaps, monitoring start dates or local road/transport interventions that could alter roadside NO₂ independently of London's ULEZ.

Key final-stage exclusions included:

### Nottingham Western Boulevard

Transport Nottingham states that Beechdale Road area works began in July 2023 and included new segregated cycle routes, junction changes and road resurfacing, with the scheme completed in 2024.

https://www.transportnottingham.com/project/beechdale-and-wigman/

This overlaps the first post-expansion year and was treated as local intervention contamination.

### Christchurch Barrack Road

BCP Council states that Barrack Road Railway Bridge maintenance began on 3 June 2024 for approximately six weeks, with the dual carriageway reduced to one lane in each direction.

https://www.bcpcouncil.gov.uk/news-hub/news-articles/barrack-road-railway-bridge-maintenance

This directly affects the monitored road during operational year 1.

### Doncaster Cleveland Street

City of Doncaster Council records that the Cleveland Street bus gate began in September 2018.

https://www.doncaster.gov.uk/Documents/DocumentView/Stream/Media/Default/Council%20and%20Democracy/Bus%20gates.pdf

Because this predates the July 2021 baseline, it is treated as an established site characteristic rather than a new study-window intervention.

### Leicester

Leicester City Council's 2025-2030 Air Quality Action Plan states that the council has no plans to introduce road charging such as a Clean Air Zone or Ultra Low Emission Zone because it does not meet central-government criteria for such a scheme.

https://www.leicester.gov.uk/sites/default/files/2025-12/air-quality-action-plan-leicester-2025-2030.pdf

## External ULEZ evidence used for context

### Greater London Authority: London-wide ULEZ One Year Report

Published 7 March 2025.

https://www.london.gov.uk/programmes-strategies/environment-and-climate-change/environment-and-climate-change-publications/london-wide-ultra-low-emission-zone-one-year-report

The report estimates that, in the first year of operation, outer-London roadside NO₂ was up to 4.8% lower than expected without the London-wide expansion.

### Greater London Authority: second-year information request

Response dated 15 August 2025.

https://www.london.gov.uk/who-we-are/governance-and-spending/sharing-our-information/foi-disclosure-log/eir-ulez-second-year-air-quality-change-aug-2025

The GLA stated that it had not replicated the one-year air-quality analysis for September 2024 to September 2025, while noting that monitoring data were publicly available.

### Peer-reviewed study

*Further improvement in London's air quality demands more than the Ultra Low Emission Zone policy*, npj Clean Air, 2025.

https://www.nature.com/articles/s44407-025-00030-9

The study used weather normalisation and an augmented synthetic-control method across a substantially larger monitoring network. For the 2023 expansion it used data from 19 July 2021 to 30 April 2024 and reported no statistically detectable NO₂ effect.

## Comparability note

The GLA report, the peer-reviewed study and RA02 use different site sets, counterfactual methods, weather treatment and time windows.

Their numerical estimates should not be treated as directly comparable measures of the same parameter.

## Snapshot provenance

`data/processed/source_metadata.json` stores the source URLs, analysis date and SHA-256 checksum of the processed monthly panel used for publication.

The live preparation script is a refresh route. It is not a guarantee that future revised monitoring data will reproduce the 2 October 2026 snapshot exactly.
