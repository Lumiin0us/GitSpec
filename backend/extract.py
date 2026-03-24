import libcst as cst
import shortuuid
import json
import textwrap
import os 

class CallVisitor(cst.CSTVisitor):
    def __init__(self):
        super().__init__()
        self.calls = set()

    def visit_Call(self, node: cst.Call):
        if isinstance(node.func, cst.Name):
            self.calls.add(node.func.value)
        elif isinstance(node.func, cst.Attribute):
            if isinstance(node.func.attr, cst.Name):
                self.calls.add(node.func.attr.value)

class MethodRemover(cst.CSTTransformer):
    """Removes top-level methods from a class body to create the 'Shell'."""
    def leave_FunctionDef(self, originalNode, updatedNode): 
        return cst.RemoveFromParent()

class GlobalRemover(cst.CSTTransformer):
    """Isolates global variables by stripping functions, classes, and imports."""
    def leave_FunctionDef(self, originalNode, updatedNode): return cst.RemoveFromParent()
    def leave_ClassDef(self, originalNode, updatedNode): return cst.RemoveFromParent()
    def leave_Import(self, originalNode, updatedNode): return cst.RemoveFromParent()
    def leave_ImportFrom(self, originalNode, updatedNode): return cst.RemoveFromParent()
    def leave_If(self, originalNode, updatedNode):
        if isinstance(originalNode.test, cst.Comparison):
            left = originalNode.test.left
            if isinstance(left, cst.Name) and left.value == "__name__":
                return cst.RemoveFromParent()
        return updatedNode

# Utility Functions
def get_calls(node):
    visitor = CallVisitor()
    node.visit(visitor)
    return sorted(list(visitor.calls))

def get_module_names(module_node):
    names = set()
    for node in module_node.body:
        if isinstance(node, cst.SimpleStatementLine):
            for s in node.body:
                if isinstance(s, (cst.Import, cst.ImportFrom)):
                    if isinstance(s, cst.Import):
                        for alias in s.names:
                            fullName = module_node.code_for_node(alias.name)
                            names.add(fullName.split('.')[0])
                    elif isinstance(s, cst.ImportFrom):
                        if s.module:
                            fullName = module_node.code_for_node(s.module)
                            names.add(fullName.split('.')[0])
    return sorted(list(names))

# Main Processor
def processPythonFile(files, folderName, repo, outputFile="code.jsonl"):
    results = []

    for file in files:
        relPath = os.path.relpath(file, repo.working_tree_dir)
        
        # Git Metadata
        commits = list(repo.iter_commits(paths=relPath))
        if commits:
            lastCommit = commits[0]
            firstCommit = commits[-1]
            historyMetadata = {
                "lastCommit": {
                    "hash": lastCommit.hexsha,
                    "msg": lastCommit.message.strip(),
                    "author": lastCommit.author.name,
                    "date": str(lastCommit.authored_datetime)
                },
                "firstCommit": {
                    "hash": firstCommit.hexsha,
                    "msg": firstCommit.message.strip(),
                    "author": firstCommit.author.name,
                    "date": str(firstCommit.authored_datetime)
                }
            }
        else:
            historyMetadata = {"lastCommit": None, "firstCommit": None}

        try:
            with open(file, 'r', encoding='utf-8') as f:
                sourceCode = f.read()
            module = cst.parse_module(sourceCode)
        except Exception as e:
            print(f"Could not read/parse file {file}: {e}")
            continue

        external_deps = get_module_names(module)
        globalVarsCode = module.visit(GlobalRemover()).code.strip()
        filepath = folderName + file.split(folderName)[-1]

        importLines = []
        for node in module.body:
            if isinstance(node, cst.SimpleStatementLine):
                if any(isinstance(s, (cst.Import, cst.ImportFrom)) for s in node.body):
                    importLines.append(module.code_for_node(node).strip())
        importedModulesCode = "\n".join(importLines)

        for node in module.body:
            # CASE 1: Top-Level Functions
            if isinstance(node, cst.FunctionDef):
                calls = get_calls(node)
                header = (
                    f"# FILE: {filepath}\n"
                    f"# TYPE: Global Function\n"
                    f"# CALLS: {', '.join(calls)}\n"
                    f"# DEPS: {', '.join(external_deps)}\n"
                    f"# LAST COMMIT: {historyMetadata['lastCommit']['msg'] if historyMetadata['lastCommit'] else 'N/A'}"
                )
                
                results.append({
                    'id': shortuuid.uuid(),
                    'name': node.name.value,
                    'filePath': filepath,
                    'calls': calls,
                    'external_deps': external_deps,
                    'history': historyMetadata,
                    'modules': importedModulesCode,
                    'globalVariables': globalVarsCode,
                    'parentClass': 'no parent',
                    'isAsync': node.asynchronous is not None,
                    'content': header + "\n\n" + module.code_for_node(node).strip(),
                })

            # CASE 2: Classes
            elif isinstance(node, cst.ClassDef):
                classShell = node.visit(MethodRemover())
                classShellCode = module.code_for_node(classShell).strip()
                
                for item in node.body.body:
                    if isinstance(item, cst.FunctionDef):
                        calls = get_calls(item)
                        header = (
                            f"# FILE: {filepath}\n"
                            f"# CLASS: {node.name.value}\n"
                            f"# TYPE: Method\n"
                            f"# CALLS: {', '.join(calls)}\n"
                            f"# DEPS: {', '.join(external_deps)}\n"
                            f"# LAST COMMIT: {historyMetadata['lastCommit']['msg'] if historyMetadata['lastCommit'] else 'N/A'}"
                        )
                        
                        results.append({
                            'id': shortuuid.uuid(),
                            'name': item.name.value,
                            'filePath': filepath,
                            'calls': calls,
                            'external_deps': external_deps,
                            'history': historyMetadata,
                            'modules': importedModulesCode,
                            'globalVariables': globalVarsCode,
                            'parentClass': classShellCode,
                            'isAsync': item.asynchronous is not None,
                            'content': header + "\n\n" + textwrap.dedent(module.code_for_node(item)).strip(),
                        })
            
    return results