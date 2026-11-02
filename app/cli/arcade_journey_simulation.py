"""Replay all active missions through the real session API in a temporary database."""

import argparse
import json
import tempfile
from pathlib import Path

from app.cli.farm_simulation import SimulationClock, SimulationStore
from app.services import arcade_journey, arcade_runtime


def run(games, report_path):
    records = []
    with tempfile.TemporaryDirectory(prefix="algo-journey-pilot-") as folder:
        clock = SimulationClock()
        store = SimulationStore(Path(folder) / "journeys.sqlite3", clock)
        try:
            store.register([dict(id="pilot", name="Тест-пилот")])
            with arcade_runtime.context() as vm:
                vm.eval(
                    Path(__file__)
                    .with_name("arcade_journey_pilot.js")
                    .read_text(encoding="utf-8-sig")
                )
                for game in games:
                    for stage in range(1, 25):
                        passed = False
                        for attempt in range(5):
                            session = store.session("pilot", game, "journey", "keyboard", stage)
                            trace = vm.call(
                                "playAdventure", session["setup"], attempt, timeout_sec=90
                            )
                            store.clock_action("pilot", session["id"], "start")
                            clock.advance(trace["ticks"] / 60 + 0.5)
                            result = store.finish(
                                "pilot", session["id"], trace["events"], trace["ticks"]
                            )
                            row = dict(
                                game=game,
                                stage=stage,
                                attempt=attempt + 1,
                                score=result["run"]["score"],
                                report=result["run"]["report"]["journey"],
                                reason=result["run"]["report"]["reason"],
                                seconds=trace["ticks"] / 60,
                                events=len(trace["events"]),
                            )
                            records.append(row)
                            if row["report"]["success"]:
                                passed = True
                                break
                        print(json.dumps(row, ensure_ascii=False), flush=True)
                        if not passed:
                            break
            progress = store.profile("pilot")["journeys"]
            summary = dict(
                games=games,
                missions=records,
                progress=progress,
                all_complete=all(progress[g]["cleared"] == 24 for g in games),
            )
        finally:
            store.connection.close()
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--games", nargs="*", choices=list(arcade_journey.catalogue()))
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    summary = run(args.games or list(arcade_journey.catalogue()), args.report)
    print("ALL_COMPLETE", summary["all_complete"], flush=True)


if __name__ == "__main__":
    main()
