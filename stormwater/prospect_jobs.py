"""Explicit local scan jobs; reading progress/results never acquires data."""
from copy import deepcopy
from pathlib import Path
from threading import Lock, Thread,Event
from drainage_core.sources import now
from .prospects import run_scan,rerank_saved,update_selected


class ProspectJobs:
    def __init__(self, root):
        self.root = Path(root)
        self.lock = Lock()
        self.state = {'status': 'idle'}
        self.stop=Event()

    def snapshot(self):
        with self.lock:
            return deepcopy(self.state)

    def start(self, refresh=False,mode='rerank',parcel_ids=None):
        if not isinstance(refresh, bool):
            raise ValueError('Refresh must be true or false')
        if mode not in ('rerank','update'):raise ValueError('Choose local rerank or bounded update')
        if mode=='update' and (self.root/'latest.json').exists() and not parcel_ids:
            raise ValueError('Select saved member parcels before updating records')
        with self.lock:
            if self.state['status'] in ('running','cancelling'):
                return deepcopy(self.state)
            self.state = {'status': 'running', 'started_at': now(), 'stage': 'local_ranking' if mode=='rerank' else 'selected_records' if parcel_ids else 'system_inventory', 'completed': 0, 'total': None}
            self.stop=Event()
        def progress(**values):
            with self.lock:
                self.state.update(values)
        def work():
            try:
                if mode=='rerank':result=rerank_saved(self.root)
                elif parcel_ids:result=update_selected(self.root,parcel_ids,progress=progress,cancel=self.stop)
                else:result=run_scan(self.root,refresh=False,refresh_stale=True,limit=50,workers=2,progress=progress,cancel=self.stop)
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
