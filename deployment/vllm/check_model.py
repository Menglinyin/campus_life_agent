import argparse,json
from pathlib import Path

def check(path):
    root=Path(path).resolve()
    config=json.loads((root/'config.json').read_text())
    quant=config.get('quantization_config',{})
    if config.get('model_type')!='qwen3' or quant.get('quant_method')!='awq' or quant.get('bits')!=4:raise ValueError('Expected Qwen3 4-bit AWQ config')
    if config.get('hidden_size')!=5120 or config.get('num_hidden_layers')!=64:raise ValueError('Expected Qwen3-32B architecture dimensions')
    if not (root/'tokenizer_config.json').is_file():raise ValueError('Tokenizer config missing')
    index=root/'model.safetensors.index.json'
    if index.is_file():
        weights=set(json.loads(index.read_text())['weight_map'].values())
        if not weights:raise ValueError('Empty weight index')
        for filename in weights:
            p=(root/filename).resolve()
            if not p.is_relative_to(root) or not p.is_file() or p.stat().st_size==0:raise ValueError('Missing or invalid weight shard')
    elif not (root/'model.safetensors').is_file() or (root/'model.safetensors').stat().st_size==0:raise ValueError('Weights missing')
    return True

def main():
    p=argparse.ArgumentParser();p.add_argument('model_dir',type=Path);a=p.parse_args()
    try:check(a.model_dir)
    except (OSError,ValueError,KeyError):p.error('Model validation failed; inspect AWQ config, tokenizer and local weight files')
    print('Local AWQ metadata and shard existence checked; this does not validate tensor contents or checksums.')
if __name__=='__main__':main()
