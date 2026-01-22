"""Tests for USPTO Patent collector and factors."""

import pytest
from datetime import datetime, date, timedelta
from unittest.mock import AsyncMock, patch, MagicMock


class TestPatentModels:
    """Tests for patent database models."""

    def test_patent_model_creation(self):
        """Test Patent model can be instantiated."""
        from src.models.patents import Patent

        patent = Patent(
            patent_number="US12345678",
            title="Method for machine learning optimization",
            patent_type="utility",
            filing_date=date(2022, 1, 15),
            grant_date=date(2024, 6, 20),
            primary_class="G06N",
            claims_count=25,
            status="granted",
        )

        assert patent.patent_number == "US12345678"
        assert patent.claims_count == 25
        assert patent.primary_class == "G06N"

    def test_patent_assignee_model_creation(self):
        """Test PatentAssignee model can be instantiated."""
        from src.models.patents import PatentAssignee

        assignee = PatentAssignee(
            patent_number="US12345678",
            assignee_name="Tech Corp Inc.",
            assignee_type="corporation",
            city="San Francisco",
            state="CA",
            country="US",
            entity_id="TECH",
            is_original_assignee=True,
        )

        assert assignee.assignee_name == "Tech Corp Inc."
        assert assignee.entity_id == "TECH"

    def test_patent_inventor_model_creation(self):
        """Test PatentInventor model can be instantiated."""
        from src.models.patents import PatentInventor

        inventor = PatentInventor(
            patent_number="US12345678",
            inventor_name="John Smith",
            city="Palo Alto",
            state="CA",
            country="US",
            sequence_number=1,
        )

        assert inventor.inventor_name == "John Smith"
        assert inventor.sequence_number == 1

    def test_patent_citation_model_creation(self):
        """Test PatentCitation model can be instantiated."""
        from src.models.patents import PatentCitation

        citation = PatentCitation(
            citing_patent="US12345678",
            cited_patent="US11111111",
            citation_type="patent",
            is_examiner_citation=False,
        )

        assert citation.citing_patent == "US12345678"
        assert citation.cited_patent == "US11111111"

    def test_patent_application_model_creation(self):
        """Test PatentApplication model can be instantiated."""
        from src.models.patents import PatentApplication

        app = PatentApplication(
            application_number="17/123456",
            title="Novel AI System",
            filing_date=date(2023, 1, 1),
            status="pending",
            entity_id="AITECH",
        )

        assert app.application_number == "17/123456"
        assert app.status == "pending"


class TestUSPTOCollector:
    """Tests for USPTO collector."""

    @pytest.fixture
    def collector(self):
        from src.collectors.uspto import USPTOCollector
        return USPTOCollector()

    @pytest.fixture
    def sample_api_response(self):
        return {
            "patents": [
                {
                    "patent_number": "US12345678",
                    "patent_title": "Machine Learning Method",
                    "patent_abstract": "A method for ML optimization",
                    "patent_date": "2024-06-20",
                    "app_date": "2022-01-15",
                    "patent_type": "utility",
                    "patent_num_claims": 25,
                    "assignees": [
                        {
                            "assignee_organization": "Tech Corp Inc.",
                            "assignee_city": "San Francisco",
                            "assignee_state": "CA",
                            "assignee_country": "US",
                        }
                    ],
                    "inventors": [
                        {
                            "inventor_first_name": "John",
                            "inventor_last_name": "Smith",
                            "inventor_city": "Palo Alto",
                            "inventor_state": "CA",
                            "inventor_country": "US",
                        }
                    ],
                    "cpcs": [
                        {"cpc_section_id": "G", "cpc_subsection_id": "G06N"}
                    ],
                }
            ],
            "count": 1,
            "total_patent_count": 1,
        }

    def test_collector_source_name(self, collector):
        """Test collector source name."""
        assert collector.SOURCE_NAME == "uspto"

    def test_parse_patents(self, collector, sample_api_response):
        """Test parsing USPTO API response."""
        parsed = collector.parse(sample_api_response)

        assert len(parsed) == 1
        patent = parsed[0]
        assert patent["patent_number"] == "US12345678"
        assert patent["title"] == "Machine Learning Method"
        assert patent["claims_count"] == 25
        assert patent["assignee_name"] == "Tech Corp Inc."
        assert patent["primary_class"] == "G06N"
        assert len(patent["inventors"]) == 1
        assert "John Smith" in patent["inventors"][0]["name"]

    def test_parse_date(self, collector):
        """Test date parsing."""
        assert collector._parse_date("2024-06-20") == date(2024, 6, 20)
        assert collector._parse_date(None) is None
        assert collector._parse_date("invalid") is None

    def test_normalize_company_name(self, collector):
        """Test company name normalization."""
        assert collector.normalize_company_name("Apple Inc.") == "APPLE"
        assert collector.normalize_company_name("Microsoft Corporation") == "MICROSOFT"
        assert collector.normalize_company_name("Google LLC") == "GOOGLE"
        assert collector.normalize_company_name("Amazon.com, Inc.") == "AMAZON.COM"
        assert collector.normalize_company_name("") == ""

    def test_normalize_company_name_preserves_important_parts(self, collector):
        """Test normalization preserves important parts."""
        result = collector.normalize_company_name("International Business Machines Corporation")
        assert "INTERNATIONAL BUSINESS MACHINES" in result

    @pytest.mark.asyncio
    async def test_collector_context_manager(self, collector):
        """Test async context manager."""
        async with collector:
            assert collector is not None
            assert collector.SOURCE_NAME == "uspto"


class TestPatentFactors:
    """Tests for patent-derived factors."""

    def test_factor_registry_has_patent_factors(self):
        """Test that patent factors are registered."""
        from src.transformations.base import FactorRegistry
        # Import to trigger registration
        from src.transformations.factors import patent_factors

        factors = FactorRegistry.get_all()

        assert "patent_momentum" in factors
        assert "innovation_velocity" in factors
        assert "patent_quality_score" in factors
        assert "technology_diversity" in factors
        assert "time_to_grant" in factors

    def test_patent_momentum_factor_definition(self):
        """Test patent momentum factor definition."""
        from src.transformations.factors.patent_factors import PatentMomentum

        factor = PatentMomentum()
        definition = factor.get_definition()

        assert definition["id"] == "patent_momentum"
        assert definition["category"] == "patents"
        assert definition["entity_type"] == "company"
        assert definition["frequency"] == "monthly"

    def test_innovation_velocity_factor_definition(self):
        """Test innovation velocity factor definition."""
        from src.transformations.factors.patent_factors import InnovationVelocity

        factor = InnovationVelocity()
        definition = factor.get_definition()

        assert definition["id"] == "innovation_velocity"
        assert definition["category"] == "patents"
        assert definition["frequency"] == "monthly"

    def test_patent_quality_score_factor_definition(self):
        """Test patent quality score factor definition."""
        from src.transformations.factors.patent_factors import PatentQualityScore

        factor = PatentQualityScore()
        definition = factor.get_definition()

        assert definition["id"] == "patent_quality_score"
        assert definition["category"] == "patents"

    def test_technology_diversity_factor_definition(self):
        """Test technology diversity factor definition."""
        from src.transformations.factors.patent_factors import TechnologyDiversity

        factor = TechnologyDiversity()
        definition = factor.get_definition()

        assert definition["id"] == "technology_diversity"
        assert definition["category"] == "patents"


class TestPatentDatabaseIntegration:
    """Integration tests for patents with database."""

    def test_store_patent(self):
        """Test storing patent in database."""
        from src.models.database import SessionLocal
        from src.models.patents import Patent

        session = SessionLocal()
        try:
            # Clean up
            session.query(Patent).filter_by(patent_number="TEST12345").delete()
            session.commit()

            # Insert
            patent = Patent(
                patent_number="TEST12345",
                title="Test Patent",
                patent_type="utility",
                grant_date=date.today(),
                claims_count=10,
                primary_class="G06F",
                status="granted",
            )
            session.add(patent)
            session.commit()

            # Query
            result = session.query(Patent).filter_by(patent_number="TEST12345").first()
            assert result is not None
            assert result.title == "Test Patent"
            assert result.claims_count == 10

            # Cleanup
            session.delete(result)
            session.commit()

        finally:
            session.close()

    def test_store_patent_with_assignee(self):
        """Test storing patent with assignee."""
        from src.models.database import SessionLocal
        from src.models.patents import Patent, PatentAssignee

        session = SessionLocal()
        try:
            # Clean up
            session.query(PatentAssignee).filter_by(patent_number="TEST67890").delete()
            session.query(Patent).filter_by(patent_number="TEST67890").delete()
            session.commit()

            # Insert patent
            patent = Patent(
                patent_number="TEST67890",
                title="Test Patent with Assignee",
                grant_date=date.today(),
                status="granted",
            )
            session.add(patent)

            # Insert assignee
            assignee = PatentAssignee(
                patent_number="TEST67890",
                assignee_name="Test Company",
                entity_id="TESTCO",
                is_original_assignee=True,
            )
            session.add(assignee)
            session.commit()

            # Query
            result = session.query(PatentAssignee).filter_by(
                patent_number="TEST67890"
            ).first()
            assert result is not None
            assert result.entity_id == "TESTCO"

            # Cleanup
            session.query(PatentAssignee).filter_by(patent_number="TEST67890").delete()
            session.query(Patent).filter_by(patent_number="TEST67890").delete()
            session.commit()

        finally:
            session.close()

    def test_calc_innovation_velocity_with_data(self):
        """Test innovation velocity calculation with test data."""
        from src.models.database import SessionLocal
        from src.models.patents import Patent, PatentAssignee
        from src.transformations.factors.patent_factors import calc_innovation_velocity

        session = SessionLocal()
        try:
            # Clean up
            session.query(PatentAssignee).filter_by(entity_id="VELOCITY_TEST").delete()
            session.query(Patent).filter(
                Patent.patent_number.like("VELTEST%")
            ).delete()
            session.commit()

            today = date.today()

            # Insert 12 patents over last year (1 per month)
            for i in range(12):
                patent_num = f"VELTEST{i:04d}"
                patent = Patent(
                    patent_number=patent_num,
                    title=f"Test Patent {i}",
                    grant_date=today - timedelta(days=30 * i),
                    status="granted",
                )
                session.add(patent)

                assignee = PatentAssignee(
                    patent_number=patent_num,
                    assignee_name="Velocity Test Corp",
                    entity_id="VELOCITY_TEST",
                )
                session.add(assignee)

            session.commit()

            # Calculate velocity
            velocity = calc_innovation_velocity(
                "VELOCITY_TEST",
                today,
                lookback_days=365
            )

            assert velocity is not None
            # Should be approximately 1 patent per month
            assert pytest.approx(velocity, rel=0.1) == 1.0

            # Cleanup
            session.query(PatentAssignee).filter_by(entity_id="VELOCITY_TEST").delete()
            session.query(Patent).filter(
                Patent.patent_number.like("VELTEST%")
            ).delete()
            session.commit()

        finally:
            session.close()
