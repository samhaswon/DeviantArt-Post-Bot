import json
import re
import requests
from typing import List


class Poster:
    stash_upload_url = "https://www.deviantart.com/api/v1/oauth2/stash/submit"
    stash_publish_url = "https://www.deviantart.com/api/v1/oauth2/stash/publish"

    def upload_and_submit(self,
                          file_path: str,
                          token: str,
                          title: str,
                          artist_comments: str,
                          tags: List[str],
                          folders: List[str],
                          is_mature: bool = True,
                          debug: bool = False
                          ):
        """
        Upload and submit an image to Deviantart.
        :param file_path: Path to the file to upload.
        :param token: The `access_token` to be used for the upload.
        :param title: The title of the deviation.
        :param artist_comments: The comment body of the deviation.
        :param tags: The tags of the deviation.
        :param folders: The folders to post the deviation in to.
        :param is_mature: If the deviation should be tagged as mature.
        :param debug:
        :return:
        """
        # Truncate title
        title = title[:50]
        # Upload image
        params = {
            "access_token": token,
            "title": title,
            "artist_comments": artist_comments,
            "is_mature": is_mature,
        }
        if len(params["artist_comments"]) <= 1:
            del params["artist_comments"]

        encoded_tags = {f"tags[{i}]": tag for i, tag in enumerate(tags)}
        data = {**params, **encoded_tags}
        with open(file_path, "rb") as image_file_pointer:
            image_file = image_file_pointer.read()
            if re.search(r"\.jpe?g$", file_path):
                files = {
                    'image': ('image.jpg', image_file, 'image/jpeg')
                }
            elif re.search(r"\.png$", file_path):
                files = {
                    'image': ('image.png', image_file, 'image/png')
                }
            else:
                raise RuntimeError(f"Invalid file type for file at {file_path}")

        result = requests.post(self.stash_upload_url, data=data, files=files)
        if debug:
            print(f"Raw {result.text=}")
        result = result.json()
        if result.get("status", "failure") != "success":
            raise RuntimeError(f"Unable to upload image!\n"
                               f"{result=}")
        if debug:
            print(f"JSON parsed {result=}")

        # Post image
        params = {
            "access_token": token,
            "allow_free_download": True,
            "add_watermark": False,
            # "catpath": "visual_art",
            "feature": "true",
            "galleryids": folders,
            "request_critique": False,
            "allow_comments": True,
            "display_resolution": 0,
            "sharing": "allow",
            "license_options": {
                "creative_commons": False,
                "commercial": False,
                "modify": "no"
            },
            "itemid": result["itemid"]
        }
        if is_mature:
            params["is_mature"] = True
            params["mature_level"] = "strict"
            params["mature_classification"] = ["nudity", "sexual"]

        post_result = requests.post(self.stash_publish_url, params=params)
        if post_result.status_code > 399:
            raise RuntimeError(f"Failed to post image with error {post_result.status_code} {post_result.reason}\n"
                               f"{post_result.text}")
        if debug:
            print(f"{post_result.text=}")
        post_result = post_result.json()
        print(f"Successfully posted deviation {post_result['deviationid']} at {post_result['url']}")

