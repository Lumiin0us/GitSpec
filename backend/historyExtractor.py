import json
from git import Repo, GitCommandError, NULL_TREE
import os

BOT_AUTHORS = ['github-actions[bot]', 'dependabot[bot]', 'pre-commit-ci[bot]', 'github-actions']
CODE_EXTENSIONS = ['.py']
MAX_FILES_PER_COMMIT = 20
MAX_COMMITS_TO_SCAN = 200

def splitDiffs(raw_diff):
    if not raw_diff: return [], []
    lines = raw_diff.split('\n')
    added, removed = [], []
    for line in lines:
        if line.startswith('+++') or line.startswith('---') or line.startswith('\\'):
            continue
        if line.startswith('+'): added.append(line[1:])
        elif line.startswith('-'): removed.append(line[1:])
    return added, removed

def isCodeCommit(files_info):
    return any(f['file'].endswith(ext) for ext in CODE_EXTENSIONS for f in files_info)

def extractHistory(repo, destPath, outputFile="commits_history.jsonl"):
    try:
        commits = list(repo.iter_commits(max_count=MAX_COMMITS_TO_SCAN))
    except (GitCommandError, ValueError):
        commits = []

    indexedCount = 0
    with open(outputFile, 'w', encoding='utf-8') as f:
        for commit in commits:
            if commit.author.name in BOT_AUTHORS:
                continue

            parent = None
            if commit.parents:
                try:
                    p = commit.parents[0]
                    repo.git.cat_file('-e', p.hexsha)
                    parent = p
                except GitCommandError:
                    parent = None

            if parent:
                diffs = parent.diff(commit, create_patch=True)
            else:
                diffs = commit.diff(NULL_TREE, create_patch=True, reverse=True)

            files_info = []
            for d in diffs:
                filePath = d.b_path if d.b_path else d.a_path
                rawPatch = d.diff.decode('utf-8', errors='replace') if d.diff else ""
                addedLines, removedLines = splitDiffs(rawPatch)

                status = d.change_type
                if not status:
                    if addedLines and not removedLines: status = 'A'
                    elif removedLines and not addedLines: status = 'D'
                    else: status = 'M'

                files_info.append({
                    'file': filePath,
                    'status': status,
                    'additions': addedLines[:20],
                    'removals': removedLines[:20]
                })

            if len(files_info) > MAX_FILES_PER_COMMIT:
                continue
            if not isCodeCommit(files_info):
                continue

            filesTouched = ", ".join(fi['file'] for fi in files_info)
            embedString = (f"{commit.summary} — files: {filesTouched} — "
                           f"author: {commit.author.name} — "
                           f"date: {commit.authored_datetime.date()}")

            commit_info = {
                'sha': commit.hexsha[:7],
                'author': commit.author.name,
                'summary': commit.summary,
                'date': commit.authored_datetime.isoformat(),
                'changes': files_info,
                'embedText': embedString
            }

            f.write(json.dumps(commit_info) + '\n')
            indexedCount += 1

    print(f"Extracted {indexedCount} commits into {outputFile}")
    return outputFile  