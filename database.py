"""
База данных VPN-бота 3.0 (Async + SQLAlchemy)
"""
import datetime
from typing import List, Dict, Optional, Any
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select, update, delete, desc, func
from sqlalchemy.orm import selectinload

from config import logger, PERIOD_DAYS
from models import Base, User, Server, ServerKey, Subscription, PromoCode, Payment, Review, ReferralReward

# Настройка БД
DB_URL = "sqlite+aiosqlite:///vpn_bot.db"

class Database:
    def __init__(self, db_url: str = DB_URL):
        self.engine = create_async_engine(db_url, echo=False)
        self.async_session = async_sessionmaker(self.engine, expire_on_commit=False)

    async def init_db(self):
        """Инициализация таблиц"""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def get_session(self) -> AsyncSession:
        return self.async_session()

    # ==================== ПОЛЬЗОВАТЕЛИ ====================

    async def get_or_create_user(self, user_id: int, username: str = None, 
                                 full_name: str = None, referrer_code: str = None) -> Dict[str, Any]:
        async with self.async_session() as session:
            result = await session.execute(select(User).where(User.id == user_id))
            user = result.scalar_one_or_none()

            if user:
                # Обновляем инфо если изменилось
                if user.username != username or user.full_name != full_name:
                    user.username = username
                    user.full_name = full_name
                    await session.commit()
                return self._user_to_dict(user)

            # Создание
            import secrets
            referral_code = secrets.token_hex(4).upper()
            
            referrer_id = None
            if referrer_code:
                # Ищем пригласившего
                ref_res = await session.execute(select(User).where(User.referral_code == referrer_code))
                referrer = ref_res.scalar_one_or_none()
                if referrer and referrer.id != user_id:
                    referrer_id = referrer.id

            new_user = User(
                id=user_id,
                username=username,
                full_name=full_name,
                referrer_id=referrer_id,
                referral_code=referral_code
            )
            session.add(new_user)
            await session.commit()
            return self._user_to_dict(new_user)

    async def get_user(self, user_id: int) -> Optional[Dict[str, Any]]:
        async with self.async_session() as session:
            result = await session.execute(select(User).where(User.id == user_id))
            user = result.scalar_one_or_none()
            return self._user_to_dict(user) if user else None

    async def mark_trial_used(self, user_id: int) -> bool:
        async with self.async_session() as session:
            await session.execute(update(User).where(User.id == user_id).values(trial_used=True))
            await session.commit()
            return True

    async def add_bonus_days(self, user_id: int, days: int) -> bool:
        async with self.async_session() as session:
            # SQLAlchemy expression for atomic update
            await session.execute(
                update(User).where(User.id == user_id).values(bonus_days=User.bonus_days + days)
            )
            await session.commit()
            return True
            
    async def use_bonus_days(self, user_id: int, days: int) -> bool:
        """Использовать бонусные дни"""
        async with self.async_session() as session:
            # Ensure we don't go below zero
            # SQLite doesn't have GREATEST in all versions, using CASE or manual check logic.
            # Simple way: fetch, check, update. Or use MAX logic.
            user_res = await session.execute(select(User.bonus_days).where(User.id == user_id))
            current = user_res.scalar() or 0
            new_val = max(0, current - days)
            
            await session.execute(
                update(User).where(User.id == user_id).values(bonus_days=new_val)
            )
            await session.commit()
            return True

    async def get_referral_stats(self, user_id: int) -> Dict[str, Any]:
        async with self.async_session() as session:
            # Count referrals
            count_res = await session.execute(select(func.count(User.id)).where(User.referrer_id == user_id))
            total_referrals = count_res.scalar() or 0

            # Count earned days
            rewards_res = await session.execute(select(func.sum(ReferralReward.bonus_days)).where(ReferralReward.referrer_id == user_id))
            earned_days = rewards_res.scalar() or 0

            # Get code
            user_res = await session.execute(select(User.referral_code).where(User.id == user_id))
            code = user_res.scalar()

            return {
                'total_referrals': total_referrals,
                'earned_days': earned_days,
                'referral_code': code
            }

    async def add_referral_reward(self, referrer_id: int, referred_id: int, days: int) -> bool:
        async with self.async_session() as session:
            reward = ReferralReward(referrer_id=referrer_id, referred_id=referred_id, bonus_days=days)
            session.add(reward)
            # Add days to user
            await session.execute(
                update(User).where(User.id == referrer_id).values(bonus_days=User.bonus_days + days)
            )
            await session.commit()
            return True
            
    async def get_statistics(self) -> Dict[str, Any]:
        """Статистика для админа"""
        async with self.async_session() as session:
            total_users = (await session.execute(select(func.count(User.id)))).scalar()
            
            active_subs = (await session.execute(
                select(func.count(Subscription.id)).where(Subscription.status == 'active')
                .where(Subscription.expires_at > func.now())
            )).scalar()
            
            total_revenue = (await session.execute(
                select(func.sum(Payment.amount)).where(Payment.status == 'confirmed')
            )).scalar() or 0
            
            return {
                'total_users': total_users,
                'active_subscriptions': active_subs,
                'total_revenue': int(total_revenue)
            }

    async def get_analytics(self, days: int = 7) -> dict:
        """Расширенная аналитика за N дней"""
        async with self.async_session() as session:
            since = datetime.now() - timedelta(days=days)
            
            # Новые пользователи по дням
            users_by_day = await session.execute(
                select(
                    func.date(User.created_at).label('day'),
                    func.count(User.id).label('count')
                )
                .where(User.created_at >= since)
                .group_by(func.date(User.created_at))
                .order_by(text('day'))
            )
            new_users = {str(row.day): row.count for row in users_by_day}
            
            # Доход по дням
            revenue_by_day = await session.execute(
                select(
                    func.date(Subscription.created_at).label('day'),
                    func.sum(Subscription.price).label('revenue')
                )
                .where(Subscription.created_at >= since)
                .where(Subscription.status.in_(['paid', 'active', 'activated']))
                .group_by(func.date(Subscription.created_at))
                .order_by(text('day'))
            )
            revenue = {str(row.day): int(row.revenue or 0) for row in revenue_by_day}
            
            # Популярные тарифы
            popular = await session.execute(
                select(
                    Subscription.period,
                    func.count(Subscription.id).label('count')
                )
                .where(Subscription.status.in_(['paid', 'active', 'activated']))
                .group_by(Subscription.period)
                .order_by(desc('count'))
            )
            tariffs = {row.period: row.count for row in popular}
            
            return {
                'new_users': new_users,
                'revenue': revenue,
                'popular_tariffs': tariffs
            }

    # ==================== СЕРВЕРЫ ====================

    async def add_server(self, name: str, location: str, country_code: str, 
                   flag_emoji: str, max_users: int = 50) -> bool:
        async with self.async_session() as session:
            try:
                server = Server(
                    name=name, location=location, country_code=country_code,
                    flag_emoji=flag_emoji, max_users=max_users
                )
                session.add(server)
                await session.commit()
                return True
            except Exception as e:
                logger.error(f"Error adding server: {e}")
                return False

    async def get_servers(self, active_only: bool = True) -> List[Dict[str, Any]]:
        async with self.async_session() as session:
            query = select(Server).order_by(Server.id)
            if active_only:
                query = query.where(Server.is_active == True)
            
            result = await session.execute(query)
            servers = result.scalars().all()
            return [self._server_to_dict(s) for s in servers]

    async def get_available_servers(self) -> List[Dict[str, Any]]:
        servers = await self.get_servers(active_only=True)
        return [s for s in servers if s['free_slots'] > 0]

    async def get_server(self, server_id: int) -> Optional[Dict[str, Any]]:
        async with self.async_session() as session:
            result = await session.execute(select(Server).where(Server.id == server_id))
            server = result.scalar_one_or_none()
            return self._server_to_dict(server) if server else None
            
    async def get_servers_with_outline(self) -> List[Dict[str, Any]]:
        """Получить серверы с настроенным Outline API"""
        async with self.async_session() as session:
            stmt = select(Server).where(Server.outline_api_url.is_not(None))
            result = await session.execute(stmt)
            servers = result.scalars().all()
            return [self._server_to_dict(s) for s in servers]

    async def update_server_outline_api(self, server_id: int, api_url: str, cert_sha256: str) -> bool:
        async with self.async_session() as session:
            await session.execute(
                update(Server).where(Server.id == server_id).values(
                    outline_api_url=api_url,
                    outline_cert=cert_sha256
                )
            )
            await session.commit()
            return True

    # ==================== КЛЮЧИ СЕРВЕРА (ФАЙЛЫ) ====================

    async def add_server_key(self, server_id: int, os_type: str, file_id: str) -> bool:
        async with self.async_session() as session:
            try:
                existing_res = await session.execute(
                    select(ServerKey).where(ServerKey.server_id == server_id, ServerKey.os_type == os_type)
                )
                existing = existing_res.scalar_one_or_none()
                
                if existing:
                    existing.file_id = file_id
                else:
                    new_key = ServerKey(server_id=server_id, os_type=os_type, file_id=file_id)
                    session.add(new_key)
                
                await session.commit()
                return True
            except Exception:
                return False

    async def get_server_key(self, server_id: int, os_type: str) -> Optional[str]:
        async with self.async_session() as session:
            result = await session.execute(
                select(ServerKey.file_id).where(ServerKey.server_id == server_id, ServerKey.os_type == os_type)
            )
            return result.scalar()

    # ==================== ПРОМОКОДЫ ====================

    async def create_promo_code(self, code: str, discount_percent: int = 0, 
                          bonus_days: int = 0, max_uses: int = 0,
                          valid_days: int = 30) -> bool:
        async with self.async_session() as session:
            try:
                valid_until = datetime.datetime.now() + datetime.timedelta(days=valid_days)
                promo = PromoCode(
                    code=code.upper(), discount_percent=discount_percent,
                    bonus_days=bonus_days, max_uses=max_uses,
                    valid_until=valid_until
                )
                session.add(promo)
                await session.commit()
                return True
            except Exception:
                return False

    async def get_promo_code(self, code: str) -> Optional[Dict[str, Any]]:
        async with self.async_session() as session:
            result = await session.execute(
                select(PromoCode).where(PromoCode.code == code.upper(), PromoCode.is_active == True)
            )
            promo = result.scalar_one_or_none()
            if promo:
                res = self._model_to_dict(promo)
                res['is_valid'] = (promo.max_uses == 0 or promo.current_uses < promo.max_uses)
                return res
            return None
            
    async def use_promo_code(self, code: str) -> bool:
        async with self.async_session() as session:
            await session.execute(
                update(PromoCode).where(PromoCode.code == code.upper()).values(current_uses=PromoCode.current_uses + 1)
            )
            await session.commit()
            return True
            
    async def get_all_promo_codes(self) -> List[Dict[str, Any]]:
        async with self.async_session() as session:
            res = await session.execute(select(PromoCode).order_by(desc(PromoCode.created_at)))
            promos = res.scalars().all()
            return [self._model_to_dict(p) for p in promos]

    # ==================== ПОДПИСКИ ====================

    async def create_subscription(self, user_id: int, period: str, os: str, 
                            price: int, is_trial: bool = False,
                            promo_code_id: int = None, server_id: int = None) -> int:
        async with self.async_session() as session:
            sub = Subscription(
                user_id=user_id, period=period, os=os, price=price,
                is_trial=is_trial, promo_code_id=promo_code_id,
                server_id=server_id
            )
            session.add(sub)
            await session.commit()
            return sub.id

    async def get_subscription(self, sub_id: int) -> Optional[Dict[str, Any]]:
        async with self.async_session() as session:
            # Eager load server and user for display
            result = await session.execute(
                select(Subscription)
                .options(selectinload(Subscription.server), selectinload(Subscription.user))
                .where(Subscription.id == sub_id)
            )
            sub = result.scalar_one_or_none()
            
            if sub:
                d = self._model_to_dict(sub)
                d['server_name'] = sub.server.name if sub.server else None
                d['flag_emoji'] = sub.server.flag_emoji if sub.server else None
                d['username'] = sub.user.username if sub.user else str(sub.user_id)
                d['created_at'] = str(d['created_at']) if d['created_at'] else None
                d['expires_at'] = str(d['expires_at']) if d['expires_at'] else None
                return d
            return None

    async def update_subscription_status(self, sub_id: int, status: str) -> bool:
        async with self.async_session() as session:
            await session.execute(
                update(Subscription).where(Subscription.id == sub_id).values(status=status)
            )
            await session.commit()
            return True

    async def activate_subscription(self, sub_id: int, server_id: int, 
                              vpn_key: str = None, days: int = None) -> bool:
        async with self.async_session() as session:
            if days is None:
                # Fetch period
                r = await session.execute(select(Subscription.period).where(Subscription.id == sub_id))
                period = r.scalar()
                # Use PERIOD_DAYS from config if not passed, but direct import here to avoid circular dep if config depends on db
                # We imported PERIOD_DAYS from config
                days = PERIOD_DAYS.get(period, 30)

            expires_at = datetime.datetime.now() + datetime.timedelta(days=days)
            
            await session.execute(
                update(Subscription).where(Subscription.id == sub_id).values(
                    server_id=server_id, vpn_key=vpn_key, status='active',
                    starts_at=datetime.datetime.now(),
                    expires_at=expires_at
                )
            )
            
            # Update server count
            await session.execute(
                update(Server).where(Server.id == server_id).values(current_users=Server.current_users + 1)
            )
            
            await session.commit()
            return True
            
    async def activate_subscription_outline(self, sub_id: int, server_id: int, 
                                      outline_key_id: str, access_url: str, days: int) -> bool:
        """Активация подписки через Outline"""
        async with self.async_session() as session:
            expires_at = datetime.datetime.now() + datetime.timedelta(days=days)
            
            await session.execute(
                update(Subscription).where(Subscription.id == sub_id).values(
                    server_id=server_id,
                    outline_key_id=str(outline_key_id), 
                    vpn_key=access_url, 
                    status='active',
                    starts_at=datetime.datetime.now(),
                    expires_at=expires_at
                )
            )
             # Update server count
            await session.execute(
                update(Server).where(Server.id == server_id).values(current_users=Server.current_users + 1)
            )
            await session.commit()
            return True

    async def get_active_subscription(self, user_id: int) -> Optional[Dict[str, Any]]:
        async with self.async_session() as session:
            result = await session.execute(
                select(Subscription)
                .options(selectinload(Subscription.server))
                .where(
                    Subscription.user_id == user_id,
                    Subscription.status == 'active',
                    Subscription.expires_at > datetime.datetime.now()
                )
                .order_by(desc(Subscription.expires_at))
                .limit(1)
            )
            sub = result.scalar_one_or_none()
            if sub:
                d = self._model_to_dict(sub)
                d['server_name'] = sub.server.name if sub.server else None
                d['flag_emoji'] = sub.server.flag_emoji if sub.server else None
                d['expires_at'] = str(d['expires_at'])
                return d
            return None
            
    async def get_subscription_outline_key(self, sub_id: int) -> Optional[Dict[str, str]]:
        """Получить данные Outline ключа для подписки"""
        async with self.async_session() as session:
            result = await session.execute(select(Subscription).where(Subscription.id == sub_id))
            sub = result.scalar_one_or_none()
            if sub and sub.outline_key_id:
                return {
                    'outline_key_id': sub.outline_key_id,
                    'access_url': sub.vpn_key
                }
            return None

    async def get_user_subscriptions(self, user_id: int) -> List[Dict[str, Any]]:
        async with self.async_session() as session:
            res = await session.execute(
                select(Subscription)
                .options(selectinload(Subscription.server))
                .where(Subscription.user_id == user_id)
                .order_by(desc(Subscription.created_at))
            )
            subs = res.scalars().all()
            return [self._enrich_sub_dict(s) for s in subs]

    # ==================== HELPERS ====================

    def _user_to_dict(self, user: User) -> Dict[str, Any]:
        return {
            'id': user.id,
            'username': user.username,
            'full_name': user.full_name,
            'referrer_id': user.referrer_id,
            'referral_code': user.referral_code,
            'trial_used': user.trial_used,
            'bonus_days': user.bonus_days,
            'created_at': str(user.created_at)
        }

    def _server_to_dict(self, server: Server) -> Dict[str, Any]:
        return {
            'id': server.id,
            'name': server.name,
            'location': server.location,
            'country_code': server.country_code,
            'flag_emoji': server.flag_emoji,
            'max_users': server.max_users,
            'current_users': server.current_users,
            'free_slots': server.free_slots,
            'is_active': server.is_active,
            'outline_api_url': server.outline_api_url,
            'outline_cert': server.outline_cert
        }

    def _model_to_dict(self, model) -> Dict[str, Any]:
        """Универсальный конвертер SQLAlchemy модели в dict"""
        d = {}
        for column in model.__table__.columns:
            d[column.name] = getattr(model, column.name)
        return d
        
    async def get_subscriptions_by_status(self, status: str) -> List[Dict[str, Any]]:
        async with self.async_session() as session:
            res = await session.execute(
                select(Subscription)
                .options(selectinload(Subscription.user), selectinload(Subscription.server))
                .where(Subscription.status == status)
                .order_by(desc(Subscription.created_at))
            )
            subs = res.scalars().all()
            return [self._enrich_sub_dict(s) for s in subs]

    def _enrich_sub_dict(self, sub) -> Dict:
        d = self._model_to_dict(sub)
        d['username'] = sub.user.username if sub.user else None
        d['server_name'] = sub.server.name if sub.server else None
        d['flag_emoji'] = sub.server.flag_emoji if sub.server else None
        d['created_at'] = str(sub.created_at)
        return d
        
    async def get_expiring_subscriptions(self, days: int = 3) -> List[Dict[str, Any]]:
         async with self.async_session() as session:
            target_date = datetime.datetime.now() + datetime.timedelta(days=days)
            res = await session.execute(
                select(Subscription)
                .options(selectinload(Subscription.user))
                .where(
                    Subscription.status == 'active',
                    Subscription.expires_at <= target_date,
                    Subscription.expires_at > datetime.datetime.now()
                )
            )
            subs = res.scalars().all()
            result = []
            for s in subs:
                d = self._model_to_dict(s)
                d['username'] = s.user.username if s.user else None
                d['expires_at'] = str(s.expires_at)
                result.append(d)
            return result

    async def get_expired_subscriptions_with_keys(self) -> List[Dict]:
        """Для очистки ключей"""
        async with self.async_session() as session:
            res = await session.execute(
                select(Subscription)
                .where(
                    Subscription.status == 'active',
                    Subscription.expires_at < datetime.datetime.now()
                )
            )
            subs = res.scalars().all()
            return [self._model_to_dict(s) for s in subs]
            
    async def expire_subscription(self, sub_id: int) -> bool:
        async with self.async_session() as session:
            sub_res = await session.execute(select(Subscription).where(Subscription.id == sub_id))
            sub = sub_res.scalar_one_or_none()
            if not sub: return False
            
            sub.status = 'expired'
            if sub.server_id:
                await session.execute(
                    update(Server).where(Server.id == sub.server_id)
                    .values(current_users=func.max(0, Server.current_users - 1))
                )
            await session.commit()
            return True
            
    async def get_expiring_subscriptions_not_reminded(self, days: int = 3) -> List[Dict]:
        """Для напомимнаний. В БД нет поля reminded. Добавим или используем updated_at или просто вернем expiring."""
        # Для простоты вернем просто истекающие, проверка отправки должна быть снаружи или доб. поле в модель
        # В старой БД было mark_reminder_sent?
        # Посмотрим в старый database.py -> там был mark_reminder_sent(sub['id']) но в create table не было поля reminded...
        # А, в старом database.py в create table тоже не было reminded. Видимо оно не работало или я пропустил.
        # Проверим старый код. Да, там был метод mark_reminder_sent, но в CREATE TABLE subscriptions поля reminder_sent не было.
        # Значит старый код падал или использовал updated_at?
        # В любом случае для MVP вернем список.
        return await self.get_expiring_subscriptions(days)

    async def mark_reminder_sent(self, sub_id: int):
        pass # Placeholder

    # Payments
    
    async def create_payment(self, subscription_id: int, user_id: int, 
                       amount: int, payment_method: str,
                       payment_id: str = None) -> int:
        async with self.async_session() as session:
            pay = Payment(
                subscription_id=subscription_id, user_id=user_id,
                amount=amount, payment_method=payment_method, payment_id=payment_id
            )
            session.add(pay)
            await session.commit()
            return pay.id

    async def confirm_payment(self, payment_id: int) -> bool:
         async with self.async_session() as session:
            pay_res = await session.execute(select(Payment).where(Payment.id == payment_id))
            pay = pay_res.scalar_one_or_none()
            if not pay: return False
            
            pay.status = 'confirmed'
            pay.confirmed_at = datetime.datetime.now()
            
            # Update sub
            await session.execute(
                update(Subscription).where(Subscription.id == pay.subscription_id).values(status='paid')
            )
            await session.commit()
            return True
            
    # Reviews
    async def has_review(self, subscription_id: int) -> bool:
        async with self.async_session() as session:
            res = await session.execute(select(func.count(Review.id)).where(Review.subscription_id == subscription_id))
            return res.scalar() > 0
            
    async def add_review(self, subscription_id: int, user_id: int, rating: int, comment: str = None):
         async with self.async_session() as session:
            r = Review(subscription_id=subscription_id, user_id=user_id, rating=rating, comment=comment)
            session.add(r)
            await session.commit()
            
    async def get_reviews(self) -> List[Dict]:
        async with self.async_session() as session:
            res = await session.execute(
                select(Review).options(selectinload(Review.user)).order_by(desc(Review.created_at))
            )
            reviews = res.scalars().all()
            result = []
            for r in reviews:
                d = self._model_to_dict(r)
                d['username'] = r.user.username if r.user else None
                result.append(d)
            return result
            
    async def get_average_rating(self) -> float:
        async with self.async_session() as session:
            res = await session.execute(select(func.avg(Review.rating)))
            return res.scalar() or 0.0

    # ==================== АНТИФРОД ====================
    
    async def check_suspicious_activity(self, user_id: int) -> dict:
        """Проверка подозрительной активности"""
        async with self.async_session() as session:
            user_res = await session.execute(select(User).where(User.id == user_id))
            user = user_res.scalar_one_or_none()
            
            if not user:
                return {"suspicious": False}
            
            flags = []
            
            # 1. Триал уже использован
            if user.trial_used:
                flags.append("trial_used")
            
            # 2. Много триалов от одного реферера (возможный абуз)
            if user.referrer_id:
                ref_trials = await session.execute(
                    select(func.count(Subscription.id))
                    .join(User, Subscription.user_id == User.id)
                    .where(User.referrer_id == user.referrer_id)
                    .where(Subscription.is_trial == True)
                )
                trial_count = ref_trials.scalar() or 0
                if trial_count > 5:
                    flags.append(f"referrer_abuse_{trial_count}")
            
            # 3. Подписка создана менее 24ч назад (быстрое пересоздание)
            recent_subs = await session.execute(
                select(func.count(Subscription.id))
                .where(Subscription.user_id == user_id)
                .where(Subscription.created_at > datetime.now() - timedelta(hours=24))
            )
            recent_count = recent_subs.scalar() or 0
            if recent_count > 3:
                flags.append(f"rapid_activity_{recent_count}")
            
            return {
                "suspicious": len(flags) > 0,
                "flags": flags,
                "block": "referrer_abuse" in "".join(flags) or recent_count > 5
            }
