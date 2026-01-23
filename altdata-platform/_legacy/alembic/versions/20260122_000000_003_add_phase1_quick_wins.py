"""Add Phase 1 Quick Wins data tables

Revision ID: 003_add_phase1_quick_wins
Revises: 002_add_users_auth
Create Date: 2026-01-22 00:00:00

Phase 1 Quick Wins includes:
- TSA Checkpoint data
- OpenTable reservations
- USGS Earthquake events
- UK Carbon Intensity
- Building Permits (FRED)
- Movie Box Office
- Cloudflare Radar
- Zillow Rental Index
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '003_add_phase1_quick_wins'
down_revision: Union[str, None] = '002_add_users_auth'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # TSA Checkpoints
    op.create_table(
        'tsa_checkpoints',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('current_year_throughput', sa.Integer(), nullable=True),
        sa.Column('prior_year_throughput', sa.Integer(), nullable=True),
        sa.Column('yoy_change_pct', sa.Float(), nullable=True),
        sa.Column('day_of_week', sa.Integer(), nullable=True),
        sa.Column('is_holiday_period', sa.Boolean(), nullable=True),
        sa.Column('raw_data_id', sa.BigInteger(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['raw_data_id'], ['raw_data_catalog.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_tsa_date', 'tsa_checkpoints', ['date'], unique=True)
    op.create_index('ix_tsa_date_dow', 'tsa_checkpoints', ['date', 'day_of_week'])

    # OpenTable Metrics
    op.create_table(
        'opentable_metrics',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('week_ending', sa.Date(), nullable=False),
        sa.Column('region', sa.String(100), nullable=False),
        sa.Column('city', sa.String(100), nullable=True),
        sa.Column('yoy_seated_diners_pct', sa.Float(), nullable=True),
        sa.Column('raw_data_id', sa.BigInteger(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['raw_data_id'], ['raw_data_catalog.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('week_ending', 'region', 'city', name='uq_opentable_week_region_city'),
    )
    op.create_index('ix_opentable_week_region', 'opentable_metrics', ['week_ending', 'region'])

    # Earthquake Events
    op.create_table(
        'earthquake_events',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('event_id', sa.String(50), nullable=False),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated', sa.DateTime(timezone=True), nullable=True),
        sa.Column('latitude', sa.Float(), nullable=False),
        sa.Column('longitude', sa.Float(), nullable=False),
        sa.Column('depth_km', sa.Float(), nullable=True),
        sa.Column('place_description', sa.String(500), nullable=True),
        sa.Column('magnitude', sa.Float(), nullable=True),
        sa.Column('magnitude_type', sa.String(10), nullable=True),
        sa.Column('felt_reports', sa.BigInteger(), nullable=True),
        sa.Column('cdi', sa.Float(), nullable=True),
        sa.Column('mmi', sa.Float(), nullable=True),
        sa.Column('alert_level', sa.String(10), nullable=True),
        sa.Column('tsunami_flag', sa.Boolean(), nullable=True),
        sa.Column('status', sa.String(20), nullable=True),
        sa.Column('net', sa.String(10), nullable=True),
        sa.Column('nst', sa.BigInteger(), nullable=True),
        sa.Column('dmin', sa.Float(), nullable=True),
        sa.Column('rms', sa.Float(), nullable=True),
        sa.Column('gap', sa.Float(), nullable=True),
        sa.Column('detail_url', sa.String(500), nullable=True),
        sa.Column('raw_data_id', sa.BigInteger(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['raw_data_id'], ['raw_data_catalog.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('event_id'),
    )
    op.create_index('ix_earthquake_timestamp', 'earthquake_events', ['timestamp'])
    op.create_index('ix_earthquake_mag_time', 'earthquake_events', ['magnitude', 'timestamp'])
    op.create_index('ix_earthquake_location', 'earthquake_events', ['latitude', 'longitude'])
    op.create_index('ix_earthquake_event_id', 'earthquake_events', ['event_id'])

    # Seismic Zones
    op.create_table(
        'seismic_zones',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('zone_id', sa.String(50), nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('min_latitude', sa.Float(), nullable=True),
        sa.Column('max_latitude', sa.Float(), nullable=True),
        sa.Column('min_longitude', sa.Float(), nullable=True),
        sa.Column('max_longitude', sa.Float(), nullable=True),
        sa.Column('risk_level', sa.String(20), nullable=True),
        sa.Column('historical_max_magnitude', sa.Float(), nullable=True),
        sa.Column('affected_sectors', sa.String(500), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('zone_id'),
    )
    op.create_index('ix_seismic_zone_id', 'seismic_zones', ['zone_id'])

    # Carbon Intensity Readings
    op.create_table(
        'carbon_intensity_readings',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('region', sa.String(50), nullable=True),
        sa.Column('intensity_forecast', sa.Float(), nullable=True),
        sa.Column('intensity_actual', sa.Float(), nullable=True),
        sa.Column('intensity_index', sa.String(20), nullable=True),
        sa.Column('generation_mix', postgresql.JSON(), nullable=True),
        sa.Column('pct_biomass', sa.Float(), nullable=True),
        sa.Column('pct_coal', sa.Float(), nullable=True),
        sa.Column('pct_gas', sa.Float(), nullable=True),
        sa.Column('pct_hydro', sa.Float(), nullable=True),
        sa.Column('pct_imports', sa.Float(), nullable=True),
        sa.Column('pct_nuclear', sa.Float(), nullable=True),
        sa.Column('pct_solar', sa.Float(), nullable=True),
        sa.Column('pct_wind', sa.Float(), nullable=True),
        sa.Column('pct_other', sa.Float(), nullable=True),
        sa.Column('raw_data_id', sa.BigInteger(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['raw_data_id'], ['raw_data_catalog.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_carbon_timestamp_region', 'carbon_intensity_readings', ['timestamp', 'region'])

    # Building Permits
    op.create_table(
        'building_permits',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('period', sa.Date(), nullable=False),
        sa.Column('geography_level', sa.String(20), nullable=True),
        sa.Column('geography_code', sa.String(20), nullable=True),
        sa.Column('geography_name', sa.String(200), nullable=True),
        sa.Column('permit_type', sa.String(50), nullable=True),
        sa.Column('units_authorized', sa.Integer(), nullable=True),
        sa.Column('valuation', sa.Numeric(15, 2), nullable=True),
        sa.Column('is_seasonally_adjusted', sa.String(10), nullable=True),
        sa.Column('raw_data_id', sa.BigInteger(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['raw_data_id'], ['raw_data_catalog.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_permits_period_geo', 'building_permits', ['period', 'geography_level', 'geography_code'])
    op.create_index('ix_permits_type', 'building_permits', ['permit_type'])

    # Box Office Daily
    op.create_table(
        'box_office_daily',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('movie_title', sa.String(500), nullable=False),
        sa.Column('movie_id', sa.String(50), nullable=True),
        sa.Column('distributor', sa.String(200), nullable=True),
        sa.Column('distributor_ticker', sa.String(20), nullable=True),
        sa.Column('daily_gross', sa.Numeric(15, 2), nullable=True),
        sa.Column('cumulative_gross', sa.Numeric(15, 2), nullable=True),
        sa.Column('theater_count', sa.Integer(), nullable=True),
        sa.Column('per_theater_avg', sa.Numeric(10, 2), nullable=True),
        sa.Column('days_in_release', sa.Integer(), nullable=True),
        sa.Column('daily_rank', sa.Integer(), nullable=True),
        sa.Column('is_new_release', sa.String(5), nullable=True),
        sa.Column('raw_data_id', sa.BigInteger(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['raw_data_id'], ['raw_data_catalog.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_boxoffice_date_movie', 'box_office_daily', ['date', 'movie_title'])
    op.create_index('ix_boxoffice_distributor', 'box_office_daily', ['distributor_ticker', 'date'])

    # Cloudflare Radar Metrics
    op.create_table(
        'cloudflare_radar_metrics',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('region_type', sa.String(20), nullable=True),
        sa.Column('region_code', sa.String(50), nullable=True),
        sa.Column('traffic_index', sa.Float(), nullable=True),
        sa.Column('traffic_change_pct', sa.Float(), nullable=True),
        sa.Column('http_share', sa.Float(), nullable=True),
        sa.Column('https_share', sa.Float(), nullable=True),
        sa.Column('http3_share', sa.Float(), nullable=True),
        sa.Column('attack_volume_index', sa.Float(), nullable=True),
        sa.Column('bot_traffic_share', sa.Float(), nullable=True),
        sa.Column('threat_score', sa.Float(), nullable=True),
        sa.Column('is_outage_detected', sa.String(5), nullable=True),
        sa.Column('outage_severity', sa.String(20), nullable=True),
        sa.Column('extra_metrics', postgresql.JSON(), nullable=True),
        sa.Column('raw_data_id', sa.BigInteger(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['raw_data_id'], ['raw_data_catalog.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_cloudflare_timestamp_region', 'cloudflare_radar_metrics', ['timestamp', 'region_type', 'region_code'])

    # Zillow Rental Index
    op.create_table(
        'zillow_rental_index',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('period', sa.Date(), nullable=False),
        sa.Column('region_type', sa.String(20), nullable=True),
        sa.Column('region_id', sa.String(20), nullable=True),
        sa.Column('region_name', sa.String(200), nullable=True),
        sa.Column('state_code', sa.String(10), nullable=True),
        sa.Column('property_type', sa.String(50), nullable=True),
        sa.Column('zori_value', sa.Float(), nullable=True),
        sa.Column('mom_change', sa.Float(), nullable=True),
        sa.Column('yoy_change', sa.Float(), nullable=True),
        sa.Column('median_listing_price', sa.Float(), nullable=True),
        sa.Column('inventory_count', sa.Float(), nullable=True),
        sa.Column('raw_data_id', sa.BigInteger(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['raw_data_id'], ['raw_data_catalog.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_zillow_period_region', 'zillow_rental_index', ['period', 'region_type', 'region_id'])
    op.create_index('ix_zillow_property', 'zillow_rental_index', ['property_type'])


def downgrade() -> None:
    # Drop tables in reverse order
    op.drop_index('ix_zillow_property', 'zillow_rental_index')
    op.drop_index('ix_zillow_period_region', 'zillow_rental_index')
    op.drop_table('zillow_rental_index')

    op.drop_index('ix_cloudflare_timestamp_region', 'cloudflare_radar_metrics')
    op.drop_table('cloudflare_radar_metrics')

    op.drop_index('ix_boxoffice_distributor', 'box_office_daily')
    op.drop_index('ix_boxoffice_date_movie', 'box_office_daily')
    op.drop_table('box_office_daily')

    op.drop_index('ix_permits_type', 'building_permits')
    op.drop_index('ix_permits_period_geo', 'building_permits')
    op.drop_table('building_permits')

    op.drop_index('ix_carbon_timestamp_region', 'carbon_intensity_readings')
    op.drop_table('carbon_intensity_readings')

    op.drop_index('ix_seismic_zone_id', 'seismic_zones')
    op.drop_table('seismic_zones')

    op.drop_index('ix_earthquake_event_id', 'earthquake_events')
    op.drop_index('ix_earthquake_location', 'earthquake_events')
    op.drop_index('ix_earthquake_mag_time', 'earthquake_events')
    op.drop_index('ix_earthquake_timestamp', 'earthquake_events')
    op.drop_table('earthquake_events')

    op.drop_index('ix_opentable_week_region', 'opentable_metrics')
    op.drop_table('opentable_metrics')

    op.drop_index('ix_tsa_date_dow', 'tsa_checkpoints')
    op.drop_index('ix_tsa_date', 'tsa_checkpoints')
    op.drop_table('tsa_checkpoints')
