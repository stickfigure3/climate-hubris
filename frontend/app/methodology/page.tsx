import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Methodology · Climate Hubris",
  description:
    "Data sources, the Blue Ocean Event projection model, Earth's energy imbalance, monsoon stress scoring by region and subregion, food production estimates, and their limits.",
};

export default function Methodology() {
  return (
    <article className="prose">
      <h1>Methodology</h1>
      <p>
        Everything on the dashboard is computed from public data by code you can read. This page says where each
        number comes from, how it is calculated, and where it should not be trusted.
      </p>

      <h2>Data sources</h2>
      <table>
        <thead>
          <tr>
            <th>Measure</th>
            <th>Source</th>
            <th>Updated</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>Arctic sea ice volume</td>
            <td>
              <a href="https://psc.apl.uw.edu/research/projects/arctic-sea-ice-volume-anomaly/">PIOMAS v2.1</a>, Polar
              Science Center, University of Washington. Monthly means and daily values, 1979 onwards.
            </td>
            <td>Checked twice a month</td>
          </tr>
          <tr>
            <td>Ocean heat content</td>
            <td>
              <a href="https://www.ncei.noaa.gov/access/global-ocean-heat-content/">NOAA NCEI</a> global ocean heat
              content anomaly, annual means, 0–700 m (1955 onwards) and 0–2000 m (2005 onwards).
            </td>
            <td>Checked twice a month</td>
          </tr>
          <tr>
            <td>Earth&rsquo;s energy imbalance</td>
            <td>
              Earth heat inventory from the{" "}
              <a href="https://github.com/ClimateIndicator/data">Indicators of Global Climate Change</a> project
              (Forster et al.), 1971 onwards: heat accumulated in the ocean, land, ice and atmosphere.
            </td>
            <td>Checked twice a month; published yearly</td>
          </tr>
          <tr>
            <td>Rainfall</td>
            <td>
              CHIRPS daily rainfall, averaged over each region and subregion through{" "}
              <a href="https://climateserv.servirglobal.net">ClimateSERV</a> (NASA SERVIR), 1991 onwards.
            </td>
            <td>Checked weekly</td>
          </tr>
          <tr>
            <td>Food production</td>
            <td>
              Cereal production by country from the{" "}
              <a href="https://data.worldbank.org/indicator/AG.PRD.CREL.MT">World Bank</a> (FAO data), split between
              states and provinces using national statistics for India, China, Brazil and Australia.
            </td>
            <td>Fixed table in the code, 2022–2024</td>
          </tr>
          <tr>
            <td>Reported conditions</td>
            <td>
              FAO GIEWS country briefs, FEWS NET regional outlooks, UN News, FloodList, NASA Earth Observatory and
              GDACS, read by a language model.
            </td>
            <td>Weekly in season, twice a month otherwise</td>
          </tr>
        </tbody>
      </table>
      <p>
        Each figure on the dashboard carries two dates: the newest value the source has published, and when this
        system last checked. If a source stops publishing, the dashboard flags it instead of presenting an old number
        as current.
      </p>

      <h2>The Blue Ocean Event projection</h2>
      <p>
        A Blue Ocean Event is the first September in which the Arctic Ocean is effectively free of sea ice. The model
        here is intentionally simple enough to check by hand.
      </p>
      <ol>
        <li>Take the lowest monthly ice volume of each year from PIOMAS (the September minimum).</li>
        <li>Take the annual mean global ocean heat content anomaly for the same years.</li>
        <li>
          Between a baseline year and the latest year with both values, divide the change in ice volume by the
          change in ocean heat. That ratio is the sensitivity: cubic kilometres of ice lost per zettajoule of heat
          the ocean has gained. By default the baseline is as far back as both records go: 1979, the first year of
          PIOMAS.
        </li>
        <li>
          Predict ocean heat by extending it in a straight line at its average yearly increase since 2020.
        </li>
        <li>
          Turn the predicted heat into ice with the sensitivity. The year that ice reaches zero is the projection.
        </li>
      </ol>
      <code className="formula">
        {`sensitivity   = (V_latest − V_baseline) / (OHC_latest − OHC_baseline)
ohc_rate      = (OHC_latest − OHC_(latest − window)) / window
OHC(t)        = OHC_latest + ohc_rate × (t − latest)
V(t)          = V_latest + sensitivity × (OHC(t) − OHC_latest)
years_to_BOE  = (V_latest − threshold) / (|sensitivity| × ohc_rate)`}
      </code>
      <p>
        The chart draws both halves of this on one set of years: ice volume on the left axis, ocean heat content on
        the right axis, each with its observed record and its projection. Ocean heat is an annual mean, so it sits
        at mid-year; the ice minimum sits in mid-September.
      </p>
      <p>
        NOAA publishes ocean heat in units of 10²² joules; the dashboard converts to zettajoules (10²¹ J), so one
        NOAA unit is ten zettajoules. Volumes are PIOMAS values in thousand cubic kilometres.
      </p>

      <h3>What you can change</h3>
      <ul>
        <li>
          <strong>Baseline year.</strong> The oldest year on record by default. A different starting year gives a
          different sensitivity, because single years are noisy.
        </li>
        <li>
          <strong>Heat uptake window.</strong> Three to six years back from the latest year; the default starts in
          2020. The window is short on purpose, to follow the recent acceleration in ocean warming, and it follows
          recent noise just as closely.
        </li>
        <li>
          <strong>Ocean layer.</strong> 0–700 m has the longer record; 0–2000 m captures more of the heat but only
          starts in 2005.
        </li>
        <li>
          <strong>Ice-free threshold.</strong> Zero by default. Researchers usually define ice-free by extent (under
          one million km²) because some thick ice lingers along coasts; a volume threshold above zero approximates
          that.
        </li>
      </ul>
      <p>
        The chart also draws a straight line fitted to every September minimum since 1979. It uses no ocean data at
        all, and is there so you can see how much the answer depends on the method.
      </p>

      <h3>Limitations</h3>
      <ul>
        <li>
          This is a first-order estimate based on a linear relationship. It does not account for non-linear
          feedbacks, albedo changes, or abrupt ice loss events.
        </li>
        <li>
          Global ocean heat is a proxy. Arctic ice responds to heat delivered to the Arctic specifically, and to
          winds, clouds and air temperature, none of which the model sees.
        </li>
        <li>
          The sensitivity is taken from two end points, not a regression, so an unusual baseline or latest year moves
          the result by years. Move the controls to see the spread.
        </li>
        <li>
          PIOMAS is a model that assimilates observations, not a direct measurement; its own uncertainty in the
          autumn minimum volume is about ±1,350 km³ (Schweiger et al., 2011).
        </li>
        <li>Published projections from climate models span decades. Treat the year shown as an illustration.</li>
      </ul>

      <h2>Then and now</h2>
      <p>
        The comparison card takes the newest day PIOMAS has published and the same calendar day in the oldest year
        of its daily record, 1979. PIOMAS uses a 365-day calendar, so 29 February never appears.
      </p>

      <h2>Earth&rsquo;s energy imbalance</h2>
      <p>
        The planet absorbs sunlight and radiates heat back to space. The imbalance is the difference between the
        two, in watts per square metre of the Earth&rsquo;s surface. The dashboard shows only that net figure, not
        the two flows.
      </p>
      <p>
        It is calculated from where the surplus ends up. The heat inventory adds up the heat gained by the ocean,
        land, ice and atmosphere since 1971; its rate of change, divided by the Earth&rsquo;s surface area, is the
        imbalance. One zettajoule a year is 0.062 W/m².
      </p>
      <code className="formula">
        {`imbalance(t) = (heat(t) − heat(t − 5)) / 5 years / 5.101 × 10¹⁴ m²`}
      </code>
      <ul>
        <li>
          Each point is the mean over the five years ending in that year, because single years of ocean heat content
          are noisy.
        </li>
        <li>
          The source publishes land, ice and atmosphere a few years behind the ocean. For those years (drawn dashed)
          the total is extended from ocean heat, assuming the ocean kept its share of the uptake, about 91%.
        </li>
        <li>
          Satellites measure the two flows directly (NASA CERES), and that is the chart most often shown. CERES data
          is only distributed behind a NASA Earthdata login, so it is not used here. The two methods agree on the
          trend; CERES resolves individual months, which the heat inventory cannot.
        </li>
      </ul>

      <h2>Monsoon stress score</h2>
      <p>
        Each region is a latitude and longitude box over the core land area of one monsoon system, with a fixed
        season. Its subregions share that season:
      </p>
      <table>
        <thead>
          <tr>
            <th>Region</th>
            <th>Season</th>
          </tr>
        </thead>
        <tbody>
          <tr><td>South Asian (India)</td><td>June to September</td></tr>
          <tr><td>East Asian</td><td>May to September</td></tr>
          <tr><td>West African</td><td>June to September</td></tr>
          <tr><td>Australian</td><td>December to March</td></tr>
          <tr><td>South American</td><td>December to March</td></tr>
          <tr><td>Southern African</td><td>November to March</td></tr>
        </tbody>
      </table>

      <h3>Subregions</h3>
      <p>
        Each region is divided into subregions, 58 in all, and every subregion is scored exactly as its region is:
        its own rainfall box, the same 1991–2020 normal, the same thresholds. Subregions follow borders that
        statistics are published for. India, China and Brazil are split into states or provinces, with small
        producers merged into a neighbour (Punjab with Haryana, Bihar with Jharkhand) so that no subregion is
        dwarfed by the one beside it; the other countries in a region are subregions of their own, or are merged
        where they are small (Senegal with Gambia, Benin with Togo).
      </p>
      <p>
        A subregion&rsquo;s box covers its farmed core, and neighbouring boxes overlap at the edges. Subregions use
        their region&rsquo;s season even where the local calendar differs: Tamil Nadu, for one, gets most of its
        rain from the October to December monsoon, which is not scored.
      </p>

      <h3>Food production and box sizes</h3>
      <p>
        On the map, every box is a square whose area is proportional to the cereals grown there, in million tonnes
        a year. A region is the sum of its subregions. Click a region and the map zooms in to its subregions, each
        sized by its share of the region. A box is centred on the area it describes and nudged just far enough that
        boxes do not overlap, so position is approximate and size is the message.
      </p>
      <ul>
        <li>
          <strong>Countries:</strong> World Bank indicator AG.PRD.CREL.MT (FAO data), the mean of 2022, 2023 and
          2024. Rice is counted as paddy.
        </li>
        <li>
          <strong>States and provinces:</strong> the country&rsquo;s figure multiplied by the group&rsquo;s share
          of the national total in that country&rsquo;s own statistics: India&rsquo;s 2023–24 foodgrains, China&rsquo;s
          2024 grain output, and Brazil&rsquo;s 2023 maize, rice and wheat.
        </li>
        <li>
          <strong>Australia:</strong> Queensland&rsquo;s wheat, barley and sorghum from the ABARES crop report.
          The Top End and the Kimberley grow almost no grain; no published figure was found, and they are entered
          as 0.05 million tonnes so that they still appear.
        </li>
      </ul>
      <p>
        These are sizing estimates, good to roughly ten percent. Cereals stand in for food: the figures leave out
        pulses, oilseeds, roots, sugar and livestock, which understates places such as northern Australia (cattle
        and sugar cane) and Brazil (soybeans). The smallest boxes are drawn larger than their production so that
        they can still be clicked. The full table can be downloaded from the dashboard.
      </p>

      <h3>Rainfall anomaly</h3>
      <p>
        Daily CHIRPS rainfall averaged over the box is summed by month. The normal for a month is its mean over
        1991–2020. The anomaly for a season is the rain that has fallen so far divided by the normal for the same
        days, minus one. A month that is only partly published is compared with a pro-rated normal.
      </p>

      <h3>Agent findings</h3>
      <p>
        A language model reads each source document and extracts explicit statements about monsoon failure,
        below-average rainfall, drought or flooding, with a severity from 0 to 10. Three checks apply to everything it
        returns:
      </p>
      <ul>
        <li>
          Every finding must include a quote, and the quote must appear word for word in the source. Findings that
          fail are discarded, and the count of discards is recorded.
        </li>
        <li>The quote itself must mention rainfall, drought or flooding.</li>
        <li>The source link and retrieval date are attached by code, never written by the model.</li>
        <li>
          A finding counts towards a subregion only if the model names one of that region&rsquo;s subregions for
          it, or if the source is a brief about a single country that is itself a subregion. Everything else counts
          towards the region alone.
        </li>
      </ul>
      <p>
        Forecasts are labelled as forecasts and shown, but only reported conditions count towards the score.
      </p>

      <h3>Combining them</h3>
      <table>
        <thead>
          <tr>
            <th>Colour</th>
            <th>Rainfall</th>
            <th>Or agent severity</th>
          </tr>
        </thead>
        <tbody>
          <tr><td>Green, normal</td><td>Within 10% of normal, or wetter</td><td>0 to 3</td></tr>
          <tr><td>Yellow, moderate stress</td><td>10% to 25% below normal</td><td>4 to 6</td></tr>
          <tr><td>Red, severe stress</td><td>More than 25% below normal</td><td>7 to 10</td></tr>
        </tbody>
      </table>
      <p>
        A region takes the worse of its two signals. Outside its season a region is shown as off-season, and the
        dashboard reports how its last completed season ended. In April, May, October and November the last-season
        summary leads.
      </p>

      <h3>Limitations</h3>
      <ul>
        <li>
          CHIRPS is published about six weeks behind, so early in a season the rainfall signal is missing and the
          score rests on agent findings alone.
        </li>
        <li>
          A region&rsquo;s average hides local failure: a drought in one state can sit inside a region that reads
          normal. The subregions are there to show it, but a subregion box is still an average over a large area.
        </li>
        <li>
          Sources for subregions are thin. Most are national briefs, so states of India, China and Brazil get an
          agent finding only when a document names them, and usually rest on rainfall alone.
        </li>
        <li>
          Excess rain is not scored from rainfall data. Flooding reaches the score only through agent findings.
        </li>
        <li>
          The India Meteorological Department API only answers allow-listed IP addresses, so state-level Indian data
          is not included yet. ReliefWeb&rsquo;s API needs a registered application name and is likewise skipped
          until one is configured.
        </li>
        <li>
          Severity is a model&rsquo;s reading of a text. The quote and source are shown with every finding so you can
          judge it yourself.
        </li>
      </ul>
    </article>
  );
}
