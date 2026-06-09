from __future__ import annotations
import asyncio
import json
import logging
from .base import AgentAdapter
from ..core.task import Task, TaskStatus

logger = logging.getLogger(__name__)

class CodexAppServerAdapter(AgentAdapter):
    """Communicates with Codex Desktop via JSON-RPC app-server."""

    def __init__(self, codex_binary='codex', cwd=None, model=None,
                 approval_policy='never'):
        self.binary = codex_binary
        self.cwd = cwd
        self.model = model
        self.approval_policy = approval_policy
        self._process = None
        self._reader = None
        self._writer = None
        self._pending = {}
        self._msg_id = 0
        self._lock = asyncio.Lock()

    async def initialize(self):
        """Start the app-server subprocess."""
        logger.info('Starting Codex app-server...')
        if isinstance(self.binary, str):
            cmd = [self.binary, 'app-server']
        else:
            cmd = list(self.binary) + ['app-server']
        if self.model:
            cmd.extend(['--model', self.model])
        self._process = await asyncio.create_subprocess_exec(
            *cmd, stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE, cwd=self.cwd)
        self._writer = self._process.stdin
        self._reader = self._process.stdout
        asyncio.create_task(self._read_loop())
        await self._send_request('initialize',
            {'protocolVersion': '2025-01-01'})
        logger.info('Codex app-server ready')

    async def create_agent(self, task):
        params = {}
        if self.model:
            params['model'] = self.model
        if self.cwd:
            params['cwd'] = self.cwd
        params['approvalPolicy'] = self.approval_policy
        result = await self._send_request('thread/start', params)
        thread_id = result.get('threadId', result.get('id', ''))
        task.agent_id = thread_id
        return thread_id

    async def send_task(self, agent_id, task):
        prompt = f'Task: {task.title}\n\n{task.description}'
        result = await self._send_request('turn/start', {
            'threadId': agent_id,
            'input': [{'type': 'text', 'text': prompt}],
        })
        output = result.get('output', '')
        if isinstance(output, list):
            output = ' '.join(item.get('text', '')
                for item in output if item.get('type') == 'text')
        task.result = str(output)
        task.status = TaskStatus.COMPLETED
        return task.result

    async def get_status(self, agent_id):
        result = await self._send_request('thread/list', {})
        threads = result.get('threads', result.get('result', []))
        for t in threads:
            if t.get('id') == agent_id or t.get('threadId') == agent_id:
                return t.get('status', 'unknown')
        return 'unknown'

    async def shutdown(self):
        if self._process:
            try:
                self._process.terminate()
                await asyncio.wait_for(self._process.wait(), timeout=5.0)
            except:
                self._process.kill()
            self._process = None
        logger.info('Codex app-server stopped')

    async def _send_request(self, method, params):
        async with self._lock:
            self._msg_id += 1
            msg_id = self._msg_id
            request = {'jsonrpc': '2.0', 'id': str(msg_id),
                       'method': method, 'params': params}
            future = asyncio.Future()
            self._pending[str(msg_id)] = future
            line = json.dumps(request) + '\n'
            self._writer.write(line.encode())
            await self._writer.drain()
        try:
            return await asyncio.wait_for(future, timeout=300.0)
        except asyncio.TimeoutError:
            self._pending.pop(str(msg_id), None)
            raise TimeoutError(f'Request {method} timed out')

    async def _read_loop(self):
        buffer = b''
        while self._reader and not self._reader.at_eof():
            try:
                chunk = await self._reader.read(65536)
                if not chunk:
                    break
                buffer += chunk
                while b'\n' in buffer:
                    line, buffer = buffer.split(b'\n', 1)
                    if not line.strip():
                        continue
                    try:
                        msg = json.loads(line.decode('utf-8'))
                        msg_id = msg.get('id')
                        if msg_id and str(msg_id) in self._pending:
                            f = self._pending.pop(str(msg_id))
                            if not f.done():
                                f.set_result(msg)
                    except json.JSONDecodeError:
                        continue
            except Exception as e:
                logger.error(f'Read error: {e}')
                break
