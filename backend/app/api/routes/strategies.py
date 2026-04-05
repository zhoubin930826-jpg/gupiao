from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_market_scope
from app.db.session import get_db
from app.schemas.market import StrategyConfig
from app.services.strategy_service import StrategyService

router = APIRouter()


@router.get("/default", response_model=StrategyConfig)
def read_strategy(
    db: Session = Depends(get_db),
    market: str = Depends(get_market_scope),
) -> StrategyConfig:
    return StrategyConfig.model_validate(StrategyService.read_config(db, market))


@router.put("/default", response_model=StrategyConfig)
def update_strategy(
    payload: StrategyConfig,
    db: Session = Depends(get_db),
    market: str = Depends(get_market_scope),
) -> StrategyConfig:
    profile = StrategyService.update_config(db, payload, market)
    return StrategyConfig.model_validate(profile)
