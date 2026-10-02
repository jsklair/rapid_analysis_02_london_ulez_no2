# Methodology note

## Analytical question

What evidence is there that the August 2023 London-wide ULEZ expansion produced an additional reduction in roadside NO₂ in newly covered outer London, relative to comparable areas outside London, and did that difference persist into the second operational year?

## Design

The final design is a comparative monthly time series.

The treated group is the equal-weight average of two eligible outer-London roadside monitors. The comparison group is the equal-weight average of three non-London traffic monitors that passed both data-quality and local-intervention screens.

Each site's monthly NO₂ is first centred on its own valid baseline mean. This removes permanent level differences across monitoring locations before group averages are constructed.

No missing monthly NO₂ values are imputed.

## Why the design changed from the initial plan

The feasibility stage initially considered site-level difference-in-differences and event-study estimation.

After the pre-declared data and intervention screens, only two treated and three primary control sites remained. Conventional cluster-robust site-level inference with five clusters would be unreliable.

The primary model was therefore changed before estimating the post-expansion effect. It uses the monthly treated-minus-control gap with heteroscedasticity-and-autocorrelation-consistent uncertainty.

## Primary specification

Outcome:

`average treated change from site baseline - average control change from site baseline`

Regressors:

- anticipation indicator;
- operational-year-1 indicator;
- operational-year-2 indicator;
- annual sine term;
- annual cosine term.

The baseline is the omitted phase.

Uncertainty uses HAC standard errors with three monthly lags.

## Diagnostics and sensitivity checks

- 18-month baseline differential-trend regression;
- calendar-month fixed effects instead of harmonic seasonality;
- explicit differential linear-trend diagnostics;
- 43-month strict complete-case panel;
- leave-one-control-out estimates;
- Bromley Harwood Avenue treated-site sensitivity.

The explicit differential-trend models are intentionally reported because the short baseline cannot rule out slower-moving treated-control divergence with confidence.

## Interpretation boundary

The preferred estimates describe relative changes in this screened monitoring panel.

They are not a complete structural estimate of the policy's causal effect on all of outer London, and they do not isolate the daily charge from scrappage support, publicity, exemptions, anticipation or wider fleet changes.
