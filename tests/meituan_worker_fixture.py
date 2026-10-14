"""Executed only by offline tests; no network transports exist in this process."""
import json
import os
import signal
import socket
import sys
import time

import httpx

from src.collectors.meituan import MeituanRawCollector
from src.collectors.meituan_worker import worker_main

MODE = sys.argv.pop(3)

def hang():
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    while True:
        time.sleep(0.1)


def handler(request):
    if MODE == 'list_hang' and request.url.path == '/list':
        while True:
            time.sleep(0.1)
    if request.url.path == '/list':
        count = 100 if MODE == 'fail_forever' else 4
        page = json.loads(request.content)['page']['pageNo']
        if MODE == 'list_partial' and page == 2:
            while True:
                time.sleep(0.1)
        return httpx.Response(200, json={'status': 1, 'data': {
            'list': [{'jobUnionId': str(i), 'name': '大模型测试工程师',
                      'cityList': [{'name': '北京'}], 'jobDuty': 'list content'} for i in range(count)],
            'page': {'totalCount': count * 2 if MODE == 'list_partial' else count,
                     'totalPage': 2 if MODE == 'list_partial' else 1}}})
    key = json.loads(request.content)['jobUnionId']
    if MODE in {'hang', 'crash', 'ipc_close'} and key == '1':
        if MODE == 'crash':
            os._exit(7)
        if MODE == 'ipc_close':
            # Deliberately leave a truncated frame before shutting down IPC.
            sock = socket.socket(fileno=os.dup(int(sys.argv[1])))
            sock.sendall(b'{"seq":999')
            sock.shutdown(socket.SHUT_RDWR)
            sock.close()
        while True:
            time.sleep(.1)
    if MODE == 'fail_forever' or (MODE == 'partial' and key == '1'):
        time.sleep(.03)
        raise httpx.ReadTimeout('offline')
    if MODE == 'no_descendants' and key == '1':
        import subprocess
        try:
            subprocess.Popen([sys.executable, '-c', 'pass'])
        except PermissionError:
            pass
        else:
            raise AssertionError('descendant creation permitted')
    return httpx.Response(200, json={'status': 1, 'data': {
        'jobDuty': '负责大模型评测质量与测试', 'jobRequirement': 'Python'}})

if MODE in {'duplicate', 'unconfirmed', 'malformed'}:
    from src.models import CollectionManifest, RawJobPosting
    channel = socket.socket(fileno=int(sys.argv[1]))
    stream = channel.makefile('rwb', buffering=0)
    config = json.loads(stream.readline())
    def exchange(message):
        channel.sendall((json.dumps(message) + '\n').encode())
        return json.loads(stream.readline())
    exchange(dict(event='ready', pid=os.getpid(), ppid=os.getppid(), pgid=os.getpgrp(),
                  sid=os.getsid(0), token=sys.argv[2]))
    job = RawJobPosting(platform='meituan', job_id='1', title='测试', company='美团',
                        description='confirmed')
    manifest = CollectionManifest(platform='meituan', name='美团', status='success', complete=True,
        source_total=1, records_fetched=1, expected_pages=1, pages_fetched=1,
        jobs_mapped=1, jobs_in_scope=1, stopped_by='source_total_reached')
    exchange(dict(seq=1, event='list', manifest=manifest.to_dict(), jobs=[job.to_dict()]))
    exchange(dict(seq=2, event='list_end', manifest=manifest.to_dict()))
    exchange(dict(seq=3, event='attempt', job_id='1'))
    message = dict(seq=4, event='success', job=job.to_dict())
    if MODE == 'unconfirmed':
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        channel.sendall(json.dumps(message).encode()[:-3])
        while True: time.sleep(.1)
    if MODE == 'malformed':
        channel.sendall(b'not-json\n')
        while True: time.sleep(.1)
    exchange(message)
    exchange(message)
    manifest.details_fetched = 1
    exchange(dict(seq=5, event='done', manifest=manifest.to_dict()))
    sys.exit(0)

original_init = MeituanRawCollector.__init__
def init(self, platform, collection):
    original_init(self, platform, collection, httpx.Client(transport=httpx.MockTransport(handler)))
MeituanRawCollector.__init__ = init

original_collect = MeituanRawCollector.collect
def collect(self):
    if MODE in {'hang', 'ipc_close', 'list_hang', 'list_partial'}:
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
    return original_collect(self)
MeituanRawCollector.collect = collect
worker_main()
