"""
Admin commands for tracking link management.
"""
from datetime import datetime, timedelta, UTC
from typing import Optional

from aiogram import Router, F
from aiogram.filters import Command, CommandObject
from aiogram.types import Message, BufferedInputFile

from src.modules.tracking.services.tracking_service import TrackingService
from src.modules.tracking.services.analytics_service import AnalyticsService
from src.modules.shared.services.anti_spam import AntiSpamGuard


def _get_command_args(command: CommandObject | None) -> str:
    """Extract command arguments."""
    if command is None or not command.args:
        return ""
    return command.args.strip()


def _parse_date(date_str: str) -> Optional[datetime]:
    """
    Parse date string in YYYY-MM-DD format.
    
    Returns:
        Datetime in UTC timezone or None if invalid
    """
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        return dt.replace(tzinfo=UTC)
    except ValueError:
        return None


def create_tracking_admin_router(
    tracking_service: TrackingService,
    analytics_service: AnalyticsService,
    guard: AntiSpamGuard,
    admin_user_ids: frozenset[int]
) -> Router:
    """
    Create router for tracking admin commands.
    
    Commands:
    - /track <tag> [slug] - Create new tracking link
    - /track_list - List all active links
    - /track_logs <link_id or slug> [start_date] [end_date] - Get event logs
    - /track_stats [link_id or slug] [start_date] [end_date] - Get statistics with chart
    - /track_delete <link_id or slug> - Soft delete a link
    
    Args:
        tracking_service: Tracking service instance
        analytics_service: Analytics service instance
        guard: Anti-spam guard
        admin_user_ids: Set of admin user IDs who can use these commands
    """
    router = Router(name="tracking_admin")
    
    def is_admin(user_id: int) -> bool:
        """Check if user is admin."""
        if not admin_user_ids:
            return False
        return user_id in admin_user_ids
    
    @router.message(Command("track"))
    async def cmd_track_create(message: Message, command: CommandObject) -> None:
        """Create a new tracking link."""
        user = message.from_user
        if not user or not is_admin(user.id):
            return
        
        args = _get_command_args(command)
        if not args:
            await message.answer(
                "ℹ️ Использование: /track <tag> [slug]\n\n"
                "Создаёт новую трекинг-ссылку.\n"
                "- tag: обязательная метка для отчётов\n"
                "- slug: опциональный URL-идентификатор (auto-generated if omitted)\n\n"
                "Пример: /track \"Рекламная кампания\" promo-2024"
            )
            return
        
        if not await guard.try_acquire(user.id):
            await message.answer("⏳ Не так быстро, подождите немного...")
            return
        
        try:
            parts = args.split(maxsplit=1)
            tag = parts[0]
            slug = parts[1] if len(parts) > 1 else None
            
            link, url = await tracking_service.create_tracking_link(tag, slug)
            
            await message.answer(
                f"✅ Трекинг-ссылка создана!\n\n"
                f"🏷 Метка: {link.tag}\n"
                f"🔗 Slug: {link.slug}\n"
                f"🆔 ID: {link.link_id}\n\n"
                f"📎 Ссылка:\n{url}\n\n"
                f"Отправьте эту ссылку для отслеживания переходов."
            )
        
        except ValueError as e:
            await message.answer(f"❌ Ошибка: {e}")
        
        finally:
            await guard.release(user.id)
    
    @router.message(Command("track_list"))
    async def cmd_track_list(message: Message) -> None:
        """List all active tracking links."""
        user = message.from_user
        if not user or not is_admin(user.id):
            return
        
        if not await guard.try_acquire(user.id):
            await message.answer("⏳ Не так быстро, подождите немного...")
            return
        
        try:
            links = await tracking_service.list_links(include_deleted=False)
            
            if not links:
                await message.answer("📭 Нет активных трекинг-ссылок.")
                return
            
            lines = ["📋 Активные трекинг-ссылки:\n"]
            for link in links:
                lines.append(
                    f"🆔 {link.link_id} | 🏷 {link.tag}\n"
                    f"   🔗 {link.slug}\n"
                    f"   📅 {link.created_at.strftime('%Y-%m-%d %H:%M UTC')}\n"
                )
            
            await message.answer("\n".join(lines))
        
        finally:
            await guard.release(user.id)
    
    @router.message(Command("track_logs"))
    async def cmd_track_logs(message: Message, command: CommandObject) -> None:
        """Get event logs for a link."""
        user = message.from_user
        if not user or not is_admin(user.id):
            return
        
        args = _get_command_args(command)
        if not args:
            await message.answer(
                "ℹ️ Использование: /track_logs <link_id|slug> [start_date] [end_date]\n\n"
                "Показывает логи событий для ссылки.\n"
                "Даты в формате YYYY-MM-DD (опционально).\n\n"
                "Пример: /track_logs 1 2024-01-01 2024-01-31"
            )
            return
        
        if not await guard.try_acquire(user.id):
            await message.answer("⏳ Не так быстро, подождите немного...")
            return
        
        try:
            parts = args.split()
            link_identifier = parts[0]
            start_date = _parse_date(parts[1]) if len(parts) > 1 else None
            end_date = _parse_date(parts[2]) if len(parts) > 2 else None
            
            if link_identifier.isdigit():
                link = await tracking_service.get_link_by_id(int(link_identifier))
            else:
                link = await tracking_service.get_link_by_slug(link_identifier)
            
            if not link:
                await message.answer("❌ Ссылка не найдена.")
                return
            
            events = await analytics_service.get_link_events(
                link_id=link.link_id,
                start_date=start_date,
                end_date=end_date
            )
            
            if not events:
                await message.answer(f"📭 Нет событий для ссылки: {link.tag}")
                return
            
            period = ""
            if start_date or end_date:
                start_str = start_date.strftime('%Y-%m-%d') if start_date else '...'
                end_str = end_date.strftime('%Y-%m-%d') if end_date else '...'
                period = f" ({start_str} — {end_str})"
            
            lines = [f"📊 События для: {link.tag}{period}\n"]
            
            for event in events[:50]:
                first_mark = "🆕" if event.first_start else "🔁"
                lines.append(
                    f"{first_mark} {event.event_type} | "
                    f"User {event.tg_user_id} | "
                    f"{event.created_at.strftime('%m-%d %H:%M UTC')}"
                )
            
            if len(events) > 50:
                lines.append(f"\n... и еще {len(events) - 50} событий")
            
            await message.answer("\n".join(lines))
        
        except ValueError as e:
            await message.answer(f"❌ Ошибка: {e}")
        
        finally:
            await guard.release(user.id)
    
    @router.message(Command("track_stats"))
    async def cmd_track_stats(message: Message, command: CommandObject) -> None:
        """Get statistics and chart for link(s)."""
        user = message.from_user
        if not user or not is_admin(user.id):
            return
        
        args = _get_command_args(command)
        
        if not await guard.try_acquire(user.id):
            await message.answer("⏳ Не так быстро, подождите немного...")
            return
        
        try:
            link_ids = None
            start_date = None
            end_date = None
            
            if args:
                parts = args.split()
                
                if parts and not parts[0].replace('-', '').isdigit():
                    
                    if parts[0].isdigit():
                        link = await tracking_service.get_link_by_id(int(parts[0]))
            
            stats = await analytics_service.get_aggregated_stats(
                link_ids=link_ids,
                start_date=start_date,
                end_date=end_date,
                daily=False
            )
            
            if not stats:
                await message.answer("📭 Нет данных за указанный период.")
                return
            
            text = analytics_service.format_stats_text(stats, include_daily=False)
            
            chart_buffer = await analytics_service.generate_chart(
                link_ids=link_ids,
                start_date=start_date,
                end_date=end_date,
                metrics=['total', 'unique', 'first_start']
            )
            
            await message.answer(text)
            
            chart_file = BufferedInputFile(
                chart_buffer.read(),
                filename="tracking_stats.png"
            )
            await message.answer_photo(chart_file)
        
        except Exception as e:
            await message.answer(f"❌ Ошибка: {e}")
        
        finally:
            await guard.release(user.id)
    
    @router.message(Command("track_delete"))
    async def cmd_track_delete(message: Message, command: CommandObject) -> None:
        """Soft delete a tracking link."""
        user = message.from_user
        if not user or not is_admin(user.id):
            return
        
        args = _get_command_args(command)
        if not args:
            await message.answer(
                "ℹ️ Использование: /track_delete <link_id|slug>\n\n"
                "Удаляет трекинг-ссылку (soft delete).\n"
                "История событий сохраняется, slug можно переиспользовать.\n\n"
                "Пример: /track_delete 1"
            )
            return
        
        if not await guard.try_acquire(user.id):
            await message.answer("⏳ Не так быстро, подождите немного...")
            return
        
        try:
            link_identifier = args.split()[0]
            
            if link_identifier.isdigit():
                link = await tracking_service.get_link_by_id(int(link_identifier))
            else:
                link = await tracking_service.get_link_by_slug(link_identifier)
            
            if not link:
                await message.answer("❌ Ссылка не найдена.")
                return
            
            deleted = await tracking_service.delete_link(link.link_id)
            
            if deleted:
                await message.answer(
                    f"✅ Ссылка удалена: {link.tag}\n\n"
                    f"История событий сохранена.\n"
                    f"Slug '{link.slug}' можно переиспользовать."
                )
            else:
                await message.answer("❌ Не удалось удалить ссылку (возможно, уже удалена).")
        
        finally:
            await guard.release(user.id)
    
    return router
