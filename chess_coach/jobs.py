"""Single-instance, bounded subprocess supervisor backed by durable job records."""

import atexit
import fcntl
import json
import os
import signal
import subprocess
import sys
import threading
from .storage import Conflict


def terminate_group(process):
    # Always address the group: Stockfish can outlive a failed worker parent.
    for sig in (signal.SIGTERM, signal.SIGKILL):
        try:
            os.killpg(process.pid, sig)
        except ProcessLookupError:
            return
        if sig == signal.SIGTERM:
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                pass
    process.wait(timeout=5)


class Supervisor:
    def __init__(self, store, engine_path, *, timeout=240):
        self.store, self.engine_path, self.timeout = store, engine_path, timeout
        self.stop_event = threading.Event()
        self.process_lock = threading.Lock()
        self.engine_lock = threading.Lock()
        self.process = None
        self.lock = open(store.path + '.worker-lock', 'a')
        try:
            fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self.lock.close()
            raise RuntimeError('Only one application worker/instance may use this database')
        store.recover()
        self.thread = threading.Thread(target=self.loop, name='analysis-supervisor', daemon=True)
        self.thread.start()
        atexit.register(self.close)

    def run_one(self, job):
        process = None
        try:
            game = self.store.game(job['user_id'], job['game_id'])
            with self.process_lock:
                if self.stop_event.is_set():
                    raise RuntimeError('Application is stopping')
                process = subprocess.Popen([sys.executable, '-m', 'chess_coach.worker'],
                                           stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                           text=True, start_new_session=True)
                self.process = process
            output, _ = process.communicate(json.dumps({'pgn': game['pgn'], 'color': game['color'],
                                                        'engine_path': self.engine_path}), timeout=self.timeout)
            if process.returncode != 0 or len(output.encode()) > 25_000_000:
                raise RuntimeError('Analysis failed; no partial result saved')
            self.store.complete(job, json.loads(output))
        except subprocess.TimeoutExpired:
            terminate_group(process)
            self.store.fail(job['id'], 'Analysis exceeded four minutes; no partial result saved')
        except (ValueError, RuntimeError, KeyError, OSError):
            if process is not None:
                terminate_group(process)
            self.store.fail(job['id'], 'Analysis failed; verify the game and engine, then try later')
        finally:
            # Also clean orphan engine children after a worker crash/success.
            if process is not None:
                terminate_group(process)
            with self.process_lock:
                self.process = None

    def loop(self):
        while not self.stop_event.is_set():
            try:
                if self.engine_lock.acquire(blocking=False):
                    try:
                        job = self.store.claim()
                        if job:
                            self.run_one(job)
                            continue
                    finally:
                        self.engine_lock.release()
            except Exception:
                # No payload/note logging. A DB failure must not kill supervision.
                import logging
                logging.getLogger(__name__).error('Analysis supervision failed')
            self.stop_event.wait(1)

    def explore(self, fen, reserve):
        """One short supervised request, never concurrent with game analysis."""
        return self.engine_request({'mode':'position','fen':fen},reserve,timeout=5,limit=32_768)

    def walkthrough(self, fen, proposed, recommended, reserve):
        return self.engine_request({'mode':'walkthrough','fen':fen,'proposed':proposed,'recommended':recommended},
                                   reserve,timeout=12,limit=131_072)

    def engine_request(self, payload, reserve, *, timeout, limit):
        if not self.engine_lock.acquire(blocking=False):
            raise RuntimeError('Engine is busy analyzing a game or another position. Try again shortly.')
        process = None
        try:
            with self.process_lock:
                if self.stop_event.is_set():
                    raise RuntimeError('Engine is stopping. Try after the application restarts.')
                reserve()
                process = subprocess.Popen([sys.executable,'-m','chess_coach.worker'],
                    stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,
                    text=True,start_new_session=True)
                self.process = process
            output, _ = process.communicate(json.dumps(payload | {'engine_path':self.engine_path}), timeout=timeout)
            if process.returncode or len(output) > limit:
                raise RuntimeError('Position analysis failed. You can keep exploring without it.')
            return json.loads(output)
        except subprocess.TimeoutExpired as error:
            raise RuntimeError('Position analysis timed out. Try again shortly.') from error
        except Conflict:
            raise
        except (OSError, ValueError, KeyError) as error:
            raise RuntimeError('Position analysis failed. You can keep exploring without it.') from error
        finally:
            if process is not None:terminate_group(process)
            with self.process_lock:self.process = None
            self.engine_lock.release()

    def close(self):
        with self.process_lock:
            if self.stop_event.is_set():
                return
            self.stop_event.set()
            process = self.process
        if process is not None:
            terminate_group(process)
        self.thread.join(timeout=8)
        self.lock.close()


if __name__ == '__main__':
    raise SystemExit('Supervisor is started by the beta app, not separately')
