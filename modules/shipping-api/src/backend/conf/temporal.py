from pydantic import BaseModel

from ..utils import auth, env, log
from ..utils.env import EnvVarSpec

from temporal_client import TemporalConf

#### Env Vars ####

TEMPORAL_HOST = EnvVarSpec(
    id="TEMPORAL_HOST",
    default="temporal"
)

TEMPORAL_PORT = EnvVarSpec(
    id="TEMPORAL_PORT",
    default="7233"
)

TEMPORAL_NAMESPACE = EnvVarSpec(
    id="TEMPORAL_NAMESPACE",
    default="default"
)

TEMPORAL_TASK_QUEUE = EnvVarSpec(
    id="TEMPORAL_TASK_QUEUE",
    default="main-task-queue"
)

VALIDATED_ENV_VARS = [
    TEMPORAL_HOST,
    TEMPORAL_PORT,
    TEMPORAL_NAMESPACE,
    TEMPORAL_TASK_QUEUE
]


#### Getters ####

def get_temporal_conf():
    """Get Temporal connection configuration."""
    return TemporalConf(
        host=env.parse(TEMPORAL_HOST),
        port=int(env.parse(TEMPORAL_PORT)),
        namespace=env.parse(TEMPORAL_NAMESPACE),
        task_queue=env.parse(TEMPORAL_TASK_QUEUE)
    )
