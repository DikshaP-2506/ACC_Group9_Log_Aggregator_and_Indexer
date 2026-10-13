import os
from pathlib import Path
from dotenv import load_dotenv

# Load local .env if present
load_dotenv()


class AgentConfig:
    """Configuration for Log Agent and Generator loaded from environment variables."""

    def __init__(self) -> None:
        self.source: str = os.getenv("AGENT_SOURCE", "server-1")
        
        default_log_file = f"logs/{self.source}.log"
        self.log_file_path: Path = Path(os.getenv("LOG_FILE_PATH", default_log_file))
        
        default_offset_file = str(self.log_file_path) + ".offset"
        self.state_file_path: Path = Path(os.getenv("STATE_FILE_PATH", default_offset_file))
        
        self.aggregator_url: str = os.getenv("AGGREGATOR_URL", "http://127.0.0.1:8000/logs")
        self.poll_interval: float = float(os.getenv("POLL_INTERVAL", "1.0"))
        self.max_retries: int = int(os.getenv("MAX_RETRIES", "3"))
        self.backoff_factor: float = float(os.getenv("BACKOFF_FACTOR", "1.5"))
        self.request_timeout: float = float(os.getenv("REQUEST_TIMEOUT", "5.0"))
        self.batch_size: int = int(os.getenv("BATCH_SIZE", "10"))


config = AgentConfig()
