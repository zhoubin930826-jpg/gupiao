from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.market import StrategyConfig
from app.services.strategy_service import StrategyService

router = APIRouter()


@router.get("/default", response_model=StrategyConfig)
def read_strategy(
    db: Session = Depends(get_db),
) -> StrategyConfig:
    return StrategyConfig.model_validate(StrategyService.read_config(db))


@router.put("/default", response_model=StrategyConfig)
def update_strategy(
    payload: StrategyConfig,
    db: Session = Depends(get_db),
) -> StrategyConfig:
    profile = StrategyService.update_config(db, payload)
    return StrategyConfig.model_validate(profile)
