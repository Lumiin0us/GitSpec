import libcst as cst
import shortuuid
import json
import textwrap
import os 

class MethodRemover(cst.CSTTransformer):
    """Removes top-level methods from a class body to create the 'Shell'."""
    def leave_FunctionDef(self, original_node, updated_node): 
        return cst.RemoveFromParent()

class GlobalRemover(cst.CSTTransformer):
    """Isolates global variables by stripping functions, classes, and imports."""
    def leave_FunctionDef(self, original_node, updated_node): return cst.RemoveFromParent()
    def leave_ClassDef(self, original_node, updated_node): return cst.RemoveFromParent()
    def leave_Import(self, original_node, updated_node): return cst.RemoveFromParent()
    def leave_ImportFrom(self, original_node, updated_node): return cst.RemoveFromParent()
    def leave_If(self, original_node, updated_node):
        if isinstance(original_node.test, cst.Comparison):
            left = original_node.test.left
            if isinstance(left, cst.Name) and left.value == "__name__":
                return cst.RemoveFromParent()
        return updated_node


def processPythonFile(files, folderName, repo, outputFile="code.jsonl"):
    results = []

    for file in files:
        relPath = os.path.relpath(file, repo.working_tree_dir)
        
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
            print(f"Could not read file {file}: {e}")
            continue
        

        # A. Extract Imports
        importLines = []
        for node in module.body:
            if isinstance(node, cst.SimpleStatementLine):
                if any(isinstance(s, (cst.Import, cst.ImportFrom)) for s in node.body):
                    importLines.append(module.code_for_node(node).strip())
        importedModulesCode = "\n".join(importLines)

        # B. Extract Globals
        globalVarsCode = module.visit(GlobalRemover()).code.strip()
        filepath = folderName + file.split(folderName)[-1]
        for node in module.body:
            # 1. Top-Level Function (Keep all nesting inside)
            if isinstance(node, cst.FunctionDef):
                results.append({
                    'id': shortuuid.uuid(),
                    'filePath': filepath,
                    'history': historyMetadata,
                    'modules': importedModulesCode,
                    'globalVariables': globalVarsCode,
                    'parentClass': 'no parent',
                    'isAsync': node.asynchronous is not None,
                    'content': module.code_for_node(node).strip(),
                })

            # 2. Class Definitions
            elif isinstance(node, cst.ClassDef):
                # Create the Shell (Variables and Header)
                classShellNode = node.visit(MethodRemover())
                classShellCode = module.code_for_node(classShellNode).strip()
                
                # Extract each Method while keeping nesting inside
                for item in node.body.body:
                    if isinstance(item, cst.FunctionDef):
                        results.append({
                            'id': shortuuid.uuid(),
                            'filePath': filepath,
                            'history': historyMetadata,
                            'modules': importedModulesCode,
                            'globalVariables': globalVarsCode,
                            'parentClass': classShellCode,
                            'isAsync': item.asynchronous is not None,
                            'content': textwrap.dedent(module.code_for_node(item)).strip(),
                        })
        
    with open(outputFile, 'w', encoding='utf-8') as f:
        for entry in results:
            f.write(json.dumps(entry) + "\n")
    return results

# finalData = processPythonFile(codeToTest)
# print(f"Extraction complete. {len(finalData)} entries in JSONL.")