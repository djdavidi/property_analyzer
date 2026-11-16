"""Install the optional free local imagery classifier into ignored data storage."""
from pathlib import Path
from hashlib import sha256
import json
import ssl
import subprocess
import urllib.request
import venv
from .semantic_cover import MODEL_SHA256,MODEL_URL,MODEL_PAGE


def main():
    import certifi
    root=Path(__file__).resolve().parents[1]
    environment=root/'data/model-runtime';folder=root/'data/models/openearthmap'
    folder.mkdir(parents=True,exist_ok=True)
    weights=folder/'weights.pth'
    if not weights.exists() or sha256(weights.read_bytes()).hexdigest()!=MODEL_SHA256:
        temporary=folder/'weights.partial'
        try:
            with urllib.request.urlopen(MODEL_URL,context=ssl.create_default_context(cafile=certifi.where()),timeout=30) as response, temporary.open('wb') as file:
                total=0
                while chunk:=response.read(1024*1024):
                    total+=len(chunk)
                    if total>128*1024*1024:raise ValueError('Model download exceeds size limit')
                    file.write(chunk)
            if sha256(temporary.read_bytes()).hexdigest()!=MODEL_SHA256:
                raise ValueError('Downloaded model does not match the pinned SHA-256')
            temporary.replace(weights)
        finally:temporary.unlink(missing_ok=True)
    if not (environment/'bin/python').exists():venv.create(environment,with_pip=True)
    subprocess.run([str(environment/'bin/python'),'-m','pip','install','-r',str(root/'requirements-imagery-model.txt')],check=True)
    freeze=subprocess.check_output([str(environment/'bin/python'),'-m','pip','freeze'],text=True)
    (folder/'runtime-lock.txt').write_text(freeze)
    (folder/'manifest.json').write_text(json.dumps({'model_sha256':MODEL_SHA256,'model_url':MODEL_URL,
        'reference':MODEL_PAGE,'architecture':'U-Net EfficientNet-B4, SCSE, 9 output classes',
        'inference':'Local CPU only; encoder_weights=None; torch weights_only=True',
        'local_accuracy':'Not independently validated; outputs remain modeled estimates'},indent=2)+'\n')
    print('Local imagery model installed. Run assessment to generate modeled canopy/surface areas.')


if __name__=='__main__':main()
