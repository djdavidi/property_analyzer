"""Local drainage workbench commands. No external writes or hosting."""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path

from .cases import ROOT, CaseStore, analyze, input_hash


def write_json(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')


def load_case(value,store):
    path=Path(value)
    return json.loads(path.read_text()) if path.is_file() else store.load(value)


def summary(case,result,store=None):
    measurement=result['measurement']
    return {'case_id':case['id'],'synthetic':case.get('synthetic_case',False),
            'input_sha256':result['input_sha256'],'ga_sqft':measurement['ga_sqft'],
            'known_ia_sqft':measurement['ia_sqft'],'unknown_sqft':measurement['unknown_sqft'],
            'processing_seconds':result['processing_seconds'],
            'independent_validation':{kind:item['status'] for kind,item in result['validation'].items()},
            'report':str(store.directory(case['id'])/'report.html') if store else None,
            'warnings':result['warnings']}


def benchmark(cases,output,documentation=None):
    """Evaluate separate supplied IA/drainage references without inventing targets."""
    records=[]
    for case in cases:
        checked=deepcopy(case)
        excluded=[ref for ref in checked.get('references',[]) if ref.get('synthetic') is True
                  or ref.get('source_kind')=='synthetic' or str(ref.get('source_url','')).startswith('synthetic:')]
        checked['references']=[ref for ref in checked.get('references',[]) if ref not in excluded]
        result=analyze(checked)
        empirical=not case.get('synthetic_case',False)
        records.append({'case_id':case['id'],'name':case['name'],'synthetic':not empirical,
                        'input_sha256':input_hash(case),
                        'validation_input_sha256':result['input_sha256'],
                        'eligible_for_empirical_summary':empirical,
                        'synthetic_reference_ids_excluded':[ref.get('id') for ref in excluded],
                        'validation':result['validation'],
                        'processing_seconds':result['processing_seconds'],
                        'manual_review_minutes':case.get('manual_review_minutes')})
    per_kind={}
    for kind in ('ia','drainage'):
        real=[r for r in records if r['eligible_for_empirical_summary']]
        measured=[r for r in real if r['validation'][kind]['status']=='measured']
        holdout=[r for r in measured if any(v['holdout'] for v in r['validation'][kind]['results'])]
        blockers=[]
        if not measured:blockers.append('No independently referenced real-site '+kind+' result is available')
        if len(measured)<3:blockers.append('Several stable completed sites spanning the planned site types have not been evaluated')
        if not holdout:blockers.append('No independently referenced real-site holdout has been evaluated')
        if any(any(v.get('resolution_sensitivity') in (None,'Not evaluated') for v in r['validation'][kind]['results']) for r in measured) or not measured:
            blockers.append('Resolution and processing sensitivity remain incomplete')
        if kind=='drainage' and (not measured or any(any(v.get('routing_disagreements') in (None,'Not independently reviewed') for v in r['validation'][kind]['results']) for r in measured)):
            blockers.append('Critical routing disagreements have not been independently reviewed')
        per_kind[kind]={'status':'incomplete' if blockers else 'measured',
                        'real_cases_with_independent_metrics':len(measured),
                        'real_holdout_cases':len(holdout),'blockers':blockers,'accuracy_target':None}
    report={'schema_version':1,'generated_at':datetime.now(timezone.utc).isoformat(),
            'scope':'Separate independent real-site IA and drainage validation; synthetic fixtures excluded',
            'assessment':per_kind,'cases':records,
            'method':{'area':'Predicted minus reference square feet; absolute percentage error against reference area',
                      'boundary':'Polygon intersection-over-union, precision, recall, false positive/negative area and Hausdorff distance in native CRS units',
                      'routing':'Independent per-outlet boundaries and separately reviewed critical routing disagreements',
                      'classification':'IA versus non-IA errors are measured by intersection; roof/pavement multiclass validation remains a separate uncompleted evidence requirement',
                      'sensitivity':'Run independent cases at supplied native resolutions/settings; no empirical sensitivity claim from a single run',
                      'target':'No numerical release threshold or accuracy commitment is established'}}
    write_json(output,report)
    if documentation:
        lines=['# Validation results','',
               'Independent real-site validation remains incomplete. Synthetic tests check deterministic behavior and workflow only; they do not count as measured real-site accuracy.','',
               'Machine-readable assessment: `data/validation/benchmarks.json`.','',
               '| Validation layer | Real cases with metrics | Real holdouts | Status |',
               '| --- | ---: | ---: | --- |']
        for kind,item in per_kind.items():
            lines.append(f"| {kind.upper()} | {item['real_cases_with_independent_metrics']} | {item['real_holdout_cases']} | {item['status']} |")
        lines+=['','## Metrics','',
                'IA and catchments are compared separately. Reports retain signed area error, absolute percentage error, boundary IoU, precision/recall, false positive and false negative area, and native-unit boundary Hausdorff distance. Equal total area alone does not establish agreement. Reference provenance, CRS and stable site vintage must be supplied explicitly.','',
                'Binary IA errors do not validate roof/pavement multiclass classification. Critical routing disagreements and processing/resolution sensitivity require additional independent review. No numerical release threshold is set.','',
                '## Executed cases','']
        for record in records:
            lines.append(f"- `{record['case_id']}`: {'synthetic fixture; excluded from empirical summary' if record['synthetic'] else 'real evidence case'}; IA {record['validation']['ia']['status']}; drainage {record['validation']['drainage']['status']}; analysis {record['processing_seconds']:.6f} seconds; logged manual review {record['manual_review_minutes'] if record['manual_review_minutes'] is not None else 'unknown'} minutes.")
        lines+=['','## Outstanding','']
        for kind,item in per_kind.items():
            for blocker in item['blockers']:lines.append(f'- {kind.upper()}: {blocker}.')
        lines+=['- Confirm independent IA labels and accepted drainage boundaries for stable completed sites, including proposed Whitaker, before recommending acceptance thresholds.',
                '- Check soil, inlet/roof/pipe connections, shared allocations, current-condition evidence and actual bills before treating modeled benefit screens as a property-specific savings claim.']
        path=Path(documentation);path.parent.mkdir(parents=True,exist_ok=True);path.write_text('\n'.join(lines)+'\n')
    return report


def parser():
    p=argparse.ArgumentParser(description=__doc__)
    commands=p.add_subparsers(dest='command',required=True)
    demo=commands.add_parser('demo',help='Create the invented, reproducible local workflow case')
    demo.add_argument('--store',type=Path,default=ROOT/'data/cases')
    serve=commands.add_parser('serve',help='Run the browser workbench on loopback')
    serve.add_argument('--port',type=int,default=8765)
    analysis=commands.add_parser('analyze',help='Analyze a saved case ID or case JSON without acquiring new sources')
    analysis.add_argument('case');analysis.add_argument('--store',type=Path,default=ROOT/'data/cases')
    analysis.add_argument('--output',type=Path)
    imported=commands.add_parser('import-whitaker',help='Import the saved public Whitaker acquisition; performs no network requests')
    imported.add_argument('--source',type=Path,default=ROOT/'data/public/whitaker-acquired.json')
    imported.add_argument('--store',type=Path,default=ROOT/'data/cases')
    validation=commands.add_parser('benchmark',help='Run separate IA/drainage reference assessments')
    validation.add_argument('cases',nargs='+');validation.add_argument('--store',type=Path,default=ROOT/'data/cases')
    validation.add_argument('--output',type=Path,default=ROOT/'data/validation/benchmarks.json')
    validation.add_argument('--documentation',type=Path,default=ROOT/'docs/VALIDATION.md')
    return p


def main(argv=None):
    args=parser().parse_args(argv)
    try:
        if args.command=='serve':
            if not 1<=args.port<=65535:raise ValueError('Port must be between 1 and 65535')
            from http.server import ThreadingHTTPServer
            from .server import Handler
            server=ThreadingHTTPServer(('127.0.0.1',args.port),Handler)
            print(f'Open http://127.0.0.1:{args.port} — local drainage workbench',flush=True)
            try:server.serve_forever()
            except KeyboardInterrupt:pass
            finally:server.server_close()
            return 0
        store=CaseStore(args.store)
        if args.command=='demo':
            from .fixtures import synthetic_case
            case=synthetic_case();result=store.save(case)
            print(json.dumps(summary(case,result,store),indent=2));return 0
        if args.command=='import-whitaker':
            from .server import acquired_case
            data=json.loads(args.source.read_text());case=acquired_case(data)
            case['created_at']=next((s.get('retrieved_at') for s in case['sources'] if s.get('retrieved_at')),case['created_at'])
            result=store.save(case)
            print(json.dumps(summary(case,result,store),indent=2));return 0
        if args.command=='analyze':
            case=load_case(args.case,store);result=analyze(case)
            if args.output:write_json(args.output,result)
            print(json.dumps(summary(case,result),indent=2));return 0
        if args.command=='benchmark':
            cases=[load_case(value,store) for value in args.cases]
            report=benchmark(cases,args.output,args.documentation)
            print(json.dumps({'assessment':report['assessment'],'output':str(args.output),'documentation':str(args.documentation)},indent=2));return 0
    except (ValueError,KeyError,FileNotFoundError) as exc:
        print(json.dumps({'error':str(exc)}));return 1
    return 1


if __name__=='__main__':
    raise SystemExit(main())
