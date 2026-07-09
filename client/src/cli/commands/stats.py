import asyncio
import json
from runtime.episode_trajectory import TrajectoryStatsCalculator

def run_stats(agent_name: str):
    """Calculates agent stats and nerd stats, printing them as a single JSON event to stdout."""
    calculator = TrajectoryStatsCalculator(agent_name)

    async def _get_all():
        stats = await calculator.get_stats()
        nerd_stats = await calculator.get_nerd_stats()
        return stats, nerd_stats

    stats, nerd_stats = asyncio.run(_get_all())

    print(json.dumps({
        "event": "stats",
        "stats": stats,
        "nerd_stats": nerd_stats,
    }), flush=True)
