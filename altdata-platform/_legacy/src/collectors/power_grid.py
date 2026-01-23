"""US Power Grid ISO collectors for load and generation data."""

import logging
from abc import abstractmethod
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from xml.etree import ElementTree

import httpx

from src.collectors.base import BaseCollector, CollectorError
from src.config.settings import settings
from src.models.database import SessionLocal
from src.models.power_grid import GridLoad, GridPrice, GenerationMix, ISORegion

logger = logging.getLogger(__name__)


class BaseGridCollector(BaseCollector[Dict, Dict]):
    """Base collector for power grid ISOs."""

    ISO_REGION: str = ""
    DEFAULT_RATE_LIMIT = 2.0

    def __init__(self, rate_limit: Optional[float] = None):
        """Initialize the grid collector.

        Args:
            rate_limit: Requests per second
        """
        super().__init__(rate_limit=rate_limit or self.DEFAULT_RATE_LIMIT)

    @abstractmethod
    async def fetch_load(self) -> Dict:
        """Fetch current grid load data."""
        pass

    @abstractmethod
    async def fetch_generation_mix(self) -> Dict:
        """Fetch current generation mix by fuel type."""
        pass

    def parse_load(self, raw_data: Dict) -> Optional[Dict]:
        """Parse load data into standard format.

        Args:
            raw_data: Raw API response

        Returns:
            Parsed load dict
        """
        return raw_data

    def parse_generation(self, raw_data: Dict) -> Optional[Dict]:
        """Parse generation mix into standard format.

        Args:
            raw_data: Raw API response

        Returns:
            Parsed generation dict
        """
        return raw_data

    async def store_load(self, load_data: Dict) -> GridLoad:
        """Store load data in database.

        Args:
            load_data: Parsed load data

        Returns:
            Created GridLoad record
        """
        session = SessionLocal()
        try:
            record = GridLoad(
                iso_region=self.ISO_REGION,
                timestamp=load_data.get("timestamp", datetime.utcnow()),
                load_mw=load_data["load_mw"],
                forecast_mw=load_data.get("forecast_mw"),
                capacity_mw=load_data.get("capacity_mw"),
                load_forecast_delta=load_data.get("load_forecast_delta"),
                load_pct_of_capacity=load_data.get("load_pct_of_capacity"),
            )
            session.add(record)
            session.commit()
            session.refresh(record)

            logger.info(f"Stored {self.ISO_REGION} load: {record.load_mw} MW")
            return record
        finally:
            session.close()

    async def store_generation(self, gen_data: Dict) -> GenerationMix:
        """Store generation mix in database.

        Args:
            gen_data: Parsed generation data

        Returns:
            Created GenerationMix record
        """
        session = SessionLocal()
        try:
            record = GenerationMix(
                iso_region=self.ISO_REGION,
                timestamp=gen_data.get("timestamp", datetime.utcnow()),
                total_generation_mw=gen_data.get("total_generation_mw"),
                natural_gas_mw=gen_data.get("natural_gas_mw"),
                coal_mw=gen_data.get("coal_mw"),
                nuclear_mw=gen_data.get("nuclear_mw"),
                hydro_mw=gen_data.get("hydro_mw"),
                wind_mw=gen_data.get("wind_mw"),
                solar_mw=gen_data.get("solar_mw"),
                other_mw=gen_data.get("other_mw"),
                imports_mw=gen_data.get("imports_mw"),
                renewable_pct=gen_data.get("renewable_pct"),
            )
            session.add(record)
            session.commit()
            session.refresh(record)

            logger.info(f"Stored {self.ISO_REGION} generation mix")
            return record
        finally:
            session.close()


class CAISOCollector(BaseGridCollector):
    """California ISO (CAISO) data collector.

    CAISO provides real-time grid data via OASIS API.
    """

    SOURCE_NAME = "caiso"
    ISO_REGION = "CAISO"
    BASE_URL = "http://oasis.caiso.com/oasisapi/SingleZip"
    DEMAND_URL = "http://www.caiso.com/outlook/SP/demand.csv"
    SUPPLY_URL = "http://www.caiso.com/outlook/SP/fuelsource.csv"

    async def fetch(self) -> Dict:
        """Fetch current CAISO data."""
        load_data = await self.fetch_load()
        gen_data = await self.fetch_generation_mix()
        return {"load": load_data, "generation": gen_data}

    async def fetch_load(self) -> Dict:
        """Fetch current CAISO demand/load."""
        await self.rate_limiter.wait()

        try:
            response = await self.http_client.get(self.DEMAND_URL)
            response.raise_for_status()

            lines = response.text.strip().split('\n')
            if len(lines) < 2:
                return {}

            # Parse CSV: Time,Current demand,Day-ahead forecast,...
            header = lines[0].split(',')
            latest = lines[-1].split(',')

            return {
                "timestamp": datetime.utcnow(),
                "load_mw": float(latest[1]) if len(latest) > 1 and latest[1] else 0,
                "forecast_mw": float(latest[2]) if len(latest) > 2 and latest[2] else None,
            }
        except Exception as e:
            logger.error(f"CAISO load fetch error: {e}")
            return {}

    async def fetch_generation_mix(self) -> Dict:
        """Fetch current CAISO generation by fuel source."""
        await self.rate_limiter.wait()

        try:
            response = await self.http_client.get(self.SUPPLY_URL)
            response.raise_for_status()

            lines = response.text.strip().split('\n')
            if len(lines) < 2:
                return {}

            header = lines[0].split(',')
            latest = lines[-1].split(',')

            # CAISO columns: Time,Solar,Wind,Geothermal,Biomass,Biogas,
            # Small hydro,Coal,Nuclear,Natural Gas,Large Hydro,Batteries,Imports,Other
            fuel_map = {}
            for i, col in enumerate(header):
                if i < len(latest):
                    try:
                        fuel_map[col.strip().lower()] = float(latest[i]) if latest[i] else 0
                    except (ValueError, IndexError):
                        continue

            solar = fuel_map.get("solar", 0)
            wind = fuel_map.get("wind", 0)
            hydro = fuel_map.get("large hydro", 0) + fuel_map.get("small hydro", 0)
            total = sum(v for k, v in fuel_map.items() if k != "time" and isinstance(v, (int, float)))

            renewable_pct = (solar + wind + hydro) / total * 100 if total > 0 else 0

            return {
                "timestamp": datetime.utcnow(),
                "total_generation_mw": total,
                "natural_gas_mw": fuel_map.get("natural gas", 0),
                "coal_mw": fuel_map.get("coal", 0),
                "nuclear_mw": fuel_map.get("nuclear", 0),
                "hydro_mw": hydro,
                "wind_mw": wind,
                "solar_mw": solar,
                "other_mw": fuel_map.get("other", 0) + fuel_map.get("geothermal", 0),
                "imports_mw": fuel_map.get("imports", 0),
                "renewable_pct": renewable_pct,
            }
        except Exception as e:
            logger.error(f"CAISO generation fetch error: {e}")
            return {}

    def parse(self, raw_data: Dict) -> Dict:
        """Parse CAISO data."""
        return raw_data


class ERCOTCollector(BaseGridCollector):
    """Electric Reliability Council of Texas (ERCOT) data collector.

    ERCOT provides real-time grid data via public API.
    """

    SOURCE_NAME = "ercot"
    ISO_REGION = "ERCOT"
    BASE_URL = "https://www.ercot.com/api/1/services/read"
    DEMAND_URL = "https://www.ercot.com/content/cdr/html/real_time_system_conditions.html"

    async def fetch(self) -> Dict:
        """Fetch current ERCOT data."""
        load_data = await self.fetch_load()
        gen_data = await self.fetch_generation_mix()
        return {"load": load_data, "generation": gen_data}

    async def fetch_load(self) -> Dict:
        """Fetch current ERCOT system conditions."""
        await self.rate_limiter.wait()

        try:
            response = await self.http_client.get(self.DEMAND_URL)
            response.raise_for_status()

            # Parse HTML table for system conditions
            # ERCOT provides: Current System Demand, Available Capacity, etc.
            content = response.text

            # Simple extraction - in production would use proper HTML parsing
            load_mw = self._extract_value(content, "Current System Demand")
            capacity_mw = self._extract_value(content, "Available Capacity")

            return {
                "timestamp": datetime.utcnow(),
                "load_mw": load_mw,
                "capacity_mw": capacity_mw,
                "load_pct_of_capacity": (load_mw / capacity_mw * 100) if capacity_mw else None,
            }
        except Exception as e:
            logger.error(f"ERCOT load fetch error: {e}")
            return {}

    async def fetch_generation_mix(self) -> Dict:
        """Fetch current ERCOT generation mix."""
        await self.rate_limiter.wait()

        try:
            # ERCOT fuel mix URL
            url = "https://www.ercot.com/content/cdr/html/CURRENT_DAYCOP_HSL.html"
            response = await self.http_client.get(url)
            response.raise_for_status()

            # Parse generation data
            return {
                "timestamp": datetime.utcnow(),
                "total_generation_mw": 0,  # Would parse from response
                "wind_mw": 0,
                "solar_mw": 0,
                "natural_gas_mw": 0,
            }
        except Exception as e:
            logger.error(f"ERCOT generation fetch error: {e}")
            return {}

    def _extract_value(self, html: str, label: str) -> float:
        """Extract numeric value from HTML content."""
        try:
            # Simple regex-free extraction
            if label in html:
                start = html.find(label)
                # Find next number after label
                for i in range(start, min(start + 200, len(html))):
                    if html[i].isdigit():
                        end = i
                        while end < len(html) and (html[end].isdigit() or html[end] in ',.'):
                            end += 1
                        return float(html[i:end].replace(',', ''))
        except Exception:
            pass
        return 0.0

    def parse(self, raw_data: Dict) -> Dict:
        """Parse ERCOT data."""
        return raw_data


class PJMCollector(BaseGridCollector):
    """PJM Interconnection data collector.

    PJM covers Mid-Atlantic and parts of Midwest.
    """

    SOURCE_NAME = "pjm"
    ISO_REGION = "PJM"
    BASE_URL = "https://api.pjm.com/api/v1"
    DATA_URL = "https://dataminer2.pjm.com/feed"

    async def fetch(self) -> Dict:
        """Fetch current PJM data."""
        load_data = await self.fetch_load()
        gen_data = await self.fetch_generation_mix()
        return {"load": load_data, "generation": gen_data}

    async def fetch_load(self) -> Dict:
        """Fetch current PJM load."""
        await self.rate_limiter.wait()

        try:
            url = f"{self.DATA_URL}/inst_load"
            response = await self.http_client.get(url)
            response.raise_for_status()

            data = response.json()
            if data and isinstance(data, list) and len(data) > 0:
                latest = data[-1]
                return {
                    "timestamp": datetime.utcnow(),
                    "load_mw": latest.get("instantaneous_load", 0),
                    "forecast_mw": latest.get("forecast_load"),
                }
            return {}
        except Exception as e:
            logger.error(f"PJM load fetch error: {e}")
            return {}

    async def fetch_generation_mix(self) -> Dict:
        """Fetch current PJM generation mix."""
        await self.rate_limiter.wait()

        try:
            url = f"{self.DATA_URL}/gen_by_fuel"
            response = await self.http_client.get(url)
            response.raise_for_status()

            data = response.json()
            result = {
                "timestamp": datetime.utcnow(),
                "total_generation_mw": 0,
            }

            if data and isinstance(data, list):
                for item in data:
                    fuel = item.get("fuel_type", "").lower()
                    mw = item.get("mw", 0)
                    result["total_generation_mw"] += mw

                    if "gas" in fuel:
                        result["natural_gas_mw"] = result.get("natural_gas_mw", 0) + mw
                    elif "coal" in fuel:
                        result["coal_mw"] = result.get("coal_mw", 0) + mw
                    elif "nuclear" in fuel:
                        result["nuclear_mw"] = result.get("nuclear_mw", 0) + mw
                    elif "wind" in fuel:
                        result["wind_mw"] = result.get("wind_mw", 0) + mw
                    elif "solar" in fuel:
                        result["solar_mw"] = result.get("solar_mw", 0) + mw
                    elif "hydro" in fuel:
                        result["hydro_mw"] = result.get("hydro_mw", 0) + mw

            return result
        except Exception as e:
            logger.error(f"PJM generation fetch error: {e}")
            return {}

    def parse(self, raw_data: Dict) -> Dict:
        """Parse PJM data."""
        return raw_data


class MISOCollector(BaseGridCollector):
    """Midcontinent ISO (MISO) data collector.

    MISO covers central US region.
    """

    SOURCE_NAME = "miso"
    ISO_REGION = "MISO"
    BASE_URL = "https://api.misoenergy.org/MISORTWDDataBroker/DataBrokerServices.asmx"

    async def fetch(self) -> Dict:
        """Fetch current MISO data."""
        load_data = await self.fetch_load()
        gen_data = await self.fetch_generation_mix()
        return {"load": load_data, "generation": gen_data}

    async def fetch_load(self) -> Dict:
        """Fetch current MISO load."""
        await self.rate_limiter.wait()

        try:
            # MISO provides data via SOAP/XML API
            url = "https://api.misoenergy.org/MISORTWDDataBroker/DataBrokerServices.asmx/getSystemConditions"
            response = await self.http_client.get(url)
            response.raise_for_status()

            # Parse XML response
            root = ElementTree.fromstring(response.text)

            # Extract values from XML
            load_mw = 0
            for elem in root.iter():
                if "ActualLoad" in elem.tag or "CurrentLoad" in elem.tag:
                    load_mw = float(elem.text or 0)
                    break

            return {
                "timestamp": datetime.utcnow(),
                "load_mw": load_mw,
            }
        except Exception as e:
            logger.error(f"MISO load fetch error: {e}")
            return {}

    async def fetch_generation_mix(self) -> Dict:
        """Fetch current MISO generation mix."""
        await self.rate_limiter.wait()

        try:
            url = "https://api.misoenergy.org/MISORTWDDataBroker/DataBrokerServices.asmx/getFuelMix"
            response = await self.http_client.get(url)
            response.raise_for_status()

            root = ElementTree.fromstring(response.text)

            result = {
                "timestamp": datetime.utcnow(),
                "total_generation_mw": 0,
            }

            fuel_mapping = {
                "coal": "coal_mw",
                "gas": "natural_gas_mw",
                "nuclear": "nuclear_mw",
                "wind": "wind_mw",
                "solar": "solar_mw",
                "hydro": "hydro_mw",
            }

            for elem in root.iter():
                tag_lower = elem.tag.lower()
                for fuel_key, result_key in fuel_mapping.items():
                    if fuel_key in tag_lower:
                        try:
                            mw = float(elem.text or 0)
                            result[result_key] = result.get(result_key, 0) + mw
                            result["total_generation_mw"] += mw
                        except ValueError:
                            pass

            return result
        except Exception as e:
            logger.error(f"MISO generation fetch error: {e}")
            return {}

    def parse(self, raw_data: Dict) -> Dict:
        """Parse MISO data."""
        return raw_data


def get_grid_collector(iso_region: str) -> BaseGridCollector:
    """Factory function to get collector for ISO region.

    Args:
        iso_region: ISO region code

    Returns:
        Appropriate collector instance

    Raises:
        ValueError: If region not supported
    """
    collectors = {
        "CAISO": CAISOCollector,
        "ERCOT": ERCOTCollector,
        "PJM": PJMCollector,
        "MISO": MISOCollector,
    }

    if iso_region not in collectors:
        raise ValueError(f"Unsupported ISO region: {iso_region}")

    return collectors[iso_region]()
