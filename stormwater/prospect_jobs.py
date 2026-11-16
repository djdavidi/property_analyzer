"""Explicit local scan jobs; reading progress/results never acquires data."""
from copy import deepcopy
from pathlib import Path
from threading import Lock, Thread,Event
from drainage_core.sources import now
from .prospects import run_scan,rerank_saved


class ProspectJobs:
    def __init__(self, root):
        self.root = Path(root)
        self.lock = Lock()
        self.state = {'status': 'idle'}
        self.stop=Event()

    def snapshot(self):
        with self.lock:
            return deepcopy(self.state)

    def start(self, refresh=False,mode='rerank'):
        if not isinstance(refresh, bool):
            raise ValueError('Refresh must be true or false')
        if mode not in ('rerank','update'):raise ValueError('Choose local rerank or bounded update')
        with self.lock:
            if self.state['status'] in ('running','cancelling'):
                return deepcopy(self.state)
            self.state = {'status': 'running', 'started_at': now(), 'stage': 'local_ranking' if mode=='rerank' else 'system_inventory', 'completed': 0, 'total': None}
            self.stop=Event()
        def progress(**values):
            with self.lock:
                self.state.update(values)
        def work():
            try:
                result = rerank_saved(self.root) if mode=='rerank' else run_scan(self.root,refresh=False,refresh_stale=True,limit=50,workers=2,progress=progress,cancel=self.stop)
                progress(status='complete', result_id=result['id'], completed_at=now())
            except Exception as exc:
                progress(status='cancelled' if self.stop.is_set() else 'failed', error=str(exc), completed_at=now())
        Thread(target=work, daemon=True).start()
        return self.snapshot()

    def cancel(self):
        with self.lock:
            if self.state['status']=='running':
                self.stop.set();self.state['status']='cancelling'
        return self.snapshot()
