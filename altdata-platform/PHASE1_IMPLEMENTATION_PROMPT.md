# Phase 1 Implementation Prompt - Complete Tier 1 Data Sources

Use this prompt to implement the remaining Tier 1 data sources after MVP is complete.

---

## The Prompt

```
You are continuing implementation of the Alternative Data Platform. The MVP (SEC EDGAR, FRED, basic API) is complete with 73 passing tests. Now implement the remaining Tier 1 data sources.

## Completed (MVP)
- ✅ SEC EDGAR collector (Form 4, 8-K)
- ✅ FRED collector (yield curve, credit spreads)
- ✅ 5 factors computing
- ✅ REST API with authentication
- ✅ 73 tests passing

## Phase 1 Goals
Add 4 more Tier 1 data sources:
1. ADS-B Exchange (aviation/M&A signals)
2. US Power Grid ISOs (industrial activity)
3. USPTO Patents (innovation tracking)
4. OpenAQ (air quality/manufacturing proxy)

## Working Loop
For each data source:
1. CREATE collector class extending BaseCollector
2. IMPLEMENT fetch() and parse() methods
3. CREATE database models for parsed data
4. CREATE factor computation functions
5. ADD API endpoints for new factors
6. WRITE tests (unit + integration)
7. VERIFY all tests pass
8. PROCEED to next source

---

## STAGE 1: ADS-B Exchange Collector
**Goal:** Track corporate jet movements for M&A signals.

### Tasks:
1. Create ADS-B collector with RapidAPI integration
2. Build aircraft-to-company mapping table
3. Implement flight pattern storage
4. Create derived factors

### Database Models:
```python
# src/models/adsb.py
from sqlalchemy import Column, String, Float, DateTime, Integer, BigInteger, Boolean
from src.models.database import Base

class Aircraft(Base):
    """Aircraft registration and ownership mapping."""
    __tablename__ = "aircraft"
    
    id = Column(BigInteger, primary_key=True)
    icao_hex = Column(String(10), unique=True, nullable=False, index=True)
    registration = Column(String(20), index=True)  # N-number
    aircraft_type = Column(String(20))  # GLF6, G650, etc.
    owner_name = Column(String(255))
    owner_type = Column(String(50))  # corporate, individual, charter
    company_entity_id = Column(String(50), index=True)  # Link to entities table
    is_corporate_jet = Column(Boolean, default=False)
    metadata = Column(JSON)

class FlightPosition(Base):
    """Real-time and historical flight positions."""
    __tablename__ = "flight_positions"
    
    id = Column(BigInteger, primary_key=True)
    icao_hex = Column(String(10), nullable=False, index=True)
    timestamp = Column(DateTime(timezone=True), nullable=False)
    latitude = Column(Float)
    longitude = Column(Float)
    altitude_ft = Column(Integer)
    ground_speed_knots = Column(Integer)
    heading = Column(Integer)
    vertical_rate = Column(Integer)
    squawk = Column(String(10))
    on_ground = Column(Boolean)
    
class FlightLanding(Base):
    """Detected landings for analysis."""
    __tablename__ = "flight_landings"
    
    id = Column(BigInteger, primary_key=True)
    icao_hex = Column(String(10), nullable=False, index=True)
    aircraft_id = Column(BigInteger, ForeignKey("aircraft.id"))
    landing_timestamp = Column(DateTime(timezone=True), nullable=False)
    airport_icao = Column(String(10))
    airport_name = Column(String(255))
    latitude = Column(Float)
    longitude = Column(Float)
    nearest_company_hq = Column(String(50))  # Entity ID if within 50km of HQ
    distance_to_hq_km = Column(Float)
```

### Collector Implementation:
```python
# src/collectors/adsb_exchange.py
from typing import List, Dict, Any
from datetime import datetime
import httpx
from .base import BaseCollector

class ADSBExchangeCollector(BaseCollector):
    """Collector for ADS-B Exchange flight data."""
    
    SOURCE_NAME = "adsb_exchange"
    DEFAULT_RATE_LIMIT = 1.0  # RapidAPI limits
    
    # RapidAPI endpoint
    BASE_URL = "https://adsbexchange-com1.p.rapidapi.com"
    
    def __init__(self, api_key: str, rapidapi_key: str):
        super().__init__()
        self.api_key = api_key
        self.headers = {
            "X-RapidAPI-Key": rapidapi_key,
            "X-RapidAPI-Host": "adsbexchange-com1.p.rapidapi.com"
        }
    
    async def fetch_aircraft_by_registration(self, registration: str) -> Dict:
        """Fetch current position of aircraft by N-number."""
        await self.rate_limiter.wait()
        
        url = f"{self.BASE_URL}/v2/registration/{registration}/"
        response = await self.http_client.get(url, headers=self.headers)
        response.raise_for_status()
        return response.json()
    
    async def fetch_aircraft_in_area(
        self, 
        lat: float, 
        lon: float, 
        radius_nm: int = 50
    ) -> List[Dict]:
        """Fetch all aircraft within radius of a point."""
        await self.rate_limiter.wait()
        
        url = f"{self.BASE_URL}/v2/lat/{lat}/lon/{lon}/dist/{radius_nm}/"
        response = await self.http_client.get(url, headers=self.headers)
        response.raise_for_status()
        return response.json().get("ac", [])
    
    async def fetch_corporate_jets(self, registrations: List[str]) -> List[Dict]:
        """Fetch positions of multiple corporate jets."""
        results = []
        for reg in registrations:
            try:
                data = await self.fetch_aircraft_by_registration(reg)
                if data.get("ac"):
                    results.extend(data["ac"])
            except Exception as e:
                logger.warning(f"Failed to fetch {reg}: {e}")
        return results
    
    def parse(self, raw_data: List[Dict]) -> List[Dict]:
        """Parse aircraft positions into structured format."""
        parsed = []
        for ac in raw_data:
            parsed.append({
                "icao_hex": ac.get("hex"),
                "registration": ac.get("r"),
                "aircraft_type": ac.get("t"),
                "latitude": ac.get("lat"),
                "longitude": ac.get("lon"),
                "altitude_ft": ac.get("alt_baro"),
                "ground_speed_knots": ac.get("gs"),
                "heading": ac.get("track"),
                "vertical_rate": ac.get("baro_rate"),
                "squawk": ac.get("squawk"),
                "on_ground": ac.get("alt_baro") == "ground",
                "timestamp": datetime.utcnow(),
            })
        return parsed
    
    def detect_landing(
        self, 
        positions: List[Dict], 
        altitude_threshold: int = 500
    ) -> List[Dict]:
        """Detect landings from position history."""
        landings = []
        # Implementation: detect altitude drops below threshold near airports
        return landings
```

### Factors to Implement:
```python
# src/transformations/factors/aviation_factors.py
from datetime import date, timedelta
from typing import List, Dict
from haversine import haversine

def calc_executive_flight_frequency(
    company_id: str,
    start_date: date,
    end_date: date,
    db_session
) -> float:
    """Number of flights per week for company jets."""
    # Query flights for company's aircraft
    flights = db_session.query(FlightLanding).join(Aircraft).filter(
        Aircraft.company_entity_id == company_id,
        FlightLanding.landing_timestamp.between(start_date, end_date)
    ).all()
    
    weeks = (end_date - start_date).days / 7
    return len(flights) / weeks if weeks > 0 else 0

def calc_hq_visit_score(
    source_company: str,
    target_company: str,
    date_range: tuple,
    db_session
) -> float:
    """Frequency of jets landing near another company's HQ."""
    # Get target company HQ coordinates
    target = db_session.query(Entity).filter_by(id=target_company).first()
    target_coords = (target.metadata.get("hq_lat"), target.metadata.get("hq_lon"))
    
    # Get landings of source company jets
    landings = db_session.query(FlightLanding).join(Aircraft).filter(
        Aircraft.company_entity_id == source_company,
        FlightLanding.landing_timestamp.between(*date_range)
    ).all()
    
    # Count landings within 50km of target HQ
    visits = sum(
        1 for l in landings 
        if haversine((l.latitude, l.longitude), target_coords) < 50
    )
    
    return visits / len(landings) if landings else 0

def calc_unusual_destination_alert(
    flight: Dict,
    historical_flights: List[Dict],
    threshold_km: float = 20
) -> int:
    """Binary flag when jet visits location not visited in prior 12 months."""
    current_dest = (flight["latitude"], flight["longitude"])
    
    for hist in historical_flights:
        hist_dest = (hist["latitude"], hist["longitude"])
        if haversine(current_dest, hist_dest) < threshold_km:
            return 0  # Been here before
    
    return 1  # New destination

def calc_multi_company_colocation(
    airport_icao: str,
    timestamp: datetime,
    window_hours: int = 24,
    db_session
) -> int:
    """Count companies with jets at same airport within time window."""
    start = timestamp - timedelta(hours=window_hours)
    end = timestamp + timedelta(hours=window_hours)
    
    landings = db_session.query(FlightLanding).join(Aircraft).filter(
        FlightLanding.airport_icao == airport_icao,
        FlightLanding.landing_timestamp.between(start, end),
        Aircraft.company_entity_id.isnot(None)
    ).all()
    
    companies = set(l.aircraft.company_entity_id for l in landings)
    return len(companies)
```

### Verification Tests:
```python
# tests/test_adsb_collector.py
import pytest
from unittest.mock import AsyncMock, patch

class TestADSBCollector:
    
    @pytest.fixture
    def collector(self):
        return ADSBExchangeCollector(
            api_key="test",
            rapidapi_key="test"
        )
    
    @pytest.fixture
    def sample_aircraft_response(self):
        return {
            "ac": [{
                "hex": "A12345",
                "r": "N123AB",
                "t": "GLF6",
                "lat": 40.7128,
                "lon": -74.0060,
                "alt_baro": 35000,
                "gs": 450,
                "track": 270,
            }]
        }
    
    def test_parse_aircraft_data(self, collector, sample_aircraft_response):
        """Test parsing aircraft position data."""
        result = collector.parse(sample_aircraft_response["ac"])
        
        assert len(result) == 1
        assert result[0]["icao_hex"] == "A12345"
        assert result[0]["registration"] == "N123AB"
        assert result[0]["latitude"] == 40.7128
    
    @pytest.mark.asyncio
    @patch("httpx.AsyncClient.get")
    async def test_fetch_by_registration(self, mock_get, collector, sample_aircraft_response):
        """Test fetching aircraft by registration."""
        mock_get.return_value = AsyncMock(
            status_code=200,
            json=lambda: sample_aircraft_response
        )
        
        result = await collector.fetch_aircraft_by_registration("N123AB")
        assert result["ac"][0]["r"] == "N123AB"

class TestAviationFactors:
    
    def test_unusual_destination_detection(self):
        """Test unusual destination alert."""
        current = {"latitude": 37.7749, "longitude": -122.4194}  # SF
        historical = [
            {"latitude": 40.7128, "longitude": -74.0060},  # NYC
            {"latitude": 34.0522, "longitude": -118.2437},  # LA
        ]
        
        result = calc_unusual_destination_alert(current, historical)
        assert result == 1  # SF is new
    
    def test_known_destination(self):
        """Test known destination returns 0."""
        current = {"latitude": 40.7128, "longitude": -74.0060}  # NYC
        historical = [
            {"latitude": 40.7130, "longitude": -74.0062},  # Near NYC
        ]
        
        result = calc_unusual_destination_alert(current, historical)
        assert result == 0  # Already visited
```

**Checkpoint 1:** ADS-B collector working, 4 aviation factors computing, tests passing.

---

## STAGE 2: US Power Grid ISOs Collector
**Goal:** Track electricity demand as industrial activity proxy.

### Tasks:
1. Create collectors for CAISO, ERCOT, PJM, MISO
2. Store load and generation data
3. Implement energy factors

### Database Models:
```python
# src/models/power_grid.py
class GridLoad(Base):
    """Electricity load data from ISOs."""
    __tablename__ = "grid_load"
    
    id = Column(BigInteger, primary_key=True)
    iso = Column(String(20), nullable=False, index=True)  # CAISO, ERCOT, PJM, MISO
    zone = Column(String(50))
    timestamp = Column(DateTime(timezone=True), nullable=False)
    load_mw = Column(Float)
    forecast_mw = Column(Float)
    
class GridGeneration(Base):
    """Generation mix data."""
    __tablename__ = "grid_generation"
    
    id = Column(BigInteger, primary_key=True)
    iso = Column(String(20), nullable=False, index=True)
    timestamp = Column(DateTime(timezone=True), nullable=False)
    total_mw = Column(Float)
    solar_mw = Column(Float)
    wind_mw = Column(Float)
    natural_gas_mw = Column(Float)
    nuclear_mw = Column(Float)
    hydro_mw = Column(Float)
    coal_mw = Column(Float)
    
class GridPrice(Base):
    """Locational Marginal Prices."""
    __tablename__ = "grid_prices"
    
    id = Column(BigInteger, primary_key=True)
    iso = Column(String(20), nullable=False, index=True)
    zone = Column(String(50), nullable=False)
    timestamp = Column(DateTime(timezone=True), nullable=False)
    lmp_price = Column(Float)
    energy_component = Column(Float)
    congestion_component = Column(Float)
    loss_component = Column(Float)
```

### Collector Implementation:
```python
# src/collectors/power_grid.py
from abc import abstractmethod
from typing import Dict, List
import httpx
from .base import BaseCollector

class BaseISOCollector(BaseCollector):
    """Base class for ISO collectors."""
    
    ISO_NAME: str = "base"
    
    @abstractmethod
    async def fetch_load(self, date: date) -> List[Dict]:
        pass
    
    @abstractmethod
    async def fetch_generation(self, date: date) -> List[Dict]:
        pass

class CAISOCollector(BaseISOCollector):
    """California ISO collector."""
    
    SOURCE_NAME = "caiso"
    ISO_NAME = "CAISO"
    BASE_URL = "http://oasis.caiso.com/oasisapi/SingleZip"
    
    async def fetch_load(self, date: date) -> List[Dict]:
        """Fetch CAISO demand data."""
        params = {
            "queryname": "SLD_FCST",
            "market_run_id": "ACTUAL",
            "startdatetime": f"{date}T00:00-0000",
            "enddatetime": f"{date}T23:59-0000",
            "version": 1
        }
        
        await self.rate_limiter.wait()
        response = await self.http_client.get(self.BASE_URL, params=params)
        return self._parse_caiso_xml(response.content)
    
    def _parse_caiso_xml(self, content: bytes) -> List[Dict]:
        """Parse CAISO OASIS XML response."""
        # Implementation for CAISO-specific XML format
        pass

class ERCOTCollector(BaseISOCollector):
    """Texas ERCOT collector."""
    
    SOURCE_NAME = "ercot"
    ISO_NAME = "ERCOT"
    BASE_URL = "https://www.ercot.com/api/1/services/read/dashboards"
    
    async def fetch_load(self, date: date) -> List[Dict]:
        """Fetch ERCOT demand data."""
        # ERCOT provides JSON API
        await self.rate_limiter.wait()
        response = await self.http_client.get(
            f"{self.BASE_URL}/systemWideActualDemand.json"
        )
        return response.json()

class PJMCollector(BaseISOCollector):
    """PJM Interconnection collector."""
    
    SOURCE_NAME = "pjm"
    ISO_NAME = "PJM"
    BASE_URL = "https://api.pjm.com/api/v1"
    
    async def fetch_load(self, date: date) -> List[Dict]:
        """Fetch PJM load data."""
        pass

class MISOCollector(BaseISOCollector):
    """Midcontinent ISO collector."""
    
    SOURCE_NAME = "miso"
    ISO_NAME = "MISO"
    BASE_URL = "https://api.misoenergy.org/MISORTWDDataBroker/DataBrokerServices.asmx"
```

### Factors to Implement:
```python
# src/transformations/factors/energy_factors.py

def calc_industrial_load_index(iso: str, date: date, db_session) -> float:
    """Base load (overnight minimum) as proxy for industrial activity."""
    loads = db_session.query(GridLoad).filter(
        GridLoad.iso == iso,
        GridLoad.timestamp >= datetime.combine(date, time(2, 0)),
        GridLoad.timestamp <= datetime.combine(date, time(5, 0))
    ).all()
    
    return min(l.load_mw for l in loads) if loads else None

def calc_weather_adjusted_demand(
    iso: str, 
    date: date, 
    temp: float, 
    humidity: float,
    db_session
) -> float:
    """Actual demand minus weather-driven demand."""
    actual = db_session.query(func.avg(GridLoad.load_mw)).filter(
        GridLoad.iso == iso,
        func.date(GridLoad.timestamp) == date
    ).scalar()
    
    # Simple weather model (would be trained on historical data)
    predicted = weather_demand_model(iso, temp, humidity, is_weekday(date))
    
    return actual - predicted if actual else None

def calc_renewable_generation_share(iso: str, timestamp: datetime, db_session) -> float:
    """Solar + Wind as percentage of total generation."""
    gen = db_session.query(GridGeneration).filter(
        GridGeneration.iso == iso,
        GridGeneration.timestamp == timestamp
    ).first()
    
    if not gen or not gen.total_mw:
        return None
    
    renewable = (gen.solar_mw or 0) + (gen.wind_mw or 0)
    return renewable / gen.total_mw

def calc_yoy_load_growth(iso: str, date: date, db_session) -> float:
    """Year-over-year change in electricity demand."""
    current = get_daily_avg_load(iso, date, db_session)
    prior = get_daily_avg_load(iso, date - timedelta(days=365), db_session)
    
    return (current - prior) / prior if prior else None
```

**Checkpoint 2:** Power grid collectors for 4 ISOs working, 8 energy factors computing.

---

## STAGE 3: USPTO Patent Collector
**Goal:** Track corporate innovation through patent filings.

### Database Models:
```python
# src/models/patents.py
class Patent(Base):
    """USPTO patent data."""
    __tablename__ = "patents"
    
    id = Column(BigInteger, primary_key=True)
    patent_number = Column(String(20), unique=True, index=True)
    application_number = Column(String(20), index=True)
    application_date = Column(DateTime)
    grant_date = Column(DateTime, index=True)
    title = Column(Text)
    abstract = Column(Text)
    assignee_name = Column(String(255), index=True)
    assignee_entity_id = Column(String(50), index=True)
    claims_count = Column(Integer)
    
class PatentInventor(Base):
    """Patent inventors."""
    __tablename__ = "patent_inventors"
    
    id = Column(BigInteger, primary_key=True)
    patent_id = Column(BigInteger, ForeignKey("patents.id"))
    inventor_name = Column(String(255))
    city = Column(String(100))
    state = Column(String(50))
    country = Column(String(50))
    
class PatentCPC(Base):
    """Cooperative Patent Classification codes."""
    __tablename__ = "patent_cpc"
    
    id = Column(BigInteger, primary_key=True)
    patent_id = Column(BigInteger, ForeignKey("patents.id"))
    cpc_code = Column(String(20), index=True)
    is_primary = Column(Boolean, default=False)
    
class PatentCitation(Base):
    """Patent citations."""
    __tablename__ = "patent_citations"
    
    id = Column(BigInteger, primary_key=True)
    citing_patent_id = Column(BigInteger, ForeignKey("patents.id"))
    cited_patent_number = Column(String(20), index=True)
    citation_type = Column(String(20))  # applicant, examiner
```

### Collector:
```python
# src/collectors/uspto.py
class USPTOCollector(BaseCollector):
    """USPTO Patent Data collector."""
    
    SOURCE_NAME = "uspto"
    BASE_URL = "https://developer.uspto.gov/ibd-api/v1"
    BULK_URL = "https://bulkdata.uspto.gov"
    
    async def fetch_recent_grants(self, days: int = 7) -> List[Dict]:
        """Fetch recently granted patents."""
        # USPTO releases data weekly on Tuesdays
        pass
    
    async def fetch_by_assignee(self, assignee: str, limit: int = 100) -> List[Dict]:
        """Fetch patents by assignee name."""
        params = {
            "searchText": f'assignee:"{assignee}"',
            "start": 0,
            "rows": limit
        }
        
        await self.rate_limiter.wait()
        response = await self.http_client.get(
            f"{self.BASE_URL}/search", 
            params=params
        )
        return response.json()
    
    def parse(self, raw_data: Dict) -> List[Dict]:
        """Parse USPTO API response."""
        patents = []
        for doc in raw_data.get("results", []):
            patents.append({
                "patent_number": doc.get("patentNumber"),
                "application_number": doc.get("applicationNumber"),
                "title": doc.get("inventionTitle"),
                "abstract": doc.get("abstractText"),
                "assignee_name": doc.get("assigneeEntityName"),
                "grant_date": parse_date(doc.get("grantDate")),
                "application_date": parse_date(doc.get("applicationDate")),
                "claims_count": doc.get("claimsCount"),
            })
        return patents
```

### Factors:
```python
# src/transformations/factors/patent_factors.py

def calc_patent_filing_velocity(company_id: str, quarter: tuple, db_session) -> int:
    """Number of patent applications filed per quarter."""
    return db_session.query(Patent).filter(
        Patent.assignee_entity_id == company_id,
        Patent.application_date.between(*quarter)
    ).count()

def calc_ai_ml_patent_share(company_id: str, date_range: tuple, db_session) -> float:
    """Percentage of patents in AI/ML technology classes."""
    AI_CPC_CODES = ["G06N", "G06F18"]  # Machine learning, pattern recognition
    
    total = db_session.query(Patent).filter(
        Patent.assignee_entity_id == company_id,
        Patent.grant_date.between(*date_range)
    ).count()
    
    ai_patents = db_session.query(Patent).join(PatentCPC).filter(
        Patent.assignee_entity_id == company_id,
        Patent.grant_date.between(*date_range),
        PatentCPC.cpc_code.like(any_(AI_CPC_CODES))
    ).distinct().count()
    
    return ai_patents / total if total > 0 else 0

def calc_citation_impact_score(company_id: str, cohort_year: int, db_session) -> float:
    """Average forward citations received per patent."""
    patents = db_session.query(Patent).filter(
        Patent.assignee_entity_id == company_id,
        extract('year', Patent.grant_date) == cohort_year
    ).all()
    
    total_citations = sum(
        db_session.query(PatentCitation).filter(
            PatentCitation.cited_patent_number == p.patent_number
        ).count()
        for p in patents
    )
    
    return total_citations / len(patents) if patents else 0
```

**Checkpoint 3:** USPTO collector working, 8 patent factors computing.

---

## STAGE 4: OpenAQ Air Quality Collector
**Goal:** Track industrial activity through pollution levels.

### Database Models:
```python
# src/models/air_quality.py
class AirQualityReading(Base):
    """Air quality measurements."""
    __tablename__ = "air_quality_readings"
    
    id = Column(BigInteger, primary_key=True)
    location_id = Column(Integer, index=True)
    location_name = Column(String(255))
    city = Column(String(100), index=True)
    country = Column(String(10), index=True)
    latitude = Column(Float)
    longitude = Column(Float)
    parameter = Column(String(20), index=True)  # pm25, pm10, no2, o3, co
    value = Column(Float)
    unit = Column(String(20))
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    
class IndustrialZone(Base):
    """Industrial zones for monitoring."""
    __tablename__ = "industrial_zones"
    
    id = Column(BigInteger, primary_key=True)
    name = Column(String(255))
    country = Column(String(10))
    latitude = Column(Float)
    longitude = Column(Float)
    zone_type = Column(String(50))  # manufacturing, refinery, port
    associated_companies = Column(JSON)  # List of entity IDs
```

### Collector:
```python
# src/collectors/openaq.py
class OpenAQCollector(BaseCollector):
    """OpenAQ air quality data collector."""
    
    SOURCE_NAME = "openaq"
    BASE_URL = "https://api.openaq.org/v2"
    DEFAULT_RATE_LIMIT = 1.0  # 100/min limit
    
    def __init__(self, api_key: str):
        super().__init__()
        self.headers = {"X-API-Key": api_key}
    
    async def fetch_measurements(
        self,
        country: str = None,
        city: str = None,
        parameter: str = "pm25",
        limit: int = 1000
    ) -> List[Dict]:
        """Fetch air quality measurements."""
        params = {
            "parameter": parameter,
            "limit": limit,
            "order_by": "datetime",
            "sort": "desc"
        }
        if country:
            params["country"] = country
        if city:
            params["city"] = city
        
        await self.rate_limiter.wait()
        response = await self.http_client.get(
            f"{self.BASE_URL}/measurements",
            params=params,
            headers=self.headers
        )
        return response.json().get("results", [])
    
    async def fetch_locations_near(
        self,
        lat: float,
        lon: float,
        radius_km: int = 25
    ) -> List[Dict]:
        """Fetch monitoring locations near a point."""
        params = {
            "coordinates": f"{lat},{lon}",
            "radius": radius_km * 1000,  # API uses meters
            "limit": 100
        }
        
        await self.rate_limiter.wait()
        response = await self.http_client.get(
            f"{self.BASE_URL}/locations",
            params=params,
            headers=self.headers
        )
        return response.json().get("results", [])
```

### Factors:
```python
# src/transformations/factors/environmental_factors.py

def calc_industrial_activity_index(
    industrial_zones: List[Dict],
    date: date,
    db_session
) -> float:
    """PM2.5 + NO2 levels near industrial zones as production proxy."""
    readings = []
    
    for zone in industrial_zones:
        # Get sensors within 10km of zone
        zone_readings = db_session.query(AirQualityReading).filter(
            AirQualityReading.parameter.in_(["pm25", "no2"]),
            func.date(AirQualityReading.timestamp) == date,
            # Simplified distance check
            AirQualityReading.latitude.between(zone["lat"] - 0.1, zone["lat"] + 0.1),
            AirQualityReading.longitude.between(zone["lon"] - 0.1, zone["lon"] + 0.1)
        ).all()
        
        readings.extend(zone_readings)
    
    return np.mean([r.value for r in readings]) if readings else None

def calc_china_manufacturing_proxy(date: date, db_session) -> float:
    """Air quality in Chinese manufacturing cities (worse = more activity)."""
    MANUFACTURING_CITIES = ["Shenzhen", "Dongguan", "Suzhou", "Ningbo", "Hangzhou"]
    
    readings = db_session.query(
        func.avg(AirQualityReading.value)
    ).filter(
        AirQualityReading.city.in_(MANUFACTURING_CITIES),
        AirQualityReading.parameter == "pm25",
        func.date(AirQualityReading.timestamp) == date
    ).scalar()
    
    return readings

def calc_lockdown_detection_score(
    location_id: int,
    date: date,
    db_session
) -> float:
    """Z-score of current pollution vs 30-day rolling average."""
    current = db_session.query(func.avg(AirQualityReading.value)).filter(
        AirQualityReading.location_id == location_id,
        func.date(AirQualityReading.timestamp) == date
    ).scalar()
    
    historical = db_session.query(AirQualityReading.value).filter(
        AirQualityReading.location_id == location_id,
        AirQualityReading.timestamp >= date - timedelta(days=30),
        AirQualityReading.timestamp < date
    ).all()
    
    if not historical or not current:
        return None
    
    values = [h.value for h in historical]
    mean = np.mean(values)
    std = np.std(values)
    
    return (current - mean) / std if std > 0 else 0
```

**Checkpoint 4:** OpenAQ collector working, 6 environmental factors computing.

---

## STAGE 5: Integration & Factor Library
**Goal:** Create unified factor computation system and API endpoints.

### Tasks:
1. Create factor registry
2. Add batch computation jobs
3. Extend API with new factors
4. Add factor correlation analysis

### Factor Registry:
```python
# src/transformations/factor_registry.py
from typing import Dict, Callable, List
from dataclasses import dataclass

@dataclass
class FactorSpec:
    id: str
    name: str
    category: str
    entity_type: str
    frequency: str
    compute_fn: Callable
    dependencies: List[str]

FACTOR_REGISTRY: Dict[str, FactorSpec] = {}

def register_factor(
    id: str,
    name: str,
    category: str,
    entity_type: str = "company",
    frequency: str = "daily",
    dependencies: List[str] = None
):
    """Decorator to register a factor computation function."""
    def decorator(fn: Callable):
        FACTOR_REGISTRY[id] = FactorSpec(
            id=id,
            name=name,
            category=category,
            entity_type=entity_type,
            frequency=frequency,
            compute_fn=fn,
            dependencies=dependencies or []
        )
        return fn
    return decorator

def compute_factor(factor_id: str, entity_id: str, date: date, db_session) -> float:
    """Compute a factor value."""
    if factor_id not in FACTOR_REGISTRY:
        raise ValueError(f"Unknown factor: {factor_id}")
    
    spec = FACTOR_REGISTRY[factor_id]
    return spec.compute_fn(entity_id, date, db_session)

def list_factors(category: str = None) -> List[FactorSpec]:
    """List available factors."""
    factors = list(FACTOR_REGISTRY.values())
    if category:
        factors = [f for f in factors if f.category == category]
    return factors
```

**Checkpoint 5:** All Tier 1 factors registered, batch computation working.

---

## STAGE 6: API Extensions
**Goal:** Add endpoints for new factors and data sources.

### New Endpoints:
```python
# Add to src/api/main.py

@app.get("/api/v1/aviation/flights", tags=["Aviation"])
async def get_corporate_flights(
    company_id: str = Query(...),
    start_date: date = Query(None),
    end_date: date = Query(None),
    api_key: str = Depends(verify_api_key)
):
    """Get corporate jet flight history."""
    pass

@app.get("/api/v1/energy/load", tags=["Energy"])
async def get_grid_load(
    iso: str = Query(..., enum=["CAISO", "ERCOT", "PJM", "MISO"]),
    date: date = Query(...),
    api_key: str = Depends(verify_api_key)
):
    """Get electricity load data."""
    pass

@app.get("/api/v1/patents/filings", tags=["Patents"])
async def get_patent_filings(
    company_id: str = Query(...),
    start_date: date = Query(None),
    end_date: date = Query(None),
    api_key: str = Depends(verify_api_key)
):
    """Get patent filing history."""
    pass

@app.get("/api/v1/environment/air-quality", tags=["Environment"])
async def get_air_quality(
    city: str = Query(None),
    country: str = Query(None),
    date: date = Query(...),
    api_key: str = Depends(verify_api_key)
):
    """Get air quality readings."""
    pass
```

**Checkpoint 6:** All API endpoints working, documentation updated.

---

## STAGE 7: End-to-End Testing
**Goal:** Verify complete Phase 1 functionality.

### Test Suite:
```python
# tests/test_phase1_e2e.py

@pytest.mark.e2e
class TestPhase1Integration:
    
    def test_aviation_factor_pipeline(self, db_session):
        """Test ADS-B → factor computation → API."""
        # 1. Seed aircraft data
        # 2. Seed flight positions
        # 3. Compute hq_visit_score
        # 4. Query via API
        # 5. Verify values match
        pass
    
    def test_energy_factor_pipeline(self, db_session):
        """Test grid data → factor computation → API."""
        pass
    
    def test_patent_factor_pipeline(self, db_session):
        """Test patent data → factor computation → API."""
        pass
    
    def test_environmental_factor_pipeline(self, db_session):
        """Test air quality → factor computation → API."""
        pass
    
    def test_cross_source_factor(self, db_session):
        """Test factor combining multiple data sources."""
        # E.g., industrial load + air quality correlation
        pass
```

**Checkpoint 7:** All 7 Tier 1 sources live, 50+ factors computing, tests passing.

---

## Success Criteria

Phase 1 is complete when:
- [ ] ADS-B collector fetching corporate jet data
- [ ] 4 ISO collectors (CAISO, ERCOT, PJM, MISO) working
- [ ] USPTO patent collector working
- [ ] OpenAQ air quality collector working
- [ ] 50+ factors computing correctly
- [ ] All new API endpoints documented
- [ ] 90+ tests passing
- [ ] Coverage > 75%
```

---

## How to Use

1. Copy the prompt above
2. Paste into Claude Code after MVP is complete
3. Work through each stage sequentially
4. Verify tests pass at each checkpoint
