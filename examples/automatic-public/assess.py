"""Reproduce free automatic acquisition on a public address, preserving existing case IDs."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from stormwater.automatic import lookup
from stormwater.acquisition import Cache,acquire_property
from stormwater.server import acquired_case
from stormwater.cases import CaseStore

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('address',nargs='?',default='1901 Vine St')
    args=parser.parse_args();cache=Cache('data/public',timeout=15);found=lookup(args.address,cache)
    if len(found['matches'])!=1:raise SystemExit(json.dumps(found,indent=2))
    case=acquired_case(acquire_property(found['matches'][0]['parcel_id'],cache))
    case['id']='auto-example-'+str(found['matches'][0]['parcel_id']);case['automatic']={'requested':True}
    result=CaseStore().run_assessment(case,cache)
    print(json.dumps({'case_id':case['id'],'measurement':{k:v for k,v in result['analysis']['measurement'].items() if k!='geometries'},
                      'estimates':result['analysis']['automatic']['estimates'],
                      'source_status':result['analysis']['automatic']['source_status']},indent=2))
