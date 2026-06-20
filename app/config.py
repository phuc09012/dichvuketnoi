from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "camera-a2"
    host: str = Field(default="0.0.0.0", alias="HOST")
    port: int = Field(default=8000, alias="PORT")
    camera_stream_url: str = Field(default="", alias="CAMERA_STREAM_URL")
    camera_id: str = Field(default="cam-gate-a", alias="CAMERA_ID")
    camera_location: str = Field(default="Main Gate A", alias="CAMERA_LOCATION")
    snapshot_dir: Path = Field(default=Path("snapshots"), alias="SNAPSHOT_DIR")
    camera_timeout: float = Field(default=5.0, alias="CAMERA_TIMEOUT")
    motion_threshold: float = Field(default=0.08, alias="MOTION_THRESHOLD")
    peer_endpoints: str = Field(default="", alias="PEER_ENDPOINTS")
    ai_service_url: str = Field(default="http://ai:9000", alias="AI_SERVICE_URL")
    ai_detect_path: str = Field(default="/api/v1/vision/detect", alias="AI_DETECT_PATH")
    ai_payload_mode: str = Field(default="url", alias="AI_PAYLOAD_MODE")
    ai_auth_header_name: str = Field(default="", alias="AI_AUTH_HEADER_NAME")
    ai_auth_header_value: str = Field(default="", alias="AI_AUTH_HEADER_VALUE")
    public_base_url: str = Field(default="", alias="PUBLIC_BASE_URL")
    camera_cooldown_seconds: float = Field(default=8.0, alias="CAMERA_COOLDOWN_SECONDS")
    mqtt_enabled: bool = Field(default=False, alias="MQTT_ENABLED")
    mqtt_broker_host: str = Field(default="", alias="MQTT_BROKER_HOST")
    mqtt_broker_port: int = Field(default=1883, alias="MQTT_BROKER_PORT")
    mqtt_username: str = Field(default="", alias="MQTT_USERNAME")
    mqtt_password: str = Field(default="", alias="MQTT_PASSWORD")
    mqtt_topic_camera_events: str = Field(default="smart-campus/events/camera", alias="MQTT_TOPIC_CAMERA_EVENTS")
    database_url: str = Field(default="postgresql://camera:camera@db:5432/camera", alias="DATABASE_URL")
    http_timeout: float = Field(default=5.0, alias="HTTP_TIMEOUT")


@lru_cache
def get_settings() -> Settings:
    return Settings()
