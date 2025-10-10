"""
Integration tests for tracking service.
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


class TestTrackingLinkCreation:
    """Test tracking link creation."""
    
    @pytest.mark.asyncio
    async def test_create_link_with_tag(self, tracking_service):
        """Test creating link with only tag."""
        link, url = await tracking_service.create_tracking_link("Test Campaign")
        
        assert link.tag == "Test Campaign"
        assert link.slug == "test-campaign"
        assert link.link_id > 0
        assert link.deleted_at is None
        assert url.startswith("https://t.me/testbot?start=")
    
    @pytest.mark.asyncio
    async def test_create_link_with_custom_slug(self, tracking_service):
        """Test creating link with custom slug."""
        link, url = await tracking_service.create_tracking_link("My Campaign", slug="promo-2024")
        
        assert link.tag == "My Campaign"
        assert link.slug == "promo-2024"
    
    @pytest.mark.asyncio
    async def test_create_link_slug_collision(self, tracking_service):
        """Test slug collision resolution."""
        # Create first link
        link1, _ = await tracking_service.create_tracking_link("Campaign 1", slug="test")
        assert link1.slug == "test"
        
        # Try to create with same slug - should resolve collision
        link2, _ = await tracking_service.create_tracking_link("Campaign 2", slug="test")
        assert link2.slug == "test-2"
    
    @pytest.mark.asyncio
    async def test_create_link_empty_tag(self, tracking_service):
        """Test that empty tag raises error."""
        with pytest.raises(ValueError, match="Tag is required"):
            await tracking_service.create_tracking_link("")
    
    @pytest.mark.asyncio
    async def test_create_link_invalid_slug(self, tracking_service):
        """Test that invalid slug raises error."""
        with pytest.raises(ValueError, match="Invalid slug"):
            await tracking_service.create_tracking_link("Campaign", slug="Invalid Slug!")


class TestTrackingEventLogging:
    """Test event logging."""
    
    @pytest.mark.asyncio
    async def test_handle_start_first_time(self, tracking_service):
        """Test handling first start."""
        # Create link
        link, url = await tracking_service.create_tracking_link("Test")
        payload = url.split("start=")[1]
        
        # Simulate user start
        result = await tracking_service.handle_start(payload, tg_user_id=12345)
        
        assert result is not None
        returned_link, is_first_start = result
        assert returned_link.link_id == link.link_id
        assert is_first_start is True
    
    @pytest.mark.asyncio
    async def test_handle_start_returning_user(self, tracking_service):
        """Test handling returning user."""
        # Create link
        link, url = await tracking_service.create_tracking_link("Test")
        payload = url.split("start=")[1]
        user_id = 12345
        
        # First start
        await tracking_service.handle_start(payload, tg_user_id=user_id)
        
        # Second start - should not be first
        result = await tracking_service.handle_start(payload, tg_user_id=user_id)
        assert result is not None
        _, is_first_start = result
        assert is_first_start is False
    
    @pytest.mark.asyncio
    async def test_handle_start_invalid_payload(self, tracking_service):
        """Test handling invalid payload."""
        result = await tracking_service.handle_start("invalid!!!", tg_user_id=12345)
        assert result is None
    
    @pytest.mark.asyncio
    async def test_handle_start_deleted_link(self, tracking_service):
        """Test handling start for deleted link."""
        # Create and delete link
        link, url = await tracking_service.create_tracking_link("Test")
        await tracking_service.delete_link(link.link_id)
        
        payload = url.split("start=")[1]
        
        # Try to start - should fail
        result = await tracking_service.handle_start(payload, tg_user_id=12345)
        assert result is None


class TestSoftDelete:
    """Test soft delete functionality."""
    
    @pytest.mark.asyncio
    async def test_delete_link(self, tracking_service):
        """Test soft deleting a link."""
        # Create link
        link, _ = await tracking_service.create_tracking_link("Test")
        
        # Delete
        deleted = await tracking_service.delete_link(link.link_id)
        assert deleted is True
        
        # Verify it's marked as deleted
        retrieved = await tracking_service.get_link_by_id(link.link_id)
        assert retrieved is None  # Not returned by default
    
    @pytest.mark.asyncio
    async def test_delete_link_twice(self, tracking_service):
        """Test that deleting twice fails."""
        # Create and delete link
        link, _ = await tracking_service.create_tracking_link("Test")
        await tracking_service.delete_link(link.link_id)
        
        # Try to delete again
        deleted = await tracking_service.delete_link(link.link_id)
        assert deleted is False
    
    @pytest.mark.asyncio
    async def test_slug_reuse_after_delete(self, tracking_service):
        """Test that slug can be reused after deletion."""
        # Create and delete link with slug
        link1, _ = await tracking_service.create_tracking_link("Campaign 1", slug="promo")
        await tracking_service.delete_link(link1.link_id)
        
        # Create new link with same slug
        link2, _ = await tracking_service.create_tracking_link("Campaign 2", slug="promo")
        assert link2.slug == "promo"
        assert link2.link_id != link1.link_id
    
    @pytest.mark.asyncio
    async def test_events_preserved_after_delete(self, tracking_service, repository):
        """Test that event history is preserved after deletion."""
        # Create link and log events
        link, url = await tracking_service.create_tracking_link("Test")
        payload = url.split("start=")[1]
        
        await tracking_service.handle_start(payload, tg_user_id=12345)
        await tracking_service.handle_start(payload, tg_user_id=67890)
        
        # Delete link
        await tracking_service.delete_link(link.link_id)
        
        # Events should still exist
        events = await repository.get_events_for_link(link.link_id)
        assert len(events) == 2


class TestAnalytics:
    """Test analytics and aggregations."""
    
    @pytest.mark.asyncio
    async def test_get_aggregated_stats(self, tracking_service, analytics_service, repository):
        """Test getting aggregated statistics."""
        # Create link and log events
        link, url = await tracking_service.create_tracking_link("Test")
        payload = url.split("start=")[1]
        
        await tracking_service.handle_start(payload, tg_user_id=1)
        await tracking_service.handle_start(payload, tg_user_id=2)
        await tracking_service.handle_start(payload, tg_user_id=1)  # Returning user
        
        # Get stats
        stats = await analytics_service.get_aggregated_stats(
            link_ids=[link.link_id],
            daily=False
        )
        
        assert len(stats) == 1
        stat = stats[0]
        assert stat.total_events == 3
        assert stat.unique_users == 2  # Two unique users
        assert stat.first_starts == 2  # Two first starts
    
    @pytest.mark.asyncio
    async def test_daily_aggregation(self, tracking_service, analytics_service, repository):
        """Test daily aggregation."""
        # Create link
        link, url = await tracking_service.create_tracking_link("Test")
        payload = url.split("start=")[1]
        
        # Log events
        await tracking_service.handle_start(payload, tg_user_id=1)
        
        # Get daily stats
        stats = await analytics_service.get_aggregated_stats(
            link_ids=[link.link_id],
            daily=True
        )
        
        assert len(stats) >= 1
        # Today should have at least one event
        today_stats = [s for s in stats if s.date and s.date.date() == datetime.now(UTC).date()]
        assert len(today_stats) == 1
        assert today_stats[0].total_events >= 1
    
    @pytest.mark.asyncio
    async def test_date_filtering(self, tracking_service, analytics_service):
        """Test date range filtering."""
        # Create link and log events
        link, url = await tracking_service.create_tracking_link("Test")
        payload = url.split("start=")[1]
        
        await tracking_service.handle_start(payload, tg_user_id=1)
        
        # Get stats for tomorrow (should be empty)
        tomorrow = datetime.now(UTC) + timedelta(days=1)
        stats = await analytics_service.get_aggregated_stats(
            link_ids=[link.link_id],
            start_date=tomorrow,
            end_date=tomorrow,
            daily=False
        )
        
        assert len(stats) == 0
    
    @pytest.mark.asyncio
    async def test_format_stats_text(self, analytics_service):
        """Test stats text formatting."""
        from src.modules.tracking.domain.models import LinkStats
        
        stats = [
            LinkStats(
                link_id=1,
                tag="Test Campaign",
                slug="test",
                date=None,
                total_events=100,
                unique_users=50,
                first_starts=30
            )
        ]
        
        text = analytics_service.format_stats_text(stats, include_daily=False)
        
        assert "Test Campaign" in text
        assert "100" in text
        assert "50" in text
        assert "30" in text


class TestMultipleLinkScenarios:
    """Test scenarios with multiple links."""
    
    @pytest.mark.asyncio
    async def test_multiple_links_different_users(self, tracking_service, analytics_service):
        """Test tracking multiple links with different users."""
        # Create two links
        link1, url1 = await tracking_service.create_tracking_link("Campaign A")
        link2, url2 = await tracking_service.create_tracking_link("Campaign B")
        
        payload1 = url1.split("start=")[1]
        payload2 = url2.split("start=")[1]
        
        # User 1 visits both links
        await tracking_service.handle_start(payload1, tg_user_id=1)
        await tracking_service.handle_start(payload2, tg_user_id=1)
        
        # User 2 visits only link 1
        await tracking_service.handle_start(payload1, tg_user_id=2)
        
        # Check stats for link 1
        stats1 = await analytics_service.get_aggregated_stats(
            link_ids=[link1.link_id],
            daily=False
        )
        assert stats1[0].total_events == 2
        assert stats1[0].unique_users == 2
        
        # Check stats for link 2
        stats2 = await analytics_service.get_aggregated_stats(
            link_ids=[link2.link_id],
            daily=False
        )
        assert stats2[0].total_events == 1
        assert stats2[0].unique_users == 1
