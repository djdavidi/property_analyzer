"""Apply an explicit jurisdiction profile to frozen GIS evidence, without routing."""
import argparse
import json
from pathlib import Path
import tempfile

from .jurisdictions import PROFILES, get_profile


def parser():
    p=argparse.ArgumentParser(description=__doc__,epilog=(
        'Example: ./credits --jurisdiction philadelphia-pwd --case gis/case.json '
        '--gis gis/analysis.json --policy philly-policy.json --output credits.json. '
        'Existing Philadelphia workbench cases provide gis-analysis.json separately '
        'from their combined analysis.json. This command never reruns GIS.'))
    p.add_argument('--jurisdiction',required=True,choices=PROFILES)
    p.add_argument('--case',type=Path,required=True,help='Frozen GIS case.json')
    p.add_argument('--gis',type=Path,required=True,help='Matching frozen GIS analysis.json')
    p.add_argument('--policy',type=Path,help='Separate baseline/benefits/tariff JSON; omit to use case fields')
    p.add_argument('--output',type=Path,required=True,help='New policy result JSON; existing input files cannot be overwritten')
    return p


def main(argv=None):
    args=parser().parse_args(argv)
    inputs=[args.case,args.gis]+([args.policy] if args.policy else [])
    if any(args.output.resolve()==value.resolve() for value in inputs):
        print(json.dumps({'error':'Policy output must not overwrite frozen input files'}));return 1
    try:
        case=json.loads(args.case.read_text())
        artifact=json.loads(args.gis.read_text())
        policy=json.loads(args.policy.read_text()) if args.policy else None
        result=get_profile(args.jurisdiction).apply(case,artifact,policy_inputs=policy)
        result['schema_version']=1
        result['artifact_type']='jurisdiction-policy-analysis'
        args.output.parent.mkdir(parents=True,exist_ok=True)
        # A unique sibling avoids overwriting any coincidentally named input
        # such as credits.json.tmp, and concurrent invocations cannot collide.
        with tempfile.NamedTemporaryFile(mode='w',dir=args.output.parent,
                                         prefix=args.output.name+'.',suffix='.tmp',delete=False) as stream:
            temporary=Path(stream.name)
            stream.write(json.dumps(result,indent=2,sort_keys=True,allow_nan=False)+'\n')
        temporary.replace(args.output)
        print(json.dumps({'jurisdiction':result['jurisdiction'],'gis_input_sha256':result['gis_input_sha256'],
                          'policy_input_sha256':result['policy_input_sha256'],
                          'billing_status':result['billing'].get('status','calculated'),
                          'output':str(args.output)},indent=2))
        return 0
    except (OSError,ValueError,KeyError,TypeError) as exc:
        print(json.dumps({'error':str(exc)}));return 1


if __name__=='__main__':
    raise SystemExit(main())
