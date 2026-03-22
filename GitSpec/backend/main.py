from clone import cloneRepo
from crawl import repoCrawler
from extract import processPythonFile

folderName, repo = cloneRepo('https://github.com/fastapi/fastapi')
files = repoCrawler(folderName)
results = processPythonFile(files, folderName, repo)