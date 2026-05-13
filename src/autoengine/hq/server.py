"""Server functions for HyperQueue."""

import logging
import shutil
import subprocess
import sys
import time
from math import ceil
from pathlib import Path

from hyperqueue.client import Client
from hyperqueue.ffi.protocol import ResourceRequest

DEFAULT_RESOURCES = ResourceRequest(cpus=1, resources={"mem": 500})

logging.basicConfig(
    filename="hq_manager.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class HQManager:
    """Hyperqueue connection manager."""

    def __init__(
        self, server_dir: str = "./.hq-server", log_path: str = "hq.log"
    ) -> None:
        self.server_dir = Path(server_dir).resolve()
        self.log_path = Path(log_path).resolve()
        # Resolve absolute path to hq / pixi to satisfy Ruff S607
        self.hq_bin = self._resolve_bin("hq")
        self.pixi_bin = self._resolve_bin("pixi")
        self.client = None

    def _resolve_bin(self, name: str) -> str:
        """Resolve absolute path of an executable, preferring the pixi env."""
        env_bin = Path(sys.executable).parent
        env_path = env_bin / name

        if env_path.exists():
            msg = f"Resolved {name} from {env_path}."
            logger.info(msg)
            return str(env_path.resolve())

        path = shutil.which(name)
        if not path:
            msg = f"{name} executable not found in PATH."
            raise RuntimeError(msg)

        msg = f"Resolved {name} from system PATH: {path}"
        logger.info(msg)
        return path

    def pixi_activation_hook(self) -> str:
        """Return the activation script for Pixi environment."""
        return subprocess.check_output(  # noqa: S603
            [self.pixi_bin, "shell-hook"], text=True, shell=False
        )

    def start(self) -> None:
        """Clean up stale files and start the server."""
        if self.log_path.exists():
            self.log_path.unlink()

        if self.server_dir.exists():
            shutil.rmtree(self.server_dir)

        self.server_dir.mkdir(parents=True, exist_ok=True)
        log_file = self.log_path.open("w")

        subprocess.Popen(  # noqa: S603
            [self.hq_bin, "server", "start", "--server-dir", str(self.server_dir)],
            stdout=log_file,
            stderr=subprocess.STDOUT,
        )

        self._wait_for_server()
        self.client = Client(server_dir=str(self.server_dir))
        msg = f"HQ Server started. Dir: {self.server_dir}."
        logger.info(msg)

    def _resolve_server_dir(self) -> Path:
        """Return the versioned subdirectory HQ wrote its access file into."""
        candidates = sorted(self.server_dir.glob("[0-9][0-9][0-9]"))
        if candidates:
            return candidates[-1]

        return self.server_dir

    def _wait_for_server(self) -> None:
        """Check for server responsiveness."""
        max_checks = 15
        for i in range(max_checks):
            time.sleep(1)
            srv_dir = str(self._resolve_server_dir())
            res = subprocess.run(  # noqa: S603
                [self.hq_bin, "--server-dir", srv_dir, "job", "list"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
                shell=False,
            )

            if res.returncode == 0:
                self.server_dir = Path(srv_dir)
                return

            msg = f"Waiting for server to respond... (attempt {i + 1}/{max_checks})"
            logger.info(msg)

        msg = f"HQ server failed to start in {max_checks} attempts."
        raise RuntimeError(msg)

    def add_slurm_workers(
        self,
        n_proc: int,
        n_mem: int,
        n_scratch: str,
        time_limit: str,
        partition: str = "batch",
    ) -> None:
        """
        Format and execute a SLURM allocation.

        Parameters
        ----------
        n_proc
            Number of CPUs.
        n_mem
            Amount of memory per CPU in MB.
        n_scratch
            Amount of scratch space in GB.
        time_limit
            Maximum worker wall time (dd:hh:mm:ss)
        partition
            Name of the cluster partition to request resources from.
        """
        mem_mib = ceil(n_mem / 1.049)
        cmd = [
            self.hq_bin,
            "--server-dir",
            str(self.server_dir),
            "alloc",
            "add",
            "slurm",
            "--time-limit",
            time_limit,
            f"--cpus={n_proc}",
            f"--resource=mem=sum({mem_mib})",
            "--",
            f"--partition={partition}",
            f"--ntasks={n_proc}",
            f"--mem-per-cpu={n_mem}",
            f"--gres=lscratch:{n_scratch}",
        ]
        subprocess.run(cmd, check=True)  # noqa: S603

        msg = f"SLURM allocation added: {n_proc} CPUs, {n_mem}MB per CPU."
        logger.info(msg)
