from git import Repo
import os 
import shutil 
import stat

def readOnlyHandler(func, path, execinfo):
    os.chmod(path, stat.S_IWRITE)
    func(path)

def cloneRepo(repository):
    basePath = os.path.dirname(os.path.abspath(__file__))
    folderName = repository.split('/')[-1]
    destinationPath =  os.path.join(basePath, folderName)
    if os.path.exists(destinationPath):
        shutil.rmtree(destinationPath, onerror=readOnlyHandler)
    try:
        repo = Repo.clone_from(repository, destinationPath)
        print("Succesfully Cloned!")
        return folderName, repo
    except Exception as e:
        print("An error occurred: ", e)
        return None, None