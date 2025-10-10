"""
Analytics service for aggregating stats and generating charts.
"""
from datetime import datetime, timedelta, UTC
from io import BytesIO
from typing import List, Optional, Literal

import matplotlib
matplotlib.use('Agg')  # Non-interactive backend for server use
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

from src.modules.tracking.domain.interfaces import TrackingRepository
from src.modules.tracking.domain.models import LinkStats, TrackingEvent


MetricType = Literal['total', 'unique', 'first_start']

# Default date range: last 30 days
DEFAULT_DAYS = 30


class AnalyticsService:
    """Service for analytics and reporting."""
    
    def __init__(self, repository: TrackingRepository):
        self._repository = repository
    
    async def get_link_events(
        self,
        link_id: int,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[TrackingEvent]:
        """
        Get all events for a link with date filtering.
        
        Args:
            link_id: Link identifier
            start_date: Start date (inclusive, UTC), defaults to 30 days ago
            end_date: End date (inclusive, UTC), defaults to today
        
        Returns:
            List of tracking events
        """
        if start_date is None:
            start_date = datetime.now(UTC) - timedelta(days=DEFAULT_DAYS)
        
        if end_date is None:
            end_date = datetime.now(UTC)
        
        return await self._repository.get_events_for_link(
            link_id=link_id,
            start_date=start_date,
            end_date=end_date
        )
    
    async def get_aggregated_stats(
        self,
        link_ids: Optional[List[int]] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        daily: bool = True
    ) -> List[LinkStats]:
        """
        Get aggregated statistics.
        
        Args:
            link_ids: Filter by specific links (None for all active links)
            start_date: Start date (inclusive, UTC), defaults to 30 days ago
            end_date: End date (inclusive, UTC), defaults to today
            daily: Whether to aggregate by day (True) or all-time (False)
        
        Returns:
            List of aggregated statistics
        """
        if start_date is None:
            start_date = datetime.now(UTC) - timedelta(days=DEFAULT_DAYS)
        
        if end_date is None:
            end_date = datetime.now(UTC)
        
        return await self._repository.get_aggregated_stats(
            link_ids=link_ids,
            start_date=start_date,
            end_date=end_date,
            daily=daily
        )
    
    async def generate_chart(
        self,
        link_ids: Optional[List[int]] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        metrics: List[MetricType] = None,
        title: Optional[str] = None
    ) -> BytesIO:
        """
        Generate PNG chart for tracking metrics.
        
        Args:
            link_ids: Filter by specific links (None for all active links)
            start_date: Start date (inclusive, UTC), defaults to 30 days ago
            end_date: End date (inclusive, UTC), defaults to today
            metrics: List of metrics to plot ('total', 'unique', 'first_start')
                    Defaults to ['total', 'unique']
            title: Custom chart title
        
        Returns:
            BytesIO buffer containing PNG image
        """
        if metrics is None:
            metrics = ['total', 'unique']
        
        if start_date is None:
            start_date = datetime.now(UTC) - timedelta(days=DEFAULT_DAYS)
        
        if end_date is None:
            end_date = datetime.now(UTC)
        
        stats = await self.get_aggregated_stats(
            link_ids=link_ids,
            start_date=start_date,
            end_date=end_date,
            daily=True
        )
        
        if not title:
            if link_ids and len(link_ids) == 1:
                link = await self._repository.get_link_by_id(link_ids[0])
                title = f"Analytics: {link.tag if link else 'Unknown'}"
            elif link_ids:
                title = f"Analytics: {len(link_ids)} links"
            else:
                title = "Analytics: All Links"
        
        return self._create_time_series_chart(
            stats=stats,
            metrics=metrics,
            title=title,
            start_date=start_date,
            end_date=end_date
        )
    
    def _create_time_series_chart(
        self,
        stats: List[LinkStats],
        metrics: List[MetricType],
        title: str,
        start_date: datetime,
        end_date: datetime
    ) -> BytesIO:
        """
        Create time series chart from stats.
        
        Args:
            stats: List of daily link statistics
            metrics: Metrics to plot
            title: Chart title
            start_date: Start date for X-axis
            end_date: End date for X-axis
        
        Returns:
            BytesIO buffer with PNG image
        """
        date_aggregates = {}
        for stat in stats:
            if stat.date is None:
                continue
            
            date_key = stat.date.date()
            if date_key not in date_aggregates:
                date_aggregates[date_key] = {
                    'total': 0,
                    'unique': 0,
                    'first_start': 0
                }
            
            date_aggregates[date_key]['total'] += stat.total_events
            date_aggregates[date_key]['unique'] += stat.unique_users
            date_aggregates[date_key]['first_start'] += stat.first_starts
        
        current_date = start_date.date()
        end_date_only = end_date.date()
        
        dates = []
        total_values = []
        unique_values = []
        first_start_values = []
        
        while current_date <= end_date_only:
            dates.append(current_date)
            
            if current_date in date_aggregates:
                agg = date_aggregates[current_date]
                total_values.append(agg['total'])
                unique_values.append(agg['unique'])
                first_start_values.append(agg['first_start'])
            else:
                total_values.append(0)
                unique_values.append(0)
                first_start_values.append(0)
            
            current_date += timedelta(days=1)
        
        fig, ax = plt.subplots(figsize=(12, 6))
        
        metric_configs = {
            'total': ('Total Events', total_values, 'blue'),
            'unique': ('Unique Users', unique_values, 'green'),
            'first_start': ('First Starts', first_start_values, 'orange')
        }
        
        for metric in metrics:
            if metric in metric_configs:
                label, values, color = metric_configs[metric]
                ax.plot(dates, values, marker='o', label=label, color=color, linewidth=2)
        
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d'))
        ax.xaxis.set_major_locator(mdates.DayLocator(interval=max(1, len(dates) // 10)))
        plt.xticks(rotation=45, ha='right')
        
        ax.set_xlabel('Date')
        ax.set_ylabel('Count')
        ax.set_title(title, fontsize=14, fontweight='bold')
        ax.legend()
        ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        
        buffer = BytesIO()
        plt.savefig(buffer, format='png', dpi=150, bbox_inches='tight')
        buffer.seek(0)
        plt.close(fig)
        
        return buffer
    
    def format_stats_text(
        self,
        stats: List[LinkStats],
        include_daily: bool = False
    ) -> str:
        """
        Format statistics as human-readable text.
        
        Args:
            stats: List of statistics
            include_daily: Whether to include daily breakdown
        
        Returns:
            Formatted text string
        """
        if not stats:
            return "No data available for the specified period."
        
        if include_daily:
            lines = ["📊 Daily Statistics:\n"]
            
            by_link = {}
            for stat in stats:
                if stat.link_id not in by_link:
                    by_link[stat.link_id] = {
                        'tag': stat.tag,
                        'slug': stat.slug,
                        'daily': []
                    }
                by_link[stat.link_id]['daily'].append(stat)
            
            for link_id, data in by_link.items():
                lines.append(f"\n🔗 {data['tag']} ({data['slug']})")
                
                for stat in sorted(data['daily'], key=lambda s: s.date or datetime.min):
                    date_str = stat.date.strftime('%Y-%m-%d') if stat.date else 'Total'
                    lines.append(
                        f"  {date_str}: "
                        f"{stat.total_events} events, "
                        f"{stat.unique_users} unique, "
                        f"{stat.first_starts} first starts"
                    )
        else:
            lines = ["📊 Summary Statistics:\n"]
            
            for stat in stats:
                lines.append(
                    f"🔗 {stat.tag} ({stat.slug}):\n"
                    f"  Total events: {stat.total_events}\n"
                    f"  Unique users: {stat.unique_users}\n"
                    f"  First starts: {stat.first_starts}\n"
                )
        
        return "\n".join(lines)
