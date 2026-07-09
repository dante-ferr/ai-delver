import asyncio
import json
from runtime.episode_trajectory import TrajectoryStatsCalculator

def run_stats(agent_name: str):
    """Calculates agent stats locally and prints them as JSON to stdout."""
    calculator = TrajectoryStatsCalculator(agent_name)
    # run asyncio loop to calculate stats
    stats = asyncio.run(calculator.get_stats())
    
    print(json.dumps({
        "event": "stats",
        "stats": stats
    }), flush=True)
