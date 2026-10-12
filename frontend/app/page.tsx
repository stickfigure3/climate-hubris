"use client";

import { ArcticSection } from "@/components/ArcticSection";
import { MonsoonSection } from "@/components/MonsoonSection";
import { useApi } from "@/lib/api";
import type { Meta } from "@/lib/types";

export default function Dashboard() {
  const meta = useApi<Meta>("/api/meta");
  return (
    <>
      <div className="intro">
        <h1>Two slow emergencies, measured as they happen</h1>
        <p>
          Arctic sea ice keeps thinning, and the monsoons that billions of people farm by do not always deliver.
          This dashboard tracks both from public data, refreshed on a schedule, with every number dated.
        </p>
      </div>
      <ArcticSection meta={meta.data} />
      <MonsoonSection meta={meta.data} />
    </>
  );
}
