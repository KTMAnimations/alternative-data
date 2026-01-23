"""Initial schema - create all tables

Revision ID: 001
Revises:
Create Date: 2024-01-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # === Core Tables ===

    # raw_data_catalog - Catalog of raw data files
    op.create_table(
        'raw_data_catalog',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('source', sa.String(50), nullable=False),
        sa.Column('file_path', sa.Text(), nullable=False),
        sa.Column('fetch_timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('data_timestamp', sa.DateTime(timezone=True)),
        sa.Column('checksum', sa.String(64), nullable=False),
        sa.Column('record_count', sa.Integer()),
        sa.Column('file_size_bytes', sa.BigInteger()),
        sa.Column('extra_data', sa.JSON()),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_raw_data_catalog_source', 'raw_data_catalog', ['source'])
    op.create_index('ix_raw_data_source_timestamp', 'raw_data_catalog', ['source', 'fetch_timestamp'])

    # entities - Company/security entities
    op.create_table(
        'entities',
        sa.Column('id', sa.String(50), nullable=False),
        sa.Column('entity_type', sa.String(20), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('ticker', sa.String(20)),
        sa.Column('cik', sa.String(20)),
        sa.Column('lei', sa.String(20)),
        sa.Column('isin', sa.String(20)),
        sa.Column('exchange', sa.String(20)),
        sa.Column('sector', sa.String(100)),
        sa.Column('industry', sa.String(100)),
        sa.Column('aliases', sa.JSON()),
        sa.Column('extra_data', sa.JSON()),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('created_at', sa.DateTime(timezone=True)),
        sa.Column('updated_at', sa.DateTime(timezone=True)),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_entities_entity_type', 'entities', ['entity_type'])
    op.create_index('ix_entities_ticker', 'entities', ['ticker'])
    op.create_index('ix_entities_cik', 'entities', ['cik'])
    op.create_index('ix_entity_ticker_type', 'entities', ['ticker', 'entity_type'])

    # factors - Computed factor values
    op.create_table(
        'factors',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('factor_name', sa.String(100), nullable=False),
        sa.Column('entity_id', sa.String(50), nullable=False),
        sa.Column('entity_type', sa.String(20), nullable=False),
        sa.Column('value', sa.Float()),
        sa.Column('effective_date', sa.DateTime(), nullable=False),
        sa.Column('computed_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False, default=1),
        sa.Column('source_data_ids', postgresql.ARRAY(sa.BigInteger())),
        sa.Column('extra_data', sa.JSON()),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_factors_factor_name', 'factors', ['factor_name'])
    op.create_index('ix_factors_entity_id', 'factors', ['entity_id'])
    op.create_index('ix_factor_name_entity_date', 'factors', ['factor_name', 'entity_id', 'effective_date'])
    op.create_index('ix_factor_entity_date', 'factors', ['entity_id', 'effective_date'])

    # factor_definitions - Factor metadata
    op.create_table(
        'factor_definitions',
        sa.Column('id', sa.String(100), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('description', sa.Text()),
        sa.Column('category', sa.String(50)),
        sa.Column('entity_type', sa.String(20), nullable=False),
        sa.Column('frequency', sa.String(20)),
        sa.Column('lookback_days', sa.Integer()),
        sa.Column('dependencies', sa.JSON()),
        sa.Column('version', sa.Integer(), nullable=False, default=1),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('created_at', sa.DateTime(timezone=True)),
        sa.Column('updated_at', sa.DateTime(timezone=True)),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_factor_definitions_category', 'factor_definitions', ['category'])

    # api_keys - API authentication
    op.create_table(
        'api_keys',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('key_hash', sa.String(64), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('description', sa.Text()),
        sa.Column('permissions', sa.JSON()),
        sa.Column('rate_limit', sa.Integer(), default=1000),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('created_at', sa.DateTime(timezone=True)),
        sa.Column('expires_at', sa.DateTime(timezone=True)),
        sa.Column('last_used_at', sa.DateTime(timezone=True)),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('key_hash')
    )
    op.create_index('ix_api_keys_key_hash', 'api_keys', ['key_hash'])

    # === SEC Tables ===

    # sec_form4_transactions
    op.create_table(
        'sec_form4_transactions',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('accession_number', sa.String(30), nullable=False),
        sa.Column('cik', sa.String(20), nullable=False),
        sa.Column('issuer_cik', sa.String(20), nullable=False),
        sa.Column('issuer_name', sa.String(255)),
        sa.Column('ticker', sa.String(20)),
        sa.Column('insider_cik', sa.String(20)),
        sa.Column('insider_name', sa.String(255)),
        sa.Column('insider_title', sa.String(100)),
        sa.Column('is_director', sa.Boolean()),
        sa.Column('is_officer', sa.Boolean()),
        sa.Column('is_ten_percent_owner', sa.Boolean()),
        sa.Column('transaction_type', sa.String(10)),
        sa.Column('transaction_code', sa.String(5)),
        sa.Column('shares', sa.Float()),
        sa.Column('price_per_share', sa.Float()),
        sa.Column('total_value', sa.Float()),
        sa.Column('shares_owned_after', sa.Float()),
        sa.Column('ownership_type', sa.String(1)),
        sa.Column('transaction_date', sa.DateTime()),
        sa.Column('filed_date', sa.DateTime()),
        sa.Column('raw_data_id', sa.BigInteger(), sa.ForeignKey('raw_data_catalog.id')),
        sa.Column('extra_data', sa.JSON()),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('accession_number')
    )
    op.create_index('ix_sec_form4_cik', 'sec_form4_transactions', ['cik'])
    op.create_index('ix_sec_form4_issuer_cik', 'sec_form4_transactions', ['issuer_cik'])
    op.create_index('ix_sec_form4_ticker', 'sec_form4_transactions', ['ticker'])
    op.create_index('ix_sec_form4_filed_date', 'sec_form4_transactions', ['filed_date'])
    op.create_index('ix_form4_ticker_date', 'sec_form4_transactions', ['ticker', 'transaction_date'])
    op.create_index('ix_form4_insider_date', 'sec_form4_transactions', ['insider_cik', 'transaction_date'])

    # sec_filings
    op.create_table(
        'sec_filings',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('accession_number', sa.String(30), nullable=False),
        sa.Column('cik', sa.String(20), nullable=False),
        sa.Column('ticker', sa.String(20)),
        sa.Column('company_name', sa.String(255)),
        sa.Column('form_type', sa.String(20), nullable=False),
        sa.Column('filed_date', sa.DateTime(), nullable=False),
        sa.Column('period_date', sa.DateTime()),
        sa.Column('accepted_datetime', sa.DateTime()),
        sa.Column('document_url', sa.Text()),
        sa.Column('sentiment_score', sa.Float()),
        sa.Column('risk_score', sa.Float()),
        sa.Column('raw_data_id', sa.BigInteger(), sa.ForeignKey('raw_data_catalog.id')),
        sa.Column('extra_data', sa.JSON()),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('accession_number')
    )
    op.create_index('ix_sec_filings_cik', 'sec_filings', ['cik'])
    op.create_index('ix_sec_filings_ticker', 'sec_filings', ['ticker'])
    op.create_index('ix_sec_filings_form_type', 'sec_filings', ['form_type'])
    op.create_index('ix_sec_filings_filed_date', 'sec_filings', ['filed_date'])
    op.create_index('ix_filing_type_date', 'sec_filings', ['form_type', 'filed_date'])

    # === FRED Tables ===

    # fred_series
    op.create_table(
        'fred_series',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('series_id', sa.String(50), nullable=False),
        sa.Column('observation_date', sa.DateTime(), nullable=False),
        sa.Column('value', sa.Float()),
        sa.Column('realtime_start', sa.DateTime()),
        sa.Column('realtime_end', sa.DateTime()),
        sa.Column('raw_data_id', sa.BigInteger(), sa.ForeignKey('raw_data_catalog.id')),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_fred_series_series_id', 'fred_series', ['series_id'])
    op.create_index('ix_fred_series_date', 'fred_series', ['series_id', 'observation_date'], unique=True)

    # === Aviation Tables ===

    # aircraft
    op.create_table(
        'aircraft',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('icao_hex', sa.String(10), nullable=False),
        sa.Column('registration', sa.String(20)),
        sa.Column('aircraft_type', sa.String(20)),
        sa.Column('aircraft_model', sa.String(100)),
        sa.Column('owner_name', sa.String(255)),
        sa.Column('owner_type', sa.String(50)),
        sa.Column('company_entity_id', sa.String(50)),
        sa.Column('is_corporate_jet', sa.Boolean(), default=False),
        sa.Column('extra_data', sa.JSON()),
        sa.Column('created_at', sa.DateTime(timezone=True)),
        sa.Column('updated_at', sa.DateTime(timezone=True)),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('icao_hex')
    )
    op.create_index('ix_aircraft_icao_hex', 'aircraft', ['icao_hex'])
    op.create_index('ix_aircraft_registration', 'aircraft', ['registration'])
    op.create_index('ix_aircraft_company', 'aircraft', ['company_entity_id'])
    op.create_index('ix_aircraft_type_corporate', 'aircraft', ['aircraft_type', 'is_corporate_jet'])

    # flight_positions
    op.create_table(
        'flight_positions',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('icao_hex', sa.String(10), nullable=False),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('latitude', sa.Float()),
        sa.Column('longitude', sa.Float()),
        sa.Column('altitude_ft', sa.Integer()),
        sa.Column('ground_speed_knots', sa.Integer()),
        sa.Column('heading', sa.Integer()),
        sa.Column('vertical_rate', sa.Integer()),
        sa.Column('squawk', sa.String(10)),
        sa.Column('on_ground', sa.Boolean()),
        sa.Column('flight_id', sa.String(50)),
        sa.Column('raw_data_id', sa.BigInteger(), sa.ForeignKey('raw_data_catalog.id')),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_flight_positions_icao_hex', 'flight_positions', ['icao_hex'])
    op.create_index('ix_flight_pos_icao_time', 'flight_positions', ['icao_hex', 'timestamp'])
    op.create_index('ix_flight_pos_time', 'flight_positions', ['timestamp'])

    # flight_landings
    op.create_table(
        'flight_landings',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('icao_hex', sa.String(10), nullable=False),
        sa.Column('aircraft_id', sa.BigInteger(), sa.ForeignKey('aircraft.id')),
        sa.Column('landing_timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('airport_icao', sa.String(10)),
        sa.Column('airport_name', sa.String(255)),
        sa.Column('latitude', sa.Float()),
        sa.Column('longitude', sa.Float()),
        sa.Column('nearest_company_hq', sa.String(50)),
        sa.Column('distance_to_hq_km', sa.Float()),
        sa.Column('extra_data', sa.JSON()),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_flight_landings_icao_hex', 'flight_landings', ['icao_hex'])
    op.create_index('ix_flight_landings_airport_icao', 'flight_landings', ['airport_icao'])
    op.create_index('ix_landing_airport_time', 'flight_landings', ['airport_icao', 'landing_timestamp'])
    op.create_index('ix_landing_icao_time', 'flight_landings', ['icao_hex', 'landing_timestamp'])

    # airports
    op.create_table(
        'airports',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('icao_code', sa.String(10), nullable=False),
        sa.Column('iata_code', sa.String(10)),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('city', sa.String(100)),
        sa.Column('country', sa.String(100)),
        sa.Column('latitude', sa.Float(), nullable=False),
        sa.Column('longitude', sa.Float(), nullable=False),
        sa.Column('elevation_ft', sa.Integer()),
        sa.Column('airport_type', sa.String(50)),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('icao_code')
    )
    op.create_index('ix_airports_icao_code', 'airports', ['icao_code'])
    op.create_index('ix_airports_iata_code', 'airports', ['iata_code'])
    op.create_index('ix_airport_location', 'airports', ['latitude', 'longitude'])

    # company_hq
    op.create_table(
        'company_hq',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('entity_id', sa.String(50), nullable=False),
        sa.Column('company_name', sa.String(255)),
        sa.Column('address', sa.String(500)),
        sa.Column('city', sa.String(100)),
        sa.Column('state', sa.String(50)),
        sa.Column('country', sa.String(100)),
        sa.Column('latitude', sa.Float(), nullable=False),
        sa.Column('longitude', sa.Float(), nullable=False),
        sa.Column('nearest_airport_icao', sa.String(10)),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('entity_id')
    )
    op.create_index('ix_company_hq_entity_id', 'company_hq', ['entity_id'])
    op.create_index('ix_company_hq_location', 'company_hq', ['latitude', 'longitude'])

    # === Shipping Tables ===

    # vessels
    op.create_table(
        'vessels',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('mmsi', sa.String(20), nullable=False),
        sa.Column('imo', sa.String(20)),
        sa.Column('name', sa.String(255)),
        sa.Column('callsign', sa.String(20)),
        sa.Column('vessel_type', sa.String(50)),
        sa.Column('vessel_type_code', sa.Integer()),
        sa.Column('flag', sa.String(10)),
        sa.Column('gross_tonnage', sa.Integer()),
        sa.Column('deadweight', sa.Integer()),
        sa.Column('length_m', sa.Float()),
        sa.Column('width_m', sa.Float()),
        sa.Column('draught_m', sa.Float()),
        sa.Column('year_built', sa.Integer()),
        sa.Column('owner', sa.String(255)),
        sa.Column('manager', sa.String(255)),
        sa.Column('created_at', sa.DateTime(timezone=True)),
        sa.Column('updated_at', sa.DateTime(timezone=True)),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('mmsi')
    )
    op.create_index('ix_vessels_mmsi', 'vessels', ['mmsi'])
    op.create_index('ix_vessels_imo', 'vessels', ['imo'])
    op.create_index('ix_vessels_name', 'vessels', ['name'])
    op.create_index('ix_vessel_type', 'vessels', ['vessel_type'])
    op.create_index('ix_vessel_flag', 'vessels', ['flag'])

    # vessel_positions
    op.create_table(
        'vessel_positions',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('mmsi', sa.String(20), nullable=False),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('latitude', sa.Float(), nullable=False),
        sa.Column('longitude', sa.Float(), nullable=False),
        sa.Column('speed_knots', sa.Float()),
        sa.Column('course', sa.Float()),
        sa.Column('heading', sa.Float()),
        sa.Column('nav_status', sa.String(50)),
        sa.Column('destination', sa.String(255)),
        sa.Column('eta', sa.DateTime(timezone=True)),
        sa.Column('source', sa.String(50)),
        sa.Column('fetched_at', sa.DateTime(timezone=True)),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_vessel_positions_mmsi', 'vessel_positions', ['mmsi'])
    op.create_index('ix_vessel_positions_timestamp', 'vessel_positions', ['timestamp'])
    op.create_index('ix_vessel_pos_mmsi_time', 'vessel_positions', ['mmsi', 'timestamp'])
    op.create_index('ix_vessel_pos_time', 'vessel_positions', ['timestamp'])

    # ports
    op.create_table(
        'ports',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('port_id', sa.String(20), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('country', sa.String(10), nullable=False),
        sa.Column('region', sa.String(100)),
        sa.Column('latitude', sa.Float()),
        sa.Column('longitude', sa.Float()),
        sa.Column('port_type', sa.String(50)),
        sa.Column('max_vessel_size', sa.String(50)),
        sa.Column('is_major', sa.Boolean(), default=False),
        sa.Column('primary_cargo_types', sa.JSON()),
        sa.Column('annual_teu_capacity', sa.Integer()),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('port_id')
    )
    op.create_index('ix_ports_port_id', 'ports', ['port_id'])
    op.create_index('ix_ports_name', 'ports', ['name'])
    op.create_index('ix_ports_country', 'ports', ['country'])
    op.create_index('ix_port_country', 'ports', ['country'])

    # port_calls
    op.create_table(
        'port_calls',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('mmsi', sa.String(20), nullable=False),
        sa.Column('port_id', sa.String(20), nullable=False),
        sa.Column('call_type', sa.String(20), nullable=False),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('duration_hours', sa.Float()),
        sa.Column('cargo_type', sa.String(100)),
        sa.Column('cargo_volume', sa.Float()),
        sa.Column('detected_at', sa.DateTime(timezone=True)),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_port_calls_mmsi', 'port_calls', ['mmsi'])
    op.create_index('ix_port_calls_port_id', 'port_calls', ['port_id'])
    op.create_index('ix_port_calls_timestamp', 'port_calls', ['timestamp'])
    op.create_index('ix_port_call_port_time', 'port_calls', ['port_id', 'timestamp'])
    op.create_index('ix_port_call_mmsi', 'port_calls', ['mmsi'])

    # shipping_routes
    op.create_table(
        'shipping_routes',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('route_id', sa.String(50), nullable=False),
        sa.Column('name', sa.String(255)),
        sa.Column('origin_port', sa.String(20)),
        sa.Column('destination_port', sa.String(20)),
        sa.Column('waypoints', sa.JSON()),
        sa.Column('typical_duration_days', sa.Float()),
        sa.Column('distance_nm', sa.Float()),
        sa.Column('is_major_lane', sa.Boolean(), default=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('route_id')
    )
    op.create_index('ix_shipping_routes_route_id', 'shipping_routes', ['route_id'])
    op.create_index('ix_route_origin', 'shipping_routes', ['origin_port'])
    op.create_index('ix_route_dest', 'shipping_routes', ['destination_port'])

    # port_congestion
    op.create_table(
        'port_congestion',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('port_id', sa.String(20), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('vessels_at_anchor', sa.Integer()),
        sa.Column('vessels_in_port', sa.Integer()),
        sa.Column('avg_wait_time_hours', sa.Float()),
        sa.Column('vessels_arriving_24h', sa.Integer()),
        sa.Column('vessels_departing_24h', sa.Integer()),
        sa.Column('container_vessels', sa.Integer()),
        sa.Column('tankers', sa.Integer()),
        sa.Column('bulk_carriers', sa.Integer()),
        sa.Column('computed_at', sa.DateTime(timezone=True)),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_port_congestion_port_id', 'port_congestion', ['port_id'])
    op.create_index('ix_port_congestion_date', 'port_congestion', ['date'])
    op.create_index('ix_port_cong_port_date', 'port_congestion', ['port_id', 'date'])

    # global_shipping_indices
    op.create_table(
        'global_shipping_indices',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('global_activity_index', sa.Float()),
        sa.Column('container_activity_index', sa.Float()),
        sa.Column('tanker_activity_index', sa.Float()),
        sa.Column('bulk_activity_index', sa.Float()),
        sa.Column('asia_pacific_index', sa.Float()),
        sa.Column('europe_index', sa.Float()),
        sa.Column('americas_index', sa.Float()),
        sa.Column('global_congestion_index', sa.Float()),
        sa.Column('china_congestion_index', sa.Float()),
        sa.Column('us_congestion_index', sa.Float()),
        sa.Column('computed_at', sa.DateTime(timezone=True)),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('date')
    )
    op.create_index('ix_global_shipping_indices_date', 'global_shipping_indices', ['date'])

    # === Weather Tables ===

    # weather_observations
    op.create_table(
        'weather_observations',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('location_id', sa.String(50), nullable=False),
        sa.Column('city', sa.String(100)),
        sa.Column('country', sa.String(10)),
        sa.Column('latitude', sa.Float()),
        sa.Column('longitude', sa.Float()),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('temp_c', sa.Float()),
        sa.Column('temp_feels_like_c', sa.Float()),
        sa.Column('temp_min_c', sa.Float()),
        sa.Column('temp_max_c', sa.Float()),
        sa.Column('humidity_pct', sa.Integer()),
        sa.Column('pressure_hpa', sa.Integer()),
        sa.Column('visibility_m', sa.Integer()),
        sa.Column('cloud_cover_pct', sa.Integer()),
        sa.Column('wind_speed_ms', sa.Float()),
        sa.Column('wind_gust_ms', sa.Float()),
        sa.Column('wind_direction_deg', sa.Integer()),
        sa.Column('rain_1h_mm', sa.Float()),
        sa.Column('rain_3h_mm', sa.Float()),
        sa.Column('snow_1h_mm', sa.Float()),
        sa.Column('snow_3h_mm', sa.Float()),
        sa.Column('weather_main', sa.String(50)),
        sa.Column('weather_description', sa.String(100)),
        sa.Column('weather_icon', sa.String(10)),
        sa.Column('raw_data_id', sa.BigInteger()),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_weather_observations_location_id', 'weather_observations', ['location_id'])
    op.create_index('ix_weather_observations_city', 'weather_observations', ['city'])
    op.create_index('ix_weather_observations_country', 'weather_observations', ['country'])
    op.create_index('ix_weather_observations_timestamp', 'weather_observations', ['timestamp'])
    op.create_index('ix_weather_obs_loc_time', 'weather_observations', ['location_id', 'timestamp'])
    op.create_index('ix_weather_obs_city', 'weather_observations', ['city'])

    # weather_forecasts
    op.create_table(
        'weather_forecasts',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('location_id', sa.String(50), nullable=False),
        sa.Column('city', sa.String(100)),
        sa.Column('country', sa.String(10)),
        sa.Column('latitude', sa.Float()),
        sa.Column('longitude', sa.Float()),
        sa.Column('forecast_timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('fetched_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('temp_c', sa.Float()),
        sa.Column('temp_feels_like_c', sa.Float()),
        sa.Column('humidity_pct', sa.Integer()),
        sa.Column('cloud_cover_pct', sa.Integer()),
        sa.Column('wind_speed_ms', sa.Float()),
        sa.Column('pop', sa.Float()),
        sa.Column('rain_mm', sa.Float()),
        sa.Column('snow_mm', sa.Float()),
        sa.Column('weather_main', sa.String(50)),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_weather_forecasts_location_id', 'weather_forecasts', ['location_id'])
    op.create_index('ix_weather_fcst_loc_time', 'weather_forecasts', ['location_id', 'forecast_timestamp'])

    # weather_alerts
    op.create_table(
        'weather_alerts',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('location_id', sa.String(50)),
        sa.Column('alert_id', sa.String(100)),
        sa.Column('sender', sa.String(255)),
        sa.Column('event', sa.String(100)),
        sa.Column('start_time', sa.DateTime(timezone=True)),
        sa.Column('end_time', sa.DateTime(timezone=True)),
        sa.Column('description', sa.Text()),
        sa.Column('severity', sa.String(20)),
        sa.Column('affected_zones', sa.JSON()),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('alert_id')
    )
    op.create_index('ix_weather_alerts_location_id', 'weather_alerts', ['location_id'])
    op.create_index('ix_weather_alerts_alert_id', 'weather_alerts', ['alert_id'])
    op.create_index('ix_weather_alert_event', 'weather_alerts', ['event'])
    op.create_index('ix_weather_alert_time', 'weather_alerts', ['start_time', 'end_time'])

    # weather_daily
    op.create_table(
        'weather_daily',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('location_id', sa.String(50), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('temp_avg_c', sa.Float()),
        sa.Column('temp_min_c', sa.Float()),
        sa.Column('temp_max_c', sa.Float()),
        sa.Column('humidity_avg_pct', sa.Integer()),
        sa.Column('precipitation_mm', sa.Float()),
        sa.Column('snow_mm', sa.Float()),
        sa.Column('wind_avg_ms', sa.Float()),
        sa.Column('cloud_cover_avg_pct', sa.Integer()),
        sa.Column('heating_degree_days', sa.Float()),
        sa.Column('cooling_degree_days', sa.Float()),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_weather_daily_location_id', 'weather_daily', ['location_id'])
    op.create_index('ix_weather_daily_date', 'weather_daily', ['date'])
    op.create_index('ix_weather_daily_loc_date', 'weather_daily', ['location_id', 'date'])

    # === Alert Tables ===

    # alert_rules
    op.create_table(
        'alert_rules',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('description', sa.String(500)),
        sa.Column('factor_name', sa.String(100), nullable=False),
        sa.Column('entity_id', sa.String(50)),
        sa.Column('condition', sa.Enum('gt', 'lt', 'eq', 'zscore_gt', 'zscore_lt', 'pct_change_gt', 'pct_change_lt', name='alertcondition')),
        sa.Column('threshold', sa.Float(), nullable=False),
        sa.Column('lookback_days', sa.Integer(), default=30),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('notification_channel', sa.Enum('email', 'slack', 'webhook', name='notificationchannel'), default='slack'),
        sa.Column('notification_config', sa.String(500)),
        sa.Column('cooldown_minutes', sa.Integer(), default=60),
        sa.Column('created_by', sa.String(100)),
        sa.Column('created_at', sa.DateTime()),
        sa.Column('updated_at', sa.DateTime()),
        sa.PrimaryKeyConstraint('id')
    )

    # alert_notifications
    op.create_table(
        'alert_notifications',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('rule_id', sa.Integer(), sa.ForeignKey('alert_rules.id'), nullable=False),
        sa.Column('entity_id', sa.String(50)),
        sa.Column('factor_value', sa.Float()),
        sa.Column('threshold', sa.Float()),
        sa.Column('computed_value', sa.Float()),
        sa.Column('triggered_at', sa.DateTime()),
        sa.Column('notified_at', sa.DateTime()),
        sa.Column('notification_channel', sa.Enum('email', 'slack', 'webhook', name='notificationchannel')),
        sa.Column('notification_status', sa.Enum('pending', 'sent', 'failed', name='notificationstatus'), default='pending'),
        sa.Column('error_message', sa.String(500)),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_alert_notifications_rule_id', 'alert_notifications', ['rule_id'])


def downgrade() -> None:
    # Drop tables in reverse order (respecting foreign key dependencies)
    op.drop_table('alert_notifications')
    op.drop_table('alert_rules')

    op.drop_table('weather_daily')
    op.drop_table('weather_alerts')
    op.drop_table('weather_forecasts')
    op.drop_table('weather_observations')

    op.drop_table('global_shipping_indices')
    op.drop_table('port_congestion')
    op.drop_table('shipping_routes')
    op.drop_table('port_calls')
    op.drop_table('ports')
    op.drop_table('vessel_positions')
    op.drop_table('vessels')

    op.drop_table('company_hq')
    op.drop_table('airports')
    op.drop_table('flight_landings')
    op.drop_table('flight_positions')
    op.drop_table('aircraft')

    op.drop_table('fred_series')
    op.drop_table('sec_filings')
    op.drop_table('sec_form4_transactions')

    op.drop_table('api_keys')
    op.drop_table('factor_definitions')
    op.drop_table('factors')
    op.drop_table('entities')
    op.drop_table('raw_data_catalog')

    # Drop enums
    op.execute('DROP TYPE IF EXISTS notificationstatus')
    op.execute('DROP TYPE IF EXISTS notificationchannel')
    op.execute('DROP TYPE IF EXISTS alertcondition')
