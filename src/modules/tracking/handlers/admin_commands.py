"""
Admin commands for tracking link management.
"""
from datetime import datetime, timedelta, UTC
from typing import Optional
from html import escape
import shlex

from aiogram import Router, F
from aiogram.filters import Command, CommandObject
from aiogram.types import Message, BufferedInputFile, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from src.modules.tracking.services.tracking_service import TrackingService
from src.modules.tracking.services.analytics_service import AnalyticsService
from src.modules.shared.services.anti_spam import AntiSpamGuard


def _get_command_args(command: CommandObject | None) -> str:
    """Extract command arguments."""
    if command is None or not command.args:
        return ""
    return command.args.strip()


def _parse_track_args(args: str) -> tuple[str, Optional[str]]:
    """
    Parse /track command arguments.
    
    Supports:
    - /track "Tag with spaces" slug
    - /track TagWithoutSpaces slug
    - /track "Tag only"
    - /track TagOnly
    
    Returns:
        Tuple of (tag, slug or None)
    """
    if not args:
        raise ValueError("Empty arguments")
    
    try:
        # Try to parse with shell-like quotes
        parts = shlex.split(args)
        if len(parts) == 1:
            return parts[0], None
        elif len(parts) == 2:
            return parts[0], parts[1]
        else:
            # If more than 2 parts, first is tag, last is slug, rest ignored
            return parts[0], parts[-1]
    except ValueError:
        # If shlex fails, fall back to simple split
        parts = args.split(maxsplit=1)
        if len(parts) == 1:
            return parts[0], None
        else:
            return parts[0], parts[1]


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
                "ℹ️ Использование: /track [tag] [slug]\n\n"
                "Создаёт новую трекинг-ссылку.\n"
                "- tag: обязательная метка для отчётов (можно в кавычках если есть пробелы)\n"
                "- slug: опциональный URL-идентификатор (auto-generated if omitted)\n\n"
                "Примеры:\n"
                "/track \"Рекламная кампания\" promo-2024\n"
                "/track Реклама\n"
                "/track \"Реклама в VK\""
            )
            return
        
        if not await guard.try_acquire(user.id):
            await message.answer("⏳ Не так быстро, подождите немного...")
            return
        
        try:
            tag, slug = _parse_track_args(args)
            
            link, url = await tracking_service.create_tracking_link(tag, slug)
            
            await message.answer(
                f"✅ Трекинг-ссылка создана!\n\n"
                f"🏷 Метка: {escape(link.tag)}\n"
                f"🔗 Slug: {escape(link.slug)}\n"
                f"🆔 ID: {link.link_id}\n\n"
                f"📎 Ссылка:\n{url}\n\n"
                f"Отправьте эту ссылку для отслеживания переходов.",
                parse_mode="HTML"
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
                    f"🆔 {link.link_id} | 🏷 {escape(link.tag)}\n"
                    f"   🔗 {escape(link.slug)}\n"
                    f"   📅 {link.created_at.strftime('%Y-%m-%d %H:%M UTC')}\n"
                )
            
            await message.answer("\n".join(lines), parse_mode="HTML")
        
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
                "ℹ️ Использование: /track_logs [link_id|slug] [start_date] [end_date]\n\n"
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
                await message.answer(f"📭 Нет событий для ссылки: {escape(link.tag)}", parse_mode="HTML")
                return
            
            period = ""
            if start_date or end_date:
                start_str = start_date.strftime('%Y-%m-%d') if start_date else '...'
            period = ""
            if start_date or end_date:
                start_str = start_date.strftime('%Y-%m-%d') if start_date else '...'
                end_str = end_date.strftime('%Y-%m-%d') if end_date else '...'
                period = f" ({start_str} — {end_str})"
            
            # Calculate statistics
            total_events = len(events)
            unique_users = len(set(e.tg_user_id for e in events))
            
            # Build header with summary
            lines = [
                f"📊 <b>Логи: {escape(link.tag)}</b>{period}\n",
                f"📈 Всего переходов: {total_events}",
                f"👥 Уникальных пользователей: {unique_users}\n",
                "━━━━━━━━━━━━━━━━━━━━━━\n"
            ]
            
            # Group events by date for better readability
            from collections import defaultdict
            events_by_date = defaultdict(list)
            for event in events[:100]:  # Increased limit to 100
                date_key = event.created_at.strftime('%Y-%m-%d')
                events_by_date[date_key].append(event)
            
            # Display events grouped by date
            for date_key in sorted(events_by_date.keys(), reverse=True)[:10]:  # Last 10 days
                day_events = events_by_date[date_key]
                lines.append(f"\n📅 <b>{date_key}</b> ({len(day_events)} событий)")
                
                for event in day_events[:20]:  # Max 20 per day
                    first_mark = "🆕" if event.first_start else "🔁"
                    time_str = event.created_at.strftime('%H:%M')
                    lines.append(
                        f"  {first_mark} {time_str} | User {event.tg_user_id}"
                    )
                
                if len(day_events) > 20:
                    lines.append(f"  ... еще {len(day_events) - 20} событий в этот день")
            
            if total_events > 100:
                lines.append(f"\n💡 Показано 100 из {total_events} событий")
            
            await message.answer("\n".join(lines), parse_mode="HTML")
        
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
                "ℹ️ Использование: /track_delete [link_id|slug]\n\n"
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
                    f"✅ Ссылка удалена: {escape(link.tag)}\n\n"
                    f"История событий сохранена.\n"
                    f"Slug '{escape(link.slug)}' можно переиспользовать.",
                    parse_mode="HTML"
                )
            else:
                await message.answer("❌ Не удалось удалить ссылку (возможно, уже удалена).")
        
        finally:
            await guard.release(user.id)
    
    @router.message(Command("track_status"))
    async def cmd_track_status(message: Message, command: CommandObject) -> None:
        """
        Get comprehensive status for tracking links.
        
        Without arguments: shows summary for all links
        With argument: shows detailed status for specific link with logs and chart button
        """
        user = message.from_user
        if not user or not is_admin(user.id):
            return
        
        args = _get_command_args(command)
        
        if not await guard.try_acquire(user.id):
            await message.answer("⏳ Не так быстро, подождите немного...")
            return
        
        try:
            if not args:
                # Show summary for all links
                links = await tracking_service.list_links(include_deleted=False)
                
                if not links:
                    await message.answer("📭 Нет активных трекинг-ссылок.")
                    return
                
                # Get stats for all links
                all_stats = []
                for link in links:
                    events = await analytics_service.get_link_events(link_id=link.link_id)
                    unique_users = len(set(e.tg_user_id for e in events))
                    
                    all_stats.append({
                        'link': link,
                        'total': len(events),
                        'unique': unique_users
                    })
                
                # Sort by total events
                all_stats.sort(key=lambda x: x['total'], reverse=True)
                
                lines = ["📊 <b>Сводка по всем трекинг-ссылкам</b>\n"]
                
                for stat in all_stats:
                    link = stat['link']
                    lines.append(
                        f"🔗 <b>{escape(link.tag)}</b> (#{link.link_id})\n"
                        f"   Slug: {escape(link.slug)}\n"
                        f"   📈 Всего: {stat['total']} | "
                        f"👥 Уникальных: {stat['unique']}\n"
                    )
                
                lines.append(
                    f"\n💡 Для детального просмотра используйте:\n"
                    f"/track_status [slug или ID]"
                )
                
                # Add button for general chart
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="📊 Показать график", callback_data="chart:all")]
                ])
                
                await message.answer("\n".join(lines), parse_mode="HTML", reply_markup=keyboard)
                
            else:
                # Show detailed status for specific link
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
                    await message.answer(f"📭 Нет событий для ссылки: {escape(link.tag)}", parse_mode="HTML")
                    return
                
                period = ""
                if start_date or end_date:
                    start_str = start_date.strftime('%Y-%m-%d') if start_date else '...'
                    end_str = end_date.strftime('%Y-%m-%d') if end_date else '...'
                    period = f" ({start_str} — {end_str})"
                
                # Calculate statistics
                total_events = len(events)
                unique_users = len(set(e.tg_user_id for e in events))
                
                # Generate tracking URL
                tracking_url = await tracking_service.generate_start_link(link.link_id)
                
                # Build header with summary
                lines = [
                    f"📊 <b>Статус: {escape(link.tag)}</b>{period}\n",
                    f"🆔 ID: {link.link_id} | Slug: {escape(link.slug)}",
                    f"� Ссылка: <code>{tracking_url}</code>",
                    f"📈 Всего переходов: {total_events}",
                    f"� Уникальных пользователей: {unique_users}\n",
                    "━━━━━━━━━━━━━━━━━━━━━━\n"
                ]
                
                # Group events by date for better readability
                from collections import defaultdict
                events_by_date = defaultdict(list)
                for event in events[:100]:
                    date_key = event.created_at.strftime('%Y-%m-%d')
                    events_by_date[date_key].append(event)
                
                # Display events grouped by date
                for date_key in sorted(events_by_date.keys(), reverse=True)[:7]:  # Last 7 days
                    day_events = events_by_date[date_key]
                    lines.append(f"\n📅 <b>{date_key}</b> ({len(day_events)} событий)")
                    
                    for event in day_events[:15]:  # Max 15 per day
                        time_str = event.created_at.strftime('%H:%M')
                        lines.append(
                            f"  • {time_str} | User {event.tg_user_id}"
                        )
                    
                    if len(day_events) > 15:
                        lines.append(f"  ... еще {len(day_events) - 15} событий")
                
                if total_events > 100:
                    lines.append(f"\n💡 Показано 100 из {total_events} событий")
                
                # Add button for chart
                callback_data = f"chart:{link.link_id}"
                if start_date:
                    callback_data += f":{start_date.strftime('%Y-%m-%d')}"
                if end_date:
                    callback_data += f":{end_date.strftime('%Y-%m-%d')}"
                
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="📊 Показать график", callback_data=callback_data)]
                ])
                
                await message.answer("\n".join(lines), parse_mode="HTML", reply_markup=keyboard)
        
        except ValueError as e:
            await message.answer(f"❌ Ошибка: {e}")
        
        finally:
            await guard.release(user.id)
    
    @router.callback_query(F.data.startswith("chart:"))
    async def callback_generate_chart(callback: CallbackQuery) -> None:
        """Generate and send chart based on callback data."""
        if not callback.from_user or not is_admin(callback.from_user.id):
            await callback.answer("❌ Нет доступа")
            return
        
        await callback.answer("⏳ Генерирую график...")
        
        try:
            # Parse callback data: "chart:link_id" or "chart:all" or "chart:link_id:start_date:end_date"
            parts = callback.data.split(":")
            
            if parts[1] == "all":
                # General chart for all active links
                links = await tracking_service.list_links(include_deleted=False)
                if not links:
                    await callback.message.answer("❌ Нет активных ссылок.")
                    return
                
                link_ids = [link.link_id for link in links]
                
                # Generate chart with all links
                chart_buffer = await analytics_service.generate_chart(
                    link_ids=link_ids,
                    start_date=None,  # Last 30 days by default
                    end_date=None,
                    metrics=['total', 'unique'],
                    title="Общая статистика: все ссылки"
                )
                
                chart_file = BufferedInputFile(
                    chart_buffer.read(),
                    filename="chart_all_links.png"
                )
                
                await callback.message.answer_photo(
                    chart_file,
                    caption="📊 Общий график для всех активных ссылок",
                    parse_mode="HTML"
                )
            else:
                # Single link chart
                link_id = int(parts[1])
                start_date = _parse_date(parts[2]) if len(parts) > 2 else None
                end_date = _parse_date(parts[3]) if len(parts) > 3 else None
                
                link = await tracking_service.get_link_by_id(link_id)
                if not link:
                    await callback.message.answer("❌ Ссылка не найдена.")
                    return
                
                # Generate chart
                chart_buffer = await analytics_service.generate_chart(
                    link_ids=[link_id],
                    start_date=start_date,
                    end_date=end_date,
                    metrics=['total', 'unique'],
                    title=f"Статистика: {link.tag}"
                )
                
                chart_file = BufferedInputFile(
                    chart_buffer.read(),
                    filename=f"chart_{link.slug}.png"
                )
                
                await callback.message.answer_photo(
                    chart_file,
                    caption=f"📊 График для: {escape(link.tag)}",
                    parse_mode="HTML"
                )
            
        except Exception as e:
            await callback.message.answer(f"❌ Ошибка при генерации графика: {e}")
    
    return router
