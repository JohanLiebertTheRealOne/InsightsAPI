"""
Portfolio analytics service: compute basic metrics for demo.
"""

from typing import Optional, Dict, Any


async def compute_portfolio_metrics(user_id: int) -> Optional[Dict[str, Any]]:
    # Demo implementation; plug in real computations later
    return {
        "user_id": user_id,
        "total_gain": "12.5%",
        "risk_ratio": 1.8,
        "details": {"note": "Demo metrics"},
    }



