"""Independent loopback map/editor for one saved GIS project; no policy imports."""
import argparse
import base64
from hashlib import sha256
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json
from pathlib import Path
import re
from urllib.parse import urlparse

from shapely.geometry import shape,mapping
from .engine import analyze
from .geometry import reproject
from .workspace import ProjectStore

WEB=Path(__file__).resolve().parent/'web'


class Handler(BaseHTTPRequestHandler):
    store=None

    def send(self,data,status=200,mime='application/json'):
        body=data if isinstance(data,bytes) else json.dumps(data,allow_nan=False,separators=(',',':')).encode() if mime=='application/json' else data.encode()
        self.send_response(status);self.send_header('Content-Type',mime);self.send_header('Content-Length',str(len(body)))
        self.send_header('X-Content-Type-Options','nosniff');self.send_header('Cache-Control','no-store')
        self.end_headers();self.wfile.write(body)

    def local(self):
        return self.headers.get('Host','').split(':')[0] in ('127.0.0.1','localhost')

    def do_GET(self):
        if not self.local():return self.send({'error':'Loopback Host required'},403)
        path=urlparse(self.path).path
        try:
            if path=='/api/config':return self.send({'mode':'gis','title':'GIS & drainage workbench','jurisdictions':[],'saved_views':True})
            if path.startswith('/api/saved/'):return self.send(self.store.saved())
            if path=='/api/cases':return self.send(self.store.list())
            if path.startswith('/api/cases/'):
                case=self.store.load()
                if path.split('/')[-1]!=case['id']:raise ValueError('Unknown project case')
                return self.send(case)
            if path.startswith('/exports/'):
                _,_,id,name=path.split('/')
                if id!=self.store.load()['id']:raise ValueError('Unknown project case')
                formats={'case.json':'application/json','analysis.json':'application/json','report.html':'text/html; charset=utf-8',
                         'measurements.geojson':'application/geo+json'}
                if name not in formats:raise ValueError('Unknown export')
                return self.send((self.store.root/name).read_bytes(),mime=formats[name])
            if path.startswith('/api/blob/'):
                digest=path.split('/')[-1];case=self.store.load();info=case.get('imagery') or {}
                if not re.fullmatch('[a-f0-9]{64}',digest) or digest!=info.get('sha256') or not info.get('blob_path'):
                    raise ValueError('Image is not part of the saved project')
                from .media import read_blob
                body=read_blob(info,roots=[self.store.root/'sources',self.store.root])
                if sha256(body).hexdigest()!=digest:raise ValueError('Source hash mismatch')
                return self.send(body,mime='image/png')
            name='index.html' if path=='/' else path.lstrip('/')
            formats={'index.html':'text/html; charset=utf-8','app.js':'text/javascript','style.css':'text/css'}
            if name not in formats:return self.send({'error':'Not found'},404)
            body=(WEB/name).read_bytes()
            if name=='index.html':body=body.replace(b'<body>',b'<body data-mode="gis">')
            return self.send(body,mime=formats[name])
        except (ValueError,KeyError,FileNotFoundError) as exc:self.send({'error':str(exc)},404)

    def do_POST(self):
        if not self.local():return self.send({'error':'Loopback Host required'},403)
        origin=self.headers.get('Origin')
        if origin and origin not in (f'http://127.0.0.1:{self.server.server_port}',f'http://localhost:{self.server.server_port}'):
            return self.send({'error':'Foreign origin rejected'},403)
        try:
            length=int(self.headers.get('Content-Length','0'))
            if not 0<length<=32*1024*1024:raise ValueError('Request must be between 1 byte and 32 MB')
            data=json.loads(self.rfile.read(length));path=urlparse(self.path).path
            if path=='/api/analyze':return self.send(analyze(data['case']))
            if path=='/api/save':return self.send(self.store.save(data['case']))
            if path=='/api/align-case':
                from .projection import project_case,warp_display
                from .geometry import projected_crs
                projected_crs(data['target_crs'])
                original=data['case'];aligned=project_case(original,data['target_crs'])
                if original.get('imagery'):
                    aligned['imagery']=warp_display(original,data['target_crs'],self.store.root/'sources')
                aligned.setdefault('assumptions',[]).append('Case vectors aligned to native DEM CRS; no elevation resampling. Previous area-accounting CRS retained.')
                return self.send(aligned)
            if path=='/api/import-boundary':
                from .cli import parser,build_project
                payload=json.dumps(data['geojson'],allow_nan=False).encode();digest=sha256(payload).hexdigest()
                inputs=self.store.root/'inputs';inputs.mkdir(exist_ok=True)
                boundary=inputs/(digest+'.geojson');boundary.write_bytes(payload)
                args=['run','--boundary',str(boundary),'--output',str(self.store.root)]
                if data.get('crs'):args+=['--boundary-crs',data['crs']]
                if data.get('name'):args+=['--name',data['name']]
                return self.send(build_project(parser().parse_args(args)))
            if path=='/api/import-features':
                from .cli import _read_geojson
                payload=json.dumps(data['geojson'],allow_nan=False).encode();digest=sha256(payload).hexdigest()
                folder=self.store.root/'inputs';folder.mkdir(exist_ok=True);file=folder/(digest+'.geojson');file.write_bytes(payload)
                features,source_crs=_read_geojson(file,data.get('crs'))
                for index,f in enumerate(features):
                    f['id']=str(f.get('id','import-'+digest[:12]+'-'+str(index)))
                    p=f.setdefault('properties',{})
                    if not p.get('layer') and p.get('class') in ('roof','pavement','pervious','unknown'):p['layer']='surface'
                    if not p.get('layer'):raise ValueError('Features require a layer, and surfaces require a class')
                    f['geometry']=mapping(reproject(shape(f['geometry']),source_crs,data['target_crs']))
                return self.send({'features':features,'provenance':{'path':str(file),'sha256':digest,'crs':source_crs.to_string(),
                    'acquisition_date':None,'processing':'explicit vector coordinate transformation'}})
            if path=='/api/import-raster':
                from .raster import import_dem,classify_raster
                content=base64.b64decode(data['content'],validate=True);digest=sha256(content).hexdigest()
                folder=self.store.root/'inputs';folder.mkdir(exist_ok=True);file=folder/(digest+'.tif')
                if not file.exists():file.write_bytes(content)
                if data['kind']=='dem':
                    item=import_dem(file,vertical_unit=data['vertical_unit'],acquisition_date=data.get('acquisition_date'))
                    item['grid']['source_quality']={'vertical_units':'assumed','basis':'User-specified units; add reviewed source evidence in case details'}
                    item['warnings'].append('Vertical units are caller-supplied until reviewed source evidence is recorded')
                else:
                    item=classify_raster(file,data['class_map'],acquisition_date=data.get('acquisition_date'))
                    for index,f in enumerate(item['features']['features']):
                        f['id']='raster-'+digest[:12]+'-'+str(index)
                        f['geometry']=mapping(reproject(shape(f['geometry']),item['crs'],data['target_crs']))
                return self.send(item)
            return self.send({'error':'Not found'},404)
        except Exception as exc:self.send({'error':str(exc)},400)


def serve(*,port=8766,workspace):
    class ProjectHandler(Handler):pass
    ProjectHandler.store=ProjectStore(workspace)
    server=ThreadingHTTPServer(('127.0.0.1',port),ProjectHandler)
    print(f'Open http://127.0.0.1:{server.server_port} — independent GIS map/editor',flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workspace',type=Path,required=True);p.add_argument('--port',type=int,default=8766)
    args=p.parse_args();serve(port=args.port,workspace=args.workspace)
