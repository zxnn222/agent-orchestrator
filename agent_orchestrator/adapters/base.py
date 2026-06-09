import abc

class AgentAdapter(abc.ABC):
    """Interface for agent communication."""

    @abc.abstractmethod
    async def initialize(self):
        ...

    @abc.abstractmethod
    async def create_agent(self, task):
        """Create agent for task. Returns agent ID."""
        ...

    @abc.abstractmethod
    async def send_task(self, agent_id, task):
        """Send task to agent. Returns result."""
        ...

    @abc.abstractmethod
    async def get_status(self, agent_id):
        ...

    @abc.abstractmethod
    async def shutdown(self):
        ...
