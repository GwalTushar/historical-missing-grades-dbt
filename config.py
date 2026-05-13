from sqlmesh.core.config import Config, ModelDefaultsConfig

config = Config(
    model_defaults=ModelDefaultsConfig(dialect="duckdb"),
)
