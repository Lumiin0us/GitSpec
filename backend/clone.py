import os
import shutil
import stat
import tempfile
from git import Repo

def readOnlyHandler(func, path, execinfo):
    os.chmod(path, stat.S_IWRITE)
    func(path)

def cloneRepo(repository):
    basePath = tempfile.gettempdir() 
    folderName = repository.rstrip('/').split('/')[-1]
    destinationPath = os.path.join(basePath, folderName)

    if os.path.exists(destinationPath):
        shutil.rmtree(destinationPath, onerror=readOnlyHandler)
    
    try:
        repo = Repo.clone_from(repository, destinationPath)
        return destinationPath, repo 
    except Exception as e:
        print("Error: ", e)
        return None, None
        
def cleanupRepo(path):
    try:
        if os.path.exists(path):
            shutil.rmtree(path, onerror=readOnlyHandler)
    except Exception as e:
        print(f"Cleanup warning: {e}")