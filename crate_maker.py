from rocrate.rocrate import ContextEntity, ROCrate
import ipynbname
import nbformat
import mimetypes
from datetime import datetime
from giturlparse import parse as ghparse
import requests

def add_gh_file(crate, url):
    datafile = url.replace("/raw/", "/blob/")
    gh_parts = ghparse(datafile)

    # API url to get the latest commit for this file
    gh_commit_url = f"https://api.github.com/repos/{gh_parts.owner}/{gh_parts.repo}/commits?path={gh_parts.path_raw.split('/')[-1]}"
    try:
        response = requests.get(gh_commit_url)

        # Get the date of the last commit
        date = response.json()[0]["commit"]["committer"]["date"][:10]

    except (IndexError, KeyError):
        date = None

    # Different API endpoint for file data
    gh_file_url = f"https://api.github.com/repos/{gh_parts.owner}/{gh_parts.repo}/contents/{gh_parts.path_raw.split('/')[-1]}"
    try:
        response = requests.get(gh_file_url)
        contents_data = response.json()
        # Get the file size
        try:
            size = contents_data["size"]
        except TypeError:
            size = None

    except KeyError:
            size = None
    obj_properties = {
        "@type": [
            "File",
            "Dataset"
        ],
        "contentSize": size,
        "dateModified": date,
        "name": gh_parts.path_raw.split('/')[-1],
        "url": datafile
    }
    crate.add_file(datafile, properties=obj_properties)

def create_rocrate(subject, file_path, start_date, end_date):
    """
    Create an RO-Crate metadata file describing the downloaded dataset.
    """
    crate = ROCrate()

    # Initialise crate with dataset
    crate.add_file(file_path)

    # Add notebook details
    nb_path = ipynbname.path()
    nb = nbformat.read(nb_path, nbformat.NO_CONVERT)
    metadata = nb.metadata.rocrate
    nb_url = metadata.get("url", "")
    nb_properties = {
        "@type": ["File", "SoftwareSourceCode"],
        "name": metadata.get("name", ""),
        "description": metadata.get("description", ""),
        "encodingFormat": "application/x-ipynb+json",
        "codeRepository": metadata.get("codeRepository", ""),
        "url": nb_url,
    }
    crate.add(ContextEntity(crate, nb_url, properties=nb_properties))

    # Add action
    action_id = f"{nb_path.stem}_run"
    action_properties = {
        "@type": "CreateAction",
        "instrument": {"@id": nb_url},
        "actionStatus": {"@id": "http://schema.org/CompletedActionStatus"},
        "name": f"Run of notebook: {nb_path.name}",
        "result": {"@id": f"{file_path.name}/"},
        "object": [{"@id": o["url"]} for o in metadata["action"][0]["object"]],
        "query": f"{subject['id']} ({subject['name']})",
        "startDate": start_date,
        "endDate": end_date,
    }
    
    # If there are any GitHub references in action objects, add them to the crate
    for obj in metadata["action"][0]["object"]:
        if "github.com" in obj["url"]:
            add_gh_file(crate, obj["url"])

    # Update dataset details
    encoding = mimetypes.guess_type(file_path)[0]
    stats = file_path.stat()
    size = stats.st_size
    date = datetime.fromtimestamp(stats.st_mtime).strftime("%Y-%m-%d")
    rows = 0
    with file_path.open("r") as df:
        for line in df:
            rows += 1
    crate.update_jsonld(
        {
            "@id": file_path.name,
            "dateModified": date,
            "contentSize": size,
            "size": rows,
            "encodingFormat": encoding,
        }
    )
    crate.add(ContextEntity(crate, action_id, properties=action_properties))

    # Save the crate
    crate.write(file_path.parent)
    crate.write_zip(file_path.parent)