"""TradingView integration API routes (US-025 and US-026)."""

from datetime import datetime
from typing import Optional
from enum import Enum

from fastapi import APIRouter, Depends, HTTPException, Query, status, Request, BackgroundTasks
from pydantic import BaseModel, Field, HttpUrl
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.models.factors import Factor, FactorDomain

router = APIRouter()


# --------------------------------------------------------------------------
# Enums and Constants
# --------------------------------------------------------------------------

class PineScriptVersion(str, Enum):
    """Supported Pine Script versions."""
    V5 = "v5"
    V4 = "v4"


class TradingViewSyncStatus(str, Enum):
    """Sync status for TradingView connection."""
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    PENDING = "pending"
    ERROR = "error"


class AnnotationType(str, Enum):
    """Types of TradingView annotations."""
    HORIZONTAL_LINE = "horizontal_line"
    VERTICAL_LINE = "vertical_line"
    TREND_LINE = "trend_line"
    TEXT = "text"
    SHAPE = "shape"
    LABEL = "label"


# --------------------------------------------------------------------------
# Request/Response Schemas
# --------------------------------------------------------------------------

class PineScriptGenerateRequest(BaseModel):
    """Request for Pine Script generation."""
    version: PineScriptVersion = Field(default=PineScriptVersion.V5, description="Pine Script version")
    include_webhook: bool = Field(default=True, description="Include webhook integration code")
    webhook_url: Optional[str] = Field(None, description="Custom webhook URL for real-time data")
    overlay: bool = Field(default=False, description="Display indicator as overlay on chart")
    show_alerts: bool = Field(default=True, description="Include alert conditions in script")
    custom_colors: Optional[dict] = Field(None, description="Custom color scheme for indicator")


class PineScriptResponse(BaseModel):
    """Response containing generated Pine Script code."""
    factor_id: str
    factor_name: str
    pine_script_code: str
    version: PineScriptVersion
    setup_instructions: list[str]
    webhook_url: Optional[str]
    generated_at: datetime


class WebhookPushRequest(BaseModel):
    """Request for pushing factor data via webhook."""
    factor_id: str = Field(..., description="Factor ID to push")
    tickers: list[str] = Field(..., min_length=1, description="Tickers to include")
    webhook_secret: str = Field(..., min_length=16, description="Webhook authentication secret")


class WebhookPushResponse(BaseModel):
    """Response for webhook push."""
    status: str
    factor_id: str
    tickers_pushed: list[str]
    timestamp: datetime
    next_push_scheduled: Optional[datetime]


class AnnotationImportRequest(BaseModel):
    """Request for importing TradingView annotations."""
    chart_id: str = Field(..., description="TradingView chart ID")
    annotation_types: Optional[list[AnnotationType]] = Field(None, description="Types to import")
    ticker: str = Field(..., description="Ticker symbol")
    start_date: Optional[datetime] = Field(None, description="Start date for annotations")
    end_date: Optional[datetime] = Field(None, description="End date for annotations")


class AnnotationData(BaseModel):
    """Individual annotation data."""
    id: str
    type: AnnotationType
    timestamp: datetime
    price_level: Optional[float]
    text: Optional[str]
    color: Optional[str]
    metadata: dict = Field(default_factory=dict)


class AnnotationImportResponse(BaseModel):
    """Response for annotation import."""
    chart_id: str
    ticker: str
    annotations: list[AnnotationData]
    total_count: int
    imported_at: datetime


class OAuthInitRequest(BaseModel):
    """Request to initialize OAuth flow."""
    redirect_uri: str = Field(..., description="OAuth redirect URI")
    scopes: list[str] = Field(default=["chart:read", "chart:write"], description="Requested scopes")


class OAuthInitResponse(BaseModel):
    """Response with OAuth authorization URL."""
    authorization_url: str
    state: str
    expires_at: datetime


class OAuthCallbackRequest(BaseModel):
    """OAuth callback handling."""
    code: str = Field(..., description="Authorization code")
    state: str = Field(..., description="State parameter for CSRF protection")


class OAuthTokenResponse(BaseModel):
    """OAuth token response."""
    access_token: str
    refresh_token: Optional[str]
    token_type: str = "Bearer"
    expires_in: int
    scopes: list[str]


class TradingViewConnectionStatus(BaseModel):
    """Status of TradingView connection."""
    status: TradingViewSyncStatus
    connected_at: Optional[datetime]
    last_sync: Optional[datetime]
    scopes: list[str]
    username: Optional[str]


# --------------------------------------------------------------------------
# Pine Script Generation Helpers
# --------------------------------------------------------------------------

def generate_pine_script_v5(
    factor: Factor,
    include_webhook: bool = True,
    webhook_url: Optional[str] = None,
    overlay: bool = False,
    show_alerts: bool = True,
    custom_colors: Optional[dict] = None,
) -> str:
    """Generate Pine Script v5 code for a factor."""

    # Default colors
    colors = custom_colors or {
        "positive": "#26a69a",
        "negative": "#ef5350",
        "neutral": "#78909c",
    }

    # Build the indicator header
    indicator_type = "overlay=true" if overlay else "overlay=false"

    script = f'''// Pine Script v5 - {factor.name}
// Generated by Alternative Data Platform
// Factor ID: {factor.factor_id}
// Domain: {factor.domain.value}
// Description: {factor.description}

//@version=5
indicator("{factor.name}", "{factor.factor_id[:8].upper()}", {indicator_type})

// ============================================================================
// Configuration
// ============================================================================

// Factor input parameters
var string FACTOR_ID = "{factor.factor_id}"
var string API_ENDPOINT = "https://api.altdata.example.com/api/v1"

// Display settings
showLabels = input.bool(true, "Show Value Labels", group="Display")
showBackground = input.bool(true, "Show Background Color", group="Display")
alertThreshold = input.float(2.0, "Alert Threshold (Std Dev)", minval=0.5, maxval=5.0, group="Alerts")

// Color settings
colorPositive = input.color({colors["positive"]}, "Positive Color", group="Colors")
colorNegative = input.color({colors["negative"]}, "Negative Color", group="Colors")
colorNeutral = input.color({colors["neutral"]}, "Neutral Color", group="Colors")

// ============================================================================
// Data Variables
// ============================================================================

// Factor value storage (updated via webhook or manual input)
var float factorMean = na
var float factorVariance = na
var float factorZScore = na
var string lastUpdateTime = na

// Historical data arrays
var float[] meanHistory = array.new_float(100, na)
var float[] varianceHistory = array.new_float(100, na)

// ============================================================================
// Helper Functions
// ============================================================================

// Calculate z-score for current value
f_calculateZScore(value, mean, stdDev) =>
    stdDev > 0 ? (value - mean) / stdDev : 0.0

// Determine signal color based on z-score
f_getSignalColor(zscore) =>
    zscore > 1.0 ? colorPositive :
    zscore < -1.0 ? colorNegative :
    colorNeutral

// Format factor value for display
f_formatValue(val) =>
    na(val) ? "N/A" : str.tostring(val, "#.####")

// ============================================================================
// Main Factor Processing
// ============================================================================

// Note: In production, factorMean and factorVariance would be updated
// via webhook integration. For demonstration, we use placeholder logic.

// Simulated factor value (replace with actual webhook data)
demoFactorValue = ta.sma(close, 14) / ta.sma(close, 50) - 1.0

// Update factor values
factorMean := demoFactorValue
factorVariance := ta.variance(close, 20) / math.pow(ta.sma(close, 20), 2)

// Calculate z-score
rollingMean = ta.sma(demoFactorValue, 20)
rollingStdDev = ta.stdev(demoFactorValue, 20)
factorZScore := f_calculateZScore(demoFactorValue, rollingMean, rollingStdDev)

// ============================================================================
// Visualization
// ============================================================================

// Plot factor value
plotColor = f_getSignalColor(factorZScore)
plot(factorMean, "Factor Value", color=plotColor, linewidth=2)

// Plot confidence bands (mean +/- 2 std dev)
upperBand = rollingMean + 2 * rollingStdDev
lowerBand = rollingMean - 2 * rollingStdDev
p1 = plot(upperBand, "Upper Band", color=color.new(colorPositive, 70))
p2 = plot(lowerBand, "Lower Band", color=color.new(colorNegative, 70))
fill(p1, p2, color=color.new(colorNeutral, 90), title="Confidence Band")

// Zero line reference
hline(0, "Zero Line", color=color.gray, linestyle=hline.style_dashed)

// Background coloring based on signal strength
bgcolor(showBackground and factorZScore > alertThreshold ? color.new(colorPositive, 90) : na, title="Strong Positive")
bgcolor(showBackground and factorZScore < -alertThreshold ? color.new(colorNegative, 90) : na, title="Strong Negative")

// Value labels
if showLabels and bar_index == last_bar_index
    label.new(
        bar_index, factorMean,
        "Factor: " + f_formatValue(factorMean) + "\\nZ-Score: " + f_formatValue(factorZScore),
        style=label.style_label_left,
        color=plotColor,
        textcolor=color.white
    )
'''

    # Add alert conditions if requested
    if show_alerts:
        script += '''
// ============================================================================
// Alert Conditions
// ============================================================================

// Strong positive signal alert
alertcondition(
    factorZScore > alertThreshold and factorZScore[1] <= alertThreshold,
    title="Strong Positive Signal",
    message="{{ticker}}: {factor_name} shows strong positive signal (Z-Score: {{{{plot(\\"Factor Value\\")}}}})".format(factor_name="{factor_name}")
)

// Strong negative signal alert
alertcondition(
    factorZScore < -alertThreshold and factorZScore[1] >= -alertThreshold,
    title="Strong Negative Signal",
    message="{{ticker}}: {factor_name} shows strong negative signal (Z-Score: {{{{plot(\\"Factor Value\\")}}}})".format(factor_name="{factor_name}")
)

// Factor crosses zero
alertcondition(
    ta.cross(factorMean, 0),
    title="Factor Crosses Zero",
    message="{{ticker}}: {factor_name} crossed zero line".format(factor_name="{factor_name}")
)
'''.format(factor_name=factor.name)

    # Add webhook integration code if requested
    if include_webhook:
        webhook_endpoint = webhook_url or f"https://api.altdata.example.com/api/v1/tradingview/webhook/{factor.factor_id}"
        script += f'''
// ============================================================================
// Webhook Integration
// ============================================================================
//
// To receive real-time factor updates, configure a webhook alert:
//
// 1. Go to Alerts (Alt+A or Cmd+A)
// 2. Create a new alert with the following settings:
//    - Condition: This indicator (any condition)
//    - Webhook URL: {webhook_endpoint}
//    - Message: Use the JSON template below
//
// Webhook JSON Template:
// {{
//   "factor_id": "{factor.factor_id}",
//   "ticker": "{{{{ticker}}}}",
//   "exchange": "{{{{exchange}}}}",
//   "time": "{{{{timenow}}}}",
//   "factor_value": {{{{plot("Factor Value")}}}},
//   "zscore": {{{{plot("Factor Value")}}}}
// }}
//
// API Documentation: https://api.altdata.example.com/docs#tradingview
// ============================================================================
'''

    # Add footer with metadata
    script += f'''
// ============================================================================
// Factor Metadata
// ============================================================================
// Factor ID: {factor.factor_id}
// Name: {factor.name}
// Domain: {factor.domain.value}
// Formula: {factor.formula}
// Economic Rationale: {factor.economic_rationale[:200]}...
//
// Primary Entities: {", ".join(factor.primary_entities) if factor.primary_entities else "N/A"}
// Historical IC: {float(factor.historical_ic) if factor.historical_ic else "N/A"}
// Historical IR: {float(factor.historical_ir) if factor.historical_ir else "N/A"}
//
// Generated: {datetime.utcnow().isoformat()}
// ============================================================================
'''

    return script


def get_setup_instructions(factor: Factor, version: PineScriptVersion) -> list[str]:
    """Get TradingView setup instructions."""
    return [
        "1. Open TradingView (tradingview.com) and navigate to any chart",
        "2. Click on 'Pine Editor' at the bottom of the screen",
        "3. Delete any existing code in the editor",
        "4. Paste the generated Pine Script code into the editor",
        "5. Click 'Save' and give the indicator a name",
        "6. Click 'Add to Chart' to apply the indicator",
        "7. (Optional) Configure alerts by clicking the Alert button",
        "8. (Optional) Set up webhook integration for real-time updates:",
        f"   - Create an alert with Webhook URL pointing to your API endpoint",
        f"   - Use the provided JSON template in the alert message",
        "9. Adjust indicator settings via the Settings gear icon",
        f"10. This script uses Pine Script {version.value} syntax",
    ]


# --------------------------------------------------------------------------
# API Endpoints
# --------------------------------------------------------------------------

@router.post("/{factor_id}/pinescript", response_model=PineScriptResponse)
async def generate_pinescript(
    factor_id: str,
    request: Optional[PineScriptGenerateRequest] = None,
    db: AsyncSession = Depends(get_db),
):
    """
    Generate Pine Script v5 code for a factor (US-025).

    Creates a complete TradingView indicator script that:
    - Displays the factor value as a chart overlay or separate panel
    - Includes confidence bands and z-score calculations
    - Provides alert conditions for significant signals
    - Includes webhook integration code for real-time data feeds
    - Contains setup instructions for TradingView
    """
    # Get factor from database
    query = select(Factor).where(Factor.factor_id == factor_id)
    result = await db.execute(query)
    factor = result.scalar_one_or_none()

    if not factor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Factor {factor_id} not found",
        )

    # Use defaults if no request provided
    if request is None:
        request = PineScriptGenerateRequest()

    # Generate Pine Script code
    if request.version == PineScriptVersion.V5:
        pine_script = generate_pine_script_v5(
            factor=factor,
            include_webhook=request.include_webhook,
            webhook_url=request.webhook_url,
            overlay=request.overlay,
            show_alerts=request.show_alerts,
            custom_colors=request.custom_colors,
        )
    else:
        # V4 fallback (simplified)
        pine_script = generate_pine_script_v5(
            factor=factor,
            include_webhook=request.include_webhook,
            webhook_url=request.webhook_url,
            overlay=request.overlay,
            show_alerts=request.show_alerts,
            custom_colors=request.custom_colors,
        ).replace("//@version=5", "//@version=4")

    # Get setup instructions
    instructions = get_setup_instructions(factor, request.version)

    return PineScriptResponse(
        factor_id=factor.factor_id,
        factor_name=factor.name,
        pine_script_code=pine_script,
        version=request.version,
        setup_instructions=instructions,
        webhook_url=request.webhook_url,
        generated_at=datetime.utcnow(),
    )


@router.post("/webhook/push", response_model=WebhookPushResponse)
async def push_factor_webhook(
    request: WebhookPushRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """
    Push factor data to TradingView via webhook (US-026).

    Enables real-time factor value updates to be pushed to TradingView
    charts configured with webhook alerts.
    """
    # Verify factor exists
    query = select(Factor).where(Factor.factor_id == request.factor_id)
    result = await db.execute(query)
    factor = result.scalar_one_or_none()

    if not factor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Factor {request.factor_id} not found",
        )

    # TODO: Implement actual webhook push logic
    # This would:
    # 1. Validate the webhook secret
    # 2. Fetch latest factor values for the tickers
    # 3. Format data for TradingView webhook format
    # 4. Push to registered TradingView webhook endpoints

    # For now, return a placeholder response
    return WebhookPushResponse(
        status="queued",
        factor_id=request.factor_id,
        tickers_pushed=request.tickers,
        timestamp=datetime.utcnow(),
        next_push_scheduled=None,
    )


@router.post("/annotations/import", response_model=AnnotationImportResponse)
async def import_annotations(
    request: AnnotationImportRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Import annotations from TradingView charts (US-026).

    Allows importing chart annotations (lines, labels, shapes) from
    TradingView for analysis and factor correlation studies.
    """
    # TODO: Implement actual TradingView annotation import
    # This would:
    # 1. Use TradingView API to fetch chart annotations
    # 2. Parse and transform annotation data
    # 3. Store annotations for analysis

    # For now, return placeholder response
    return AnnotationImportResponse(
        chart_id=request.chart_id,
        ticker=request.ticker,
        annotations=[],  # Would contain imported annotations
        total_count=0,
        imported_at=datetime.utcnow(),
    )


@router.post("/oauth/init", response_model=OAuthInitResponse)
async def init_oauth(
    request: OAuthInitRequest,
):
    """
    Initialize OAuth flow for TradingView connection (US-026).

    Starts the OAuth 2.0 authorization flow to connect the platform
    with a user's TradingView account.
    """
    import secrets

    # Generate state for CSRF protection
    state = secrets.token_urlsafe(32)

    # TODO: Implement actual OAuth flow
    # This would:
    # 1. Store state in session/cache with expiry
    # 2. Generate proper TradingView authorization URL
    # 3. Include requested scopes

    # Placeholder OAuth URL (TradingView OAuth endpoint structure)
    oauth_url = (
        f"https://www.tradingview.com/oauth/authorize?"
        f"client_id=YOUR_CLIENT_ID&"
        f"redirect_uri={request.redirect_uri}&"
        f"response_type=code&"
        f"scope={'+'.join(request.scopes)}&"
        f"state={state}"
    )

    return OAuthInitResponse(
        authorization_url=oauth_url,
        state=state,
        expires_at=datetime.utcnow(),  # Would be actual expiry
    )


@router.post("/oauth/callback", response_model=OAuthTokenResponse)
async def oauth_callback(
    request: OAuthCallbackRequest,
):
    """
    Handle OAuth callback from TradingView (US-026).

    Exchanges the authorization code for access tokens.
    """
    # TODO: Implement actual OAuth token exchange
    # This would:
    # 1. Validate state parameter
    # 2. Exchange code for tokens with TradingView
    # 3. Store tokens securely
    # 4. Return token information

    # Placeholder response
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="OAuth callback not yet implemented. TradingView OAuth integration pending.",
    )


@router.get("/connection/status", response_model=TradingViewConnectionStatus)
async def get_connection_status(
    # TODO: Add user dependency
):
    """
    Get TradingView connection status (US-026).

    Returns the current status of the TradingView OAuth connection
    for the authenticated user.
    """
    # TODO: Implement actual status check
    # This would:
    # 1. Check if user has valid TradingView tokens
    # 2. Verify token validity
    # 3. Return connection details

    # Placeholder response for disconnected state
    return TradingViewConnectionStatus(
        status=TradingViewSyncStatus.DISCONNECTED,
        connected_at=None,
        last_sync=None,
        scopes=[],
        username=None,
    )


@router.delete("/connection")
async def disconnect_tradingview(
    # TODO: Add user dependency
):
    """
    Disconnect TradingView account (US-026).

    Revokes OAuth tokens and removes the TradingView connection.
    """
    # TODO: Implement actual disconnection
    # This would:
    # 1. Revoke tokens with TradingView
    # 2. Remove stored tokens
    # 3. Clean up related data

    return {"status": "disconnected", "message": "TradingView account disconnected"}


@router.get("/webhook/{factor_id}/config")
async def get_webhook_config(
    factor_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Get webhook configuration for a factor.

    Returns the webhook URL and JSON template for TradingView alert configuration.
    """
    # Verify factor exists
    query = select(Factor).where(Factor.factor_id == factor_id)
    result = await db.execute(query)
    factor = result.scalar_one_or_none()

    if not factor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Factor {factor_id} not found",
        )

    webhook_url = f"https://api.altdata.example.com/api/v1/tradingview/webhook/{factor_id}"

    json_template = {
        "factor_id": factor_id,
        "ticker": "{{ticker}}",
        "exchange": "{{exchange}}",
        "time": "{{timenow}}",
        "interval": "{{interval}}",
        "factor_value": "{{plot('Factor Value')}}",
        "alert_type": "{{strategy.order.action}}",
    }

    return {
        "factor_id": factor_id,
        "factor_name": factor.name,
        "webhook_url": webhook_url,
        "json_template": json_template,
        "instructions": [
            "1. Open your TradingView chart with the factor indicator",
            "2. Create a new Alert (Alt+A)",
            "3. Set Condition to your desired trigger",
            f"4. Enable 'Webhook URL' and paste: {webhook_url}",
            "5. In the Message field, paste the JSON template",
            "6. Save the alert",
        ],
    }
