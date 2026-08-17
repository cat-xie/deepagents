"""Docker 沙箱后端：基于 deepagents 的 BaseSandbox + docker-py。

子类只需要实现 4 个抽象成员：
- id property                       → 返回容器 ID/name
- execute(command, timeout)         → 在容器里跑 shell 命令
- upload_files(files: list[tuple[path, bytes]]) → 把文件写进容器
- download_files(paths: list[str])  → 从容器读文件

BaseSandbox 已经用 shell 命令实现了所有其它文件操作（ls / read / grep / edit / glob / delete），
所以只要 execute 可靠，FilesystemMiddleware 的所有工具就能工作。

同时 SandboxBackendProtocol 会让 deepagents 注册一个 execute 工具，agent 可以直接
调用 shell 命令，输出被隔离在容器内，不会影响宿主机。
"""

from __future__ import annotations

import io
import os
import tarfile
from datetime import datetime
from typing import Final

from deepagents.backends.protocol import (
    ExecuteResponse,
    FileDownloadResponse,
    FileUploadResponse,
)
from deepagents.backends.sandbox import BaseSandbox

# 容器内的工作目录，FilesystemBackend 意义上的“根目录”
WORK_DIR: Final[str] = "/workspace"

# 输出硬截断阈值（超出会标记 truncated=True，防止巨量输出撑爆上下文）
_OUTPUT_HARD_LIMIT_BYTES: Final[int] = 200 * 1024  # 200KB


class DockerSandboxBackend(BaseSandbox):
    """用本地 Docker 容器当沙箱。

    用法：
        backend = DockerSandboxBackend(image="python:3.11-slim-bookworm")
        agent = create_deep_agent(backend=backend, ...)
    """

    # 我们用的镜像是 Debian slim，带 POSIX shell + coreutils，符合 capture offload
    # 的前提（BaseSandbox 的 wrapper 需要 sh + dd + head + tail）。
    # 如果换更小的 alpine（musl + busybox），建议改回 False。
    enable_capture_offload: bool = True

    def __init__(
        self,
        image: str = "python:3.11-slim-bookworm",
        *,
        work_dir: str = WORK_DIR,
        memory_limit_mb: int = 1024,
        cpu_period: int = 100000,
        cpu_quota: int = 50000,       # 默认 0.5 核，防止 agent 死循环卡死宿主机
        default_timeout: int = 120,    # 单次 execute 默认超时（秒）
        container_name: str | None = None,
        # 如果你担心 agent 读了 .env 外泄，可以把这个改成 None 彻底断网
        network_disabled: bool = False,
    ) -> None:
        # 按需延迟导入，避免没装 docker-py 时 import 本文件就报错
        try:
            import docker  # noqa: WPS433
        except ImportError as e:  # pragma: no cover - 环境依赖提示
            raise ImportError(
                "docker-py 未安装，请执行: pip install docker"
            ) from e

        self._docker = docker.from_env()
        self._work_dir = work_dir.rstrip("/") or "/"
        self._default_timeout = default_timeout
        self._image = image

        # 保证镜像存在，不存在就拉。第一次会慢一些，之后有缓存
        try:
            self._docker.images.get(image)
        except docker.errors.ImageNotFound:
            print(f"[DockerSandbox] 拉取镜像 {image}（第一次可能需要几分钟）...")
            self._docker.images.pull(image)
            print(f"[DockerSandbox] 镜像拉取完成")

        # 容器名字方便用户 docker ps 一眼认出，没给就加时间戳后缀
        if container_name is None:
            container_name = f"deepagents-sandbox-{datetime.now():%Y%m%d-%H%M%S}"

        host_config = self._docker.api.create_host_config(
            mem_limit=f"{memory_limit_mb}m",
            cpu_period=cpu_period,
            cpu_quota=cpu_quota,
        )

        print(f"[DockerSandbox] 创建容器 {container_name}（image={image}）...")
        created = self._docker.api.create_container(
            image=image,
            name=container_name,
            command=["tail", "-f", "/dev/null"],  # 让容器一直挂着不退出
            working_dir=self._work_dir,
            environment={"HOME": self._work_dir},
            host_config=host_config,
            network_disabled=network_disabled,
            labels={"owner": "deepagents-local-sandbox"},
        )
        self._container_id: str = created["Id"]
        self._container_name = container_name

        self._docker.api.start(self._container_id)
        # 确保工作目录存在
        try:
            self._docker.api.exec_start(
                self._docker.api.exec_create(
                    self._container_id,
                    ["mkdir", "-p", self._work_dir],
                )["Id"]
            )
        except Exception:  # pragma: no cover - 失败不影响启动
            pass

        print(f"[DockerSandbox] 容器已启动: {self._container_name}")

    # ------------------------------------------------------------------
    # 资源清理：脚本退出时顺带停掉并删除容器，避免留下孤儿容器
    # ------------------------------------------------------------------
    def stop_and_remove(self) -> None:
        try:
            self._docker.api.stop(self._container_id, timeout=5)
        except Exception:
            pass
        try:
            self._docker.api.remove_container(self._container_id, force=True)
            print(f"[DockerSandbox] 容器已清理: {self._container_name}")
        except Exception:
            pass

    def __del__(self):  # pragma: no cover - Python 析构不保证时机
        try:
            self.stop_and_remove()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # BaseSandbox 要求实现的 4 个抽象成员
    # ------------------------------------------------------------------

    @property
    def id(self) -> str:  # noqa: A003 - 遵守协议命名
        return self._container_name

    def execute(self, command: str, *, timeout: int | None = None) -> ExecuteResponse:
        use_timeout = timeout if timeout is not None else self._default_timeout
        exec_id = self._docker.api.exec_create(
            self._container_id,
            # 统一通过 sh -c 执行，保证 BaseSandbox 内那些 python3 -c 脚本、
            # shell 管道、重定向语法都能跑
            ["sh", "-c", command],
            workdir=self._work_dir,
        )["Id"]

        raw: bytes = b""
        exit_code: int | None = None
        truncated = False

        try:
            raw = self._docker.api.exec_start(exec_id, demux=False, stream=False)
            inspect = self._docker.api.exec_inspect(exec_id)
            exit_code = inspect.get("ExitCode")
            if isinstance(raw, bytes):
                if len(raw) > _OUTPUT_HARD_LIMIT_BYTES:
                    raw = raw[:_OUTPUT_HARD_LIMIT_BYTES]
                    truncated = True
        except Exception as e:  # pragma: no cover - 健壮性兜底
            raw = f"[docker exec error] {e}".encode("utf-8")
            exit_code = None

        output = raw.decode("utf-8", errors="replace")
        return ExecuteResponse(
            output=output,
            exit_code=exit_code,
            truncated=truncated,
        )

    def upload_files(self, files: list[tuple[str, bytes]]) -> list[FileUploadResponse]:
        responses: list[FileUploadResponse] = []
        for path, content in files:
            # 规范化成绝对路径（相对于 work_dir）
            if not path.startswith("/"):
                path = self._work_dir + "/" + path
            # 但 BaseSandbox 传入的已经是 /workspace/xxx 的绝对路径；
            # 为稳妥起见强制在 work_dir 内，防止路径穿越写入容器其它位置
            if not path.startswith(self._work_dir + "/") and path != self._work_dir:
                responses.append(FileUploadResponse(
                    path=path,
                    error="invalid_path: 只能写入沙箱 work_dir 下的路径",
                ))
                continue

            try:
                # 先确保父目录存在
                parent = os.path.dirname(path)
                if parent:
                    self._docker.api.exec_start(
                        self._docker.api.exec_create(
                            self._container_id, ["mkdir", "-p", parent],
                        )["Id"]
                    )

                # docker-py 没有“直接给内容写文件”的高阶 API，
                # 标准做法是构造一个只有这一个文件的 tar 包，
                # 然后 put_archive 打进 /，会自动去掉 tar 里的前缀
                tar_buffer = io.BytesIO()
                with tarfile.open(fileobj=tar_buffer, mode="w") as tar:
                    info = tarfile.TarInfo(name=path.lstrip("/"))
                    info.size = len(content)
                    info.mode = 0o644
                    tar.addfile(info, io.BytesIO(content))
                tar_buffer.seek(0)
                ok = self._docker.api.put_archive(self._container_id, "/", tar_buffer)
                if not ok:
                    responses.append(FileUploadResponse(
                        path=path, error="put_archive_failed: docker API 返回 false",
                    ))
                else:
                    responses.append(FileUploadResponse(path=path, error=None))
            except Exception as e:
                responses.append(FileUploadResponse(path=path, error=str(e)))

        return responses

    def download_files(self, paths: list[str]) -> list[FileDownloadResponse]:
        results: list[FileDownloadResponse] = []
        for path in paths:
            if not path.startswith("/"):
                path = self._work_dir + "/" + path
            if not path.startswith(self._work_dir + "/") and path != self._work_dir:
                results.append(FileDownloadResponse(
                    path=path, content=None,
                    error="invalid_path: 只能读取沙箱 work_dir 下的路径",
                ))
                continue

            try:
                stream, _stat = self._docker.api.get_archive(self._container_id, path)
                chunks = b"".join(stream)
                tar_buffer = io.BytesIO(chunks)
                with tarfile.open(fileobj=tar_buffer, mode="r") as tar:
                    member = tar.next()
                    if member is None or not member.isfile():
                        results.append(FileDownloadResponse(
                            path=path, content=None, error="not_a_file",
                        ))
                        continue
                    extracted = tar.extractfile(member)
                    content = extracted.read() if extracted else b""
                results.append(FileDownloadResponse(path=path, content=content, error=None))
            except Exception as e:
                # docker 找不到文件的话抛 404，这里统一归一化成 not_found
                msg = str(e)
                norm = "not_found" if ("404" in msg or "not found" in msg.lower()) else msg
                results.append(FileDownloadResponse(path=path, content=None, error=norm))
        return results
