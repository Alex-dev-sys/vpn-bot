from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime, Text, BigInteger
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.sql import func
from datetime import datetime

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'

    id = Column(BigInteger, primary_key=True)
    username = Column(String)
    full_name = Column(String)
    referrer_id = Column(BigInteger, ForeignKey('users.id'), nullable=True)
    referral_code = Column(String, unique=True)
    trial_used = Column(Boolean, default=False)
    bonus_days = Column(Integer, default=0)
    created_at = Column(DateTime, server_default=func.now())

    # Relationships
    subscriptions = relationship("Subscription", back_populates="user")
    reviews = relationship("Review", back_populates="user")
    
class Server(Base):
    __tablename__ = 'servers'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, unique=True, nullable=False)
    location = Column(String, nullable=False)
    country_code = Column(String, nullable=False)
    flag_emoji = Column(String, nullable=False)
    max_users = Column(Integer, default=50)
    current_users = Column(Integer, default=0)
    outline_api_url = Column(String, nullable=True)
    outline_cert = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())

    subscriptions = relationship("Subscription", back_populates="server")
    keys = relationship("ServerKey", back_populates="server")

    @property
    def free_slots(self):
        return max(0, self.max_users - self.current_users)

class ServerKey(Base):
    __tablename__ = 'server_keys'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    server_id = Column(Integer, ForeignKey('servers.id'), nullable=False)
    os_type = Column(String, nullable=False)
    file_id = Column(String, nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    
    server = relationship("Server", back_populates="keys")

class Subscription(Base):
    __tablename__ = 'subscriptions'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey('users.id'), nullable=False)
    server_id = Column(Integer, ForeignKey('servers.id'), nullable=True)
    period = Column(String, nullable=False)
    os = Column(String, nullable=False)
    price = Column(Integer, nullable=False)
    status = Column(String, default='pending')
    is_trial = Column(Boolean, default=False)
    vpn_key = Column(Text, nullable=True) # JSON or simple string
    promo_code_id = Column(Integer, ForeignKey('promo_codes.id'), nullable=True)
    starts_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    outline_key_id = Column(String, nullable=True) # Stores Outline Key ID for API deletion
    reminder_sent = Column(Boolean, default=False)  # Track if expiration reminder was sent

    user = relationship("User", back_populates="subscriptions")
    server = relationship("Server", back_populates="subscriptions")
    promo_code = relationship("PromoCode", back_populates="subscriptions")
    payment = relationship("Payment", uselist=False, back_populates="subscription")
    review = relationship("Review", uselist=False, back_populates="subscription")

class PromoCode(Base):
    __tablename__ = 'promo_codes'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String, unique=True, nullable=False)
    discount_percent = Column(Integer, default=0)
    bonus_days = Column(Integer, default=0)
    max_uses = Column(Integer, default=0)
    current_uses = Column(Integer, default=0)
    valid_until = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())

    subscriptions = relationship("Subscription", back_populates="promo_code")

class Payment(Base):
    __tablename__ = 'payments'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    subscription_id = Column(Integer, ForeignKey('subscriptions.id'), nullable=False)
    user_id = Column(BigInteger, ForeignKey('users.id'), nullable=False)
    amount = Column(Integer, nullable=False)
    payment_method = Column(String, nullable=False)
    payment_id = Column(String, nullable=True)
    status = Column(String, default='pending')
    created_at = Column(DateTime, server_default=func.now())
    confirmed_at = Column(DateTime, nullable=True)
    
    subscription = relationship("Subscription", back_populates="payment")

class Review(Base):
    __tablename__ = 'reviews'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    subscription_id = Column(Integer, ForeignKey('subscriptions.id'), nullable=False)
    user_id = Column(BigInteger, ForeignKey('users.id'), nullable=False)
    rating = Column(Integer, nullable=False)
    comment = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    
    user = relationship("User", back_populates="reviews")
    subscription = relationship("Subscription", back_populates="review")

class ReferralReward(Base):
    __tablename__ = 'referral_rewards'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    referrer_id = Column(BigInteger, ForeignKey('users.id'), nullable=False)
    referred_id = Column(BigInteger, ForeignKey('users.id'), nullable=False)
    bonus_days = Column(Integer, nullable=False)
    created_at = Column(DateTime, server_default=func.now())
