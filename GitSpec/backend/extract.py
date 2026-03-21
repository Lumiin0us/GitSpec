from git import Repo
import os 
import shutil 

def cloneRepo(repository):
    basePath = os.path.dirname(os.path.abspath(__file__))
    folderName = "tmp"
    destinationPath =  os.path.join(basePath, folderName)
    if os.path.exists(destinationPath):
        shutil.rmtree(destinationPath, onerror=readonly_handler)
    try:
        repo = Repo.clone_from(repository, destinationPath)
        print("Succesfully Cloned!")
        return repo 
    except Exception as e:
        print("An error occurred: ", e)
        return None 

