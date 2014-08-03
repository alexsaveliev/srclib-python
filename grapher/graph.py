import os
import sys
import argparse as ap
from os import path
from glob import glob
from collections import namedtuple

import jedi

def main():
    argser = ap.ArgumentParser(description='graph.py is a command that dumps all Python definitions and references found in code rooted at a directory')
    argser.add_argument('dir', help='path to root directory of code')

    args = argser.parse_args()
    os.chdir(args.dir)          # set working directory to be source directory

    source_files = glob('**/*.py')
    source_files.extend(glob('*.py'))

    modules = [filename_to_module_name(f) for f in source_files]
    jedi.api.preload_module(modules)

    defs = [d for d in get_defs(source_files)]
    refs = [r for r in get_refs(source_files)]
    print '\n'.join([str(r) for r in refs])
    print '\n'.join([str(d) for d in defs])

def get_defs(source_files):
    for source_file in source_files:
        source = None
        with open(source_file) as sf:
            source = unicode(sf.read())
        defs = jedi.api.defined_names(source, path=source_file)
        for def_ in defs:
            for d in get_defs_(def_, source_file):
                yield d

def get_defs_(def_, source_file):
    yield jedi_def_to_def(def_, source_file)

    # TODO: this seems to break (e.g., local variables in a function)
    # subdefs = def_.defined_names()
    # for subdef in subdefs:
    #     for d in get_defs_(subdef, source_file):
    #         yield d

def jedi_def_to_def(def_, source_file):
    full_name = full_name_of_def(def_)
    return Def(
        Path=full_name,
        Kind=def_.type,
        Name=def_.name,
        File=source_file,
        StartPos=def_.start_pos,
        # EndPos=def_.end_pos,
        EndPos = None,
        Exported=True,          # TODO: not all vars are exported
        Data=None,
    )

def full_name_of_def(def_):
    return ('%s.%s' % (def_.full_name, def_.name)) if def_.type == 'statement' else def_.full_name

def get_refs(source_files):
    for source_file in source_files:
        for name_part, def_ in ParserContext(source_file).refs():
            full_name = full_name_of_def(def_)
            yield Ref(
                DefPath=full_name.replace('.', '/'),
                Def=False,
                File=source_file,
                StartPos=name_part.start_pos,
                EndPos=name_part.end_pos,
            )

Def = namedtuple('Def', ['Path', 'Kind', 'Name', 'File', 'StartPos', 'EndPos', 'Exported', 'Data'])
Ref = namedtuple('Ref', ['DefPath', 'Def', 'File', 'StartPos', 'EndPos'])

class ParserContext(object):
    def __init__(self, source_file):
        self.source_file = source_file
        with open(source_file) as sf:
            self.source = unicode(sf.read())
            self.parser = jedi.parser.Parser(self.source, source_file)

    def refs(self):
        for r in self.scope_refs(self.parser.module):
            yield r

    def scope_refs(self, scope):
        for import_ in scope.imports:
            for r in self.import_refs(import_):
                yield r
        for stmt in scope.statements:
            for r in self.stmt_refs(stmt):
                yield r
        for subscope in scope.subscopes:
            for r in self.scope_refs(subscope):
                yield r

    def import_refs(self, import_):
        # TODO: extract all possible references from this
        return
        yield

    def stmt_refs(self, stmt):
        if isinstance(stmt, jedi.parser.representation.KeywordStatement):
            return
        if isinstance(stmt, jedi.parser.representation.Flow):
            return

        for token in stmt._token_list:
            if not isinstance(token, jedi.parser.representation.Name):
                continue
            for name_part in token.names:
                defs = jedi.api.Script(
                    path=self.source_file,
                    line=name_part.start_pos[0],
                    column=name_part.start_pos[1],
                ).goto_assignments()
                for def_ in defs:
                    yield (name_part, def_)

def resolve_import_paths(scopes):
    for s in scopes.copy():
        if isinstance(s, jedi.evaluate.imports.ImportWrapper):
            scopes.remove(s)
            scopes.update(resolve_import_paths(set(s.follow())))
    return scopes

def filename_to_module_name(filename):
    if path.basename(filename) == '__init__.py':
        return path.dirname(filename).replace('/', '.')
    return path.splitext(filename)[0].replace('/', '.')

if __name__ == '__main__':
    main()
