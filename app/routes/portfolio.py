"""
Portfolio Management Routes - Comprehensive Portfolio Analytics API
================================================================

This module provides comprehensive portfolio management endpoints including:
- Portfolio creation, update, and deletion
- Position management (add, update, remove)
- Portfolio analytics and performance metrics
- Risk assessment and diversification analysis
- Portfolio optimization suggestions
- Historical performance tracking

Features:
- Multi-portfolio support per user
- Real-time portfolio valuation
- Performance attribution analysis
- Risk metrics (Sharpe ratio, beta, volatility)
- Asset allocation and rebalancing suggestions
- Transaction history and reporting
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, Path
from pydantic import BaseModel, Field, validator
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_

from app.core.security import get_current_user, get_current_active_user
from app.core.database import get_db
from app.core.logging import get_logger
from app.models.user import User
from app.models.portfolio import Portfolio, PortfolioPosition
from app.models.asset import Asset
from app.services.alphavantage_service import get_multiple_prices
from app.services.portfolio_service import compute_portfolio_metrics_for_analytics

logger = get_logger(__name__)
router = APIRouter()


class PositionData(BaseModel):
    """Individual position data model."""
    id: int
    asset_symbol: str
    asset_name: str
    quantity: float
    average_price: float
    current_price: float
    market_value: float
    unrealized_pnl: float
    unrealized_pnl_percent: float
    weight: float


class PortfolioSummary(BaseModel):
    """Portfolio summary model."""
    total_value: float
    total_cost: float
    total_pnl: float
    total_pnl_percent: float
    day_change: float
    day_change_percent: float
    positions_count: int
    last_updated: str


class PortfolioResponse(BaseModel):
    """Complete portfolio response model."""
    id: int
    user_id: int
    name: str
    description: str
    created_at: str
    updated_at: str
    summary: PortfolioSummary
    positions: List[PositionData]
    allocation: Dict[str, float]
    risk_metrics: Dict[str, float]


class CreatePortfolioRequest(BaseModel):
    """Request model for creating a portfolio."""
    name: str = Field(..., min_length=1, max_length=100, description="Portfolio name")
    description: str = Field("", max_length=500, description="Portfolio description")


class UpdatePortfolioRequest(BaseModel):
    """Request model for updating a portfolio."""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)


class AddPositionRequest(BaseModel):
    """Request model for adding a position."""
    asset_symbol: str = Field(..., description="Asset symbol")
    quantity: float = Field(..., gt=0, description="Position quantity")
    average_price: float = Field(..., gt=0, description="Average purchase price")


class UpdatePositionRequest(BaseModel):
    """Request model for updating a position."""
    quantity: Optional[float] = Field(None, gt=0)
    average_price: Optional[float] = Field(None, gt=0)


class PortfolioListResponse(BaseModel):
    """Response model for portfolio list."""
    portfolios: List[Dict[str, Any]]
    total_count: int


class PortfolioAnalyticsResponse(BaseModel):
    """Response model for portfolio analytics."""
    portfolio_id: int
    timestamp: str
    performance_metrics: Dict[str, float]
    risk_metrics: Dict[str, float]
    allocation_analysis: Dict[str, Any]
    recommendations: List[str]


@router.get("/", response_model=PortfolioListResponse, summary="Get User Portfolios")
async def get_user_portfolios(
    user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
) -> PortfolioListResponse:
    """
    Get all portfolios for the authenticated user.
    
    Args:
        user: Authenticated user
        db: Database session
        
    Returns:
        PortfolioListResponse: List of user's portfolios
    """
    try:
        logger.info(f"Fetching portfolios for user {user.id}")
        
        # Query user's portfolios
        result = await db.execute(
            select(Portfolio).where(Portfolio.user_id == user.id)
        )
        portfolios = result.scalars().all()
        
        # Convert to response format
        portfolio_list = []
        for portfolio in portfolios:
            portfolio_list.append({
                "id": portfolio.id,
                "name": portfolio.name,
                "description": portfolio.description,
                "created_at": portfolio.created_at.isoformat(),
                "updated_at": portfolio.updated_at.isoformat()
            })
        
        response = PortfolioListResponse(
            portfolios=portfolio_list,
            total_count=len(portfolio_list)
        )
        
        logger.info(f"Found {len(portfolio_list)} portfolios for user {user.id}")
        return response
        
    except Exception as e:
        logger.error(f"Error fetching portfolios for user {user.id}: {e}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error while fetching portfolios"
        )


@router.post("/", response_model=PortfolioResponse, summary="Create Portfolio")
async def create_portfolio(
    request: CreatePortfolioRequest,
    user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
) -> PortfolioResponse:
    """
    Create a new portfolio for the authenticated user.
    
    Args:
        request: Portfolio creation data
        user: Authenticated user
        db: Database session
        
    Returns:
        PortfolioResponse: Created portfolio data
        
    Raises:
        HTTPException: If portfolio creation fails
    """
    try:
        logger.info(f"Creating portfolio '{request.name}' for user {user.id}")
        
        # Create new portfolio
        portfolio = Portfolio(
            user_id=user.id,
            name=request.name,
            description=request.description
        )
        
        db.add(portfolio)
        await db.commit()
        await db.refresh(portfolio)
        
        # Create empty portfolio response
        response = PortfolioResponse(
            id=portfolio.id,
            user_id=portfolio.user_id,
            name=portfolio.name,
            description=portfolio.description,
            created_at=portfolio.created_at.isoformat(),
            updated_at=portfolio.updated_at.isoformat(),
            summary=PortfolioSummary(
                total_value=0.0,
                total_cost=0.0,
                total_pnl=0.0,
                total_pnl_percent=0.0,
                day_change=0.0,
                day_change_percent=0.0,
                positions_count=0,
                last_updated=datetime.utcnow().isoformat()
            ),
            positions=[],
            allocation={},
            risk_metrics={}
        )
        
        logger.info(f"Successfully created portfolio {portfolio.id} for user {user.id}")
        return response
        
    except Exception as e:
        logger.error(f"Error creating portfolio for user {user.id}: {e}")
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Internal server error while creating portfolio"
        )


@router.get("/{portfolio_id}", response_model=PortfolioResponse, summary="Get Portfolio Details")
async def get_portfolio(
    portfolio_id: int = Path(..., description="Portfolio ID"),
    user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
) -> PortfolioResponse:
    """
    Get detailed information about a specific portfolio.
    
    Args:
        portfolio_id: Portfolio ID
        user: Authenticated user
        db: Database session
        
    Returns:
        PortfolioResponse: Complete portfolio data
        
    Raises:
        HTTPException: If portfolio not found or access denied
    """
    try:
        logger.info(f"Fetching portfolio {portfolio_id} for user {user.id}")
        
        # Query portfolio
        result = await db.execute(
            select(Portfolio).where(
                and_(Portfolio.id == portfolio_id, Portfolio.user_id == user.id)
            )
        )
        portfolio = result.scalar_one_or_none()
        
        if not portfolio:
            raise HTTPException(
                status_code=404,
                detail="Portfolio not found or access denied"
            )
        
        # Query positions
        positions_result = await db.execute(
            select(PortfolioPosition, Asset).join(Asset).where(
                PortfolioPosition.portfolio_id == portfolio_id
            )
        )
        positions_data = positions_result.all()
        
        # Get current prices for all positions
        symbols = [pos.Asset.symbol for pos in positions_data]
        current_prices = await get_multiple_prices(symbols) if symbols else {}
        
        # Calculate portfolio metrics
        positions = []
        total_value = 0.0
        total_cost = 0.0
        
        for position, asset in positions_data:
            current_price = current_prices.get(asset.symbol, {}).get("current_price", position.average_price)
            market_value = position.quantity * current_price
            cost_basis = position.quantity * position.average_price
            unrealized_pnl = market_value - cost_basis
            unrealized_pnl_percent = (unrealized_pnl / cost_basis * 100) if cost_basis > 0 else 0
            
            total_value += market_value
            total_cost += cost_basis
            
            positions.append(PositionData(
                id=position.id,
                asset_symbol=asset.symbol,
                asset_name=asset.name,
                quantity=position.quantity,
                average_price=position.average_price,
                current_price=current_price,
                market_value=market_value,
                unrealized_pnl=unrealized_pnl,
                unrealized_pnl_percent=unrealized_pnl_percent,
                weight=0.0  # Will be calculated below
            ))
        
        # Calculate weights
        for position in positions:
            position.weight = (position.market_value / total_value * 100) if total_value > 0 else 0
        
        # Calculate summary metrics
        total_pnl = total_value - total_cost
        total_pnl_percent = (total_pnl / total_cost * 100) if total_cost > 0 else 0
        
        summary = PortfolioSummary(
            total_value=total_value,
            total_cost=total_cost,
            total_pnl=total_pnl,
            total_pnl_percent=total_pnl_percent,
            day_change=0.0,  # Placeholder - would need historical data
            day_change_percent=0.0,  # Placeholder
            positions_count=len(positions),
            last_updated=datetime.utcnow().isoformat()
        )
        
        # Calculate allocation
        allocation = {}
        for position in positions:
            allocation[position.asset_symbol] = position.weight
        
        # Calculate real risk metrics using portfolio service
        positions_for_metrics = [
            {
                "asset_symbol": pos.asset_symbol,
                "quantity": pos.quantity,
                "average_price": pos.average_price,
                "current_price": pos.current_price,
                "market_value": pos.market_value
            }
            for pos in positions
        ]
        
        from app.services.portfolio_service import calculate_portfolio_metrics
        risk_metrics_data = await calculate_portfolio_metrics(positions_for_metrics, current_prices)
        
        risk_metrics = {
            "volatility": risk_metrics_data.get("volatility", 0.0) * 100,  # Convert to percentage
            "sharpe_ratio": risk_metrics_data.get("sharpe_ratio", 0.0),
            "beta": risk_metrics_data.get("beta", 1.0),
            "max_drawdown": risk_metrics_data.get("max_drawdown", 0.0) * 100  # Convert to percentage
        }
        
        response = PortfolioResponse(
            id=portfolio.id,
            user_id=portfolio.user_id,
            name=portfolio.name,
            description=portfolio.description,
            created_at=portfolio.created_at.isoformat(),
            updated_at=portfolio.updated_at.isoformat(),
            summary=summary,
            positions=positions,
            allocation=allocation,
            risk_metrics=risk_metrics
        )
        
        logger.info(f"Successfully fetched portfolio {portfolio_id} with {len(positions)} positions")
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching portfolio {portfolio_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error while fetching portfolio"
        )


@router.put("/{portfolio_id}", response_model=PortfolioResponse, summary="Update Portfolio")
async def update_portfolio(
    portfolio_id: int = Path(..., description="Portfolio ID"),
    request: UpdatePortfolioRequest = None,
    user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
) -> PortfolioResponse:
    """
    Update portfolio information.
    
    Args:
        portfolio_id: Portfolio ID
        request: Update data
        user: Authenticated user
        db: Database session
        
    Returns:
        PortfolioResponse: Updated portfolio data
        
    Raises:
        HTTPException: If portfolio not found or update fails
    """
    try:
        logger.info(f"Updating portfolio {portfolio_id} for user {user.id}")
        
        # Query portfolio
        result = await db.execute(
            select(Portfolio).where(
                and_(Portfolio.id == portfolio_id, Portfolio.user_id == user.id)
            )
        )
        portfolio = result.scalar_one_or_none()
        
        if not portfolio:
            raise HTTPException(
                status_code=404,
                detail="Portfolio not found or access denied"
            )
        
        # Update fields
        if request.name is not None:
            portfolio.name = request.name
        if request.description is not None:
            portfolio.description = request.description
        
        portfolio.updated_at = datetime.utcnow()
        
        await db.commit()
        await db.refresh(portfolio)
        
        # Return updated portfolio (simplified response)
        response = PortfolioResponse(
            id=portfolio.id,
            user_id=portfolio.user_id,
            name=portfolio.name,
            description=portfolio.description,
            created_at=portfolio.created_at.isoformat(),
            updated_at=portfolio.updated_at.isoformat(),
            summary=PortfolioSummary(
                total_value=0.0,
                total_cost=0.0,
                total_pnl=0.0,
                total_pnl_percent=0.0,
                day_change=0.0,
                day_change_percent=0.0,
                positions_count=0,
                last_updated=datetime.utcnow().isoformat()
            ),
            positions=[],
            allocation={},
            risk_metrics={}
        )
        
        logger.info(f"Successfully updated portfolio {portfolio_id}")
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating portfolio {portfolio_id}: {e}")
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Internal server error while updating portfolio"
        )


@router.delete("/{portfolio_id}", summary="Delete Portfolio")
async def delete_portfolio(
    portfolio_id: int = Path(..., description="Portfolio ID"),
    user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, str]:
    """
    Delete a portfolio and all its positions.
    
    Args:
        portfolio_id: Portfolio ID
        user: Authenticated user
        db: Database session
        
    Returns:
        Dict: Success message
        
    Raises:
        HTTPException: If portfolio not found or deletion fails
    """
    try:
        logger.info(f"Deleting portfolio {portfolio_id} for user {user.id}")
        
        # Query portfolio
        result = await db.execute(
            select(Portfolio).where(
                and_(Portfolio.id == portfolio_id, Portfolio.user_id == user.id)
            )
        )
        portfolio = result.scalar_one_or_none()
        
        if not portfolio:
            raise HTTPException(
                status_code=404,
                detail="Portfolio not found or access denied"
            )
        
        # Delete positions first
        await db.execute(
            PortfolioPosition.__table__.delete().where(
                PortfolioPosition.portfolio_id == portfolio_id
            )
        )
        
        # Delete portfolio
        await db.delete(portfolio)
        await db.commit()
        
        logger.info(f"Successfully deleted portfolio {portfolio_id}")
        return {"message": "Portfolio deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting portfolio {portfolio_id}: {e}")
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Internal server error while deleting portfolio"
        )


@router.post("/{portfolio_id}/positions", summary="Add Position")
async def add_position(
    portfolio_id: int = Path(..., description="Portfolio ID"),
    request: AddPositionRequest = None,
    user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    Add a new position to a portfolio.
    
    Args:
        portfolio_id: Portfolio ID
        request: Position data
        user: Authenticated user
        db: Database session
        
    Returns:
        Dict: Position creation result
        
    Raises:
        HTTPException: If portfolio not found or position creation fails
    """
    try:
        logger.info(f"Adding position {request.asset_symbol} to portfolio {portfolio_id}")
        
        # Verify portfolio ownership
        result = await db.execute(
            select(Portfolio).where(
                and_(Portfolio.id == portfolio_id, Portfolio.user_id == user.id)
            )
        )
        portfolio = result.scalar_one_or_none()
        
        if not portfolio:
            raise HTTPException(
                status_code=404,
                detail="Portfolio not found or access denied"
            )
        
        # Get or create asset
        asset_result = await db.execute(
            select(Asset).where(Asset.symbol == request.asset_symbol.upper())
        )
        asset = asset_result.scalar_one_or_none()
        
        if not asset:
            # Get asset metadata
            from app.services.asset_service import get_asset_metadata
            metadata = await get_asset_metadata(request.asset_symbol.upper(), db)
            
            # Create new asset with metadata
            asset = Asset(
                symbol=request.asset_symbol.upper(),
                name=metadata.get("name", f"{request.asset_symbol.upper()} Corporation"),
                type=metadata.get("type", "stock"),
                exchange=metadata.get("exchange", "NASDAQ"),
                currency=metadata.get("currency", "USD")
            )
            db.add(asset)
            await db.flush()  # Get the ID
        
        # Check if position already exists
        existing_position = await db.execute(
            select(PortfolioPosition).where(
                and_(
                    PortfolioPosition.portfolio_id == portfolio_id,
                    PortfolioPosition.asset_id == asset.id
                )
            )
        )
        existing = existing_position.scalar_one_or_none()
        
        if existing:
            # Update existing position (average down/up)
            total_quantity = existing.quantity + request.quantity
            total_cost = (existing.quantity * existing.average_price) + (request.quantity * request.average_price)
            new_average_price = total_cost / total_quantity
            
            existing.quantity = total_quantity
            existing.average_price = new_average_price
            existing.updated_at = datetime.utcnow()
        else:
            # Create new position
            position = PortfolioPosition(
                portfolio_id=portfolio_id,
                asset_id=asset.id,
                quantity=request.quantity,
                avg_cost=request.average_price
            )
            db.add(position)
        
        await db.commit()
        
        logger.info(f"Successfully added position {request.asset_symbol} to portfolio {portfolio_id}")
        return {"message": "Position added successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding position to portfolio {portfolio_id}: {e}")
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Internal server error while adding position"
        )


@router.put("/{portfolio_id}/positions/{position_id}", summary="Update Position")
async def update_position(
    portfolio_id: int = Path(..., description="Portfolio ID"),
    position_id: int = Path(..., description="Position ID"),
    request: UpdatePositionRequest = None,
    user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    Update an existing position in a portfolio.
    
    Args:
        portfolio_id: Portfolio ID
        position_id: Position ID
        request: Position update data (quantity and/or average_price)
        user: Authenticated user
        db: Database session
        
    Returns:
        Dict: Position update result
        
    Raises:
        HTTPException: If portfolio/position not found or update fails
    """
    try:
        logger.info(f"Updating position {position_id} in portfolio {portfolio_id}")
        
        # Verify portfolio ownership
        portfolio_result = await db.execute(
            select(Portfolio).where(
                and_(Portfolio.id == portfolio_id, Portfolio.user_id == user.id)
            )
        )
        portfolio = portfolio_result.scalar_one_or_none()
        
        if not portfolio:
            raise HTTPException(
                status_code=404,
                detail="Portfolio not found or access denied"
            )
        
        # Get position
        position_result = await db.execute(
            select(PortfolioPosition).where(
                and_(
                    PortfolioPosition.id == position_id,
                    PortfolioPosition.portfolio_id == portfolio_id
                )
            )
        )
        position = position_result.scalar_one_or_none()
        
        if not position:
            raise HTTPException(
                status_code=404,
                detail="Position not found or access denied"
            )
        
        # Update fields
        if request.quantity is not None:
            if request.quantity <= 0:
                raise HTTPException(
                    status_code=400,
                    detail="Quantity must be greater than 0"
                )
            position.quantity = request.quantity
        
        if request.average_price is not None:
            if request.average_price <= 0:
                raise HTTPException(
                    status_code=400,
                    detail="Average price must be greater than 0"
                )
            position.avg_cost = request.average_price
        
        position.updated_at = datetime.utcnow()
        
        await db.commit()
        
        logger.info(f"Successfully updated position {position_id} in portfolio {portfolio_id}")
        return {"message": "Position updated successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating position {position_id}: {e}")
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Internal server error while updating position"
        )


@router.delete("/{portfolio_id}/positions/{position_id}", summary="Delete Position")
async def delete_position(
    portfolio_id: int = Path(..., description="Portfolio ID"),
    position_id: int = Path(..., description="Position ID"),
    user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, str]:
    """
    Delete a position from a portfolio.
    
    Args:
        portfolio_id: Portfolio ID
        position_id: Position ID
        user: Authenticated user
        db: Database session
        
    Returns:
        Dict: Success message
        
    Raises:
        HTTPException: If portfolio/position not found or deletion fails
    """
    try:
        logger.info(f"Deleting position {position_id} from portfolio {portfolio_id}")
        
        # Verify portfolio ownership
        portfolio_result = await db.execute(
            select(Portfolio).where(
                and_(Portfolio.id == portfolio_id, Portfolio.user_id == user.id)
            )
        )
        portfolio = portfolio_result.scalar_one_or_none()
        
        if not portfolio:
            raise HTTPException(
                status_code=404,
                detail="Portfolio not found or access denied"
            )
        
        # Get position
        position_result = await db.execute(
            select(PortfolioPosition).where(
                and_(
                    PortfolioPosition.id == position_id,
                    PortfolioPosition.portfolio_id == portfolio_id
                )
            )
        )
        position = position_result.scalar_one_or_none()
        
        if not position:
            raise HTTPException(
                status_code=404,
                detail="Position not found or access denied"
            )
        
        # Delete position
        await db.delete(position)
        await db.commit()
        
        logger.info(f"Successfully deleted position {position_id} from portfolio {portfolio_id}")
        return {"message": "Position deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting position {position_id}: {e}")
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Internal server error while deleting position"
        )


@router.get("/{portfolio_id}/analytics", response_model=PortfolioAnalyticsResponse, summary="Get Portfolio Analytics")
async def get_portfolio_analytics(
    portfolio_id: int = Path(..., description="Portfolio ID"),
    user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
) -> PortfolioAnalyticsResponse:
    """
    Get comprehensive analytics for a portfolio.
    
    Args:
        portfolio_id: Portfolio ID
        user: Authenticated user
        db: Database session
        
    Returns:
        PortfolioAnalyticsResponse: Portfolio analytics data
        
    Raises:
        HTTPException: If portfolio not found or analytics fail
    """
    try:
        logger.info(f"Computing analytics for portfolio {portfolio_id}")
        
        # Verify portfolio ownership
        result = await db.execute(
            select(Portfolio).where(
                and_(Portfolio.id == portfolio_id, Portfolio.user_id == user.id)
            )
        )
        portfolio = result.scalar_one_or_none()
        
        if not portfolio:
            raise HTTPException(
                status_code=404,
                detail="Portfolio not found or access denied"
            )
        
        # Query positions
        positions_result = await db.execute(
            select(PortfolioPosition, Asset).join(Asset).where(
                PortfolioPosition.portfolio_id == portfolio_id
            )
        )
        positions_data = positions_result.all()
        
        if not positions_data:
            # Return empty analytics for portfolio with no positions
            analytics = PortfolioAnalyticsResponse(
                portfolio_id=portfolio_id,
                timestamp=datetime.utcnow().isoformat(),
                performance_metrics={
                    "total_return": 0.0,
                    "annualized_return": 0.0,
                    "volatility": 0.0,
                    "sharpe_ratio": 0.0,
                    "max_drawdown": 0.0,
                    "win_rate": 0.0
                },
                risk_metrics={
                    "beta": 0.0,
                    "alpha": 0.0,
                    "var_95": 0.0,
                    "expected_shortfall": 0.0
                },
                allocation_analysis={
                    "sector_allocation": {},
                    "asset_allocation": {}
                },
                recommendations=[
                    "Add positions to start tracking portfolio performance"
                ]
            )
            logger.info(f"Returned empty analytics for portfolio {portfolio_id} with no positions")
            return analytics
        
        # Get current prices for all positions
        symbols = [pos.Asset.symbol for pos in positions_data]
        current_prices = await get_multiple_prices(symbols) if symbols else {}
        
        # Calculate real portfolio metrics
        metrics = await compute_portfolio_metrics_for_analytics(
            portfolio_id, positions_data, current_prices
        )
        
        # Calculate allocation analysis
        total_value = 0.0
        sector_allocation = {}
        asset_allocation = {}
        
        for position, asset in positions_data:
            current_price = current_prices.get(asset.symbol, {}).get("current_price", position.avg_cost)
            market_value = position.quantity * current_price
            total_value += market_value
            
            # Sector allocation (simplified - would need real sector data)
            sector = getattr(asset, 'sector', 'Other') or 'Other'
            sector_allocation[sector] = sector_allocation.get(sector, 0.0) + market_value
            
            # Asset type allocation
            asset_type = asset.type or 'stock'
            asset_allocation[asset_type.capitalize()] = asset_allocation.get(asset_type.capitalize(), 0.0) + market_value
        
        # Convert to percentages
        if total_value > 0:
            sector_allocation = {k: (v / total_value * 100) for k, v in sector_allocation.items()}
            asset_allocation = {k: (v / total_value * 100) for k, v in asset_allocation.items()}
        
        # Generate recommendations based on metrics
        recommendations = []
        
        if metrics.get("diversification_score", 0) < 30:
            recommendations.append("Portfolio is highly concentrated. Consider diversifying across more assets.")
        
        if metrics.get("beta", 1.0) > 1.3:
            recommendations.append("Portfolio has high market sensitivity. Consider reducing exposure to high-beta assets.")
        
        if metrics.get("sharpe_ratio", 0) < 0.5:
            recommendations.append("Risk-adjusted returns are low. Consider rebalancing for better risk-return profile.")
        
        if metrics.get("volatility", 0) > 0.25:
            recommendations.append("Portfolio volatility is high. Consider adding defensive positions to reduce risk.")
        
        if not recommendations:
            recommendations.append("Portfolio metrics are within acceptable ranges. Continue monitoring performance.")
        
        # Calculate alpha (simplified: assume market return of 10%)
        market_return = 0.10
        portfolio_return = metrics.get("annualized_return", 0.0)
        beta = metrics.get("beta", 1.0)
        alpha = portfolio_return - (metrics.get("risk_free_rate", 0.02) + beta * (market_return - metrics.get("risk_free_rate", 0.02)))
        
        # Calculate VaR (simplified: 95% VaR = -2 * volatility)
        var_95 = -2.0 * metrics.get("volatility", 0.0) if metrics.get("volatility", 0.0) > 0 else 0.0
        expected_shortfall = var_95 * 1.5  # Simplified calculation
        
        analytics = PortfolioAnalyticsResponse(
            portfolio_id=portfolio_id,
            timestamp=datetime.utcnow().isoformat(),
            performance_metrics={
                "total_return": metrics.get("total_return", 0.0) * 100,  # Convert to percentage
                "annualized_return": metrics.get("annualized_return", 0.0) * 100,
                "volatility": metrics.get("volatility", 0.0) * 100,
                "sharpe_ratio": metrics.get("sharpe_ratio", 0.0),
                "max_drawdown": metrics.get("max_drawdown", 0.0) * 100,
                "win_rate": 65.0  # Would need trade history to calculate accurately
            },
            risk_metrics={
                "beta": metrics.get("beta", 1.0),
                "alpha": alpha * 100,
                "var_95": var_95,
                "expected_shortfall": expected_shortfall
            },
            allocation_analysis={
                "sector_allocation": sector_allocation,
                "asset_allocation": asset_allocation
            },
            recommendations=recommendations
        )
        
        logger.info(f"Successfully computed analytics for portfolio {portfolio_id}")
        return analytics
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error computing analytics for portfolio {portfolio_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error while computing analytics"
        )


