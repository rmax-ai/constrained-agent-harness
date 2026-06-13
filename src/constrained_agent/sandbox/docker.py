"""Docker-backed sandbox implementation."""

from __future__ import annotations

import asyncio
import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Any

import docker
from docker.errors import DockerException

from constrained_agent.errors import SandboxError
from constrained_agent.sandbox.protocol import ExecutionRequest, ExecutionResult, Sandbox

_OUTPUT_LIMIT_BYTES = 1024 * 1024
_PIDS_LIMIT = 256


@dataclass(slots=True)
class _ContainerRecord:
    container_id: str
    image_digest: str | None


class DockerSandbox(Sandbox):
    """Execute argv commands inside constrained Docker containers."""

    def __init__(
        self,
        *,
        image: str,
        cpu_limit: float,
        memory_limit: str,
        network_disabled: bool,
        read_only: bool,
        workspace_mount: str,
        protected_mounts: list[str],
        user: str = "nobody",
        env_allowlist: list[str],
    ) -> None:
        self._client = docker.from_env()
        self._api_client = self._client.api
        self._image = image
        self._cpu_limit = cpu_limit
        self._memory_limit = memory_limit
        self._network_disabled = network_disabled
        self._read_only = read_only
        self._workspace_mount = Path(workspace_mount).resolve()
        self._protected_mounts = [Path(path).resolve() for path in protected_mounts]
        self._user = user
        self._env_allowlist = tuple(env_allowlist)
        self._containers: dict[str, _ContainerRecord] = {}

    async def execute(self, request: ExecutionRequest) -> ExecutionResult:
        """Run a command in a disposable Docker container."""
        started_at = perf_counter()
        container = None
        image_digest = self._resolve_image_digest()
        try:
            container = await asyncio.to_thread(self._create_container, request)
            self._containers[container.id] = _ContainerRecord(
                container_id=container.id,
                image_digest=image_digest,
            )
            await asyncio.to_thread(container.start)
            try:
                wait_result = await asyncio.wait_for(
                    asyncio.to_thread(container.wait),
                    timeout=request.timeout_seconds,
                )
                timed_out = False
            except TimeoutError:
                timed_out = True
                await asyncio.to_thread(container.kill)
                wait_result = {"StatusCode": 124}

            stdout_text, stderr_text, truncated = await asyncio.to_thread(
                self._read_limited_logs,
                container,
            )
            exit_code = int(wait_result.get("StatusCode", -1))
            return ExecutionResult(
                stdout=stdout_text,
                stderr=stderr_text,
                exit_code=exit_code,
                duration_seconds=perf_counter() - started_at,
                timed_out=timed_out,
                truncated=truncated,
                container_image=image_digest or self._image,
            )
        except DockerException as exc:
            raise SandboxError(str(exc)) from exc
        finally:
            if container is not None:
                await asyncio.to_thread(self._remove_container, container.id)

    async def close(self) -> None:
        """Remove any tracked containers and close Docker clients."""
        for container_id in list(self._containers):
            await asyncio.to_thread(self._remove_container, container_id)
        await asyncio.to_thread(self._client.close)
        await asyncio.to_thread(self._api_client.close)

    def _create_container(self, request: ExecutionRequest) -> Any:
        volumes = self._build_volumes()
        working_dir = self._container_working_dir(request.working_dir)
        environment = self._filtered_env(request.env)
        nano_cpus = max(1, int(self._cpu_limit * 1_000_000_000))
        return self._client.containers.create(
            image=self._image,
            command=request.argv,
            detach=True,
            stdin_open=False,
            tty=False,
            network_disabled=self._network_disabled,
            read_only=self._read_only,
            volumes=volumes,
            working_dir=working_dir,
            user=self._user,
            environment=environment,
            mem_limit=self._memory_limit,
            nano_cpus=nano_cpus,
            pids_limit=_PIDS_LIMIT,
            privileged=False,
            remove=False,
            security_opt=["no-new-privileges"],
        )

    def _build_volumes(self) -> dict[str, dict[str, str]]:
        volumes = {
            str(self._workspace_mount): {
                "bind": "/workspace",
                "mode": "rw",
            }
        }
        for protected_path in self._protected_mounts:
            target = Path("/workspace") / protected_path.relative_to(self._workspace_mount)
            volumes[str(protected_path)] = {
                "bind": str(target),
                "mode": "ro",
            }
        return volumes

    def _container_working_dir(self, working_dir: str | None) -> str:
        if working_dir is None:
            return "/workspace"
        working_path = Path(working_dir)
        if working_path.is_absolute():
            try:
                relative = working_path.resolve().relative_to(self._workspace_mount)
            except ValueError as exc:
                raise SandboxError(f"working directory escapes workspace: {working_dir}") from exc
            return str(Path("/workspace") / relative)
        return str(Path("/workspace") / working_path)

    def _filtered_env(self, request_env: Mapping[str, str] | None) -> dict[str, str]:
        allowed: dict[str, str] = {}
        for key in self._env_allowlist:
            if key in os.environ:
                allowed[key] = os.environ[key]
        if request_env is not None:
            for key, value in request_env.items():
                if key in self._env_allowlist:
                    allowed[key] = value
        return allowed

    def _read_limited_logs(self, container: Any) -> tuple[str, str, bool]:
        stdout_bytes = container.logs(stdout=True, stderr=False)
        stderr_bytes = container.logs(stdout=False, stderr=True)
        combined_length = len(stdout_bytes) + len(stderr_bytes)
        truncated = combined_length > _OUTPUT_LIMIT_BYTES
        if not truncated:
            return (
                stdout_bytes.decode("utf-8", errors="replace"),
                stderr_bytes.decode("utf-8", errors="replace"),
                False,
            )

        stdout_limit = min(len(stdout_bytes), _OUTPUT_LIMIT_BYTES // 2)
        stderr_limit = min(len(stderr_bytes), _OUTPUT_LIMIT_BYTES - stdout_limit)
        stdout_text = stdout_bytes[:stdout_limit].decode("utf-8", errors="replace")
        stderr_text = stderr_bytes[:stderr_limit].decode("utf-8", errors="replace")
        return stdout_text, stderr_text, True

    def _resolve_image_digest(self) -> str | None:
        try:
            image = self._client.images.get(self._image)
        except DockerException:
            return None
        repo_digests = image.attrs.get("RepoDigests") or []
        if repo_digests:
            return str(repo_digests[0])
        return image.id

    def _remove_container(self, container_id: str) -> None:
        self._containers.pop(container_id, None)
        try:
            container = self._client.containers.get(container_id)
        except DockerException:
            return
        try:
            container.remove(force=True)
        except DockerException:
            return
