"""
Database connection and session management for Lead Magnet Bot.
Uses SQLAlchemy with async support.

Supports:
- PostgreSQL (via asyncpg) - production
- SQLite (via aiosqlite) - development/testing (only if DEV_MODE=1)
"""

import logging
import os
import re
from typing import AsyncGenerator
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine
)
from sqlalchemy.pool import QueuePool

from .base_models import Base

logger = logging.getLogger(__name__)

# Database URL from environment
DATABASE_URL = os.getenv('DATABASE_URL', '')
DEV_MODE = os.getenv('DEV_MODE', '0') == '1'

# Fallback to SQLite only in development mode
if not DATABASE_URL and DEV_MODE:
    DATABASE_URL = 'sqlite+aiosqlite:///./lead_magnet_bot.db'
    logger.warning("Using SQLite database (DEV_MODE enabled). This should not be used in production!")

# Validate DATABASE_URL for production
if not DATABASE_URL:
    logger.critical("DATABASE_URL is not set and DEV_MODE is disabled. Cannot start bot.")
    raise ValueError("DATABASE_URL environment variable is required. Set DEV_MODE=1 for local SQLite development.")

# Convert postgres:// to postgresql+asyncpg:// (Railway/Heroku compatibility)
if DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql+asyncpg://', 1)
    logger.info("Converted postgres:// to postgresql+asyncpg://")
elif DATABASE_URL.startswith('postgresql://') and '+asyncpg' not in DATABASE_URL:
    DATABASE_URL = DATABASE_URL.replace('postgresql://', 'postgresql+asyncpg://', 1)
    logger.info("Converted postgresql:// to postgresql+asyncpg://")

# Remove sslmode from URL if present (asyncpg doesn't support it in URL)
if DATABASE_URL.startswith('postgresql+asyncpg://'):
    had_sslmode = 'sslmode=' in DATABASE_URL
    DATABASE_URL = re.sub(r'[?&]sslmode=[^&]*', '', DATABASE_URL)
    DATABASE_URL = re.sub(r'\?sslmode=[^&]*$', '', DATABASE_URL)
    DATABASE_URL = re.sub(r'&sslmode=[^&]*', '', DATABASE_URL)
    DATABASE_URL = DATABASE_URL.rstrip('?&')
    
    if had_sslmode:
        logger.info("Removed sslmode parameter from DATABASE_URL (asyncpg doesn't support it)")

# Pool configuration
DB_POOL_SIZE = int(os.getenv('DB_POOL_SIZE', '5'))
DB_MAX_OVERFLOW = int(os.getenv('DB_MAX_OVERFLOW', '0'))

# Determine if we need SSL (for PostgreSQL)
is_postgres = DATABASE_URL.startswith('postgresql+asyncpg://')
connect_args = {}

if is_postgres:
    import ssl
    import asyncpg
    
    # Create SSL context that doesn't verify certificates (Railway uses self-signed certs)
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    
    connect_args['ssl'] = ssl_context
    
    # Store original asyncpg.connect before patching
    _original_asyncpg_connect = asyncpg.connect
    
    # Create wrapper that filters sslmode
    async def _filtered_asyncpg_connect(*args, **kwargs):
        """Wrapper around asyncpg.connect that filters out sslmode parameter."""
        if 'sslmode' in kwargs:
            logger.warning("Removing sslmode from connect args (asyncpg doesn't support it)")
            del kwargs['sslmode']
        if 'ssl' not in kwargs:
            kwargs['ssl'] = ssl_context
        return await _original_asyncpg_connect(*args, **kwargs)
    
    # Monkey-patch asyncpg.connect
    asyncpg.connect = _filtered_asyncpg_connect
    logger.info("Monkey-patched asyncpg.connect to filter sslmode parameter")

# Create async engine with controlled pool
engine_kwargs = {
    'echo': False,
    'future': True,
    'poolclass': QueuePool,
    'pool_size': DB_POOL_SIZE,
    'max_overflow': DB_MAX_OVERFLOW,
    'pool_pre_ping': True,
    'pool_recycle': 3600,
}
if connect_args:
    engine_kwargs['connect_args'] = connect_args

engine = create_async_engine(DATABASE_URL, **engine_kwargs)

# Create async session factory
async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Get database session as async context manager.
    
    Usage:
        async with get_session() as session:
            # Your database operations
            pass
    """
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_db() -> None:
    """
    Initialize database: create all tables.
    Should be called once at application startup.
    
    IMPORTANT: All models must be imported before calling this function
    to ensure they are registered in Base.metadata.
    """
    logger.info("Initializing database...")
    try:
        # Import all models to ensure they are registered in Base.metadata
        from . import models  # noqa: F401 - Import to register models
        
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"ERROR in init_db(): {e}")
        raise


async def close_db() -> None:
    """
    Close database connection.
    Should be called on application shutdown.
    """
    logger.info("Closing database connection...")
    try:
        await engine.dispose()
        logger.info("Database connection closed")
    except Exception as e:
        logger.error(f"ERROR in close_db(): {e}")
