"""Alembic environment configuration."""

from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# Import settings and Base
from src.config.settings import settings
from src.models.database import Base

# Import all models to ensure they're registered with Base.metadata
from src.models import schemas  # noqa: F401
from src.models import adsb  # noqa: F401
from src.models import power_grid  # noqa: F401
from src.models import patents  # noqa: F401
from src.models import air_quality  # noqa: F401
from src.models import weather  # noqa: F401
from src.models import trends  # noqa: F401
from src.models import sentiment  # noqa: F401
from src.models import shipping  # noqa: F401
from src.models import github  # noqa: F401
from src.models import satellite  # noqa: F401
from src.alerts import models as alert_models  # noqa: F401
# Phase 1 Quick Wins models
from src.models import tsa  # noqa: F401
from src.models import opentable  # noqa: F401
from src.models import earthquake  # noqa: F401
from src.models import carbon_intensity  # noqa: F401
from src.models import building_permits  # noqa: F401
from src.models import box_office  # noqa: F401
from src.models import cloudflare_radar  # noqa: F401
from src.models import zillow_rental  # noqa: F401

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
target_metadata = Base.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def get_url():
    """Get database URL from settings."""
    return settings.database_url


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.
    """
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.
    """
    configuration = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = get_url()
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
