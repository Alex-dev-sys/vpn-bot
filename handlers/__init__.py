"""
Модуль обработчиков VPN-бота
"""
from aiogram import Router

from .user import router as user_router
from .admin import router as admin_router
from .inline import router as inline_router

__all__ = ['user_router', 'admin_router', 'inline_router']
