from typing import Optional, List
from pydantic import BaseModel


class MachineRegisterRequest(BaseModel):
    name: str
    hostname: Optional[str] = None


class MachineResponse(BaseModel):
    id: str
    name: str
    hostname: Optional[str] = None
    ip_address: Optional[str] = None
    status: str
    registered_at: Optional[str] = None
    last_seen: Optional[str] = None
    tags: Optional[str] = "[]"


class MachineRegisterResponse(BaseModel):
    machine_id: str
    api_key: str
    machine: MachineResponse


class MetricsPayload(BaseModel):
    cpu_percent: Optional[float] = None
    memory_percent: Optional[float] = None
    disk_percent: Optional[float] = None
    load_avg_1m: Optional[float] = None
    uptime_seconds: Optional[int] = None


class HeartbeatPayload(BaseModel):
    machine_id: str
    api_key: str
    metrics: Optional[MetricsPayload] = None


class CommandDispatchRequest(BaseModel):
    machine_id: str
    command_text: str
    timeout_seconds: int = 60
    requested_by: Optional[str] = "operator"


class CommandResponse(BaseModel):
    id: str
    machine_id: str
    command_text: str
    status: str
    created_at: Optional[str] = None
    sent_at: Optional[str] = None
    completed_at: Optional[str] = None
    exit_code: Optional[int] = None
    stdout: Optional[str] = None
    stderr: Optional[str] = None
    requested_by: Optional[str] = None
    timeout_seconds: Optional[int] = None


class CommandResultPayload(BaseModel):
    machine_id: str
    api_key: str
    exit_code: int
    stdout: str = ""
    stderr: str = ""
