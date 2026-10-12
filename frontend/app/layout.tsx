import type { Metadata } from "next";
import Link from "next/link";
import "leaflet/dist/leaflet.css";
import "./globals.css";

export const metadata: Metadata = {
  title: "Climate Hubris: Arctic sea ice and global monsoons",
  description:
    "Arctic sea ice volume against the first year on record, a first-order Blue Ocean Event projection from ocean heat, and an agent-assisted monitor of the world's monsoons and the food grown under them.",
};

const REPO_URL = process.env.NEXT_PUBLIC_REPO_URL;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <header className="site-header">
          <div className="wrap site-header-row">
            <Link href="/" className="brand">
              Climate Hubris
            </Link>
            <nav aria-label="Main">
              <Link href="/#arctic">Arctic sea ice</Link>
              <Link href="/#monsoon">Monsoons</Link>
              <Link href="/methodology/">Methodology</Link>
              {REPO_URL ? <a href={REPO_URL}>Source</a> : null}
            </nav>
          </div>
        </header>
        <main className="wrap">{children}</main>
        <footer className="site-footer">
          <div className="wrap">
            <p>
              Data: PIOMAS (Polar Science Center, University of Washington), NOAA NCEI ocean heat content, the
              Indicators of Global Climate Change heat inventory, CHIRPS rainfall via ClimateSERV (NASA SERVIR),
              cereal production from the World Bank and FAO with national statistics for India, China, Brazil and
              Australia, and bulletins from FAO GIEWS, FEWS NET, UN News, FloodList, NASA Earth Observatory and
              GDACS. Map outlines: Natural Earth.
            </p>
            <p>
              Built by <a href="https://akash.ucsciba.org">Akash Malampati</a>. Not an official forecast.{" "}
              <Link href="/methodology/">How the numbers are made</Link>.
            </p>
          </div>
        </footer>
      </body>
    </html>
  );
}
