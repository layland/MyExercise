"""Select a verified build asset for publication without rebuilding or resigning it."""
import json
import os
import re
import subprocess

TAG_PATTERN = re.compile(r"myexercise-v(\d+)\.(\d+)\.(\d+)")


def api(path):
    return json.loads(subprocess.check_output(["gh", "api", path], text=True))


def version(tag):
    match = TAG_PATTERN.fullmatch(tag)
    return tuple(map(int, match.groups())) if match else None


def select():
    build_repo = os.environ["BUILD_REPOSITORY"]
    target_repo = os.environ["GITHUB_REPOSITORY"]
    requested = os.environ.get("REQUESTED_TAG", "")
    if requested:
        if version(requested) is None:
            raise ValueError("Invalid MyExercise tag")
        release = api(f"repos/{build_repo}/releases/tags/{requested}")
    else:
        releases = api(f"repos/{build_repo}/releases?per_page=100")
        builds = [r for r in releases if version(r["tag_name"]) and not r["draft"]]
        if not builds:
            return {"skip": "true"}
        release = max(builds, key=lambda r: version(r["tag_name"]))
    tag = release["tag_name"]
    release_version = tag.removeprefix("myexercise-v")
    name = f"MyExercise-{release_version}.apk"
    published = api(f"repos/{target_repo}/releases?per_page=100")
    for existing in published:
        if existing["tag_name"] == tag and any(a["name"] == name and a["state"] == "uploaded" for a in existing["assets"]):
            return {"skip": "true"}
    if not requested and any(version(r["tag_name"]) and version(r["tag_name"]) > version(tag) for r in published):
        return {"skip": "true"}
    asset = next(a for a in release["assets"] if a["name"] == name and a["state"] == "uploaded")
    digest = asset.get("digest") or ""
    if digest and not re.fullmatch(r"sha256:[0-9a-f]{64}", digest):
        raise ValueError("Invalid APK digest")
    return {"skip": "false", "tag": tag, "version": release_version, "name": name,
            "url": asset["browser_download_url"], "digest": digest, "release_url": release["html_url"]}


if __name__ == "__main__":
    for key, value in select().items():
        if "\n" in value or "\r" in value:
            raise ValueError("Invalid workflow output")
        print(f"{key}={value}")
