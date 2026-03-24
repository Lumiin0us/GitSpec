import os 

def repoCrawler(folderName):
    scriptDir = os.path.dirname(os.path.abspath(__file__))
    pythonFiles = []

    for (root,dirs,files) in os.walk(os.path.join(scriptDir, folderName),topdown=True):
        for file in files: 
            if file.lower().endswith('.py'):
                pythonFiles.append(os.path.join(root, file))
    return pythonFiles