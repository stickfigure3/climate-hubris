import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Methodology · Climate Hubris",
  description: "Data sources, the Blue Ocean Event projection model, monsoon stress scoring, and their limits.",
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
            <td>Regional rainfall</td>
            <td>
              CHIRPS daily rainfall, averaged over each region through{" "}
              <a href="https://climateserv.servirglobal.net">ClimateSERV</a> (NASA SERVIR), 1991 onwards.
            </td>
            <td>Checked weekly</td>
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
          Between a baseline year (2000 by default) and the latest year with both values, divide the change in ice
          volume by the change in ocean heat. That ratio is the sensitivity: cubic kilometres of ice lost per
          zettajoule of heat the ocean has gained.
        </li>
        <li>Average the yearly increase in ocean heat over the last decade.</li>
        <li>Multiply the two to get ice lost per year, and divide the ice that remains by it.</li>
      </ol>
      <code className="formula">
        {`sensitivity   = (V_latest − V_baseline) / (OHC_latest − OHC_baseline)
ohc_rate      = (OHC_latest − OHC_(latest − window)) / window
years_to_BOE  = (V_latest − threshold) / (|sensitivity| × ohc_rate)`}
      </code>
      <p>
        NOAA publishes ocean heat in units of 10²² joules; the dashboard converts to zettajoules (10²¹ J), so one
        NOAA unit is ten zettajoules. Volumes are PIOMAS values in thousand cubic kilometres.
      </p>

      <h3>What you can change</h3>
      <ul>
        <li>
          <strong>Baseline year.</strong> A different starting year gives a different sensitivity, because single
          years are noisy.
        </li>
        <li>
          <strong>Heat uptake window.</strong> Three to twenty years. Short windows follow recent acceleration and
          recent noise alike.
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

      <h2>Monsoon stress score</h2>
      <p>
        Each region is a latitude and longitude box over the core land area of one monsoon system, with a fixed
        season:
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
          A box average hides sub-regional failure: a drought in one state can sit inside a region that reads normal.
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
