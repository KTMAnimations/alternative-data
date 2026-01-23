"""Stage 3 Tests: SEC EDGAR collector verification."""

import pytest
from datetime import datetime


def test_parse_form4_xml(sample_form4_xml):
    """Test Form 4 XML parsing."""
    from src.collectors.sec_edgar import SECEdgarCollector

    collector = SECEdgarCollector(user_agent="Test test@test.com")
    result = collector.parse_form4_xml(sample_form4_xml)

    assert result["issuer_cik"] == "0001318605"
    assert result["ticker"] == "TSLA"
    assert result["issuer_name"] == "Tesla, Inc."
    assert result["insider_name"] == "Musk Elon"
    assert result["insider_title"] == "CEO"
    assert result["is_director"] is True
    assert result["is_officer"] is True
    assert len(result["transactions"]) == 1

    txn = result["transactions"][0]
    assert txn["shares"] == 10000
    assert txn["price"] == 250.00
    assert txn["transaction_code"] == "P"  # Purchase


def test_parse_form4_xml_sale():
    """Test Form 4 XML parsing for a sale transaction."""
    from src.collectors.sec_edgar import SECEdgarCollector

    sale_xml = '''<?xml version="1.0"?>
    <ownershipDocument>
        <issuer>
            <issuerCik>0000320193</issuerCik>
            <issuerName>Apple Inc.</issuerName>
            <issuerTradingSymbol>AAPL</issuerTradingSymbol>
        </issuer>
        <reportingOwner>
            <reportingOwnerId>
                <rptOwnerCik>0001214156</rptOwnerCik>
                <rptOwnerName>COOK TIMOTHY D</rptOwnerName>
            </reportingOwnerId>
            <reportingOwnerRelationship>
                <isDirector>0</isDirector>
                <isOfficer>1</isOfficer>
                <officerTitle>Chief Executive Officer</officerTitle>
            </reportingOwnerRelationship>
        </reportingOwner>
        <nonDerivativeTable>
            <nonDerivativeTransaction>
                <transactionDate>
                    <value>2024-01-15</value>
                </transactionDate>
                <transactionCoding>
                    <transactionCode>S</transactionCode>
                </transactionCoding>
                <transactionAmounts>
                    <transactionShares>
                        <value>50000</value>
                    </transactionShares>
                    <transactionPricePerShare>
                        <value>185.50</value>
                    </transactionPricePerShare>
                    <transactionAcquiredDisposedCode>
                        <value>D</value>
                    </transactionAcquiredDisposedCode>
                </transactionAmounts>
                <postTransactionAmounts>
                    <sharesOwnedFollowingTransaction>
                        <value>3000000</value>
                    </sharesOwnedFollowingTransaction>
                </postTransactionAmounts>
                <ownershipNature>
                    <directOrIndirectOwnership>
                        <value>D</value>
                    </directOrIndirectOwnership>
                </ownershipNature>
            </nonDerivativeTransaction>
        </nonDerivativeTable>
    </ownershipDocument>'''

    collector = SECEdgarCollector(user_agent="Test test@test.com")
    result = collector.parse_form4_xml(sale_xml)

    assert result["issuer_cik"] == "0000320193"
    assert result["ticker"] == "AAPL"
    assert result["insider_name"] == "COOK TIMOTHY D"
    assert len(result["transactions"]) == 1

    txn = result["transactions"][0]
    assert txn["shares"] == 50000
    assert txn["price"] == 185.50
    assert txn["transaction_code"] == "S"  # Sale
    assert txn["acquired_disposed"] == "D"  # Disposed
    assert txn["shares_owned_after"] == 3000000
    assert txn["ownership_type"] == "D"  # Direct


def test_parse_form4_multiple_transactions():
    """Test Form 4 with multiple transactions."""
    from src.collectors.sec_edgar import SECEdgarCollector

    multi_xml = '''<?xml version="1.0"?>
    <ownershipDocument>
        <issuer>
            <issuerCik>0000789019</issuerCik>
            <issuerName>Microsoft Corporation</issuerName>
            <issuerTradingSymbol>MSFT</issuerTradingSymbol>
        </issuer>
        <reportingOwner>
            <reportingOwnerId>
                <rptOwnerName>Test Insider</rptOwnerName>
            </reportingOwnerId>
        </reportingOwner>
        <nonDerivativeTable>
            <nonDerivativeTransaction>
                <transactionDate><value>2024-01-10</value></transactionDate>
                <transactionCoding><transactionCode>P</transactionCode></transactionCoding>
                <transactionAmounts>
                    <transactionShares><value>1000</value></transactionShares>
                    <transactionPricePerShare><value>380.00</value></transactionPricePerShare>
                </transactionAmounts>
            </nonDerivativeTransaction>
            <nonDerivativeTransaction>
                <transactionDate><value>2024-01-12</value></transactionDate>
                <transactionCoding><transactionCode>P</transactionCode></transactionCoding>
                <transactionAmounts>
                    <transactionShares><value>500</value></transactionShares>
                    <transactionPricePerShare><value>385.00</value></transactionPricePerShare>
                </transactionAmounts>
            </nonDerivativeTransaction>
        </nonDerivativeTable>
    </ownershipDocument>'''

    collector = SECEdgarCollector(user_agent="Test test@test.com")
    result = collector.parse_form4_xml(multi_xml)

    assert result["ticker"] == "MSFT"
    assert len(result["transactions"]) == 2

    assert result["transactions"][0]["shares"] == 1000
    assert result["transactions"][0]["price"] == 380.00
    assert result["transactions"][1]["shares"] == 500
    assert result["transactions"][1]["price"] == 385.00


def test_collector_user_agent():
    """Test that user agent is properly set."""
    from src.collectors.sec_edgar import SECEdgarCollector

    user_agent = "MyApp contact@example.com"
    collector = SECEdgarCollector(user_agent=user_agent)

    assert collector.user_agent == user_agent
    assert "User-Agent" in collector.headers
    assert collector.headers["User-Agent"] == user_agent


def test_collector_rate_limit():
    """Test that rate limit is configurable."""
    from src.collectors.sec_edgar import SECEdgarCollector

    collector = SECEdgarCollector(user_agent="Test test@test.com", rate_limit=5.0)

    assert collector.rate_limiter.min_interval == 0.2  # 1/5 seconds


def test_collector_source_name():
    """Test source name is correct."""
    from src.collectors.sec_edgar import SECEdgarCollector

    collector = SECEdgarCollector(user_agent="Test test@test.com")
    assert collector.SOURCE_NAME == "sec_edgar"


def test_parse_empty_xml():
    """Test handling of minimal/empty XML."""
    from src.collectors.sec_edgar import SECEdgarCollector

    minimal_xml = '''<?xml version="1.0"?>
    <ownershipDocument>
    </ownershipDocument>'''

    collector = SECEdgarCollector(user_agent="Test test@test.com")
    result = collector.parse_form4_xml(minimal_xml)

    assert result["issuer_cik"] is None
    assert result["ticker"] is None
    assert len(result["transactions"]) == 0


def test_parse_invalid_xml():
    """Test handling of invalid XML."""
    from src.collectors.sec_edgar import SECEdgarCollector
    from src.collectors.base import CollectorError

    invalid_xml = "not valid xml at all <<<"

    collector = SECEdgarCollector(user_agent="Test test@test.com")

    with pytest.raises(CollectorError):
        collector.parse_form4_xml(invalid_xml)


@pytest.mark.asyncio
async def test_collector_context_manager():
    """Test async context manager."""
    from src.collectors.sec_edgar import SECEdgarCollector

    async with SECEdgarCollector(user_agent="Test test@test.com") as collector:
        assert collector is not None
        assert collector.SOURCE_NAME == "sec_edgar"
