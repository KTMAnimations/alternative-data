"""SEC EDGAR data collector for Form 4 filings and other SEC documents."""

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from xml.etree import ElementTree

import httpx

from src.collectors.base import BaseCollector, CollectorError
from src.config.settings import settings
from src.models.database import SessionLocal
from src.models.schemas import RawDataCatalog, SECForm4Transaction

logger = logging.getLogger(__name__)


class SECEdgarCollector(BaseCollector[str, List[Dict]]):
    """Collector for SEC EDGAR Form 4 filings.

    Fetches insider trading filings from SEC EDGAR and parses them
    into structured transaction data.
    """

    SOURCE_NAME = "sec_edgar"
    BASE_URL = "https://www.sec.gov"
    DEFAULT_RATE_LIMIT = 10.0  # SEC allows 10 requests per second

    def __init__(
        self,
        user_agent: Optional[str] = None,
        rate_limit: Optional[float] = None,
    ):
        """Initialize the SEC EDGAR collector.

        Args:
            user_agent: User-Agent string (required by SEC)
            rate_limit: Requests per second (default: 10)
        """
        super().__init__(rate_limit=rate_limit or settings.sec_edgar_rate_limit)
        self.user_agent = user_agent or settings.sec_edgar_user_agent
        self.headers = {
            "User-Agent": self.user_agent,
            "Accept-Encoding": "gzip, deflate",
        }

    @property
    def http_client(self) -> httpx.AsyncClient:
        """HTTP client with SEC-compliant headers."""
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(
                timeout=30.0,
                follow_redirects=True,
                headers=self.headers,
            )
        return self._http_client

    async def fetch(self) -> str:
        """Fetch recent Form 4 filings RSS feed.

        Returns:
            RSS feed XML content
        """
        # Fetch recent Form 4 filings from SEC RSS feed
        url = f"{self.BASE_URL}/cgi-bin/browse-edgar?action=getcurrent&type=4&company=&dateb=&owner=include&count=40&output=atom"

        await self.rate_limiter.wait()
        response = await self.http_client.get(url)
        response.raise_for_status()

        return response.text

    async def fetch_form4_document(self, filing_url: str) -> str:
        """Fetch a specific Form 4 XML document.

        Args:
            filing_url: URL to the Form 4 filing

        Returns:
            Form 4 XML content
        """
        await self.rate_limiter.wait()
        response = await self.http_client.get(filing_url)
        response.raise_for_status()
        return response.text

    async def fetch_recent_form4s(self, limit: int = 40) -> List[Dict]:
        """Fetch recent Form 4 filings with full details.

        Args:
            limit: Maximum number of filings to fetch

        Returns:
            List of parsed Form 4 transactions
        """
        # Get RSS feed
        feed_xml = await self.fetch()

        # Parse RSS feed to get filing URLs
        filings = self._parse_rss_feed(feed_xml)

        results = []
        for filing in filings[:limit]:
            try:
                # Get the actual Form 4 XML document
                if filing.get("xml_url"):
                    xml_content = await self.fetch_form4_document(filing["xml_url"])
                    parsed = self.parse_form4_xml(xml_content)
                    parsed["filing_info"] = filing
                    results.append(parsed)
            except Exception as e:
                logger.warning(f"Failed to fetch/parse filing: {e}")
                continue

        return results

    def _parse_rss_feed(self, xml_content: str) -> List[Dict]:
        """Parse SEC RSS feed to extract filing metadata.

        Args:
            xml_content: RSS/Atom feed XML

        Returns:
            List of filing metadata dicts
        """
        filings = []
        try:
            # SEC uses Atom format
            ns = {"atom": "http://www.w3.org/2005/Atom"}
            root = ElementTree.fromstring(xml_content)

            for entry in root.findall("atom:entry", ns):
                filing = {}

                # Get title (contains company name)
                title_elem = entry.find("atom:title", ns)
                if title_elem is not None and title_elem.text:
                    filing["title"] = title_elem.text

                # Get filing links
                for link in entry.findall("atom:link", ns):
                    href = link.get("href", "")
                    if href:
                        filing["url"] = href
                        # Try to construct the XML document URL
                        if "/Archives/edgar/data/" in href:
                            # Convert filing index URL to actual document URL
                            base_url = href.replace("-index.htm", "")
                            # The primary document is usually the last part with .xml
                            parts = base_url.split("/")
                            accession = parts[-1] if parts else ""
                            accession_clean = accession.replace("-", "")
                            filing["xml_url"] = f"{base_url}/{accession_clean}.xml"
                            filing["accession_number"] = accession

                # Get filing date
                updated_elem = entry.find("atom:updated", ns)
                if updated_elem is not None and updated_elem.text:
                    filing["filed_date"] = updated_elem.text

                filings.append(filing)

        except ElementTree.ParseError as e:
            logger.error(f"Failed to parse RSS feed: {e}")

        return filings

    def parse(self, raw_data: str) -> List[Dict]:
        """Parse RSS feed data.

        Args:
            raw_data: RSS feed XML content

        Returns:
            List of filing metadata
        """
        return self._parse_rss_feed(raw_data)

    def parse_form4_xml(self, xml_content: str) -> Dict[str, Any]:
        """Parse Form 4 XML into structured transaction data.

        Args:
            xml_content: Form 4 XML document

        Returns:
            Parsed filing data with transactions
        """
        result = {
            "issuer_cik": None,
            "issuer_name": None,
            "ticker": None,
            "insider_cik": None,
            "insider_name": None,
            "insider_title": None,
            "is_director": False,
            "is_officer": False,
            "is_ten_percent_owner": False,
            "transactions": [],
        }

        try:
            root = ElementTree.fromstring(xml_content)

            # Parse issuer info
            issuer = root.find(".//issuer")
            if issuer is not None:
                cik = issuer.find("issuerCik")
                if cik is not None and cik.text:
                    result["issuer_cik"] = cik.text.strip()

                name = issuer.find("issuerName")
                if name is not None and name.text:
                    result["issuer_name"] = name.text.strip()

                symbol = issuer.find("issuerTradingSymbol")
                if symbol is not None and symbol.text:
                    result["ticker"] = symbol.text.strip()

            # Parse reporting owner info
            owner = root.find(".//reportingOwner")
            if owner is not None:
                owner_id = owner.find(".//reportingOwnerId")
                if owner_id is not None:
                    owner_cik = owner_id.find("rptOwnerCik")
                    if owner_cik is not None and owner_cik.text:
                        result["insider_cik"] = owner_cik.text.strip()

                    owner_name = owner_id.find("rptOwnerName")
                    if owner_name is not None and owner_name.text:
                        result["insider_name"] = owner_name.text.strip()

                rel = owner.find(".//reportingOwnerRelationship")
                if rel is not None:
                    is_dir = rel.find("isDirector")
                    result["is_director"] = is_dir is not None and is_dir.text == "1"

                    is_off = rel.find("isOfficer")
                    result["is_officer"] = is_off is not None and is_off.text == "1"

                    is_ten = rel.find("isTenPercentOwner")
                    result["is_ten_percent_owner"] = is_ten is not None and is_ten.text == "1"

                    title = rel.find("officerTitle")
                    if title is not None and title.text:
                        result["insider_title"] = title.text.strip()

            # Parse non-derivative transactions
            for txn in root.findall(".//nonDerivativeTransaction"):
                transaction = self._parse_transaction(txn)
                if transaction:
                    result["transactions"].append(transaction)

            # Parse derivative transactions
            for txn in root.findall(".//derivativeTransaction"):
                transaction = self._parse_transaction(txn, is_derivative=True)
                if transaction:
                    result["transactions"].append(transaction)

        except ElementTree.ParseError as e:
            logger.error(f"Failed to parse Form 4 XML: {e}")
            raise CollectorError(f"XML parse error: {e}")

        return result

    def _parse_transaction(
        self, txn_elem: ElementTree.Element, is_derivative: bool = False
    ) -> Optional[Dict]:
        """Parse a single transaction element.

        Args:
            txn_elem: Transaction XML element
            is_derivative: Whether this is a derivative transaction

        Returns:
            Transaction dict or None if parsing fails
        """
        transaction = {
            "is_derivative": is_derivative,
            "shares": None,
            "price": None,
            "transaction_code": None,
            "acquired_disposed": None,
            "transaction_date": None,
            "shares_owned_after": None,
            "ownership_type": None,
        }

        # Transaction date
        date_elem = txn_elem.find(".//transactionDate/value")
        if date_elem is not None and date_elem.text:
            try:
                transaction["transaction_date"] = datetime.strptime(
                    date_elem.text.strip(), "%Y-%m-%d"
                )
            except ValueError:
                pass

        # Transaction code (P=Purchase, S=Sale, etc.)
        code_elem = txn_elem.find(".//transactionCoding/transactionCode")
        if code_elem is not None and code_elem.text:
            transaction["transaction_code"] = code_elem.text.strip()

        # Transaction amounts
        amounts = txn_elem.find(".//transactionAmounts")
        if amounts is not None:
            shares = amounts.find("transactionShares/value")
            if shares is not None and shares.text:
                try:
                    transaction["shares"] = float(shares.text.strip())
                except ValueError:
                    pass

            price = amounts.find("transactionPricePerShare/value")
            if price is not None and price.text:
                try:
                    transaction["price"] = float(price.text.strip())
                except ValueError:
                    pass

            acq_disp = amounts.find("transactionAcquiredDisposedCode/value")
            if acq_disp is not None and acq_disp.text:
                transaction["acquired_disposed"] = acq_disp.text.strip()

        # Post-transaction holdings
        post = txn_elem.find(".//postTransactionAmounts/sharesOwnedFollowingTransaction/value")
        if post is not None and post.text:
            try:
                transaction["shares_owned_after"] = float(post.text.strip())
            except ValueError:
                pass

        # Ownership type (D=Direct, I=Indirect)
        ownership = txn_elem.find(".//ownershipNature/directOrIndirectOwnership/value")
        if ownership is not None and ownership.text:
            transaction["ownership_type"] = ownership.text.strip()

        return transaction

    async def store_transactions(self, parsed_data: List[Dict]) -> int:
        """Store parsed Form 4 transactions in database.

        Args:
            parsed_data: List of parsed Form 4 filings

        Returns:
            Number of transactions stored
        """
        session = SessionLocal()
        count = 0

        try:
            for filing in parsed_data:
                filing_info = filing.get("filing_info", {})
                accession_number = filing_info.get("accession_number")

                if not accession_number:
                    continue

                # Check if already exists
                existing = session.query(SECForm4Transaction).filter_by(
                    accession_number=accession_number
                ).first()

                if existing:
                    continue

                # Create transaction records
                for txn in filing.get("transactions", []):
                    if txn.get("shares") and txn.get("transaction_code"):
                        record = SECForm4Transaction(
                            accession_number=accession_number,
                            cik=filing.get("insider_cik") or "unknown",
                            issuer_cik=filing.get("issuer_cik") or "unknown",
                            issuer_name=filing.get("issuer_name"),
                            ticker=filing.get("ticker"),
                            insider_cik=filing.get("insider_cik"),
                            insider_name=filing.get("insider_name"),
                            insider_title=filing.get("insider_title"),
                            is_director=filing.get("is_director", False),
                            is_officer=filing.get("is_officer", False),
                            is_ten_percent_owner=filing.get("is_ten_percent_owner", False),
                            transaction_type=txn.get("transaction_code"),
                            transaction_code=txn.get("transaction_code"),
                            shares=txn.get("shares"),
                            price_per_share=txn.get("price"),
                            total_value=(txn.get("shares") or 0) * (txn.get("price") or 0),
                            shares_owned_after=txn.get("shares_owned_after"),
                            ownership_type=txn.get("ownership_type"),
                            transaction_date=txn.get("transaction_date"),
                            filed_date=datetime.fromisoformat(
                                filing_info.get("filed_date", "").replace("Z", "+00:00")
                            ) if filing_info.get("filed_date") else None,
                        )
                        session.add(record)
                        count += 1

                        # Only store first transaction for this filing
                        # (accession_number is unique)
                        break

            session.commit()
            logger.info(f"Stored {count} Form 4 transactions")

        except Exception as e:
            session.rollback()
            logger.error(f"Failed to store transactions: {e}")
            raise
        finally:
            session.close()

        return count

    async def run_collection(self, limit: int = 40) -> int:
        """Run full collection cycle.

        Args:
            limit: Maximum filings to fetch

        Returns:
            Number of transactions stored
        """
        logger.info(f"Starting SEC EDGAR collection (limit={limit})")

        try:
            # Fetch and parse filings
            filings = await self.fetch_recent_form4s(limit=limit)

            # Store raw data
            if filings:
                await self.store_raw(filings)

            # Store parsed transactions
            count = await self.store_transactions(filings)

            logger.info(f"SEC EDGAR collection complete: {count} transactions")
            return count

        finally:
            await self.close()
