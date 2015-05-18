from collections import namedtuple
import os

import jedi


def _debug_print_tree(node, indent=0, func=repr):
    """ Print visual representation of Jedi AST. """
    ret = "\t" * indent + func(node) + "\n"

    children = getattr(node, "children", None)
    if children:
        for child in children:
            ret += _debug_print_tree(child, indent=indent+1, func=func)
    return ret


class FileGrapherException(Exception):
    """ Something went wrong while graphing the file. """


class FileGrapher(object):
    """
    FileGrapher is used to extract definitions and references from single Python source file.
    """
    Def = namedtuple('Def', ['Path', 'Kind', 'Name', 'File', 'DefStart', 'DefEnd', 'Exported', 'Docstring', 'Data'])
    Ref = namedtuple('Ref', ['DefPath', 'DefFile', 'Def', 'File', 'Start', 'End', 'ToBuiltin'])

    def __init__(self, base_dir, source_file, log):
        """
        Create a new grapher.
        """
        self._base_dir = base_dir
        self._file = source_file
        # TODO: Can easily remove `log` to have cleaner class. Only used once.
        self._log = log
        self._source = None
        self._defs = {}
        self._refs = {}

    @property
    def graph(self):
        # TODO: Maybe move to `__init__`?
        self._load()

        # Add module/package defs.
        module = os.path.splitext(self._file)[0]
        if os.path.basename(self._file) == '__init__.py':
            module = os.path.normpath(os.path.dirname(self._file))

        self._add_def(self.Def(
            Path=module,
            Kind='module',
            Name=module.split('/')[-1],
            File=self._file,
            DefStart=0,
            DefEnd=0,
            Exported=True,
            # TODO: extract module/package-level doc.
            Docstring='',
            Data=None,
        ))

        # Jedi.
        try:
            jedi_names = jedi.names(source=self._source, path=self._file, all_scopes=True, references=True)
        except Exception as e:
            raise FileGrapherException('failed to parse {}: {}'.format(self._file, str(e)))

        jedi_defs, jedi_refs = [], []
        for jedi_name in jedi_names:
            # Imports should be refs.
            if jedi_name.is_definition() and jedi_name.type != 'import':
                    jedi_defs.append(jedi_name)
            else:
                jedi_refs.append(jedi_name)

        # Defs.
        for jedi_def in jedi_defs:
            self._log.debug(
                '\nProcessing def: %s | %s | %s',
                jedi_def.desc_with_module,
                jedi_def.name,
                jedi_def.type,
            )
            self._add_def(self._jedi_def_to_def(jedi_def))

        # Refs.
        for jedi_ref in jedi_refs:
            self._log.debug(
                '\nProcessing ref: %s | %s | %s',
                jedi_ref.desc_with_module,
                jedi_ref.name,
                jedi_ref.type,
            )

            # Try to find definition.
            ref_def = jedi_ref
            # If def is import, then follow it.
            depth = 0
            while (not ref_def.is_definition() or ref_def.type == "import") and depth < 100:
                depth += 1
                # noinspection PyBroadException
                try:
                    ref_defs = ref_def.goto_assignments()
                except Exception:
                    self._log.error('error getting definitions for reference {}'.format(jedi_ref))
                    break

                if len(ref_defs) == 0:
                    break

                ref_def = ref_defs[0]
            else:
                self._log.debug(
                    'Ref def search (precondition failed) | %s | %s | %s\n',
                    ref_def.is_definition(),
                    ref_def.type,
                    ref_def.name
                )

            if ref_def.type == "import":
                # We didn't find anything.
                self._log.debug('Ref def not found \n')
                continue

            sg_def = self._jedi_def_to_def_key(ref_def)
            self._log.debug(
                'Ref-Def: %s | %s | %s | %s \n',
                sg_def.Name,
                sg_def.Path,
                sg_def.Kind,
                sg_def.File,
            )

            ref_start = self._to_offset(jedi_ref.line, jedi_ref.column)
            ref_end = ref_start + len(jedi_ref.name)
            self._add_ref(self.Ref(
                DefPath=sg_def.Path,
                DefFile=sg_def.File,
                Def=False,
                File=self._file,
                Start=ref_start,
                End=ref_end,
                ToBuiltin=ref_def.in_builtin_module(),
            ))

        return self._defs, self._refs

    def _load(self):
        """ Load file in memory. """
        with open(self._file) as f:
            self._source = f.read()

        # TODO: Does this work with windows style newlines?
        source_lines = self._source.split('\n')
        self._cumulative_off = [0]
        for line in source_lines:
            self._cumulative_off.append(self._cumulative_off[-1] + len(line) + 1)

    def _jedi_def_to_def(self, d):
        # TODO: Add back this if needed:
        # If def is a name, then the location of the definition is the last name part
        start = self._to_offset(d.line, d.column)
        end = start + len(d.name)

        return self.Def(
            Path=self._full_name(d).replace('.', '/'),
            Kind=d.type,
            Name=d.name,
            File=self._file,
            DefStart=start,
            DefEnd=end,
            # TODO: not all vars are exported
            Exported=True,
            Docstring=d.docstring(raw=True),
            Data=None,
        )

    def _jedi_def_to_def_key(self, d):
        return self.Def(
            Path=self._full_name(d).replace('.', '/'),
            Kind=d.type,
            Name=d.name,
            File=d.module_path,
            DefStart=None,
            DefEnd=None,
            # TODO: not all vars are exported.
            Exported=True,
            Docstring=d.docstring(raw=True),
            Data=None,
        )

    def _full_name(self, d):
        if d.in_builtin_module() or d.module_path is None:
            return d.name
        if d.type == 'statement':
            # Workaround for self.* definitions:
            # 1. Must be inside function
            # 2. Must be in form self.something[.something ...] = thing
            jd = d._definition
            if d.parent().type == 'function':
                self._log.debug('\n%s\n', _debug_print_tree(
                    jd,
                    func=lambda n: '{} | {} | {}'.format(str(n)[:10], type(n), n.type)
                ))

            if (d.parent().type == 'function' and
                    (isinstance(jd.children[0], jedi.parser.tree.Node) or
                     isinstance(jd.children[0], jedi.evaluate.representation.InstanceElement)) and
                    (isinstance(jd.children[0].children[0], jedi.parser.tree.Name) or
                     isinstance(jd.children[0].children[0], jedi.evaluate.representation.InstanceName)) and
                    jd.children[0].children[0].value == 'self'):
                parent = d.parent()
                # Stop when:
                # - We find class or instance of class
                # - We reach module, which means we failed
                while parent.type != 'class' and parent.type != 'instance' and parent.type != 'module':
                    self._log.debug(
                        'Finding paren %s -> %s | %s',
                        parent.type,
                        parent,
                        jd.children[0].children[0].value
                    )
                    parent = parent.parent()

                rest = jd.children[0].children[1:]
                chain = []
                for node in rest:
                    chain.append(node.children[1].value)
                if parent.type != 'module':
                    name = '{}.{}'.format(parent.full_name, '.'.join(chain))
                else:
                    name = '{}.{}'.format(d.full_name, d.name)

            else:
                name = '{}.{}'.format(d.full_name, d.name)
        else:
            self._log.debug('Not-statement: %s | %s', d.name, d.module_path)
            self._log.debug('\n%s\n', _debug_print_tree(
                d,
                func=lambda n: u'{} | {} | {}'.format(unicode(n)[:10], type(n), n.type)
            ))
            # This is needed for situations like these:
            # class x(object):
            #   def yyy(self): pass
            #   def xxx(self, a):
            #     if a == 1:
            #       self.yyy(a) # <- A parameter.
            if d.is_definition():
                name = d.full_name
            else:
                name = '{}.{}'.format(d.full_name, d.name)

        # FIXME: Old code used to check if it's def or ref and only call this on refs.
        # module_path = os.path.relpath(d.module_path, self.base_dir)
        # if not d.is_definition():
        self._log.debug('Module path: %s | %s', d.module_path, d.in_builtin_module())

        module_path = self._abs_module_path_to_relative_module_path(d.module_path)

        if os.path.basename(module_path) == '__init__.py':
            parent_module = os.path.dirname(os.path.dirname(module_path))
        else:
            parent_module = os.path.dirname(module_path)

        if parent_module == '':
            return name

        self._log.debug(
            'Name: %s | %s ',
            parent_module,
            name,
        )

        return '{}.{}'.format(parent_module, name)

    def _abs_module_path_to_relative_module_path(self, module_path):
        rel_path = os.path.relpath(module_path, self._base_dir)
        if not rel_path.startswith('..'):
            return rel_path

        components = module_path.split(os.sep)
        pi1 = pi2 = -1
        for i, component in enumerate(components):
            if component in ['site-packages', 'dist-packages']:
                pi1 = i
                break
            # Fallback.
            if pi2 == -1 and component.startswith('python'):
                pi2 = i

        pi = pi1 if pi1 != -1 else pi2
        if pi != -1:
            return os.path.join(*components[pi + 1:])

        raise FileGrapherException('could not convert absolute module path {} '
                                   'to relative module path'.format(module_path))

    def _add_def(self, d):
        """ Add definition, also adds self-reference. """
        self._log.debug('Adding def: %s | %s | %s', d.Name, d.Path, d.Kind)
        if d.Path not in self._defs:
            self._defs[d.Path] = d
        # Add self-reference.
        self._add_ref(self.Ref(
            DefPath=d.Path,
            DefFile=os.path.abspath(d.File),
            Def=True,
            File=d.File,
            Start=d.DefStart,
            End=d.DefEnd,
            ToBuiltin=False,
        ))

    def _add_ref(self, r):
        """ Add reference. """
        self._log.debug('Adding ref: %s', r.DefPath)
        key = (r.DefPath, r.DefFile, r.File, r.Start, r.End)
        if key not in self._refs:
            self._refs[key] = r

    def _to_offset(self, line, column):
        """
        Converts from (line, col) position to byte offset.
        Line is 1-indexed, column is 0-indexed.
        """
        line -= 1
        if line >= len(self._cumulative_off):
            raise FileGrapherException('requested line out of bounds {} > {}'.format(
                line + 1,
                len(self._cumulative_off) - 1)
            )
        return self._cumulative_off[line] + column
