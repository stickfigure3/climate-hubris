"""Local command line for the same jobs the Lambdas run.

    python -m app.cli init       create the table (DynamoDB Local)
    python -m app.cli arctic     ingest PIOMAS, ocean heat content and Earth's heat inventory
    python -m app.cli rainfall   load the rainfall seed, then fetch newer months
    python -m app.cli imd        try the IMD state-wise API
    python -m app.cli agent      run the agent once (calls the LLM)
    python -m app.cli bootstrap  init + arctic + rainfall + imd
"""

from __future__ import annotations

import json
import logging
import sys

from .agent import run as agent
from .ingest import climateserv, eei, imd, ohc, piomas
from .store import Store, create_table


def main(argv: list[str]) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    commands = argv or ["--help"]
    if commands[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    if commands[0] == "bootstrap":
        commands = ["init", "arctic", "rainfall", "imd"]

    for command in commands:
        if command == "init":
            create_table()
            result = "table ready"
        elif command == "arctic":
            store = Store()
            result = {"piomas": piomas.ingest(store), "ohc": ohc.ingest(store), "energy_imbalance": eei.ingest(store)}
        elif command == "rainfall":
            result = climateserv.ingest(Store())
        elif command == "imd":
            result = imd.ingest(Store())
        elif command == "agent":
            result = agent.run(Store(), force=True)
        else:
            print(f"unknown command: {command}\n{__doc__}")
            return 2
        print(f"{command}: {json.dumps(result, indent=2, default=str)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
