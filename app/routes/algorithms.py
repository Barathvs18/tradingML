from typing import List
from fastapi import APIRouter, Depends, HTTPException
from app.deps import get_current_user
from app.algorithms.registry import ALGORITHMS
from app.schemas.app import AlgorithmInfo, CategoryGroup
from app.core.rate_limit import RateLimiter

router = APIRouter(prefix="/algorithms", tags=["algorithms"])

@router.get("", response_model=List[CategoryGroup], dependencies=[Depends(get_current_user), Depends(RateLimiter(60, 60))])
async def list_algorithms():
    categories = {}
    for algo in ALGORITHMS.values():
        cat = algo["category"]
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(algo)
        
    result = []
    for cat, algos in categories.items():
        algo_infos = []
        for algo in algos:
            algo_infos.append(AlgorithmInfo(
                key=algo["key"],
                name=algo["name"],
                category=algo["category"],
                description=algo["description"],
                lookback_minutes=algo["lookback_minutes"],
                default_params=algo["default_params"],
                source=algo.get("source", "reference")
            ))
        result.append(CategoryGroup(category=cat, algorithms=algo_infos))
        
    return result

@router.get("/{key}", response_model=AlgorithmInfo, dependencies=[Depends(get_current_user), Depends(RateLimiter(60, 60))])
async def get_algorithm(key: str):
    if key not in ALGORITHMS:
        raise HTTPException(status_code=404, detail="Algorithm not found")
    return ALGORITHMS[key]
