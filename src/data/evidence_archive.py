"""Read saved SEC evidence from folders or a compressed archive without extraction."""
import hashlib
import json
from pathlib import Path
from zipfile import ZipFile


class ArchiveFile:
    def __init__(self,archive,member,label):
        self.archive=archive;self.member=member;self.label=label
    def read_bytes(self):return self.archive.read(self.member)
    def read_text(self,encoding='utf-8'):return self.read_bytes().decode(encoding)
    def as_posix(self):return self.label+'::'+self.member


class ArchiveRun:
    def __init__(self,archive,prefix,label):
        self.archive=archive;self.prefix=prefix;self.label=label
    def __truediv__(self,relative):
        return ArchiveFile(self.archive,self.prefix+'/'+str(relative),self.label)
    def as_posix(self):return self.label+'::'+self.prefix


def evidence_sha256(file):return hashlib.sha256(file.read_bytes()).hexdigest()


def archive_runs(path):
    archive=ZipFile(path)
    manifest=json.loads(archive.read('archive_manifest.json'))
    return archive,[ArchiveRun(archive,prefix,path.as_posix()) for prefix in manifest['run_prefixes']]
