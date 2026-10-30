from dataclasses import dataclass


@dataclass(frozen=True)
class SandboxPolicy:
    """Minimal execution policy for a disposable coding-agent workspace."""

    user: str = "nonroot"
    network_mode: str = "none"
    allow_docker_socket: bool = False
    max_cpu_cores: int = 2
    max_memory_mb: int = 2048
    max_pids: int = 256
    read_only_root: bool = True
    mount_project: bool = True
    mount_tmpfs: bool = True

    def validate(self) -> None:
        if self.max_cpu_cores < 1:
            raise ValueError("max_cpu_cores must be at least 1")
        if self.max_memory_mb < 512:
            raise ValueError("max_memory_mb must be at least 512")
        if self.max_pids < 64:
            raise ValueError("max_pids must be at least 64")


DEFAULT_SANDBOX_POLICY = SandboxPolicy()
