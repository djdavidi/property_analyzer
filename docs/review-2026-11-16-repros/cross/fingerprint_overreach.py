"""Comment-only code edits invalidate every saved result, including the public baseline.

Run from the repository root: PYTHONPATH=. .venv/bin/python docs/review-2026-11-16-repros/cross/fingerprint_overreach.py
Works on a temporary copy; the checkout is not modified.
"""
import os, shutil, subprocess, sys, tempfile

ROOT = os.getcwd()
CODE = r'''
import sys; sys.path.insert(0, sys.argv[1])
from drainage_core.quality import processing_fingerprint
from stormwater.quality import policy_fingerprint
print(processing_fingerprint()[:12], policy_fingerprint()[:12])
'''
with tempfile.TemporaryDirectory() as tmp:
    for pkg in ('drainage_core', 'stormwater'):
        shutil.copytree(os.path.join(ROOT, pkg), os.path.join(tmp, pkg), ignore=shutil.ignore_patterns('__pycache__'))
    before = subprocess.run([sys.executable, '-c', CODE, ROOT], capture_output=True, text=True).stdout.split()
    for rel in ('drainage_core/freshness.py', 'stormwater/renewals.py'):
        with open(os.path.join(tmp, rel), 'a') as f:
            f.write('\n# comment only\n')
    after = subprocess.run([sys.executable, '-c', CODE, tmp], capture_output=True, text=True).stdout.split()
print('original physical/policy fingerprints:', before)
print('after comment-only edits:            ', after)

sys.path.insert(0, ROOT)
from drainage_core.quality import processing_fingerprint, artifact_quality
from stormwater.quality import safe_analysis

saved = {'processing_fingerprint': processing_fingerprint(),
         'policy_processing_fingerprint': 'fingerprint-before-a-comment-edit',
         'billing': {'status': 'calculated', 'monthly_total': 3138.21, 'published_monthly_total': 3138.21},
         'assessment': {'economics': {'baseline': {'status': 'calculated', 'monthly_total': 3138.21}}, 'categories': []}}
view = safe_analysis(saved)
print('recorded baseline billing after policy-file comment edit:', view['billing']['status'])
print('baseline economics:', view['assessment']['economics']['baseline']['status'])
# Converse: an artifact written before fingerprints existed, with research drainage but
# no modeled_integration block, is never invalidated by later research.py fixes.
print('pre-fingerprint research-only artifact:', artifact_quality({'research_drainage': {'runs': []}})['status'])
