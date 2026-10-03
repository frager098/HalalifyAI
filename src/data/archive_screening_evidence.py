"""Bundle saved source runs without altering their original bytes."""
import argparse
import json
from pathlib import Path
from zipfile import ZipFile,ZIP_DEFLATED
from .reconciliation import sha256


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',nargs='+',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists():raise FileExistsError('Use a new source archive name; raw archives are immutable')
    prefixes=[folder.name for folder in args.input]
    if len(set(prefixes))!=len(prefixes):raise ValueError('Run names must be distinct')
    manifest=dict(format_version=1,run_prefixes=prefixes,files={},
                  description='Exact saved SEC source bytes; no approved screening classifications')
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with ZipFile(args.output,'x',compression=ZIP_DEFLATED,compresslevel=6,allowZip64=True) as archive:
        for folder in args.input:
            for file in sorted(folder.rglob('*')):
                if not file.is_file():continue
                member=folder.name+'/'+file.relative_to(folder).as_posix()
                digest=sha256(file)
                archive.write(file,member)
                manifest['files'][member]=dict(sha256=digest,bytes=file.stat().st_size)
            print('Archived',folder.name,flush=True)
        archive.writestr('archive_manifest.json',json.dumps(manifest,sort_keys=True,indent=2))
    print('Saved',args.output,'SHA256',sha256(args.output),flush=True)


if __name__=='__main__':main()
