"""
Tests for chart generation.
"""
import pytest
import pytest_asyncio
from datetime import datetime, timedelta, UTC
from pathlib import Path

from src.modules.tracking.infrastructure.storage import SQLiteTrackingRepository
from src.modules.tracking.services.tracking_service import TrackingService
from src.modules.tracking.services.analytics_service import AnalyticsService


@pytest_asyncio.fixture
async def repository(tmp_path: Path):
    """Create a temporary repository for testing."""
    db_path = tmp_path / "test_tracking.db"
    repo = SQLiteTrackingRepository(db_path)
    await repo.initialize()
    return repo


@pytest_asyncio.fixture
async def tracking_service(repository):
    """Create tracking service with test repository."""
    return TrackingService(repository, bot_username="testbot")


@pytest_asyncio.fixture
async def analytics_service(repository):
    """Create analytics service with test repository."""
    return AnalyticsService(repository)


class TestChartGeneration:
    """Test chart generation."""
    
    @pytest.mark.asyncio
    async def test_generate_chart_basic(self, tracking_service, analytics_service):
        """Test basic chart generation."""
        # Create link and log events
        link, url = await tracking_service.create_tracking_link("Test Campaign")
        payload = url.split("start=")[1]
        
        await tracking_service.handle_start(payload, tg_user_id=1)
        await tracking_service.handle_start(payload, tg_user_id=2)
        
        # Generate chart
        chart_buffer = await analytics_service.generate_chart(
            link_ids=[link.link_id],
            metrics=['total', 'unique']
        )
        
        # Verify it's a valid PNG
        chart_data = chart_buffer.read()
        assert len(chart_data) > 0
        assert chart_data.startswith(b'\x89PNG')  # PNG magic number
    
    @pytest.mark.asyncio
    async def test_generate_chart_all_metrics(self, tracking_service, analytics_service):
        """Test chart with all metrics."""
        # Create link and log events
        link, url = await tracking_service.create_tracking_link("Test")
        payload = url.split("start=")[1]
        
        await tracking_service.handle_start(payload, tg_user_id=1)
        await tracking_service.handle_start(payload, tg_user_id=1)  # Returning
        
        # Generate chart with all metrics
        chart_buffer = await analytics_service.generate_chart(
            link_ids=[link.link_id],
            metrics=['total', 'unique', 'first_start']
        )
        
        chart_data = chart_buffer.read()
        assert len(chart_data) > 0
        assert chart_data.startswith(b'\x89PNG')
    
    @pytest.mark.asyncio
    async def test_generate_chart_empty_data(self, analytics_service):
        """Test chart generation with no data."""
        # Generate chart for non-existent link
        chart_buffer = await analytics_service.generate_chart(
            link_ids=[99999],
            metrics=['total']
        )
        
        # Should still generate a chart (with zeros)
        chart_data = chart_buffer.read()
        assert len(chart_data) > 0
        assert chart_data.startswith(b'\x89PNG')
    
    @pytest.mark.asyncio
    async def test_generate_chart_multiple_links(self, tracking_service, analytics_service):
        """Test chart for multiple links."""
        # Create multiple links
        link1, url1 = await tracking_service.create_tracking_link("Campaign 1")
        link2, url2 = await tracking_service.create_tracking_link("Campaign 2")
        
        payload1 = url1.split("start=")[1]
        payload2 = url2.split("start=")[1]
        
        # Log events
        await tracking_service.handle_start(payload1, tg_user_id=1)
        await tracking_service.handle_start(payload2, tg_user_id=2)
        
        # Generate combined chart
        chart_buffer = await analytics_service.generate_chart(
            link_ids=[link1.link_id, link2.link_id],
            metrics=['total', 'unique']
        )
        
        chart_data = chart_buffer.read()
        assert len(chart_data) > 0
        assert chart_data.startswith(b'\x89PNG')
    
    @pytest.mark.asyncio
    async def test_generate_chart_custom_title(self, tracking_service, analytics_service):
        """Test chart with custom title."""
        link, url = await tracking_service.create_tracking_link("Test")
        payload = url.split("start=")[1]
        
        await tracking_service.handle_start(payload, tg_user_id=1)
        
        # Generate chart with custom title
        chart_buffer = await analytics_service.generate_chart(
            link_ids=[link.link_id],
            title="Custom Analytics Title",
            metrics=['total']
        )
        
        chart_data = chart_buffer.read()
        assert len(chart_data) > 0
    
    @pytest.mark.asyncio
    async def test_generate_chart_date_range(self, tracking_service, analytics_service):
        """Test chart with specific date range."""
        link, url = await tracking_service.create_tracking_link("Test")
        payload = url.split("start=")[1]
        
        await tracking_service.handle_start(payload, tg_user_id=1)
        
        # Generate chart for last 7 days
        end_date = datetime.now(UTC)
        start_date = end_date - timedelta(days=7)
        
        chart_buffer = await analytics_service.generate_chart(
            link_ids=[link.link_id],
            start_date=start_date,
            end_date=end_date,
            metrics=['total', 'unique']
        )
        
        chart_data = chart_buffer.read()
        assert len(chart_data) > 0
        assert chart_data.startswith(b'\x89PNG')
