# Climate Hubris: feature list

Updated 12 October 2026. Every item on the previous to-do list is done; nothing is open.

## Arctic sea ice

- **Then-and-now card:** ice volume on the latest published day against the same date in 1979, the oldest year in the record, with the difference in km³ and percent.
- **Ice-free projection:** a headline year for the first ice-free September, from ocean heat content extended in a straight line at its average rate of increase since 2020, beside a plain linear-trend year for comparison.
- **Volume and ocean heat chart:** the full 1979 to present ice record, September minima, trend line and the projected path to zero, with global ocean heat content overlaid on the same years and its own axis on the right, observed and projected. Hover values and a table view cover both.
- **Adjustable assumptions:** baseline year (defaults to 1979, as far back as the data goes), heat-uptake window (3 to 6 years, defaulting to "since 2020"), ocean layer (0–700 m or 0–2000 m) and ice-free threshold; the API recomputes on each change.
- **Earth's energy imbalance chart:** the net imbalance only, in W/m², with no incoming or outgoing series. It is a 5-year mean derived from the published Earth heat inventory, 1976 onwards.
- **Disclaimer:** the first-order-estimate caveat is shown next to the projection.

## Global monsoon monitor

- **Six regions:** South Asian, East Asian, West African, Australian, South American and Southern African, each with a fixed season.
- **58 subregions:** every region is split along borders that statistics exist for. India, China and Brazil are split into states or provinces, with small producers merged into a neighbour; other countries are subregions of their own or merged where small. South Asia, for example, is 11 groups of Indian states plus Pakistan, Bangladesh, Nepal and Sri Lanka.
- **Food production estimates:** cereal production in million tonnes a year for every region and subregion, from World Bank/FAO country figures split by state using national statistics.
- **World map:** each region is a box sized by its cereal production and coloured green, yellow or red by stress score.
- **Zoom to subregions:** clicking a region zooms the map in and shows its subregions, each sized by its share of the region's cereals and coloured by its own score; an "All regions" button zooms back out.
- **Stress score:** the worse of rainfall anomaly against the 1991–2020 normal and agent-reported severity, calculated the same way for regions and subregions.
- **Region panel:** food production, rainfall anomaly, a 35-season history chart, a table of subregions (production, rainfall, status) and agent findings with quotes and source links.
- **Subregion panel:** the same detail for one subregion, with its share of the region and where its production estimate comes from.
- **Off-season mode:** in April, May, October and November the page leads with a last-season summary table, which now includes each region's cereal production.
- **View toggle:** switch the map between live conditions and the last completed season.

## Agent

- **Sources:** 32 FAO GIEWS country briefs (one for nearly every country that is or contains a subregion), 2 FEWS NET regional pages, and UN News, FloodList, NASA Earth Observatory and GDACS feeds.
- **Structured findings:** region, subregion where the statement is specific to one, category, observed or forecast, severity 0–10, one-sentence summary and a supporting quote.
- **Subregion decided by code:** a subregion the model names is kept only if it belongs to that region; a brief about a single country counts towards the subregion that is that country.
- **Verbatim check:** a finding is dropped unless its quote appears word for word in the source and mentions rainfall, drought or flooding.
- **Forecasts kept separate:** shown with a label, never counted in the score.
- **No repeat reads:** unchanged documents are skipped by content hash.
- **Schedule:** weekly while any monsoon is active, twice a month otherwise.
- **Model:** LangChain on Amazon Bedrock; switchable to OpenAI by setting.

## Data pipeline, API and infrastructure

- **Ingestion jobs:** PIOMAS sea ice (monthly and daily), NOAA ocean heat content, the Earth heat inventory, and CHIRPS rainfall through ClimateSERV for all 64 boxes (6 regions and 58 subregions).
- **Bundled history:** 35 years of monthly rainfall for every region and subregion ship with the repo, so a fresh setup has data immediately.
- **API:** FastAPI with endpoints for Arctic data, projection parameters, monsoon overview, a region with its subregions, a single subregion, and freshness; OpenAPI docs at /api/docs.
- **Storage:** one DynamoDB table; each dataset is a single partition.
- **Frontend:** Next.js static export, light and dark themes, mobile layout, map with no third-party tile requests.
- **Local development:** docker compose up runs the database, API, data bootstrap and frontend.
- **AWS template and deploy script:** four Lambdas from one container image, HTTP API with throttling, schedules, Amplify hosting, a $15 billing alarm and budget.
- **Tests and CI:** 52 backend tests; GitHub Actions runs tests, lint and the frontend build.

## Portfolio extras

- **Freshness labels:** every figure shows the newest date its source has published and when it was last checked; stale or unreachable sources are flagged.
- **Methodology page:** data sources, the projection formula, the energy imbalance calculation, monsoon scoring, subregions, food production estimates and their limits.
- **CSV export:** Arctic data, monthly rainfall with normals for every region and subregion, agent findings, and the food production table.
- **README:** architecture diagram, cost breakdown, local and AWS instructions.
- **Public repo:** [stickfigure3/climate-hubris](https://github.com/stickfigure3/climate-hubris), MIT licence.

## Not live yet

- **AWS deployment:** nothing is deployed; the site runs only on this machine.
- **Subregion agent findings:** the agent has not been run since subregions were added, so no finding is tied to a subregion yet and subregions are scored on rainfall alone.
- **Satellite energy imbalance:** NASA CERES, the record of energy in and out, needs an Earthdata login, so the chart uses the heat inventory instead.
- **Food production for northern Australia:** no published grain figure was found for the Northern Territory or the Kimberley; both are entered as negligible.
- **IMD state rainfall:** the client is written, but IMD refuses addresses that are not allow-listed.
- **ReliefWeb:** skipped until an approved app name is registered.
- **Claude Haiku on Bedrock:** blocked until Anthropic's use-case form is submitted; the agent has run on Amazon Nova 2 Lite so far.
